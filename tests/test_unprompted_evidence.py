"""The example must reject printed commands, even with a correct final artifact."""

import re

import pytest

from examples import test_unprompted_rules as example
from pytest_codex.run import Run
from pytest_codex.snapshot import Diff


class CapturedRun:
    def __init__(self, run):
        self.run = run

    def exec(self, prompt, **options):
        assert not re.search(r"\b(?:uv|pip)\b", prompt, re.IGNORECASE)
        assert example.COMMAND in options["files"]["AGENTS.md"]
        return self.run


def recorded_run(tmp_path, command):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["requests==2.32.5"]\n', encoding="utf-8"
    )
    return Run(
        [
            {
                "type": "item.completed",
                "item": {
                    "id": "command",
                    "type": "command_execution",
                    "command": command,
                    "exit_code": 0,
                    "status": "completed",
                },
            },
            {"type": "turn.completed"},
        ],
        tmp_path,
        Diff(modified=["pyproject.toml"]),
    )


@pytest.mark.parametrize("printer", ["echo", "Write-Output"])
def test_unprompted_acceptance_rejects_echoed_command(tmp_path, printer):
    run = recorded_run(tmp_path, f'{printer} "{example.COMMAND}"')
    with pytest.raises(AssertionError):
        example.test_dependency_follows_unprompted_project_rules(CapturedRun(run))


def test_unprompted_acceptance_allows_direct_command_inside_shell_wrapper(tmp_path):
    command = f"\"C:\\test\\pwsh.exe\" -Command '{example.COMMAND}'"
    run = recorded_run(tmp_path, command)
    example.test_dependency_follows_unprompted_project_rules(CapturedRun(run))
