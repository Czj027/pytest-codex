"""Portable JSON recordings. Replay never executes event command text."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .paths import native_path, project_path
from .run import Run
from .snapshot import Diff, tree_hash


class CassetteError(RuntimeError):
    pass


def check_cli_version(recorded, expected: str) -> None:
    """Compare portable version strings without launching an installed CLI."""

    def normalize(value):
        return value.removeprefix("codex-cli ").strip() if isinstance(value, str) else None

    if not normalize(expected) or normalize(recorded) != normalize(expected):
        raise CassetteError(
            f"CLI version mismatch: recorded={recorded!r}, expected={expected!r}. "
            "Re-record with --codex-record after checking your version pin."
        )


def cassette_key(prompt, model, config, sandbox, inputs, isolation="full") -> str:
    payload = {
        "prompt": prompt,
        "model": model,
        "config": config,
        "sandbox": sandbox,
        "inputs": tree_hash(inputs),
        "isolation": isolation,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def save_cassette(path: Path, key: str, run: Run, version: str, *, overwrite: bool = True) -> None:
    if getattr(run, "file_state", "verified") != "verified":
        raise ValueError(
            "A full cassette requires verified file state; export an observation instead"
        )
    files = {}
    for name in run.diff.added + run.diff.modified:
        source = project_path(run.project, name)
        files[name] = {
            "data": base64.b64encode(source.read_bytes()).decode("ascii"),
            "mode": source.stat().st_mode & 0o777,
        }

    # Absolute sandbox and home paths are unnecessary for playback and leak identities.
    def portable(value):
        if isinstance(value, str):
            for location, replacement in [
                (str(run.project.resolve()), "<PROJECT>"),
                (str(Path.home()), "<HOME>"),
            ]:
                for variant in (
                    location.replace("\\", "\\\\"),
                    location,
                    location.replace("\\", "/"),
                ):
                    value = value.replace(variant, replacement)
            return value
        if isinstance(value, list):
            return [portable(item) for item in value]
        if isinstance(value, dict):
            return {name: portable(item) for name, item in value.items()}
        return value

    payload = {
        "schema": 1,
        "key": key,
        "codex_version": version,
        "events": portable(run.events),
        "diff": run.diff.to_dict(),
        "files": files,
        "returncode": run.returncode,
        "stderr": portable(run.stderr),
    }
    path = native_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cassette-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        if overwrite:
            os.replace(temporary, path)
        else:
            # Same-directory hard-link publication is atomic and refuses a concurrent
            # winner. Never fall back to replace when immutable publication fails.
            os.link(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_cassette(
    path: Path, key: str, project: Path, *, expected_version: str | None = None
) -> Run:
    try:
        data = json.loads(native_path(path).read_text(encoding="utf-8"))
        if data.get("schema") != 1 or data.get("key") != key:
            raise ValueError("schema or input key does not match")
        if expected_version is not None:
            check_cli_version(data.get("codex_version"), expected_version)
        changes = Diff.from_dict(data["diff"])
        if not all(
            isinstance(names, list) and all(isinstance(n, str) for n in names)
            for names in [changes.added, changes.modified, changes.deleted]
        ):
            raise ValueError("invalid diff")
        if len(changes.changed) != len(set(changes.changed)):
            raise ValueError("duplicate or conflicting file paths")
        if set(data["files"]) != set(changes.added + changes.modified):
            raise ValueError("recorded files do not match diff")
        # Decode and validate every path/content before mutating any file.
        destinations = {name: project_path(project, name) for name in changes.changed}
        contents = {
            name: base64.b64decode(info["data"], validate=True)
            for name, info in data["files"].items()
        }
        modes = {name: int(info["mode"]) & 0o777 for name, info in data["files"].items()}
        if not isinstance(data["events"], list) or not all(
            isinstance(e, dict) for e in data["events"]
        ):
            raise ValueError("invalid events")
        run = Run(
            data["events"],
            project,
            changes,
            int(data["returncode"]),
            stderr=data.get("stderr", ""),
            replayed=True,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise CassetteError(f"Cannot replay {path}: {exc}. Re-record with --codex-record.") from exc
    for name in changes.deleted:
        destinations[name].unlink(missing_ok=True)
        parent = destinations[name].parent
        while parent != Path(project).resolve():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    for name, content in contents.items():
        destinations[name].parent.mkdir(parents=True, exist_ok=True)
        destinations[name].write_bytes(content)
        destinations[name].chmod(modes[name])
    return run
