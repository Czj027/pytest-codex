import json
import os
import subprocess

import pytest

from pytest_codex.cassette import save_cassette
from pytest_codex.paths import project_path
from pytest_codex.run import Run
from pytest_codex.runner import execute


@pytest.mark.parametrize(
    "name", [".GIT/config", ".git./config", ".git /config", "a.txt:stream", "CON", "dir/NUL.txt"]
)
def test_project_paths_reject_windows_aliases_on_every_platform(tmp_path, name):
    with pytest.raises(ValueError):
        project_path(tmp_path, name)


def test_recording_scrubs_double_escaped_machine_paths(tmp_path):
    message = (
        str(tmp_path).replace("\\", "\\\\") + " " + os.path.expanduser("~").replace("\\", "\\\\")
    )
    run = Run(
        [{"type": "item.completed", "item": {"id": "m", "type": "agent_message", "text": message}}],
        tmp_path,
    )
    path = tmp_path / "record.json"
    save_cassette(path, "key", run, "test")
    text = json.loads(path.read_text(encoding="utf-8"))["events"][0]["item"]["text"]
    assert text == "<PROJECT> <HOME>"


def test_interrupt_reaps_running_child(tmp_path, monkeypatch):
    script = tmp_path / "slow.py"
    script.write_text("import time; time.sleep(30)", encoding="utf-8")
    real_popen = subprocess.Popen
    children = []

    def start(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        if str(script) in args[0]:
            children.append(proc)
            original = proc.communicate
            first = True

            def interrupted(*values, **options):
                nonlocal first
                if first:
                    first = False
                    raise KeyboardInterrupt
                return original(*values, **options)

            proc.communicate = interrupted
        return proc

    monkeypatch.setattr(subprocess, "Popen", start)
    try:
        with pytest.raises(KeyboardInterrupt):
            execute("wait", tmp_path, codex_bin=str(script))
        assert children[0].poll() is not None
    finally:
        for proc in children:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
