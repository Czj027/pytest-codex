import json

import pytest

from pytest_codex.cassette import CassetteError, load_cassette, save_cassette
from pytest_codex.run import Run
from pytest_codex.snapshot import Diff


def test_version_mismatch_fails_before_replaying_files(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "result.txt").write_text("recorded", encoding="utf-8")
    run = Run([{"type": "turn.completed"}], project, Diff(["result.txt"]))
    path = tmp_path / "recording.json"
    save_cassette(path, "key", run, "codex-cli 0.163.0")
    (project / "result.txt").unlink()
    with pytest.raises(CassetteError, match="CLI version.*Re-record"):
        load_cassette(path, "key", project, expected_version="0.164.0")
    assert not (project / "result.txt").exists()
    assert load_cassette(path, "key", project, expected_version="0.163.0").succeeded


def test_pinned_replay_rejects_missing_version_metadata(tmp_path):
    path = tmp_path / "recording.json"
    save_cassette(path, "key", Run([], tmp_path), "codex-cli 0.163.0")
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["codex_version"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(CassetteError, match="CLI version"):
        load_cassette(path, "key", tmp_path, expected_version="0.163.0")


def test_offline_version_pin_does_not_need_cli(pytester):
    pytester.makeini("[pytest]\ncodex_project=project\ncodex_cli_version=0.163.0")
    (pytester.path / "project").mkdir()
    pytester.makepyfile('def test_run(codex):\n    assert codex.exec("hello").succeeded')
    pytester.makeconftest("""
import pytest
from pytest_codex.run import Run
@pytest.fixture(autouse=True)
def external_process(monkeypatch):
    monkeypatch.setattr("pytest_codex.plugin.cli_version", lambda binary: "codex-cli 0.163.0")
    monkeypatch.setattr("pytest_codex.plugin.execute", lambda prompt, project, **kwargs:
        Run([{"type": "turn.completed"}], project))
""")
    pytester.runpytest("--codex-record", "--codex-model=test-model").assert_outcomes(passed=1)
    pytester.makeconftest("")
    pytester.runpytest("--codex-bin=missing", "--codex-model=test-model").assert_outcomes(passed=1)
    result = pytester.runpytest(
        "--codex-bin=missing", "--codex-model=test-model", "--codex-cli-version=0.164.0"
    )
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*CLI version*Re-record*"])


def test_strict_replay_checks_local_cli_without_model_calls(pytester):
    pytester.makeini("[pytest]\ncodex_project=project")
    (pytester.path / "project").mkdir()
    binary = pytester.makepyfile(
        cli="""
import sys
if sys.argv[1:] != ["--version"]:
    raise RuntimeError("unexpected model call")
print("codex-cli 0.164.0")
"""
    )
    pytester.makepyfile(
        test_check="""
def test_version(codex):
    codex.exec("hello", model="test-model")
"""
    )
    # A real portable recording is created via the fixture's normal recording flow.
    pytester.makeconftest("""
import pytest
from pytest_codex.run import Run
@pytest.fixture(autouse=True)
def external_process(monkeypatch):
    monkeypatch.setattr("pytest_codex.plugin.cli_version", lambda binary: "codex-cli 0.163.0")
    monkeypatch.setattr("pytest_codex.plugin.execute", lambda prompt, project, **kwargs:
        Run([{"type": "turn.completed"}], project))
""")
    pytester.runpytest("--codex-record").assert_outcomes(passed=1)
    pytester.makeconftest("")
    result = pytester.runpytest("--codex-check-cli", f"--codex-bin={binary}")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*CLI version*Re-record*"])


def test_strict_replay_requires_explicit_model(pytester):
    pytester.makeini("[pytest]\ncodex_project=project\ncodex_cli_version=0.163.0")
    (pytester.path / "project").mkdir()
    pytester.makepyfile('def test_run(codex):\n    codex.exec("hello")')
    result = pytester.runpytest("--codex-bin=missing")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*explicit model*--codex-model*"])


def test_incorrect_recording_pin_stops_before_model_call(pytester):
    pytester.makeini(
        "[pytest]\ncodex_project=project\ncodex_cli_version=0.163.0\ncodex_model=explicit-model"
    )
    (pytester.path / "project").mkdir()
    pytester.makepyfile('def test_record(codex):\n    codex.exec("hello")')
    pytester.makeconftest("""
import pytest
@pytest.fixture(autouse=True)
def cli_boundary(monkeypatch):
    monkeypatch.setattr("pytest_codex.plugin.cli_version", lambda binary: "codex-cli 0.164.0")
    def no_model_call(*args, **kwargs):
        raise AssertionError("unexpected model call")
    monkeypatch.setattr("pytest_codex.plugin.execute", no_model_call)
""")
    result = pytester.runpytest("--codex-record")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*CLI version mismatch*"])
    assert not list(pytester.path.glob("cassettes/**/*.json"))
