import json
import os

import pytest

from pytest_codex.runner import execute


@pytest.fixture
def fake_cli(tmp_path):
    script = tmp_path / "fake_codex.py"
    script.write_text(
        """import json, os, pathlib, sys, time
sys.stdin.reconfigure(encoding="utf-8")
if "--version" in sys.argv:
    print("codex-cli test")
    raise SystemExit
prompt = sys.stdin.read()
if prompt == "wait":
    time.sleep(30)
home = pathlib.Path(os.environ["CODEX_HOME"])
print(json.dumps({"type": "item.completed", "item": {"id": "m", "type": "agent_message", "text": json.dumps({"prompt": prompt, "args": sys.argv[1:], "home": str(home), "auth": (home / "auth.json").exists(), "config": (home / "config.toml").exists()})}}))
pathlib.Path("result.txt").write_text("done", encoding="utf-8")
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 2}}))
""",
        encoding="utf-8",
    )
    return str(script)


def test_runner_stdin_config_isolation_and_cleanup(tmp_path, monkeypatch, fake_cli):
    source_home = tmp_path / "source-home"
    source_home.mkdir()
    (source_home / "auth.json").write_text("{}", encoding="utf-8")
    (source_home / "config.toml").write_text("private config", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(source_home))
    root = tmp_path / "project"
    root.mkdir()
    run = execute(
        "中文 prompt",
        root,
        codex_bin=fake_cli,
        config={"model_reasoning_effort": "low"},
        model="test-model",
    )
    observed = json.loads(run.final_message)
    assert run.succeeded and run.added("result.txt") and run.tokens.total == 3
    assert observed["prompt"] == "中文 prompt"
    assert observed["auth"] and not observed["config"]
    assert "--ignore-user-config" in observed["args"]
    assert 'approval_policy="never"' in observed["args"]
    assert 'model_reasoning_effort="low"' in observed["args"]
    assert "test-model" in observed["args"] and observed["args"][-1] == "-"
    assert not os.path.exists(observed["home"])
    assert (source_home / "auth.json").exists()


def test_timeout_kills_process_and_cleans_home(tmp_path, monkeypatch, fake_cli):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "empty-home"))
    with pytest.raises(TimeoutError, match="timed out"):
        execute("wait", tmp_path, codex_bin=fake_cli, timeout=0.2)
    assert not (tmp_path / "result.txt").exists()


@pytest.mark.parametrize(
    "options",
    [
        {"isolation": "bad"},
        {"sandbox": "bad"},
        {"timeout": 0},
        {"config": {"approval_policy": "on-request"}},
    ],
)
def test_runner_rejects_invalid_options_before_execution(tmp_path, fake_cli, options):
    with pytest.raises(ValueError):
        execute("test", tmp_path, codex_bin=fake_cli, **options)
