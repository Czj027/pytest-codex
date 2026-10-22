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


def make_sandbox(source: Path, target: Path, files: dict[str, str] | None = None) -> Path:
    source, target = Path(source).resolve(), Path(target).resolve()
    if not source.is_dir():
        raise ValueError(f"project directory does not exist: {source}")
    if source == target or target.is_relative_to(source):
        raise ValueError("sandbox destination must be outside the source project")
    # Validate overrides before creating anything.
    for name in files or {}:
        project_path(target, name)

    def ignore(directory, names):
        ignored = set(shutil.ignore_patterns(*COPY_IGNORE)(directory, names))
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
