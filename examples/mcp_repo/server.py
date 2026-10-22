"""Minimal read-only stdio MCP example (not a general-purpose server framework)."""

import json
import sys
from pathlib import Path


def respond(message):
    method = message.get("method")
    params = message.get("params") or {}
    if method == "initialize":
        requested = params.get("protocolVersion")
        supported = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
        return {
            "result": {
                "protocolVersion": requested if requested in supported else "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "pytest-codex-catalog", "version": "1.0.0"},
            }
        }
    if method == "ping":
        return {"result": {}}
    if method == "tools/list":
        return {
            "result": {
                "tools": [
                    {
                        "name": "lookup",
                        "description": "Look up a project in the local project catalog.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "project": {"type": "string"},
                            },
                            "required": ["project"],
                            "additionalProperties": False,
                        },
                        "annotations": {"readOnlyHint": True, "idempotentHint": True},
                    }
                ]
            }
        }
    if method == "tools/call":
        arguments = params.get("arguments") or {}
        if params.get("name") != "lookup" or not isinstance(arguments.get("project"), str):
            return {"error": {"code": -32602, "message": "Expected lookup(project: string)"}}
        catalog = json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))
        value = catalog.get(arguments["project"])
        return {
            "result": {
                "content": [{"type": "text", "text": json.dumps(value or {"error": "not found"})}],
                "isError": value is None,
            }
        }
    return {"error": {"code": -32601, "message": "Method not found"}}


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        message = json.loads(line)
        if "id" not in message:
            continue
        reply = {"jsonrpc": "2.0", "id": message["id"], **respond(message)}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    main()
