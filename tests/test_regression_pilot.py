"""Historical pilot outcomes must replay faithfully without a Codex executable."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pytest_codex.cassette import save_cassette
from pytest_codex.compare import compare_reports
from pytest_codex.run import Run

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "examples/regression"


@pytest.mark.parametrize(
    "cohort,model,exit_code", [("luna", "gpt-6-luna", 1), ("sol", "gpt-6.1-sol", 0)]
)
def test_pilot_reproduces_all_observed_outcomes(tmp_path, cohort, model, exit_code):
    output = tmp_path / "replayed.json"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(PILOT / "pytest.ini"),
            str(PILOT),
            "--codex-bin=not-installed",
            f"--codex-model={model}",
            f"--codex-recording-set={cohort}-20261023",
            f"--codex-results={output}",
            "-q",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
        check=False,
    )
    assert process.returncode == exit_code, process.stdout + process.stderr
    fresh = json.loads((PILOT / "results" / f"{cohort}-live.json").read_text(encoding="utf-8"))
    replay = json.loads(output.read_text(encoding="utf-8"))
    fields = ("case", "attempt", "status", "error_type", "grader_hash")
    assert [{f: row[f] for f in fields} for row in fresh["attempts"]] == [
        {f: row[f] for f in fields} for row in replay["attempts"]
    ]
    assert all(run["replayed"] for row in replay["attempts"] for run in row["runs"])
    with pytest.raises(ValueError, match="fresh"):
        compare_reports(fresh, replay)


def test_immutable_cassette_publish_refuses_a_concurrent_winner(tmp_path):
    target = tmp_path / "recording.json"
    target.write_text("preserve competing evidence", encoding="utf-8")
    with pytest.raises(FileExistsError):
        save_cassette(target, "key", Run([], tmp_path), "test", overwrite=False)
    assert target.read_text(encoding="utf-8") == "preserve competing evidence"
    assert not list(tmp_path.glob(".cassette-*"))
