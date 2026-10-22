"""Intentionally failing, synthetic trace for the README illustration. No model calls."""

from pathlib import Path

from pytest_codex import Run


def test_agent_uses_uv():
    run = Run(
        [
            {
                "type": "item.completed",
                "item": {
                    "id": "command-1",
                    "type": "command_execution",
                    "command": "pip install requests",
                    "exit_code": 0,
                    "aggregated_output": "Successfully installed requests",
                },
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "message-1",
                    "type": "agent_message",
                    "text": "Added requests.",
                },
            },
            {"type": "turn.completed"},
        ],
        Path.cwd(),
    )
    assert run.ran("uv add", ok=True), run
