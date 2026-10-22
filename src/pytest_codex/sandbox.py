"""Copy test inputs into a disposable Git repository."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .paths import project_path
from .snapshot import DEFAULT_IGNORE

COPY_IGNORE = DEFAULT_IGNORE | {
    "cassettes",
    ".planning",
    ".release-venv",
    ".verify-venv",
    ".uv-cache",
    ".tmp",
    "dist",
    "build",
    "*.egg-info",
}


def _git_ignored_inputs(source: Path) -> set[str]:
    # Respect Git's actual ignore rules (including nested patterns and negations).
    # Ignored local notes and recordings must not be sent to an agent during dogfooding.
    selected_is_ignored = subprocess.run(
        ["git", "check-ignore", "-q", "."],
        cwd=source,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )
    if selected_is_ignored.returncode == 0:
        # A caller explicitly selected a fixture inside an ignored scratch/temp
        # directory. Treat it as standalone, not as its ancestor repository.
        return set()
    ignored_result = subprocess.run(
        [
            "git",
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--directory",
            "-z",
            "--",
            ".",
        ],
        cwd=source,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )
    if ignored_result.returncode and any(
        (parent / ".git").exists() for parent in [source, *source.parents]
    ):
        raise RuntimeError("Cannot read Git ignore rules; refusing to copy repository inputs")
    return (
        {
            name.rstrip("/")
            for name in ignored_result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
            if name
        }
        if ignored_result.returncode == 0
        else set()
    )


def make_sandbox(source: Path, target: Path, files: dict[str, str] | None = None) -> Path:
    source, target = Path(source).resolve(), Path(target).resolve()
    if not source.is_dir():
        raise ValueError(f"project directory does not exist: {source}")
    if source == target or target.is_relative_to(source):
        raise ValueError("sandbox destination must be outside the source project")
    for name in files or {}:
        project_path(target, name)
    git_ignored = _git_ignored_inputs(source)

    def ignore(directory, names):
        ignored = set(shutil.ignore_patterns(*COPY_IGNORE)(directory, names))
        ignored.update(
            name
            for name in names
            if (Path(directory) / name).relative_to(source).as_posix() in git_ignored
        )
        for name in set(names) - ignored:
            entry = Path(directory) / name
            if entry.is_symlink() or (hasattr(entry, "is_junction") and entry.is_junction()):
                raise ValueError(f"project symlinks/junctions are not supported: {entry}")
        return ignored

    shutil.copytree(source, target, ignore=ignore)
    for name, content in (files or {}).items():
        path = project_path(target, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
    for args in (
        ["init", "-q"],
        ["add", "--all"],
        [
            "-c",
            "user.name=pytest-codex",
            "-c",
            "user.email=pytest-codex@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "baseline",
        ],
    ):
        subprocess.run(
            ["git", *args],
            cwd=target,
            check=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=30,
        )
    return target
