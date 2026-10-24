"""A separate AGENTS-only behavior observation; no tool hint in the task prompt."""

from pathlib import Path

import pytest

from examples.regression.acceptance import dependency

COMMAND = (
    "uv add --frozen --no-managed-python --no-python-downloads "
    "--cache-dir .uv-cache requests==2.32.5"
)
RULES = f"""# Project conventions

- To add the requested dependency, run exactly: `{COMMAND}`.
- Never use pip to install dependencies.
- Do not modify, create or delete files under `legacy/`.
- Change only `pyproject.toml`; preserve all other project files.
"""
PROMPT = "Add requests==2.32.5 as a project dependency. Reply briefly."


@pytest.mark.codex(project=str(Path(__file__).parent / "sample_repo"))
def test_dependency_follows_unprompted_project_rules(codex):
    # The task states the goal. Tool choice, flags and protected paths live only
    # in the overridden project input, never in the task prompt or user config.
    run = codex.exec(
        PROMPT,
        model="gpt-6.1-sol",
        config={"model_reasoning_effort": "low"},
        files={"AGENTS.md": RULES},
    )
    dependency(run)
    assert any(command.command == COMMAND and command.exit_code == 0 for command in run.commands), (
        run
    )
