"""Validate untrusted project-relative paths before reading or writing."""

from pathlib import Path, PurePosixPath, PureWindowsPath


def project_path(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or "\x00" in name:
        raise ValueError("expected a nonempty project-relative path")
    normalized = name.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    devices = {"con", "prn", "aux", "nul"} | {
        f"{prefix}{i}" for prefix in ("com", "lpt") for i in range(1, 10)
    }
    if (
        PureWindowsPath(name).drive
        or normalized.startswith("/")
        or any(
            part.casefold() in {"..", ".git"}
            or part.endswith((".", " "))
            or ":" in part
            or any(ord(character) < 32 for character in part)
            or part.split(".")[0].casefold() in devices
            for part in parts
        )
        or not parts
    ):
        raise ValueError(f"path must be relative to the project: {name!r}")
    root = Path(root).resolve()
    candidate = root.joinpath(*parts)
    if not candidate.resolve().is_relative_to(root) or candidate.resolve() == root:
        raise ValueError(f"path is outside the project: {name!r}")
    for parent in [candidate, *candidate.parents]:
        if parent == root:
            break
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError(f"symlink/junction is outside the supported project paths: {name!r}")
    return candidate
