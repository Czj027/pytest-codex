"""Assert a Skill's resulting behavior; do not infer activation from an event name."""

from pathlib import Path

import pytest


@pytest.mark.codex(project=str(Path(__file__).parent / "skill_repo"))
def test_release_skill_output(codex):
    run = codex.exec(
        "$brief-release Create the release summary from release.json.",
        model="gpt-6-luna",
        config={"model_reasoning_effort": "low"},
    )
    assert run.succeeded, run
    assert run.read("RELEASE.md").strip() == (
        "# Release 0.2.0\n\n"
        "- Version-checked replay\n- Real MCP example\n\n"
        "Review: offline replay verified"
    ), run
    assert run.changed_files == ["RELEASE.md"], run
    assert not run.ran("pip install") and not run.ran("uv add"), run
