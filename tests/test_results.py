import json

import pytest

from pytest_codex.paths import native_path
from pytest_codex.results import execution_error
from pytest_codex.run import Run


def prepare(pytester):
    pytester.makeini("[pytest]\ncodex_project=project\n")
    (pytester.path / "project").mkdir()
    (pytester.path / "project/input.txt").write_text("input", encoding="utf-8")
    pytester.makeconftest("""
pytest_plugins = ["pytest_codex.plugin"]
import pytest
from pytest_codex.run import Run
from pytest_codex.snapshot import Diff
@pytest.fixture(autouse=True)
def process(monkeypatch):
    def execute(prompt, project, **kwargs):
        (project / "out.txt").write_text(kwargs["model"] or "unspecified", encoding="utf-8")
        return Run([{"type":"turn.completed", "usage":{"input_tokens":10,
            "cached_input_tokens":4,"output_tokens":2}}], project, Diff(["out.txt"]))
    monkeypatch.setattr("pytest_codex.plugin.execute", execute)
    monkeypatch.setattr("pytest_codex.plugin.cli_version", lambda binary: "codex-cli test")
""")


def test_recording_sets_preserve_both_models_and_replay(pytester):
    prepare(pytester)
    pytester.makepyfile("""
def test_task(codex):
    run = codex.exec("public prompt")
    assert run.read("out.txt") in {"baseline", "candidate"}
""")
    for name in ("baseline", "candidate"):
        pytester.runpytest(
            "--codex-record",
            f"--codex-model={name}",
            f"--codex-recording-set={name}",
            f"--codex-results={name}.json",
        ).assert_outcomes(passed=1)
    assert len(list(pytester.path.glob("cassettes/**/*.json"))) == 2
    data = json.loads((pytester.path / "baseline.json").read_text())
    item = data["attempts"][0]
    assert item["status"] == "passed" and item["attempt"] == 1
    call = item["runs"][0]
    assert call["model"] == "baseline" and call["cli_version"] == "codex-cli test"
    assert call["usage"]["input_tokens"] == 10
    assert call["replayed"] is False and len(call["input_hash"]) == 64
    text = (pytester.path / "baseline.json").read_text()
    assert "public prompt" not in text and str(pytester.path) not in text
    pytester.makeconftest('pytest_plugins = ["pytest_codex.plugin"]')
    pytester.runpytest(
        "--codex-bin=missing",
        "--codex-model=baseline",
        "--codex-recording-set=baseline",
        "--codex-results=replay.json",
    ).assert_outcomes(passed=1)
    assert json.loads((pytester.path / "replay.json").read_text())["attempts"][0]["runs"][0][
        "replayed"
    ]


def test_results_preserve_failed_attempts_even_when_threshold_passes(pytester):
    prepare(pytester)
    pytester.makepyfile("""
import pytest
@pytest.mark.codex(runs=3, pass_rate=0.66)
def test_task(codex):
    codex.exec("secret prompt")
    assert codex.attempt != 2, "PRIVATE FAILURE TEXT"
""")
    pytester.runpytest(
        "--codex-record", "--codex-model=baseline", "--codex-results=out.json"
    ).assert_outcomes(passed=1)
    text = (pytester.path / "out.json").read_text()
    data = json.loads(text)
    assert [row["status"] for row in data["attempts"]] == ["passed", "failed", "passed"]
    assert [row["attempt"] for row in data["attempts"]] == [1, 2, 3]
    assert "PRIVATE FAILURE TEXT" not in text and "secret prompt" not in text


def test_results_separate_grader_errors_skips_and_setup_errors(pytester):
    prepare(pytester)
    pytester.makepyfile("""
import pytest
@pytest.mark.codex(runs=2)
def test_grader(codex):
    codex.exec("hello")
    raise ValueError("private grader details")
def test_skip(codex):
    pytest.skip("private skip details")
@pytest.fixture
def broken():
    raise RuntimeError("private setup details")
@pytest.mark.codex
def test_setup(codex, broken):
    pass
""")
    pytester.runpytest("--codex-record", "--codex-results=out.json").assert_outcomes(
        failed=1, skipped=1, errors=1
    )
    text = (pytester.path / "out.json").read_text()
    rows = json.loads(text)["attempts"]
    assert [row["status"] for row in rows] == ["error", "skipped", "error"]
    assert rows[0]["error_type"] == "ValueError"
    assert "private" not in text


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/b", "..", ""])
def test_invalid_recording_set_fails_before_execution(pytester, name):
    prepare(pytester)
    pytester.makepyfile('def test_task(codex): codex.exec("hello")')
    result = pytester.runpytest("--codex-record", "--codex-recording-set=" + name)
    assert result.ret == 4
    assert not list(pytester.path.glob("cassettes/**/*.json"))


def test_export_refuses_overwrite_before_model_call(pytester):
    prepare(pytester)
    path = pytester.path / "out.json"
    path.write_text("preserve", encoding="utf-8")
    pytester.makepyfile('def test_task(codex): codex.exec("hello")')
    result = pytester.runpytest("--codex-record", "--codex-results=out.json")
    assert result.ret == 4 and path.read_text() == "preserve"
    assert not list(pytester.path.glob("cassettes/**/*.json"))


def test_named_recording_cannot_be_replaced_by_another_record_run(pytester):
    prepare(pytester)
    pytester.makepyfile('def test_task(codex): codex.exec("hello")')
    options = ["--codex-record", "--codex-recording-set=baseline", "--codex-model=first"]
    pytester.runpytest(*options).assert_outcomes(passed=1)
    path = native_path(next(pytester.path.glob("cassettes/**/*.json")))
    original = path.read_bytes()
    pytester.runpytest(*options).assert_outcomes(failed=1)
    assert path.read_bytes() == original


def test_incomplete_turn_is_an_execution_error_not_a_failed_task(pytester):
    prepare(pytester)
    pytester.makeconftest("""
pytest_plugins = ["pytest_codex.plugin"]
import pytest
from pytest_codex.run import Run
@pytest.fixture(autouse=True)
def process(monkeypatch):
    monkeypatch.setattr("pytest_codex.plugin.cli_version", lambda binary: "test-cli")
    monkeypatch.setattr("pytest_codex.plugin.execute", lambda prompt, project, **kw:
        Run([{"type":"turn.failed"}], project, returncode=1))
""")
    pytester.makepyfile(
        'def test_task(codex):\n    run = codex.exec("hello")\n    assert run.succeeded'
    )
    pytester.runpytest("--codex-record", "--codex-results=out.json").assert_outcomes(failed=1)
    row = json.loads((pytester.path / "out.json").read_text(encoding="utf-8"))["attempts"][0]
    assert row["status"] == "error" and row["error_type"] == "IncompleteCodexTurn"


def test_grader_dependencies_are_in_fingerprint_and_changed_grader_is_error(pytester):
    prepare(pytester)
    pytester.makeini("[pytest]\ncodex_project=project\ncodex_grader_files=oracle.py\n")
    (pytester.path / "oracle.py").write_text("value = 1\n", encoding="utf-8")
    pytester.makepyfile("""
from pathlib import Path
def test_task(codex):
    codex.exec("hello")
    Path("oracle.py").write_text("value = 2\\n", encoding="utf-8")
""")
    pytester.runpytest("--codex-record", "--codex-results=out.json").assert_outcomes(passed=1)
    row = json.loads((pytester.path / "out.json").read_text(encoding="utf-8"))["attempts"][0]
    assert row["status"] == "error" and row["error_type"] == "GraderChanged"


def test_windows_shell_startup_failure_is_not_a_task_failure(tmp_path):
    item = {
        "id": "1",
        "type": "command_execution",
        "status": "failed",
        "command": "python check.py",
        "exit_code": -1,
        "aggregated_output": "Failed to create unified exec process: CreateProcessWithLogonW failed: 1326",
    }
    events = [{"type": "item.completed", "item": item}, {"type": "turn.completed"}]
    assert execution_error(Run(events, tmp_path)) == "ShellStartupError"
    item["exit_code"] = 1
    item["aggregated_output"] = "AssertionError: expected behavior did not occur"
    assert execution_error(Run(events, tmp_path)) is None


def test_export_hashes_parameter_ids_that_may_contain_private_prompts(pytester):
    prepare(pytester)
    pytester.makepyfile("""
import pytest
@pytest.mark.parametrize("prompt", ["PRIVATE PROMPT A", "PRIVATE PROMPT B"])
def test_task(codex, prompt):
    codex.exec(prompt)
""")
    pytester.runpytest("--codex-record", "--codex-results=out.json").assert_outcomes(passed=2)
    text = (pytester.path / "out.json").read_text(encoding="utf-8")
    rows = json.loads(text)["attempts"]
    assert "PRIVATE" not in text
    assert len({row["case"] for row in rows}) == 2
    assert all("[sha256-" in row["case"] for row in rows)


def test_runtime_xfail_is_skipped_instead_of_a_model_failure(pytester):
    prepare(pytester)
    pytester.makepyfile("""
import pytest
@pytest.mark.codex(runs=3)
def test_task(codex):
    codex.exec("hello")
    pytest.xfail("known limitation")
""")
    pytester.runpytest("--codex-record", "--codex-results=out.json").assert_outcomes(xfailed=1)
    rows = json.loads((pytester.path / "out.json").read_text(encoding="utf-8"))["attempts"]
    assert len(rows) == 1 and rows[0]["status"] == "skipped"
