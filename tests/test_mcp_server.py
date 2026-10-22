import json
import subprocess
import sys
from pathlib import Path


def test_stdio_server_initializes_lists_and_calls_tools():
    project = Path(__file__).resolve().parents[1] / "examples" / "mcp_repo"
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "lookup",
                "arguments": {"project": "pytest-codex"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "lookup",
                "arguments": {"project": "missing"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "missing",
                "arguments": {},
            },
        },
    ]
    result = subprocess.run(
        [sys.executable, str(project / "server.py")],
        cwd=project,
        input="".join(json.dumps(message) + "\n" for message in messages),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=10,
        check=True,
    )
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert [reply["id"] for reply in responses] == [1, 2, 3, 4, 5]
    assert responses[0]["result"]["capabilities"] == {"tools": {}}
    assert responses[1]["result"]["tools"][0]["name"] == "lookup"
    assert json.loads(responses[2]["result"]["content"][0]["text"])["mode"] == "offline-first"
    assert responses[3]["result"]["isError"] is True
    assert responses[4]["error"]["code"] == -32602
