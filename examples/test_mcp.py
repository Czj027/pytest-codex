"""A real local stdio MCP server, with no MCP SDK dependency or network service."""

import json
from pathlib import Path

import pytest


@pytest.mark.codex(project=str(Path(__file__).parent / "mcp_repo"))
def test_agent_queries_catalog(codex):
    run = codex.exec(
        "Look up pytest-codex in the project catalog and state its mode.",
        model="gpt-6-luna",
        config={
            "model_reasoning_effort": "low",
            "mcp_servers.catalog.command": "python",
            "mcp_servers.catalog.args": ["server.py"],
        },
    )
    assert run.succeeded, run
    assert run.called_mcp("catalog", "lookup"), run
    call = next(call for call in run.mcp_calls if call.server == "catalog")
    assert call.arguments == {"project": "pytest-codex"}, run
    assert call.error is None and call.result is not None, run
    assert call.status == "completed", run
    assert json.loads(call.result["content"][0]["text"]) == {
        "purpose": "Test Codex behavior with pytest",
        "mode": "offline-first",
    }, run
    assert "offline-first" in run.final_message, run
    assert not run.commands and not run.changed_files, run
