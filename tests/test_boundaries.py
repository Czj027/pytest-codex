import json
import os

import pytest

from pytest_codex.cassette import CassetteError, load_cassette, save_cassette
from pytest_codex.run import Run
from pytest_codex.snapshot import Diff, snapshot


def test_replay_file_directory_transition(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    (original / "node").write_bytes(b"file")
    cassette = tmp_path / "record.json"
    save_cassette(
        cassette,
        "k",
        Run([{"type": "turn.completed"}], original, Diff(["node"], [], ["node/child"])),
        "test",
    )
    replay = tmp_path / "replay"
    (replay / "node").mkdir(parents=True)
    (replay / "node" / "child").write_bytes(b"child")
    load_cassette(cassette, "k", replay)
    assert (replay / "node").read_bytes() == b"file"


def test_invalid_cassette_payload_does_not_apply_earlier_valid_file(tmp_path):
    cassette = tmp_path / "record.json"
    cassette.write_text(
        json.dumps(
            {
                "schema": 1,
                "key": "k",
                "events": [],
                "returncode": 0,
                "diff": {"added": ["ok.txt", "bad.txt"]},
                "files": {
                    "ok.txt": {"data": "b2s=", "mode": 420},
                    "bad.txt": {"data": "!invalid", "mode": 420},
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CassetteError):
        load_cassette(cassette, "k", tmp_path)
    assert not (tmp_path / "ok.txt").exists()


def test_snapshot_refuses_links_instead_of_reading_external_content(tmp_path):
    target = tmp_path / "external"
    target.write_text("private", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    try:
        (project / "link").symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(ValueError, match="symlink"):
        snapshot(project)


def test_recording_replaces_machine_paths_in_event_strings(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    events = [
        {
            "type": "item.completed",
            "item": {
                "id": "m",
                "type": "agent_message",
                "text": f"{project} then {os.path.expanduser('~')}",
            },
        },
        {"type": "turn.completed"},
    ]
    cassette = tmp_path / "portable.json"
    save_cassette(cassette, "k", Run(events, project), "test")
    text = cassette.read_text(encoding="utf-8")
    assert "<PROJECT> then <HOME>" in text
