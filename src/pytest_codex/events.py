"""Parse the JSONL event stream produced by ``codex exec --json``.

Observed event shapes (codex-cli 0.163)::

    {"type": "thread.started", "thread_id": "..."}
    {"type": "turn.started"}
    {"type": "item.started" | "item.updated" | "item.completed", "item": {...}}
    {"type": "turn.completed", "usage": {"input_tokens": ..., "output_tokens": ...}}
    {"type": "turn.failed", "error": {"message": "..."}}
    {"type": "error", "message": "..."}

Item types include ``agent_message``, ``reasoning``, ``command_execution``,
``file_change``, ``mcp_tool_call``, ``web_search``, ``todo_list`` and ``error``.
Unknown types are kept as raw dicts so new Codex versions don't break parsing.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Command",
    "FileChange",
    "Item",
    "McpCall",
    "Usage",
    "parse_jsonl",
    "unwrap_shell",
]


# --------------------------------------------------------------------------- items


@dataclass
class Item:
    id: str
    type: str
    status: str | None
    raw: dict[str, Any] = field(repr=False)


@dataclass
class Command(Item):
    command: str = ""
    """The command as the agent intended it (shell wrapper removed)."""
    raw_command: str = ""
    """The exact command line Codex executed, including any shell wrapper."""
    output: str = field(default="", repr=False)
    exit_code: int | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass
class FileChange(Item):
    changes: list[dict[str, str]] = field(default_factory=list)
    """``[{"path": ..., "kind": "add" | "update" | "delete"}]``"""


@dataclass
class McpCall(Item):
    server: str = ""
    tool: str = ""
    arguments: Any = None
    result: Any = field(default=None, repr=False)
    error: Any = None


@dataclass
class Usage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.cached_input_tokens + other.cached_input_tokens,
            self.output_tokens + other.output_tokens,
            self.reasoning_output_tokens + other.reasoning_output_tokens,
        )


# --------------------------------------------------------------------- shell unwrap

_PWSH = re.compile(
    r"""^\s*"?[^"]*?(?:pwsh|powershell)(?:\.exe)?"?\s+(?:-\w+\s+)*?-(?:Command|c)\s+(?P<q>["']?)(?P<body>.*)(?P=q)\s*$""",
    re.IGNORECASE | re.DOTALL,
)
_POSIX = re.compile(
    r"""^\s*(?:/usr)?(?:/bin/)?(?:bash|sh|zsh)\s+-l?c\s+(?P<q>["'])(?P<body>.*)(?P=q)\s*$""",
    re.DOTALL,
)
_CMD = re.compile(r"""^\s*"?[^"]*?cmd(?:\.exe)?"?\s+/[cC]\s+(?P<body>.*)$""", re.DOTALL)


def unwrap_shell(command: str) -> str:
    """Strip the ``bash -lc '...'`` / ``pwsh -Command "..."`` wrapper Codex adds."""
    for pattern in (_PWSH, _POSIX):
        m = pattern.match(command)
        if m:
            body = m.group("body")
            q = m.group("q")
            if q == '"':
                body = body.replace('\\"', '"')
            elif q == "'":
                body = body.replace("'\\''", "'")
            return body.strip()
    m = _CMD.match(command)
    if m:
        return m.group("body").strip()
    return command.strip()


# -------------------------------------------------------------------------- parsing


def _make_item(raw: dict[str, Any]) -> Item:
    t = raw.get("type", "")
    base = {"id": str(raw.get("id", "")), "type": t, "status": raw.get("status"), "raw": raw}
    if t == "command_execution":
        cmd = raw.get("command") or ""
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        return Command(
            **base,
            command=unwrap_shell(cmd),
            raw_command=cmd,
            output=raw.get("aggregated_output") or "",
            exit_code=raw.get("exit_code"),
        )
    if t == "file_change":
        return FileChange(**base, changes=list(raw.get("changes") or []))
    if t == "mcp_tool_call":
        return McpCall(
            **base,
            server=raw.get("server", ""),
            tool=raw.get("tool", ""),
            arguments=raw.get("arguments"),
            result=raw.get("result"),
            error=raw.get("error"),
        )
    return Item(**base)


def parse_jsonl(lines: Iterable[str] | str) -> list[dict[str, Any]]:
    """Parse JSONL text into event dicts, skipping blank / non-JSON lines."""
    if isinstance(lines, str):
        lines = lines.splitlines()
    events = []
    for line in lines:
        line = line.strip().lstrip("\ufeff")
        if not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def build_items(events: list[dict[str, Any]]) -> list[Item]:
    """Collapse started/updated/completed events into one final Item per id, in order."""
    order: list[str] = []
    latest: dict[str, dict[str, Any]] = {}
    for i, ev in enumerate(events):
        if not str(ev.get("type", "")).startswith("item."):
            continue
        raw = ev.get("item") or {}
        key = str(raw.get("id") or f"__anon_{i}")
        if key not in latest:
            order.append(key)
        latest[key] = raw
    return [_make_item(latest[k]) for k in order]


def total_usage(events: list[dict[str, Any]]) -> Usage:
    usage = Usage()
    for ev in events:
        if ev.get("type") == "turn.completed" and isinstance(ev.get("usage"), dict):
            u = ev["usage"]
            usage = usage + Usage(
                int(u.get("input_tokens") or 0),
                int(u.get("cached_input_tokens") or 0),
                int(u.get("output_tokens") or 0),
                int(u.get("reasoning_output_tokens") or 0),
            )
    return usage
