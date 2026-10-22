"""Queryable execution results with a compact pytest failure representation."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from .events import Command, McpCall, build_items, total_usage
from .paths import project_path
from .snapshot import Diff


class Run:
    def __init__(
        self,
        events: list[dict],
        project: Path,
        changes: Diff | None = None,
        returncode: int = 0,
        *,
        stderr: str = "",
        replayed: bool = False,
    ):
        self.events = events
        self.project = Path(project)
        self.diff = changes if changes is not None else Diff()
        self.returncode = returncode
        self.stderr = stderr
        self.replayed = replayed
        self.items = build_items(events)
        self.commands = [item for item in self.items if isinstance(item, Command)]
        self.mcp_calls = [item for item in self.items if isinstance(item, McpCall)]
        self.messages = [
            item.raw.get("text", "") for item in self.items if item.type == "agent_message"
        ]
        self.usage = total_usage(events)
        self.tokens = self.usage

    @property
    def final_message(self) -> str:
        return self.messages[-1] if self.messages else ""

    @property
    def succeeded(self) -> bool:
        types = {event.get("type") for event in self.events}
        return self.returncode == 0 and "turn.completed" in types and "turn.failed" not in types

    @property
    def changed_files(self) -> list[str]:
        return self.diff.changed

    def ran(self, pattern: str | re.Pattern) -> bool:
        return any(
            pattern in cmd.command
            if isinstance(pattern, str)
            else pattern.search(cmd.command) is not None
            for cmd in self.commands
        )

    def modified(self, pattern: str) -> bool:
        return any(fnmatch.fnmatchcase(path, pattern) for path in self.diff.modified)

    def added(self, pattern: str) -> bool:
        return any(fnmatch.fnmatchcase(path, pattern) for path in self.diff.added)

    def deleted(self, pattern: str) -> bool:
        return any(fnmatch.fnmatchcase(path, pattern) for path in self.diff.deleted)

    def called_mcp(self, server: str, tool: str | None = None) -> bool:
        return any(
            call.server == server and (tool is None or call.tool == tool) for call in self.mcp_calls
        )

    def read(self, path: str) -> str:
        return project_path(self.project, path).read_text(encoding="utf-8")

    def __repr__(self) -> str:
        commands = (
            "\n".join(f"  [{cmd.exit_code}] {cmd.command[:240]}" for cmd in self.commands[-12:])
            or "  (no commands)"
        )
        return (
            f"<Run succeeded={self.succeeded} replayed={self.replayed} "
            f"tokens={self.tokens.total}>\n{commands}\n"
            f"  changed: {', '.join(self.changed_files[:20]) or '(none)'}\n"
            f"  final: {self.final_message[:400]}"
        )
