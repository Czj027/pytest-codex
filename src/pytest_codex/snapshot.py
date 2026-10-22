"""File-tree snapshots used to detect what a Codex run changed.

Event-level ``file_change`` items are not enough: files touched by shell
commands (``uv add`` editing ``pyproject.toml``, code generators, ...) never
show up as events. So we hash the tree before and after every run.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_IGNORE = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    ".uv-cache",
}


def snapshot(root: Path, ignore: set[str] = DEFAULT_IGNORE) -> dict[str, str]:
    """Return ``{relative_posix_path: sha1}`` for every file under *root*."""
    result: dict[str, str] = {}
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        for name in [*dirnames, *filenames]:
            entry = Path(dirpath) / name
            if name not in ignore and (
                entry.is_symlink() or (hasattr(entry, "is_junction") and entry.is_junction())
            ):
                raise ValueError(f"snapshot does not support symlink/junction: {entry}")
        dirnames[:] = [d for d in dirnames if d not in ignore]
        for name in filenames:
            p = Path(dirpath) / name
            if name in ignore:
                continue
            digest = hashlib.sha1(p.read_bytes()).hexdigest()
            result[p.relative_to(root).as_posix()] = digest
    return result


@dataclass
class Diff:
    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    @property
    def changed(self) -> list[str]:
        return sorted(self.added + self.modified + self.deleted)

    def to_dict(self) -> dict[str, list[str]]:
        return {"added": self.added, "modified": self.modified, "deleted": self.deleted}

    @classmethod
    def from_dict(cls, d: dict[str, list[str]]) -> Diff:
        return cls(
            list(d.get("added", [])), list(d.get("modified", [])), list(d.get("deleted", []))
        )


def diff(before: dict[str, str], after: dict[str, str]) -> Diff:
    return Diff(
        added=sorted(set(after) - set(before)),
        modified=sorted(p for p in set(after) & set(before) if after[p] != before[p]),
        deleted=sorted(set(before) - set(after)),
    )


def tree_hash(snap: dict[str, str]) -> str:
    h = hashlib.sha256()
    for path in sorted(snap):
        h.update(f"{path}\0{snap[path]}\n".encode())
    return h.hexdigest()
