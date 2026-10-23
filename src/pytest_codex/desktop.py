"""Explicit, read-only import of local Codex Desktop observations.

This is an event-only format, deliberately separate from executable-test cassettes.
Imports do not discover history, invoke processes/models or restore project files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
from pathlib import Path

from .events import Usage
from .run import Run

SCHEMA = "pytest-codex-desktop-observation-v1"


class DesktopSessionError(ValueError):
    """The session cannot support the requested historical assertion."""


def _portable(value, cwd=""):
    if isinstance(value, str):
        for location, replacement in ((cwd, "<PROJECT>"), (str(Path.home()), "<HOME>")):
            if location:
                for variant in (
                    location.replace("\\", "\\\\"),
                    location,
                    location.replace("\\", "/"),
                ):
                    value = value.replace(variant, replacement)
        return re.sub(
            r"(?:pypi-|sk-(?:proj-)?|ghp_|github_pat_)[A-Za-z0-9_-]{20,}",
            "<REDACTED>",
            value,
        )
    if isinstance(value, list):
        return [_portable(v, cwd) for v in value]
    if isinstance(value, dict):
        return {
            _portable(str(k), cwd): (
                "<REDACTED>"
                if str(k).lower()
                in {
                    "access_token",
                    "refresh_token",
                    "id_token",
                    "api_key",
                    "password",
                    "authorization",
                }
                else _portable(v, cwd)
            )
            for k, v in value.items()
        }
    return value


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            v["text"] for v in content if isinstance(v, dict) and isinstance(v.get("text"), str)
        )
    raise DesktopSessionError("Unsupported agent message content")


def _item(raw):
    kind = raw.get("type")
    base = {"id": str(raw.get("id", "")), "status": str(raw.get("status", "completed")).lower()}
    if kind == "CommandExecution":
        command = raw.get("command")
        if isinstance(command, list) and command and all(isinstance(v, str) for v in command):
            # Keep shell bodies intact, including multiline PowerShell commands.
            if len(command) >= 3 and command[-2].lower() in {"-lc", "-c", "-command"}:
                command = command[-1]
            else:
                command = shlex.join(command)
        if not isinstance(command, str) or not command:
            raise DesktopSessionError("Unsupported command shape")
        exit_code = raw.get("exit_code")
        if exit_code is not None and (
            isinstance(exit_code, bool) or not isinstance(exit_code, int)
        ):
            raise DesktopSessionError("Unsupported command exit status")
        if not isinstance(raw.get("aggregated_output", ""), str):
            raise DesktopSessionError("Unsupported command output shape")
        return {
            **base,
            "type": "command_execution",
            "command": command,
            "exit_code": exit_code,
            "aggregated_output": raw.get("aggregated_output") or "",
        }
    if kind == "McpToolCall":
        if not all(isinstance(raw.get(k), str) for k in ("server", "tool")):
            raise DesktopSessionError("Unsupported MCP call shape")
        return {
            **base,
            "type": "mcp_tool_call",
            **{k: raw.get(k) for k in ("server", "tool", "arguments", "result", "error")},
        }
    if kind == "AgentMessage":
        return {**base, "type": "agent_message", "text": _text(raw.get("content", []))}
    return None


class DesktopRun(Run):
    """Historical observation; file bytes/diff and task acceptance are unavailable."""

    file_state = "unavailable"

    def __init__(
        self,
        events,
        *,
        turn_id,
        status,
        source_sha256,
        reported_changed_files=(),
        unsupported_items=(),
        usage_complete=False,
        cli_version="",
        model=None,
    ):
        super().__init__(
            events, Path("."), returncode=0 if status == "completed" else 1, replayed=True
        )
        self.project = None
        self.diff = None
        self.turn_id = turn_id
        self.status = status
        self.source_sha256 = source_sha256
        self.reported_changed_files = sorted(set(reported_changed_files))
        self.unsupported_items = sorted(set(unsupported_items))
        self.commands_complete = (
            status == "completed"
            and not self.unsupported_items
            and all(
                item.status in {"completed", "failed", "declined", "cancelled", "canceled"}
                for item in [*self.commands, *self.mcp_calls]
            )
        )
        self.usage_complete = usage_complete
        if status != "completed":
            self.usage = self.tokens = Usage(**events[-1].get("usage", {}))
        self.cli_version = cli_version
        self.model = model

    @property
    def changed_files(self):
        raise DesktopSessionError("Imported observations have no verified file state")

    def read(self, path):
        raise DesktopSessionError("Imported observations have no verified file state")

    modified = added = deleted = read

    def ran(self, pattern, *, ok=None):
        matched = super().ran(pattern, ok=ok)
        if not matched and not self.commands_complete:
            raise DesktopSessionError("Command coverage is incomplete; cannot assert absence")
        return matched

    def called_mcp(self, server, tool=None):
        matched = super().called_mcp(server, tool)
        if not matched and not self.commands_complete:
            raise DesktopSessionError("MCP coverage is incomplete; cannot assert absence")
        return matched

    def save(self, path, *, include_content=False):
        """Opt in to writing commands/results/final text; review before sharing."""
        if not include_content:
            raise DesktopSessionError(
                "Export contains private text: pass include_content=True after review"
            )
        payload = {
            "schema": SCHEMA,
            "file_state": "unavailable",
            "events": self.events,
            **{
                name: getattr(self, name)
                for name in (
                    "turn_id",
                    "status",
                    "source_sha256",
                    "reported_changed_files",
                    "unsupported_items",
                    "usage_complete",
                    "cli_version",
                    "model",
                )
            },
        }
        with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(_portable(payload), stream, ensure_ascii=False, indent=2)
            stream.write("\n")

    def __repr__(self):
        return f"<DesktopRun status={self.status} historical=True file_state=unavailable commands={len(self.commands)} usage_complete={self.usage_complete}>"


def _records(path):
    digest = hashlib.sha256()
    if Path(path).stat().st_size > 256 * 1024 * 1024:
        raise DesktopSessionError("Session exceeds the 256 MiB import limit")
    with Path(path).open("rb") as stream:
        for number, line in enumerate(stream, 1):
            digest.update(line)
            if not line.strip():
                continue
            try:
                record = json.loads(line.decode("utf-8-sig"))
                if not isinstance(record, dict) or not isinstance(record.get("payload"), dict):
                    raise TypeError
                if not isinstance(record.get("type"), str) or not isinstance(
                    record["payload"].get("type", ""), str
                ):
                    raise TypeError
            except (ValueError, TypeError, UnicodeError):
                raise DesktopSessionError(f"Invalid session record at line {number}") from None
            yield record
    return digest.hexdigest()


def _read_session(path):
    turns = {}
    current = None
    meta = None
    records = _records(path)
    while True:
        try:
            record = next(records)
        except StopIteration as stop:
            source_sha256 = stop.value
            break
        kind, payload = record.get("type"), record["payload"]
        typ = payload.get("type")
        if kind == "session_meta":
            if meta is not None or turns:
                raise DesktopSessionError("Invalid or duplicate session metadata")
            if not all(isinstance(payload.get(k, ""), str) for k in ("cwd", "cli_version")):
                raise DesktopSessionError("Unsupported session metadata shape")
            meta = payload
        elif kind == "event_msg" and typ == "task_started":
            turn_id = payload.get("turn_id")
            if meta is None or not isinstance(turn_id, str) or not turn_id:
                raise DesktopSessionError("Session metadata and explicit turn IDs are required")
            if turn_id in turns:
                raise DesktopSessionError("Duplicate turn start; unsupported session structure")
            current = turn_id
            turns[current] = {
                "started_at": record.get("timestamp") or payload.get("started_at"),
                "items": [],
                "pending": {},
                "unsupported": [],
                "files": [],
                "status": "incomplete",
                "usage": None,
                "model": None,
                "final": "",
            }
        else:
            attributed = payload.get("turn_id", current)
            if not isinstance(attributed, str) or attributed not in turns:
                continue
            turn = turns[attributed]
            if kind == "turn_context":
                if payload.get("model") is not None and not isinstance(payload["model"], str):
                    raise DesktopSessionError("Unsupported model metadata shape")
                turn["model"] = payload.get("model")
            elif kind == "token_usage_record":
                usage = payload.get("turn_token_usage")
                turn["usage"] = None
                if isinstance(usage, dict):
                    if not {"input_tokens", "cached_input_tokens", "output_tokens"}.issubset(usage):
                        continue
                    for name in (
                        "input_tokens",
                        "cached_input_tokens",
                        "output_tokens",
                        "reasoning_output_tokens",
                    ):
                        if (
                            isinstance(usage.get(name, 0), bool)
                            or not isinstance(usage.get(name, 0), int)
                            or usage.get(name, 0) < 0
                        ):
                            raise DesktopSessionError("Unsupported turn usage shape")
                    turn["usage"] = {
                        name: usage.get(name, 0)
                        for name in (
                            "input_tokens",
                            "cached_input_tokens",
                            "output_tokens",
                            "reasoning_output_tokens",
                        )
                    }
            elif kind == "event_msg" and typ in {"item_started", "item_updated", "item_completed"}:
                raw = payload.get("item")
                if not isinstance(raw, dict):
                    raise DesktopSessionError("Unsupported completed item shape")
                item_id = str(raw.get("id") or "anonymous")
                if typ != "item_completed":
                    if raw.get("type") not in {
                        "UserMessage",
                        "Reasoning",
                        "ContextCompaction",
                        "AgentMessage",
                    }:
                        turn["pending"][item_id] = str(raw.get("type", "unknown"))
                        if raw.get("type") in {"CommandExecution", "McpToolCall"}:
                            item = _item({**raw, "status": "in_progress", "exit_code": None})
                            turn["items"].append(item)
                    continue
                turn["pending"].pop(item_id, None)
                item = _item(raw)
                if item:
                    turn["items"].append(item)
                elif raw.get("type") == "FileChange":
                    changes = raw.get("changes")
                    if not isinstance(changes, dict):
                        raise DesktopSessionError("Unsupported reported file-change shape")
                    turn["files"].extend(changes)
                elif raw.get("type") not in {"UserMessage", "Reasoning", "ContextCompaction"}:
                    turn["unsupported"].append(str(raw.get("type", "unknown")))
            elif kind == "response_item" and typ in {"function_call", "custom_tool_call"}:
                # Opaque code-mode calls may contain arbitrary subprocesses. Do not
                # pretend canonical command items prove that none were omitted.
                turn["unsupported"].append("opaque_tool:" + str(payload.get("name", "unknown")))
            elif kind == "event_msg" and typ in {"task_complete", "turn_aborted"}:
                if turn["status"] != "incomplete":
                    raise DesktopSessionError("Duplicate or conflicting terminal event")
                turn["status"] = "completed" if typ == "task_complete" else "aborted"
                if typ == "task_complete":
                    if payload.get("last_agent_message") is not None and not isinstance(
                        payload["last_agent_message"], str
                    ):
                        raise DesktopSessionError("Unsupported final message shape")
                    turn["final"] = payload.get("last_agent_message") or ""
                if attributed == current:
                    current = None
    if meta is None or not turns:
        raise DesktopSessionError(
            "No supported desktop turns found; expected session metadata and task_started events"
        )
    return meta, turns, source_sha256


def list_desktop_turns(path):
    """Read only one explicitly supplied file; return identifiers/status, not prompts."""
    _, turns, _ = _read_session(path)
    return [
        {"turn_id": key, "status": value["status"], "model": value["model"]}
        for key, value in turns.items()
    ]


def _load_observation(path, turn_id):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA or data.get("file_state") != "unavailable":
            raise ValueError
        if data["status"] not in {"completed", "incomplete", "aborted"} or not isinstance(
            data["turn_id"], str
        ):
            raise ValueError
        if not re.fullmatch(r"[a-f0-9]{64}", data["source_sha256"]):
            raise ValueError
        if not isinstance(data["events"], list) or not all(
            isinstance(e, dict) for e in data["events"]
        ):
            raise ValueError
        if not data["events"]:
            raise ValueError
        for event in data["events"]:
            if event.get("type") in {"item.completed", "item.started"}:
                if set(event) != {"type", "item"} or not isinstance(event["item"], dict):
                    raise ValueError
                item = event["item"]
                allowed = {
                    "command_execution": {
                        "id",
                        "type",
                        "status",
                        "command",
                        "exit_code",
                        "aggregated_output",
                    },
                    "mcp_tool_call": {
                        "id",
                        "type",
                        "status",
                        "server",
                        "tool",
                        "arguments",
                        "result",
                        "error",
                    },
                    "agent_message": {"id", "type", "status", "text"},
                }.get(item.get("type"))
                if allowed is None or set(item) - allowed:
                    raise ValueError
                if not all(isinstance(item.get(k), str) for k in ("id", "status")):
                    raise TypeError
                if item["type"] == "command_execution":
                    if not isinstance(item.get("command"), str) or not item["command"]:
                        raise TypeError
                    code = item.get("exit_code")
                    if code is not None and (isinstance(code, bool) or not isinstance(code, int)):
                        raise TypeError
                    if not isinstance(item.get("aggregated_output"), str):
                        raise TypeError
                elif item["type"] == "mcp_tool_call":
                    if not all(isinstance(item.get(k), str) for k in ("server", "tool")):
                        raise TypeError
                elif not isinstance(item.get("text"), str):
                    raise TypeError
            elif event.get("type") in {"turn.completed", "turn.failed"}:
                if event is not data["events"][-1] or set(event) - {"type", "usage", "error"}:
                    raise ValueError
                usage = event.get("usage", {})
                if not isinstance(usage, dict) or set(usage) - {
                    "input_tokens",
                    "cached_input_tokens",
                    "output_tokens",
                    "reasoning_output_tokens",
                }:
                    raise ValueError
                if any(
                    isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in usage.values()
                ):
                    raise ValueError
            else:
                raise ValueError
        expected_terminal = "turn.completed" if data["status"] == "completed" else "turn.failed"
        if data["events"][-1].get("type") != expected_terminal:
            raise ValueError
        for name in ("reported_changed_files", "unsupported_items"):
            if not isinstance(data[name], list) or not all(isinstance(v, str) for v in data[name]):
                raise ValueError
        if not isinstance(data["usage_complete"], bool):
            raise TypeError
        observed_usage = data["events"][-1].get("usage", {})
        if data["usage_complete"] != bool(observed_usage):
            raise ValueError
        if data["usage_complete"] and not {
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
        }.issubset(observed_usage):
            raise ValueError
        if not isinstance(data.get("cli_version"), str) or (
            data.get("model") is not None and not isinstance(data["model"], str)
        ):
            raise TypeError
        if turn_id is not None and data["turn_id"] != turn_id:
            raise DesktopSessionError("Requested turn_id not found")
        return DesktopRun(
            _portable(data["events"]),
            **{
                name: data.get(name)
                for name in (
                    "turn_id",
                    "status",
                    "source_sha256",
                    "reported_changed_files",
                    "unsupported_items",
                    "usage_complete",
                    "cli_version",
                    "model",
                )
            },
        )
    except (ValueError, KeyError, TypeError, AttributeError):
        raise DesktopSessionError("Invalid or incompatible desktop observation") from None


def from_desktop_session(path, *, turn_id=None):
    """Load a selected historical desktop turn or an explicit event-only export."""
    if Path(path).suffix.lower() == ".json":
        return _load_observation(path, turn_id)
    meta, turns, source_sha256 = _read_session(path)
    if turn_id is None:
        if len(turns) != 1:
            raise DesktopSessionError(
                "Multiple turns: select an explicit turn_id using list_desktop_turns"
            )
        turn_id = next(iter(turns))
    if turn_id not in turns:
        raise DesktopSessionError("Requested turn_id not found")
    return _run_from_turn(meta, turns[turn_id], source_sha256, turn_id)


def _run_from_turn(meta, turn, source_sha256, turn_id):
    """Shared normalizer so a local panel can parse each selected session once."""
    items = turn["items"]
    if turn["final"]:
        items = [
            *items,
            {
                "id": "desktop-final",
                "type": "agent_message",
                "text": turn["final"],
                "status": "completed",
            },
        ]
    events = [
        {
            "type": "item.started" if item.get("status") == "in_progress" else "item.completed",
            "item": item,
        }
        for item in items
    ]
    if turn["status"] == "completed":
        events.append({"type": "turn.completed", "usage": turn["usage"] or {}})
    else:
        events.append(
            {
                "type": "turn.failed",
                "error": {"message": turn["status"]},
                "usage": turn["usage"] or {},
            }
        )
    return DesktopRun(
        _portable(events, meta.get("cwd", "")),
        turn_id=turn_id,
        status=turn["status"],
        source_sha256=source_sha256,
        reported_changed_files=_portable(turn["files"], meta.get("cwd", "")),
        unsupported_items=[
            *turn["unsupported"],
            *("unfinished:" + name for name in turn["pending"].values()),
        ],
        usage_complete=turn["usage"] is not None,
        cli_version=meta.get("cli_version", ""),
        model=turn["model"],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser(
        "list", help="list turn IDs/status from one explicit session file"
    )
    listing.add_argument("session")
    importing = commands.add_parser(
        "import-session", help="export event-only observation; review content before sharing"
    )
    importing.add_argument("session")
    importing.add_argument("--turn-id")
    importing.add_argument("--output", required=True)
    importing.add_argument(
        "--include-content",
        action="store_true",
        help="acknowledge commands, results and final text may be private",
    )
    commands.add_parser(
        "engine", help="show the detected bundled binary and --version; no model call"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            print(json.dumps(list_desktop_turns(args.session), ensure_ascii=False))
        elif args.command == "import-session":
            run = from_desktop_session(args.session, turn_id=args.turn_id)
            run.save(args.output, include_content=args.include_content)
            print("Saved historical event-only observation; review before sharing.")
        else:
            from .desktop_engine import find_desktop_binary
            from .runner import cli_version

            binary = find_desktop_binary()
            print(json.dumps({"binary": binary, "version": cli_version(binary)}))
    except (OSError, DesktopSessionError):
        parser.exit(
            2,
            "Cannot import desktop session: check format, turn selection, output path and content opt-in.\n",
        )


if __name__ == "__main__":
    main()
