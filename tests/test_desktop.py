import json
import subprocess
import sys

import pytest

from pytest_codex.desktop import DesktopSessionError, from_desktop_session, list_desktop_turns


def write_session(path, extra=()):
    records = [
        {
            "type": "session_meta",
            "payload": {
                "id": "private-id",
                "cwd": "/private/project",
                "cli_version": "0.163.0",
                "originator": "codex_work_desktop",
                "base_instructions": "PRIVATE RULES",
            },
        },
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "one"}},
        {
            "type": "response_item",
            "payload": {"type": "message", "role": "user", "content": [{"text": "PRIVATE PROMPT"}]},
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "turn_id": "one",
                "item": {
                    "type": "CommandExecution",
                    "id": "cmd",
                    "command": ["bash", "-lc", "uv add requests"],
                    "exit_code": 0,
                    "status": "Completed",
                    "aggregated_output": "done at /private/project",
                },
            },
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "turn_id": "one",
                "item": {
                    "type": "McpToolCall",
                    "id": "mcp",
                    "server": "demo",
                    "tool": "lookup",
                    "arguments": {"id": 1},
                    "result": {"ok": True},
                    "status": "Completed",
                },
            },
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "turn_id": "one",
                "item": {
                    "type": "FileChange",
                    "id": "file",
                    "changes": {
                        "/private/project/result.txt": {"type": "add", "diff": "PRIVATE PATCH"}
                    },
                },
            },
        },
        {
            "type": "token_usage_record",
            "payload": {
                "turn_id": "one",
                "turn_token_usage": {
                    "input_tokens": 10,
                    "cached_input_tokens": 4,
                    "output_tokens": 2,
                },
            },
        },
        {
            "type": "token_usage_record",
            "payload": {
                "turn_id": "one",
                "turn_token_usage": {
                    "input_tokens": 20,
                    "cached_input_tokens": 8,
                    "output_tokens": 4,
                },
            },
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "last_token_usage": {"input_tokens": 10, "output_tokens": 2},
                    "total_token_usage": {"input_tokens": 999, "output_tokens": 99},
                },
            },
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "turn_id": "one",
                "item": {
                    "type": "AgentMessage",
                    "id": "reply",
                    "phase": "final",
                    "content": [{"type": "Text", "text": "Done"}],
                },
            },
        },
        {
            "type": "event_msg",
            "payload": {"type": "task_complete", "turn_id": "one", "last_agent_message": "Done"},
        },
        *extra,
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def test_import_observation_and_preserve_file_state_boundary(tmp_path):
    source = write_session(tmp_path / "session.jsonl")
    run = from_desktop_session(source)
    assert run.succeeded and run.replayed and run.ran("uv add", ok=True)
    assert run.called_mcp("demo", "lookup") and run.mcp_calls[0].arguments == {"id": 1}
    assert run.final_message == "Done"
    assert run.tokens.input_tokens == 20 and run.tokens.output_tokens == 4
    assert run.tokens.cached_input_tokens == 8
    assert run.reported_changed_files == ["<PROJECT>/result.txt"]
    assert run.project is None and run.diff is None and run.file_state == "unavailable"
    for action in (
        lambda: run.changed_files,
        lambda: run.modified("*"),
        lambda: run.added("*"),
        lambda: run.deleted("*"),
        lambda: run.read("result.txt"),
    ):
        with pytest.raises(DesktopSessionError, match="file state"):
            action()
    assert "PRIVATE RULES" not in json.dumps(run.events)
    assert "PRIVATE PROMPT" not in json.dumps(run.events)
    assert "PRIVATE PATCH" not in json.dumps(run.events)


def test_multi_turn_explicit_selection_abort_and_incomplete(tmp_path):
    extra = [
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "two"}},
        {"type": "event_msg", "payload": {"type": "turn_aborted", "turn_id": "two"}},
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "three"}},
    ]
    path = write_session(tmp_path / "session.jsonl", extra)
    assert [t["status"] for t in list_desktop_turns(path)] == ["completed", "aborted", "incomplete"]
    with pytest.raises(DesktopSessionError, match="turn_id"):
        from_desktop_session(path)
    assert from_desktop_session(path, turn_id="one").succeeded
    assert not from_desktop_session(path, turn_id="two").succeeded
    assert not from_desktop_session(path, turn_id="three").succeeded
    with pytest.raises(DesktopSessionError, match="not found"):
        from_desktop_session(path, turn_id="missing")


def test_malformed_records_and_duplicate_metadata_fail_without_content(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"secret":"PRIVATE"\n', encoding="utf-8")
    with pytest.raises(DesktopSessionError, match="line 1") as exc:
        from_desktop_session(path)
    assert "PRIVATE" not in str(exc.value)
    write_session(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "session_meta", "payload": {}}) + "\n")
    with pytest.raises(DesktopSessionError, match="metadata"):
        from_desktop_session(path)


def test_export_requires_content_opt_in_and_cannot_be_full_cassette(tmp_path):
    from pytest_codex.cassette import save_cassette

    run = from_desktop_session(write_session(tmp_path / "session.jsonl"))
    dest = tmp_path / "observation.json"
    with pytest.raises(DesktopSessionError, match="include_content"):
        run.save(dest)
    assert not dest.exists()
    run.save(dest, include_content=True)
    text = dest.read_text(encoding="utf-8")
    assert "/private/project" not in text and "PRIVATE" not in text and "private-id" not in text
    loaded = from_desktop_session(dest)
    assert loaded.ran("uv add", ok=True) and loaded.tokens.total == 24
    assert loaded.file_state == "unavailable" and loaded.source_sha256 == run.source_sha256
    with pytest.raises(FileExistsError):
        run.save(dest, include_content=True)
    with pytest.raises(ValueError, match="file state"):
        save_cassette(tmp_path / "full.json", "key", run, "test")


def test_unknown_coverage_blocks_negative_claims_and_redacts_tokens(tmp_path):
    path = write_session(tmp_path / "session.jsonl")
    records = [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()]
    records.insert(
        -1,
        {
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "turn_id": "one",
                "item": {"type": "FutureTool", "id": "unknown", "secret": "private"},
            },
        },
    )
    records[-2]["payload"]["item"]["secret"] = "ghp_" + "A" * 36
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    run = from_desktop_session(path)
    assert not run.commands_complete and "FutureTool" in run.unsupported_items
    assert run.ran("uv add", ok=True)
    with pytest.raises(DesktopSessionError, match="incomplete"):
        run.ran("pip install")
    assert "ghp_" not in json.dumps(run.events)


def test_cli_list_and_explicit_export(tmp_path):
    path = write_session(tmp_path / "session.jsonl")
    listed = subprocess.run(
        [sys.executable, "-m", "pytest_codex.desktop", "list", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert listed.returncode == 0 and "one" in listed.stdout and "PRIVATE" not in listed.stdout
    dest = tmp_path / "out.json"
    exported = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest_codex.desktop",
            "import-session",
            str(path),
            "--output",
            str(dest),
            "--include-content",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert exported.returncode == 0 and from_desktop_session(dest).succeeded


def test_opaque_response_tools_cannot_be_asserted_absent(tmp_path):
    path = write_session(tmp_path / "session.jsonl")
    records = path.read_text(encoding="utf-8").splitlines()
    records.insert(
        -1,
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "exec",
                    "input": "PRIVATE CODE",
                    "call_id": "opaque",
                },
            }
        ),
    )
    path.write_text("\n".join(records), encoding="utf-8")
    run = from_desktop_session(path)
    assert not run.commands_complete
    with pytest.raises(DesktopSessionError, match="incomplete"):
        run.ran("never")
    assert "PRIVATE CODE" not in json.dumps(run.events)


def test_aborted_usage_preserved_and_other_turn_usage_excluded(tmp_path):
    path = write_session(tmp_path / "session.jsonl")
    records = [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()]
    records.insert(
        -1,
        {
            "type": "token_usage_record",
            "payload": {"turn_id": "foreign", "turn_token_usage": {"input_tokens": 999}},
        },
    )
    records[-1]["payload"]["type"] = "turn_aborted"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    run = from_desktop_session(path)
    assert not run.succeeded and run.usage_complete and run.tokens.total == 24
    dest = tmp_path / "aborted.json"
    run.save(dest, include_content=True)
    assert from_desktop_session(dest).tokens.total == 24


def test_imported_no_usage_is_explicit_and_export_validation(tmp_path):
    path = write_session(tmp_path / "session.jsonl")
    records = [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()]
    records = [r for r in records if r["type"] != "token_usage_record"]
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    run = from_desktop_session(path)
    assert not run.usage_complete and run.tokens.total == 0
    dest = tmp_path / "observation.json"
    run.save(dest, include_content=True)
    data = json.loads(dest.read_text(encoding="utf-8"))
    data["events"].append(
        {"type": "response_item", "payload": {"role": "developer", "text": "PRIVATE RULES"}}
    )
    dest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(DesktopSessionError, match="observation"):
        from_desktop_session(dest)


def test_fixture_and_public_facade_import_without_live_mode(pytester):
    path = write_session(pytester.path / "session.jsonl")
    pytester.makeini("[pytest]\n")
    pytester.makeconftest('pytest_plugins = ["pytest_codex.plugin"]')
    pytester.makepyfile(f"""
from pytest_codex import from_desktop_session
def test_history(codex):
    assert codex.from_desktop_session({str(path)!r}).ran("uv add", ok=True)
    assert from_desktop_session({str(path)!r}).succeeded
""")
    pytester.runpytest("--codex-bin=not-installed").assert_outcomes(passed=1)


def test_incomplete_observation_cannot_assert_absent_mcp(tmp_path):
    path = write_session(tmp_path / "session.jsonl")
    rows = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(rows[:-1]), encoding="utf-8")
    run = from_desktop_session(path)
    with pytest.raises(DesktopSessionError, match="incomplete"):
        run.called_mcp("not-observed")


def test_export_rejects_bool_exit_and_malformed_agent_text(tmp_path):
    run = from_desktop_session(write_session(tmp_path / "session.jsonl"))
    for bad in ({"exit_code": False}, {"command": ["echo", "bad"]}):
        path = tmp_path / ("bad-" + next(iter(bad)) + ".json")
        run.save(path, include_content=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["events"][0]["item"].update(bad)
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(DesktopSessionError, match="observation"):
            from_desktop_session(path)


def test_usage_after_completion_and_while_another_turn_is_active(tmp_path):
    path = write_session(
        tmp_path / "session.jsonl",
        [
            {
                "type": "token_usage_record",
                "payload": {
                    "turn_id": "one",
                    "turn_token_usage": {"input_tokens": 50, "output_tokens": 5},
                },
            },
            {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "two"}},
            {
                "type": "token_usage_record",
                "payload": {
                    "turn_id": "one",
                    "turn_token_usage": {"input_tokens": 60, "output_tokens": 6},
                },
            },
        ],
    )
    assert from_desktop_session(path, turn_id="one").tokens.total == 66
    assert not from_desktop_session(path, turn_id="two").usage_complete


@pytest.mark.parametrize(
    "payload",
    [
        {"type": []},
        {"type": "task_complete", "turn_id": "one", "last_agent_message": {"private": "text"}},
    ],
)
def test_unsupported_required_shapes_fail_explicitly(tmp_path, payload):
    path = write_session(tmp_path / "session.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[-1] = json.dumps({"type": "event_msg", "payload": payload})
    path.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(DesktopSessionError):
        from_desktop_session(path)


def test_fixture_import_cannot_enter_fresh_comparison(pytester):
    path = write_session(pytester.path / "session.jsonl")
    pytester.makeini("[pytest]\n")
    pytester.makeconftest('pytest_plugins = ["pytest_codex.plugin"]')
    pytester.makepyfile(f"""
def test_history(codex):
    codex.from_desktop_session({str(path)!r})
""")
    result = pytester.runpytest("--codex-results=attempts.json")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*Desktop observations cannot enter*"])


def test_engine_diagnostic_does_not_run_a_task(monkeypatch, capsys):
    from pytest_codex.desktop import main

    monkeypatch.setattr("pytest_codex.desktop_engine.find_desktop_binary", lambda: "desktop-engine")
    monkeypatch.setattr("pytest_codex.runner.cli_version", lambda binary: "codex-cli test")
    main(["engine"])
    assert json.loads(capsys.readouterr().out) == {
        "binary": "desktop-engine",
        "version": "codex-cli test",
    }


def test_conflicting_terminal_cannot_turn_abort_into_success(tmp_path):
    path = write_session(tmp_path / "session.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[-1]["payload"]["type"] = "turn_aborted"
    rows.append({"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "one"}})
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    with pytest.raises(DesktopSessionError, match="terminal"):
        from_desktop_session(path)
