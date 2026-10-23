"""Opt-in, privacy-minimal attempt summaries for fresh regression comparisons."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import pytest


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def case_id(item):
    # pytest's default parameter IDs can contain the entire prompt or credentials.
    # Keep the test location readable, but never export raw parameter IDs.
    name, separator, parameters = item.nodeid.partition("[")
    return name + ("[sha256-" + digest(parameters) + "]" if separator else "")


def configure(config):
    selected = config.getoption("codex_recording_set")
    if selected is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", selected):
        raise pytest.UsageError("recording-set must be 1-64 ASCII letters, digits, '-' or '_'")
    output = config.getoption("codex_results")
    config._codex_result_path = None
    if output is None:
        return
    path = Path(output)
    if not path.is_absolute():
        path = config.rootpath / path
    if path.exists():
        raise pytest.UsageError("Codex results file already exists; choose a new output path")
    config._codex_result_path = path
    for name in config.getini("codex_grader_files"):
        candidate = (config.rootpath / name).resolve()
        if not candidate.is_relative_to(config.rootpath.resolve()) or not candidate.is_file():
            raise pytest.UsageError("codex_grader_files must name files inside the pytest root")
    config._codex_results = {
        "schema": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "context": {
            "python": platform.python_version(),
            "platform": sys.platform,
            "plugin_version": version("pytest-codex"),
            "recording_set": selected,
        },
        "attempts": [],
    }


def record_case(item, factory, status, error_type=None, phase="call"):
    config = item.config
    if config._codex_result_path is None:
        return
    runs = list(factory._result_calls) if factory is not None else []
    errors = [
        run.get("execution_error") or ("IncompleteCodexTurn" if not run["succeeded"] else None)
        for run in runs
    ]
    if status in {"passed", "failed"} and any(errors):
        status, error_type = "error", next(error for error in errors if error)
    module = Path(str(item.path)).relative_to(config.rootpath).as_posix()
    current_grader = grader_hash(item)
    expected_grader = getattr(item, "_codex_grader_hash", current_grader)
    if current_grader != expected_grader:
        status, error_type = "error", "GraderChanged"
    row = {
        "case": case_id(item),
        "attempt": factory.attempt if factory is not None else 1,
        "status": status,
        "phase": phase,
        "error_type": error_type,
        "location": {"file": module, "line": item.location[1] + 1},
        "grader_hash": expected_grader,
        "runs": runs,
    }
    config._codex_results["attempts"].append(row)
    item._codex_exported = True


def execution_error(run):
    """Recognize incomplete turns and a narrow, observed shell-startup diagnostic."""
    if not run.succeeded:
        return "IncompleteCodexTurn"
    if any(
        command.exit_code == -1
        and command.output.startswith("Failed to create unified exec process:")
        for command in run.commands
    ):
        return "ShellStartupError"
    return None


def grader_hash(item):
    root = item.config.rootpath.resolve()
    files = [Path(str(item.path))]
    for name in item.config.getini("codex_grader_files"):
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise pytest.UsageError("codex_grader_files must name files inside the pytest root")
        files.append(path)
    return digest(
        {path.relative_to(root).as_posix(): path.read_text(encoding="utf-8") for path in files}
    )


def finish(config):
    path = config._codex_result_path
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects evidence even if another process creates it mid-run.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(config._codex_results, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
