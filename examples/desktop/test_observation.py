"""Synthetic desktop observation; no user history, engine or login is read."""

import json


def test_desktop_observation(codex, tmp_path):
    path = tmp_path / "synthetic-session.jsonl"
    records = [
        {"type": "session_meta", "payload": {"originator": "codex_work_desktop"}},
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "example"}},
        {
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "turn_id": "example",
                "item": {
                    "type": "CommandExecution",
                    "id": "cmd",
                    "command": ["uv", "add", "requests"],
                    "exit_code": 0,
                    "status": "Completed",
                    "aggregated_output": "Added requests",
                },
            },
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "task_complete",
                "turn_id": "example",
                "last_agent_message": "Dependency added.",
            },
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
    run = codex.from_desktop_session(path, turn_id="example")
    assert run.succeeded
    assert run.ran("uv add", ok=True)
    assert run.commands_complete
    assert not run.ran("pip install")
    assert run.file_state == "unavailable"
