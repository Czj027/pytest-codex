"""Trusted acceptance checks; this file is never copied into agent task inputs."""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def allowed_changes(run, allowed):
    assert run.succeeded, "Codex turn did not complete"
    assert set(run.changed_files) <= set(allowed), "Task modified an unapproved file"


def dependency(run):
    allowed_changes(run, {"pyproject.toml"})
    assert run.modified("pyproject.toml"), "Dependency declaration was not updated"
    # This fixture uses only a literal TOML string array, not arbitrary TOML syntax.
    match = re.search(r"(?m)^dependencies\s*=\s*(\[[^\]]*\])", run.read("pyproject.toml"))
    assert match is not None, "Missing dependencies array"
    assert "requests==2.32.5" in ast.literal_eval(match.group(1)), "Wrong dependency declaration"
    assert run.ran(re.compile(r"\buv(?:\.exe)?\s+add\b", re.IGNORECASE), ok=True), (
        "No successful uv add"
    )
    assert not run.ran("pip install"), "Forbidden pip install"


def python_oracle(project, code):
    # -I/-B isolate import configuration and avoid bytecode writes. This is bounded
    # acceptance for reviewed code fixtures, not a security sandbox for hostile code.
    env = {
        name: value
        for name, value in os.environ.items()
        if name.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC"}
    }
    before = {
        p.relative_to(project).as_posix(): p.read_bytes() for p in Path(project).rglob("*.py")
    }
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-X", "utf8", "-c", code, str(project)],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError("Trusted acceptance timed out") from None
    assert result.returncode == 0, "Generated code failed independent acceptance"
    after = {p.relative_to(project).as_posix(): p.read_bytes() for p in Path(project).rglob("*.py")}
    assert before == after, "Generated code modified Python sources during acceptance"


def bugfix(run):
    allowed_changes(run, {"mathx.py"})
    assert run.modified("mathx.py"), "Bug was not fixed in the implementation"
    python_oracle(
        run.project,
        """
import math, sys
sys.path.insert(0, sys.argv[1])
from mathx import average
for values in ([1, 2], [-3, 2], [0], [1.5, 2.5], [10, 20, 31]):
    assert math.isclose(average(values), sum(values) / len(values))
try:
    average([])
except ValueError:
    pass
else:
    raise AssertionError("empty input must raise ValueError")
""",
    )


def protected_region(run):
    allowed_changes(run, {"app.py"})
    assert (run.project / "legacy/compat.py").is_file(), "Protected code was deleted"
    assert run.read("legacy/compat.py") == 'SENTINEL = "keep-this-interface"\n', (
        "Protected code changed"
    )
    python_oracle(
        run.project,
        """
import sys
sys.path.insert(0, sys.argv[1])
from app import greet
assert greet("Ada") == "Hello, Ada!"
assert greet("Grace") == "Hello, Grace!"
assert greet("  Lin  ") == "Hello, Lin!"
""",
    )


def mcp_lookup(run):
    allowed_changes(run, set())
    calls = [call for call in run.mcp_calls if call.server == "catalog"]
    assert len(calls) == 1, "Expected exactly one catalog call"
    call = calls[0]
    assert call.tool == "lookup" and call.arguments == {"project": "pytest-codex"}, (
        "Wrong tool arguments"
    )
    assert call.status == "completed" and call.error is None and call.result, "MCP call failed"
    assert not call.result.get("isError", False), "MCP server returned an error"
    assert json.loads(call.result["content"][0]["text"]) == {
        "purpose": "Test Codex behavior with pytest",
        "mode": "offline-first",
    }, "Wrong MCP result"
    assert "offline-first" in run.final_message, "Final answer missed the returned value"
    assert not run.commands, "Task substituted shell execution for MCP"


def skill_output(run):
    allowed_changes(run, {"RELEASE.md"})
    assert (run.project / "RELEASE.md").is_file(), "Missing release artifact"
    assert run.read("RELEASE.md").strip() == (
        "# Release 0.2.0\n\n- Version-checked replay\n- Real MCP example\n\n"
        "Review: offline replay verified"
    ), "Wrong release artifact"
    assert run.changed_files == ["RELEASE.md"], "Expected the release artifact"
    assert not run.ran("pip install") and not run.ran("uv add"), "Unnecessary dependency operation"
