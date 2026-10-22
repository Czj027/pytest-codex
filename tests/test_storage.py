import json

import pytest

from pytest_codex.cassette import CassetteError, cassette_key, load_cassette, save_cassette
from pytest_codex.run import Run
from pytest_codex.sandbox import make_sandbox
from pytest_codex.snapshot import Diff, snapshot


def test_sandbox_copy_overrides_git_baseline_and_exclusions(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_text("old", encoding="utf-8")
    (source / ".venv").mkdir()
    (source / ".venv" / "private").write_text("no", encoding="utf-8")
    target = make_sandbox(source, tmp_path / "copy", {"a.txt": "new", "rules/AGENTS.md": "rules"})
    assert (source / "a.txt").read_text() == "old"
    assert (target / "a.txt").read_text() == "new"
    assert not (target / ".venv").exists()
    assert (target / ".git").is_dir()
    import subprocess

    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=target) == b""


@pytest.mark.parametrize("path", ["../oops", "C:\\oops", "/oops", "..\\oops"])
def test_override_rejects_escape(tmp_path, path):
    source = tmp_path / "src"
    source.mkdir()
    with pytest.raises(ValueError):
        make_sandbox(source, tmp_path / "dst", {path: "bad"})


def test_cassette_roundtrip_binary_deletion_modes_and_key(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.bin").write_bytes(b"\x00\xff")
    (root / "a.bin").chmod(0o755)
    run = Run([{"type": "turn.completed"}], root, Diff(["a.bin"], [], ["gone.txt"]))
    key = cassette_key("prompt", None, {}, "workspace-write", snapshot(root), "full")
    path = tmp_path / "cassette.json"
    save_cassette(path, key, run, "codex-cli test")
    (root / "a.bin").unlink()
    (root / "gone.txt").write_text("delete", encoding="utf-8")
    replay = load_cassette(path, key, root)
    assert replay.succeeded and replay.replayed
    assert (root / "a.bin").read_bytes() == b"\x00\xff"
    assert not (root / "gone.txt").exists()
    assert replay.deleted("gone.txt")
    with pytest.raises(CassetteError, match="record"):
        load_cassette(path, "changed-key", root)
    assert key != cassette_key("other", None, {}, "workspace-write", snapshot(root), "full")


def test_missing_and_malicious_cassette_fail_before_mutation(tmp_path):
    with pytest.raises(CassetteError, match="record"):
        load_cassette(tmp_path / "missing", "k", tmp_path)
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "key": "k",
                "events": [],
                "diff": {"added": ["../escape"]},
                "files": {"../escape": {"data": "eA==", "mode": 420}},
                "returncode": 0,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CassetteError):
        load_cassette(path, "k", tmp_path)
    assert not (tmp_path.parent / "escape").exists()


def test_recording_roundtrip_with_long_windows_filename(tmp_path):
    from pytest_codex.cleanup import remove_tree

    directory = tmp_path / ("x" * max(1, 230 - len(str(tmp_path)) - 1))
    path = directory / ("recording-" + "y" * 70 + ".json")
    run = Run([{"type": "turn.completed"}], tmp_path)
    save_cassette(path, "key", run, "codex-cli test")
    assert load_cassette(path, "key", tmp_path).succeeded
    remove_tree(directory, tmp_path)
