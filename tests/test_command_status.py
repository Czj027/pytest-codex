import re

from pytest_codex import Run


def test_ran_filters_success_failure_and_incomplete_commands(tmp_path):
    events = []
    for index, (command, code) in enumerate(
        [
            ("uv add good", 0),
            ("uv add bad", 1),
            ("uv add pending", None),
        ]
    ):
        events.append(
            {
                "type": "item.completed",
                "item": {
                    "id": str(index),
                    "type": "command_execution",
                    "command": command,
                    "exit_code": code,
                },
            }
        )
    run = Run(events, tmp_path)
    assert run.ran("uv add", ok=True)
    assert run.ran(re.compile(r"uv add good$"), ok=True)
    assert not run.ran("bad", ok=True)
    assert run.ran("bad", ok=False)
    assert not run.ran("good", ok=False)
    assert not run.ran("pending", ok=False)
    assert not run.ran("pending", ok=True)
    assert run.ran("pending")
    assert run.ran("bad")
