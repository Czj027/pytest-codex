import json
import os

import pytest

from pytest_codex.dashboard_data import evaluate_rules, read_agents, recent_tasks, suggest_rules


def session(
    path,
    project,
    *,
    turn="one",
    command="uv add requests",
    complete=True,
    unknown=False,
    usage=True,
    timestamp="2026-01-01T12:00:00Z",
):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "type": "session_meta",
            "payload": {"cwd": str(project), "base_instructions": "PRIVATE INSTRUCTIONS"},
        },
        {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {"type": "task_started", "turn_id": turn},
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "turn_id": turn,
                "item": {
                    "type": "CommandExecution",
                    "id": "cmd",
                    "command": command,
                    "exit_code": 0,
                    "status": "Completed",
                    "aggregated_output": "private output omitted from panel",
                },
            },
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "turn_id": turn,
                "item": {
                    "type": "FileChange",
                    "id": "file",
                    "changes": {str(project / "legacy/old.py"): {"type": "update"}},
                },
            },
        },
    ]
    if unknown:
        rows.append(
            {
                "type": "response_item",
                "payload": {"type": "custom_tool_call", "name": "exec", "input": "PRIVATE CODE"},
            }
        )
    if usage:
        rows.append(
            {
                "type": "token_usage_record",
                "payload": {
                    "turn_id": turn,
                    "turn_token_usage": {
                        "input_tokens": 20,
                        "cached_input_tokens": 8,
                        "output_tokens": 4,
                    },
                },
            }
        )
    if complete:
        rows.append(
            {
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "turn_id": turn,
                    "last_agent_message": "PRIVATE FINAL",
                },
            }
        )
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


def test_recent_tasks_filter_project_and_include_usage_boundary(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "sessions"
    session(source / "rollout-old.jsonl", project)
    session(
        source / "rollout-new.jsonl",
        project,
        turn="new",
        usage=False,
        timestamp="2026-01-02T12:00:00Z",
    )
    session(source / "rollout-other.jsonl", tmp_path / "other", command="SECRET OTHER PROJECT")
    data = recent_tasks(source, project, limit=2)
    assert [r["turn_id"] for r in data["tasks"]] == ["new", "one"]
    assert data["tasks"][0]["usage"] is None
    assert data["tasks"][1]["usage"] == {"input": 20, "cached": 8, "uncached": 12, "output": 4}
    text = json.dumps(data)
    assert "SECRET OTHER PROJECT" not in text
    assert "PRIVATE" not in text and "private output" not in text
    assert str(tmp_path) not in text
    assert data["tasks"][1]["files"] == ["legacy/old.py"]
    assert data["tasks"][0]["files_verified"] is False


def test_rules_three_states_and_reported_file_boundary(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "sessions"
    session(source / "rollout-one.jsonl", project, command="python -m pip\ninstall requests")
    task = recent_tasks(source, project)["tasks"][0]
    assert evaluate_rules(task, {"commands": [], "files": []})["status"] == "unknown"
    result = evaluate_rules(task, {"commands": ["pip install"], "files": ["legacy/*"]})
    assert result["status"] == "fail" and len(result["hits"]) == 2
    assert evaluate_rules(task, {"commands": ["npm install"], "files": []})["status"] == "pass"
    assert evaluate_rules(task, {"commands": [], "files": ["secret/*"]})["status"] == "unknown"
    task["commands_complete"] = False
    assert evaluate_rules(task, {"commands": ["npm install"], "files": []})["status"] == "unknown"
    with pytest.raises(ValueError):
        evaluate_rules(task, {"commands": [""], "files": []})


def test_agents_suggestions_are_narrow_and_file_symlink_is_not_read(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    text = "Never run `pip install`.\n不要修改 `legacy/*`。\nUse uv.\n"
    (project / "AGENTS.md").write_text(text, encoding="utf-8")
    assert read_agents(project)["text"] == text
    assert suggest_rules(text) == {"commands": ["pip install"], "files": ["legacy/*"]}
    assert suggest_rules("Do not expose credentials. Run `pytest` before release.") == {
        "commands": [],
        "files": [],
    }
    target = tmp_path / "private.md"
    target.write_text("PRIVATE OUTSIDE", encoding="utf-8")
    (project / "AGENTS.md").unlink()
    try:
        (project / "AGENTS.md").symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    assert "PRIVATE OUTSIDE" not in json.dumps(read_agents(project))


def test_scan_limit_errors_and_invalid_limits_are_visible(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "sessions"
    path = session(source / "rollout-bad.jsonl", project)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n{broken")
    data = recent_tasks(source, project)
    assert data["errors"] and not data["tasks"]
    session(source / "rollout-ok.jsonl", project)
    data = recent_tasks(source, project, scan_limit=1)
    assert data["scan_limited"]
    with pytest.raises(ValueError):
        recent_tasks(source, project, limit=1000)


def test_sessions_symlink_is_skipped_and_each_session_is_parsed_once(tmp_path, monkeypatch):
    from pytest_codex import dashboard_data

    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "sessions"
    path = session(source / "rollout-one.jsonl", project)
    original = dashboard_data._read_session
    calls = []

    def spy(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(dashboard_data, "_read_session", spy)
    recent_tasks(source, project)
    assert len(calls) == 1
    outside = tmp_path / "outside"
    other = session(outside / "rollout-private.jsonl", project, command="PRIVATE OUTSIDE")
    try:
        (source / "rollout-link.jsonl").symlink_to(other)
    except OSError:
        return
    os.utime(path, None)
    assert "PRIVATE OUTSIDE" not in json.dumps(recent_tasks(source, project))


def test_started_command_without_completion_still_hits_and_never_turns_green(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "sessions"
    path = session(source / "rollout-one.jsonl", project)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[2]["payload"]["type"] = "item_started"
    rows[2]["payload"]["item"]["command"] = "pip install secret"
    rows[2]["payload"]["item"].pop("exit_code")
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    task = recent_tasks(source, project)["tasks"][0]
    assert not task["commands_complete"]
    assert task["commands"][0]["exit_code"] is None
    assert evaluate_rules(task, {"commands": ["pip install"], "files": []})["status"] == "fail"
    assert evaluate_rules(task, {"commands": ["npm install"], "files": []})["status"] == "unknown"


@pytest.mark.parametrize(
    "usage", [{}, {"input_tokens": 20}, {"input_tokens": 20, "output_tokens": 3}]
)
def test_partial_usage_is_unknown_instead_of_zero(tmp_path, usage):
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "sessions"
    path = session(source / "rollout-one.jsonl", project)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[-2]["payload"]["turn_token_usage"] = usage
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert recent_tasks(source, project)["tasks"][0]["usage"] is None


def test_long_display_is_bounded_and_cannot_claim_absence(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "sessions"
    session(source / "rollout-one.jsonl", project, command="echo " + "x" * 4000 + " pip install")
    task = recent_tasks(source, project)["tasks"][0]
    assert len(task["commands"][0]["command"]) <= 2000
    assert not task["commands_complete"] and task["display_limited"]
    assert evaluate_rules(task, {"commands": ["pip install"], "files": []})["status"] == "unknown"


def test_nonterminal_item_status_cannot_become_green(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "sessions"
    path = session(source / "rollout-one.jsonl", project)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[2]["payload"]["item"]["status"] = "InProgress"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    task = recent_tasks(source, project)["tasks"][0]
    assert evaluate_rules(task, {"commands": ["pip install"], "files": []})["status"] == "unknown"
