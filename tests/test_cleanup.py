import os
import stat
from pathlib import Path

import pytest

from pytest_codex.cleanup import remove_tree


def test_cleanup_removes_readonly_git_style_files(tmp_path):
    root = tmp_path / "owned"
    root.mkdir()
    file = root / "readonly"
    file.write_text("data", encoding="utf-8")
    file.chmod(stat.S_IREAD)
    remove_tree(root, tmp_path)
    assert not root.exists()


def test_cleanup_refuses_parent_or_other_directory(tmp_path):
    with pytest.raises(ValueError):
        remove_tree(tmp_path, tmp_path)
    with pytest.raises(ValueError):
        remove_tree(tmp_path.parent, tmp_path)


def test_cleanup_removes_long_git_object_paths(tmp_path):
    from pytest_codex.sandbox import make_sandbox

    source = tmp_path / "source"
    source.mkdir()
    (source / "input.txt").write_text("data", encoding="utf-8")
    root = tmp_path / ("x" * max(1, 215 - len(str(tmp_path)) - 1))
    make_sandbox(source, root)
    remove_tree(root, tmp_path)
    assert not root.exists()


def test_cleanup_tolerates_a_descendant_disappearing_after_scan(tmp_path, monkeypatch):
    import shutil
    import sys

    root = tmp_path / "owned"
    child = root / ".git/objects/maintenance.lock"
    child.parent.mkdir(parents=True)
    child.write_text("temporary", encoding="utf-8")
    original = shutil.rmtree

    def raced(path, *, onerror):
        # Reproduce Python 3.10 rmtree's callback after a scanned child vanishes.
        child.unlink()
        try:
            child.unlink()
        except FileNotFoundError:
            onerror(os.unlink, str(child), sys.exc_info())
        original(path, onerror=onerror)

    monkeypatch.setattr(shutil, "rmtree", raced)
    remove_tree(root, tmp_path)
    assert not root.exists()


def test_cleanup_still_reports_a_missing_top_level_target(tmp_path):
    with pytest.raises(FileNotFoundError):
        remove_tree(tmp_path / "missing", tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Windows literal trailing-dot alias")
def test_cleanup_deletes_exact_authorized_target_not_literal_alias(tmp_path):
    owner = tmp_path / "owned"
    target = owner / "child"
    target.mkdir(parents=True)
    literal_owner = Path("\\\\?\\" + str(owner) + ".")
    literal_child = literal_owner / "child"
    literal_child.mkdir(parents=True)
    (literal_child / "sentinel").write_text("keep", encoding="utf-8")
    try:
        remove_tree(Path(str(owner) + ".") / "child", owner)
        assert not target.exists()
        assert (literal_child / "sentinel").read_text(encoding="utf-8") == "keep"
    finally:
        remove_tree(owner, tmp_path)
        remove_tree(literal_owner, Path("\\\\?\\" + str(tmp_path)))
