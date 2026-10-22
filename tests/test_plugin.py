import pytest


def bootstrap(pytester):
    pytester.makeconftest('pytest_plugins = ["pytest_codex.plugin"]')
    pytester.makeini("[pytest]\ncodex_project = project\ncodex_isolation = full\n")
    project = pytester.path / "project"
    project.mkdir()
    (project / "input.txt").write_text("input", encoding="utf-8")


def test_default_replay_missing_never_invokes_codex(pytester):
    bootstrap(pytester)
    pytester.makepyfile('def test_missing(codex):\n    codex.exec("hello")')
    result = pytester.runpytest("--codex-bin=does-not-exist")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*Re-record with --codex-record*"])


def test_record_then_replay_multiple_calls_and_changed_input(pytester):
    bootstrap(pytester)
    # Substitute only the paid external process. Sandbox, cassette and fixture are real.
    pytester.makeconftest("""
pytest_plugins = ["pytest_codex.plugin"]
import pytest
from pytest_codex.run import Run
from pytest_codex.snapshot import Diff
@pytest.fixture(autouse=True)
def external_process(monkeypatch):
    def execute(prompt, project, **kwargs):
        (project / "out.txt").write_text(prompt, encoding="utf-8")
        return Run([{"type": "turn.completed"}], project, Diff(["out.txt"]))
    monkeypatch.setattr("pytest_codex.plugin.execute", execute)
    monkeypatch.setattr("pytest_codex.plugin.cli_version", lambda binary: "test-cli")
""")
    pytester.makepyfile("""
def test_calls(codex):
    first = codex.exec("first")
    second = codex.exec("second")
    assert first.read("out.txt") == "first"
    assert second.read("out.txt") == "second"
    assert first.project != second.project
""")
    pytester.runpytest("--codex-record").assert_outcomes(passed=1)
    assert len(list(pytester.path.glob("cassettes/**/*.json"))) == 2
    # Remove even the external-process substitute: replay must not need it.
    pytester.makeconftest('pytest_plugins = ["pytest_codex.plugin"]')
    pytester.runpytest("--codex-bin=missing").assert_outcomes(passed=1)
    (pytester.path / "project" / "input.txt").write_text("changed", encoding="utf-8")
    pytester.runpytest("--codex-bin=missing").assert_outcomes(failed=1)


@pytest.mark.parametrize("required,passed", [(0.66, True), (0.8, False)])
def test_repeat_pass_rate_and_attempt_recordings(pytester, required, passed):
    bootstrap(pytester)
    pytester.makepyfile(f"""
import pytest
attempts = []
@pytest.mark.codex(runs=3, pass_rate={required})
def test_rate(codex):
    attempts.append(codex.attempt)
    assert codex.attempt != 2
def test_all_ran():
    assert attempts == [1, 2, 3]
""")
    result = pytester.runpytest()
    result.assert_outcomes(passed=2 if passed else 1, failed=0 if passed else 1)
    result.stdout.fnmatch_lines(["*2/3*66.7%*"])


def test_repeat_does_not_swallow_unexpected_errors(pytester):
    bootstrap(pytester)
    pytester.makepyfile("""
import pytest
@pytest.mark.codex(runs=3, pass_rate=0.1)
def test_bug(codex):
    raise ValueError("programming bug")
""")
    result = pytester.runpytest()
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*ValueError: programming bug*"])


@pytest.mark.parametrize(
    "marker", ["runs=0", "runs=1.5", "runs=2, pass_rate=1.1", "runs=2, pass_rate=float('nan')"]
)
def test_invalid_marker_fails_collection(pytester, marker):
    bootstrap(pytester)
    pytester.makepyfile(f"import pytest\n@pytest.mark.codex({marker})\ndef test_bad(codex): pass")
    result = pytester.runpytest()
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*invalid codex marker*"])
