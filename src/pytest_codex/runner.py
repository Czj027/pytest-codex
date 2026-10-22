"""Invoke Codex without a shell; isolate configuration and bound runtime."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .cleanup import remove_tree
from .events import parse_jsonl
from .run import Run
from .snapshot import diff, snapshot


def binary_command(binary: str = "codex") -> list[str]:
    found = shutil.which(binary)
    if found is None:
        candidate = Path(binary).resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"Codex executable not found: {binary}")
        found = str(candidate)
    if found.lower().endswith(".py"):
        return [sys.executable, found]
    if found.lower().endswith(".ps1"):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            raise FileNotFoundError("PowerShell is required for this Codex launcher")
        return [shell, "-NoProfile", "-File", found]
    return [found]


def cli_version(binary: str = "codex") -> str:
    result = subprocess.run(
        [*binary_command(binary), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        stdin=subprocess.DEVNULL,
        check=True,
    )
    return result.stdout.strip()


def toml_value(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and math.isfinite(value):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ", ".join(f"{json.dumps(str(k))} = {toml_value(v)}" for k, v in value.items())
            + "}"
        )
    raise ValueError(f"unsupported TOML config value: {type(value).__name__}")


@contextmanager
def isolated_environment(isolation: str):
    env = dict(os.environ)
    # Do not leak active parent-session transport identifiers into the child session.
    for name in ("CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_TOOL_CALL_ID"):
        env.pop(name, None)
    if isolation != "full":
        yield env
        return
    base = Path.home() / ".cache" / "pytest-codex" / "homes"
    base.mkdir(parents=True, exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix="run-", dir=base))
    try:
        home.chmod(0o700)
        source = Path(env.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
        if source.is_file():
            shutil.copyfile(source, home / "auth.json")
            (home / "auth.json").chmod(0o600)
        env["CODEX_HOME"] = str(home)
        yield env
    finally:
        remove_tree(home, base)


def execute(
    prompt: str,
    project: Path,
    *,
    codex_bin: str = "codex",
    model: str | None = None,
    sandbox: str = "workspace-write",
    config: dict | None = None,
    isolation: str = "full",
    timeout: float = 300,
) -> Run:
    if isolation not in {"none", "config", "full"}:
        raise ValueError("isolation must be none, config or full")
    if sandbox not in {"read-only", "workspace-write", "danger-full-access"}:
        raise ValueError("invalid Codex sandbox mode")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a positive finite number")
    options = dict(config or {})
    if options.get("approval_policy", "never") != "never":
        raise ValueError("noninteractive execution requires approval_policy=never")
    if "sandbox_mode" in options:
        raise ValueError("use the sandbox argument instead of config sandbox_mode")
    options["approval_policy"] = "never"
    if os.name == "nt" and isolation == "full":
        options.setdefault("windows.sandbox", "elevated")
    args = [
        *binary_command(codex_bin),
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "-s",
        sandbox,
    ]
    if isolation != "none":
        args.append("--ignore-user-config")
    if model is not None:
        args.extend(["-m", model])
    for name, value in sorted(options.items()):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise ValueError(f"invalid config key: {name!r}")
        args.extend(["-c", f"{name}={toml_value(value)}"])
    args.append("-")
    project = Path(project).resolve()
    before = snapshot(project)
    with isolated_environment(isolation) as env:
        extra = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        process = subprocess.Popen(
            args,
            cwd=project,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **extra,
        )
        completed = False
        try:
            stdout, stderr = process.communicate(prompt, timeout=timeout)
            completed = True
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Codex timed out after {timeout}s in {project}") from exc
        finally:
            if not completed:
                _stop_process(process)
    return Run(
        parse_jsonl(stdout),
        project,
        diff(before, snapshot(project)),
        process.returncode,
        stderr=stderr,
    )


def _stop_process(process):
    """Terminate the process group on timeout, interruption or pipe failure."""
    try:
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass  # Still kill and reap the immediate process below.
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    finally:
        if process.poll() is None:
            process.kill()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
            process.wait(timeout=5)
