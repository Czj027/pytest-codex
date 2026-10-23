import json
from types import SimpleNamespace

import pytest

from pytest_codex.desktop_engine import find_desktop_binary


def test_explicit_override_is_validated_without_search(tmp_path, monkeypatch):
    binary = tmp_path / "engine.py"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setenv("PYTEST_CODEX_DESKTOP_BIN", str(binary))
    assert find_desktop_binary() == str(binary.resolve())
    monkeypatch.setenv("PYTEST_CODEX_DESKTOP_BIN", str(tmp_path / "missing"))
    with pytest.raises(FileNotFoundError, match="PYTEST_CODEX_DESKTOP_BIN"):
        find_desktop_binary()


def test_macos_known_bundle(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CODEX_DESKTOP_BIN", raising=False)
    binary = tmp_path / "Applications/Codex.app/Contents/Resources/codex"
    binary.parent.mkdir(parents=True)
    binary.write_text("", encoding="utf-8")
    monkeypatch.setattr("pytest_codex.desktop_engine.sys.platform", "darwin")
    monkeypatch.setattr("pytest_codex.desktop_engine.Path.home", lambda: tmp_path)
    assert find_desktop_binary() == str(binary.resolve())


def test_windows_uses_registered_current_package(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CODEX_DESKTOP_BIN", raising=False)
    binary = tmp_path / "app/resources/codex.exe"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"stub")
    monkeypatch.setattr("pytest_codex.desktop_engine.sys.platform", "win32")
    monkeypatch.setattr("pytest_codex.desktop_engine.shutil.which", lambda name: "powershell.exe")
    observed = []

    def inventory(args, **kwargs):
        observed.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps(str(tmp_path)))

    monkeypatch.setattr("pytest_codex.desktop_engine.subprocess.run", inventory)
    assert find_desktop_binary() == str(binary.resolve())
    assert "OpenAI.Codex" in observed[0][0][-1]
    assert observed[0][1]["timeout"] <= 15
    assert not observed[0][1].get("shell", False)


def test_discovery_failure_has_explicit_path_escape_hatch(monkeypatch):
    monkeypatch.delenv("PYTEST_CODEX_DESKTOP_BIN", raising=False)
    monkeypatch.setattr("pytest_codex.desktop_engine.sys.platform", "linux")
    with pytest.raises(FileNotFoundError, match="--codex-bin"):
        find_desktop_binary()


def test_desktop_flag_replay_does_not_discover_and_fixture_import(pytester):
    pytester.makeini("[pytest]\ncodex_project = project\n")
    (pytester.path / "project").mkdir()
    pytester.makeconftest("""
pytest_plugins = ["pytest_codex.plugin"]
import pytest
@pytest.fixture(autouse=True)
def no_discovery(monkeypatch):
    def forbidden():
        raise AssertionError("desktop discovery during replay")
    monkeypatch.setattr("pytest_codex.plugin.find_desktop_binary", forbidden)
""")
    pytester.makepyfile("""
def test_missing(codex):
    codex.exec("hello")
""")
    result = pytester.runpytest("--codex-desktop")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*Cannot replay*"])
    assert "desktop discovery during replay" not in result.stdout.str()


def test_desktop_live_uses_explicit_engine_with_existing_isolation(pytester):
    fake = pytester.path / "desktop.py"
    fake.write_text(
        """import json,sys
if "--version" in sys.argv:
    print("codex-cli test")
else:
    sys.stdin.read()
    print(json.dumps({"type":"turn.completed"}))
""",
        encoding="utf-8",
    )
    pytester.makeconftest(f"""
pytest_plugins = ["pytest_codex.plugin"]
import pytest
@pytest.fixture(autouse=True)
def desktop(monkeypatch):
    monkeypatch.setenv("PYTEST_CODEX_DESKTOP_BIN", {str(fake)!r})
""")
    pytester.makeini("[pytest]\ncodex_isolation = config\ncodex_project = project\n")
    (pytester.path / "project").mkdir()
    pytester.makepyfile("""
def test_desktop(codex):
    assert codex.exec("hello", files=[]).succeeded
""")
    pytester.runpytest("--codex-desktop", "--codex-live").assert_outcomes(passed=1)
