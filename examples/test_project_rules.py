"""Dogfood this repository's own instructions with two models and repeated attempts."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6.1-sol"])
@pytest.mark.codex(runs=2, pass_rate=1.0)
def test_our_release_checklist(codex, tmp_path, model):
    # Use the actual project rules, without copying unrelated work or local notes.
    project = tmp_path / "release-inputs"
    project.mkdir(exist_ok=True)
    (project / "AGENTS.md").write_bytes((ROOT / "AGENTS.md").read_bytes())
    run = codex.exec(
        "Give me the release checklist for this project.",
        project=project,
        model=model,
        config={"model_reasoning_effort": "low"},
    )
    assert run.succeeded, run
    assert json.loads(run.final_message) == {
        "package": "pytest-codex",
        "checks": ["offline tests", "lint", "build", "recording privacy"],
    }, run
    assert not run.commands and not run.changed_files, run
