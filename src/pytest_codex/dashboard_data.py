"""Bounded, read-only project history and deterministic rule checks for the panel."""

from __future__ import annotations

import fnmatch
import hashlib
import heapq
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .desktop import _portable, _read_session, _run_from_turn


def _linked(path):
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)
    except OSError:
        return True


def _candidates(root):
    for folder, directories, names in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if not _linked(Path(folder) / name)]
        for name in names:
            if not name.startswith("rollout-") or not name.endswith(".jsonl"):
                continue
            path = Path(folder) / name
            if _linked(path):
                continue
            try:
                resolved = path.resolve()
                if resolved.is_relative_to(root):
                    yield resolved.stat().st_mtime, resolved
            except OSError:
                continue


def _time(value, fallback):
    try:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError
            return parsed.timestamp(), parsed.isoformat()
        if type(value) in (int, float):
            seconds = value / 1000 if value > 100_000_000_000 else value
            parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
            return parsed.timestamp(), parsed.isoformat()
    except (ValueError, OSError, OverflowError):
        pass
    return fallback, None


def _summary(run):
    usage = None
    if run.usage_complete and run.tokens.cached_input_tokens <= run.tokens.input_tokens:
        usage = {
            "input": run.tokens.input_tokens,
            "cached": run.tokens.cached_input_tokens,
            "uncached": run.tokens.input_tokens - run.tokens.cached_input_tokens,
            "output": run.tokens.output_tokens,
        }
    files = []
    for name in run.reported_changed_files:
        name = name.replace("\\", "/")
        files.append(name.removeprefix("<PROJECT>/"))
    limited = (
        len(run.commands) > 100
        or any(len(c.command) > 2000 for c in run.commands)
        or len(files) > 500
        or len(run.mcp_calls) > 100
        or any(len(name) > 1000 for name in files)
        or len(run.unsupported_items) > 100
        or any(len(name) > 256 for name in run.unsupported_items)
        or len(run.turn_id) > 256
        or any(len(c.server) > 256 or len(c.tool) > 256 for c in run.mcp_calls)
    )
    return {
        "id": hashlib.sha256((run.source_sha256 + run.turn_id).encode()).hexdigest()[:20],
        "turn_id": run.turn_id[:256],
        "status": run.status,
        "model": run.model[:256] if run.model else None,
        "commands": [
            {"command": c.command[:2000], "exit_code": c.exit_code} for c in run.commands[:100]
        ],
        "commands_complete": run.commands_complete and not limited,
        "display_limited": limited,
        "unsupported_items": [name[:256] for name in run.unsupported_items[:100]],
        "files": [name[:1000] for name in files[:500]],
        "files_verified": False,
        "usage": usage,
        "mcp": [
            {"server": c.server[:256], "tool": c.tool[:256], "status": c.status[:128]}
            for c in run.mcp_calls[:100]
        ],
    }


def recent_tasks(sessions, project, *, limit=20, scan_limit=500):
    """An explicit panel launch opts into this project-scoped metadata scan."""
    if (
        type(limit) is not int
        or not 1 <= limit <= 100
        or type(scan_limit) is not int
        or not 1 <= scan_limit <= 5000
    ):
        raise ValueError("Use 1-100 tasks and 1-5000 candidate logs")
    root, project = Path(sessions).resolve(), Path(project).resolve()
    if not project.is_dir():
        raise ValueError("Select an existing project directory")
    result = {
        "tasks": [],
        "errors": [],
        "scanned": 0,
        "matching_sessions": 0,
        "scan_limited": False,
        "task_limited": False,
    }
    if not root.is_dir():
        result["errors"].append({"reason": "会话目录不存在或不可读"})
        return result
    candidates = heapq.nlargest(scan_limit + 1, _candidates(root), key=lambda v: (v[0], str(v[1])))
    result["scan_limited"] = len(candidates) > scan_limit
    tasks = []
    observed = 0
    for modified, path in candidates[:scan_limit]:
        result["scanned"] += 1
        try:
            with path.open("rb") as stream:
                header = stream.readline(2 * 1024 * 1024)
            first = json.loads(header.decode("utf-8-sig"))
            metadata = first.get("payload", {})
            if first.get("type") != "session_meta" or not isinstance(metadata, dict):
                raise ValueError
            cwd = metadata.get("cwd")
            if not isinstance(cwd, str) or Path(cwd).resolve() != project:
                continue
            result["matching_sessions"] += 1
            meta, turns, sha = _read_session(path)
            for turn_id, turn in turns.items():
                sort, timestamp = _time(turn.get("started_at"), modified)
                observed += 1
                key = sort, modified, observed
                if len(tasks) >= limit and key <= tasks[0][:3]:
                    continue
                row = _summary(_run_from_turn(meta, turn, sha, turn_id))
                row["started_at"] = timestamp
                heapq.heappush(tasks, (*key, row))
                if len(tasks) > limit:
                    heapq.heappop(tasks)
        except (OSError, ValueError, TypeError, AttributeError):
            result["errors"].append({"reason": "一个日志不完整、不可读或格式不兼容；未计为通过"})
    tasks.sort(key=lambda t: t[:3], reverse=True)
    result["task_limited"] = observed > limit
    result["tasks"] = [t[3] for t in tasks[:limit]]
    return result


def read_agents(project):
    project = Path(project).resolve()
    path = project / "AGENTS.md"
    if _linked(path) or not path.is_file():
        return {"text": "", "state": "missing", "truncated": False}
    try:
        with path.open("rb") as stream:
            raw = stream.read(64 * 1024 + 1)
        text = raw[: 64 * 1024].decode("utf-8-sig").replace("\r\n", "\n")
        return {
            "text": _portable(text, str(project)),
            "state": "available",
            "truncated": len(raw) > 64 * 1024,
        }
    except (OSError, UnicodeError):
        return {"text": "", "state": "unreadable", "truncated": False}


def suggest_rules(text):
    """Only explicit prohibition fragments are candidates; user confirms them."""
    found = {"commands": [], "files": []}
    for kind, verbs, chinese in (
        ("commands", "run|execute|use", "运行|执行|使用"),
        ("files", "modify|edit|touch|write|delete", "修改|改动|写入|删除"),
    ):
        expression = rf"(?:\b(?:never|do not|don't)\s+(?:{verbs})\s+|(?:禁止|不要|不得)(?:{chinese})\s*)`([^`\n]{{1,256}})`"
        found[kind].extend(re.findall(expression, text, re.IGNORECASE))
    return {kind: list(dict.fromkeys(values))[:100] for kind, values in found.items()}


def validate_rules(rules):
    if not isinstance(rules, dict) or set(rules) != {"commands", "files"}:
        raise ValueError("Rules need commands and files lists")
    for values in rules.values():
        if (
            not isinstance(values, list)
            or len(values) > 100
            or any(not isinstance(v, str) or not v.strip() or len(v) > 256 for v in values)
        ):
            raise ValueError("Each rule must be 1-256 characters; at most 100 of each kind")
    return {key: list(dict.fromkeys(v.strip() for v in values)) for key, values in rules.items()}


def evaluate_rules(task, rules):
    rules = validate_rules(rules)
    hits = []
    for pattern in rules["commands"]:
        needle = " ".join(pattern.split()).casefold()
        for command in task["commands"]:
            if needle in " ".join(command["command"].split()).casefold():
                hits.append({"kind": "command", "rule": pattern, "value": command["command"]})
    for pattern in rules["files"]:
        for path in task["files"]:
            if fnmatch.fnmatchcase(path, pattern.replace("\\", "/")):
                hits.append({"kind": "reported_file", "rule": pattern, "value": path})
    status = (
        "fail"
        if hits
        else "pass"
        if rules["commands"] and not rules["files"] and task["commands_complete"]
        else "unknown"
    )
    return {
        "status": status,
        "hits": hits,
        "reason": "已观察到命中"
        if hits
        else "已配置命令规则未命中，且命令记录完整"
        if status == "pass"
        else "未配置规则或证据不完整；文件记录不能证明没有改动",
    }
