import subprocess

import pytest

from pytest_codex.sandbox import make_sandbox


def test_git_ignored_private_files_do_not_enter_sandbox(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / ".gitignore").write_text("private/\nlocal-notes.md\n", encoding="utf-8")
    (source / "private").mkdir()
    (source / "private" / "auth.txt").write_text("do not copy", encoding="utf-8")
    (source / "local-notes.md").write_text("private notes", encoding="utf-8")
    (source / "public.py").write_text("print('hello')", encoding="utf-8")
    # Tracked inputs remain inputs even if an ignore pattern subsequently matches.
    (source / "tracked.md").write_text("public", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "tracked.md"], check=True)
    (source / ".gitignore").write_text("private/\n*.md\n", encoding="utf-8")
    target = make_sandbox(source, tmp_path / "copy")
    assert (target / "public.py").read_text(encoding="utf-8") == "print('hello')"
    assert (target / "tracked.md").read_text(encoding="utf-8") == "public"
    assert not (target / "local-notes.md").exists()
    assert not (target / "private").exists()


def test_nested_project_honors_ignore_negations(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("*.local\n!keep.local\n", encoding="utf-8")
    source = root / "nested"
    source.mkdir()
    (source / "private.local").write_text("private", encoding="utf-8")
    (source / "keep.local").write_text("public", encoding="utf-8")
    target = make_sandbox(source, tmp_path / "copy")
    assert not (target / "private.local").exists()
    assert (target / "keep.local").read_text(encoding="utf-8") == "public"


def test_git_ignore_failure_in_a_repository_does_not_copy_private_files(tmp_path, monkeypatch):
    source = tmp_path / "repo"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / ".gitignore").write_text("private.txt", encoding="utf-8")
    (source / "private.txt").write_text("not public", encoding="utf-8")
    real_run = subprocess.run

    def git_failure(args, **kwargs):
        if args[:2] == ["git", "ls-files"]:
            return subprocess.CompletedProcess(args, 128, b"", b"cannot read Git index")
        return real_run(args, **kwargs)

    monkeypatch.setattr("pytest_codex.sandbox.subprocess.run", git_failure)
    with pytest.raises(RuntimeError, match="Git ignore"):
        make_sandbox(source, tmp_path / "copy")
    assert not (tmp_path / "copy").exists()


def test_explicit_project_below_ignored_parent_is_a_standalone_fixture(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("scratch/", encoding="utf-8")
    source = root / "scratch" / "fixture"
    source.mkdir(parents=True)
    (source / "input.txt").write_text("explicit input", encoding="utf-8")
    target = make_sandbox(source, tmp_path / "copy")
    assert (target / "input.txt").read_text(encoding="utf-8") == "explicit input"
