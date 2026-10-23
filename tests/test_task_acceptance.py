import json
import shutil
from pathlib import Path

import pytest

from examples.regression import acceptance
from pytest_codex.run import Run
from pytest_codex.snapshot import Diff

FIXTURES = Path(__file__).resolve().parents[1] / "examples/regression/fixtures"


def fixture_run(tmp_path, name, changed):
    target = tmp_path / name
    shutil.copytree(FIXTURES / name, target)
    return Run([{"type": "turn.completed"}], target, Diff(modified=changed))


def test_independent_bug_oracle_rejects_original_and_accepts_fixed_code(tmp_path):
    run = fixture_run(tmp_path, "bugfix", ["mathx.py"])
    with pytest.raises(AssertionError, match="independent acceptance"):
        acceptance.bugfix(run)
    (run.project / "mathx.py").write_text(
        "def average(values):\n    if not values: raise ValueError('empty')\n"
        "    return sum(values) / len(values)\n",
        encoding="utf-8",
    )
    acceptance.bugfix(run)


def test_protected_oracle_checks_output_and_rejects_boundary_changes(tmp_path):
    run = fixture_run(tmp_path, "protected", ["app.py"])
    with pytest.raises(AssertionError, match="independent acceptance"):
        acceptance.protected_region(run)
    (run.project / "app.py").write_text(
        'def greet(name):\n    return "Hello, " + name.strip() + "!"\n',
        encoding="utf-8",
    )
    acceptance.protected_region(run)
    (run.project / "legacy/compat.py").write_text("changed", encoding="utf-8")
    with pytest.raises(AssertionError, match="Protected code"):
        acceptance.protected_region(run)


def test_mcp_oracle_checks_result_not_just_tool_presence(tmp_path):
    item = {
        "type": "mcp_tool_call",
        "id": "1",
        "status": "completed",
        "server": "catalog",
        "tool": "lookup",
        "arguments": {"project": "pytest-codex"},
        "error": None,
        "result": {"content": [{"type": "text", "text": json.dumps({"mode": "wrong"})}]},
    }

    def make_run():
        return Run(
            [
                {"type": "item.completed", "item": item},
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "id": "2", "text": "offline-first"},
                },
                {"type": "turn.completed"},
            ],
            tmp_path,
        )

    with pytest.raises(AssertionError, match="Wrong MCP result"):
        acceptance.mcp_lookup(make_run())
    item["result"]["content"][0]["text"] = json.dumps(
        {"purpose": "Test Codex behavior with pytest", "mode": "offline-first"}
    )
    acceptance.mcp_lookup(make_run())
    item["result"]["isError"] = True
    with pytest.raises(AssertionError, match="server returned an error"):
        acceptance.mcp_lookup(make_run())
