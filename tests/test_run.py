import re

import pytest

from pytest_codex.run import Run
from pytest_codex.snapshot import Diff


def trace(command="uv add requests"):
    return [
        {
            "type": "item.started",
            "item": {"id": "c", "type": "command_execution", "command": command},
        },
        {
            "type": "item.completed",
            "item": {"id": "c", "type": "command_execution", "command": command, "exit_code": 0},
        },
        {
            "type": "item.completed",
            "item": {"id": "w", "type": "error", "message": "config warning"},
        },
        {"type": "item.completed", "item": {"id": "m", "type": "agent_message", "text": "DONE"}},
        {
            "type": "item.completed",
            "item": {
                "id": "t",
                "type": "mcp_tool_call",
                "server": "demo",
                "tool": "lookup",
                "arguments": {},
            },
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 12, "cached_input_tokens": 4, "output_tokens": 3},
        },
    ]


def test_trace_queries_and_failure_summary(tmp_path):
    (tmp_path / "out.txt").write_text("hello", encoding="utf-8")
    run = Run(
        trace('bash -lc "uv add requests"'),
        tmp_path,
        Diff(["out.txt"], ["pyproject.toml"], ["old.txt"]),
    )
    assert len(run.commands) == 1
    assert run.ran("uv add") and run.ran(re.compile(r"uv add \w+"))
    assert not run.ran("pip install")
    assert run.added("*.txt") and run.modified("pyproject.*") and run.deleted("old.*")
    assert run.changed_files == ["old.txt", "out.txt", "pyproject.toml"]
    assert run.messages == ["DONE"] and run.final_message == "DONE"
    assert run.called_mcp("demo") and run.called_mcp("demo", "lookup")
    assert not run.called_mcp("demo", "missing")
    assert run.tokens.total == 15 and run.usage.cached_input_tokens == 4
    assert run.read("out.txt") == "hello"
    assert run.succeeded
    assert "uv add requests" in repr(run) and "pyproject.toml" in repr(run)


@pytest.mark.parametrize(
    "events,code", [([], 0), (trace(), 1), (trace() + [{"type": "turn.failed"}], 0)]
)
def test_success_requires_completion_without_failure(tmp_path, events, code):
    assert not Run(events, tmp_path, returncode=code).succeeded


@pytest.mark.parametrize("path", ["../secret", "C:/outside.txt", "/outside", "..\\outside"])
def test_read_cannot_escape_project(tmp_path, path):
    with pytest.raises(ValueError, match="relative|outside"):
        Run([], tmp_path).read(path)
