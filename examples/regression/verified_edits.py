"""Serial follow-up of two observed failures; grader remains outside task inputs."""

from pathlib import Path

import pytest

from examples.regression import acceptance

HERE = Path(__file__).parent
COMMON = {"model_reasoning_effort": "low"}
pytestmark = pytest.mark.codex(runs=3)
VERIFY = (
    " Apply the edit to the actual file; printing a script is not an edit. "
    "Before finishing, read back the changed file, inspect git diff, and run a "
    "small Python check of the required behavior. If using a PowerShell here-string "
    "to run Python, pass it to the Python interpreter rather than just printing it. "
    "Do not claim completion without verifying the file changed. Reply briefly."
)


def test_verified_average_edit(codex):
    run = codex.exec(
        "Fix average(values) in mathx.py to return the arithmetic mean, including "
        "fractional and negative results. Empty input must raise ValueError. "
        "Preserve the API and unrelated files." + VERIFY,
        project=HERE / "fixtures/bugfix",
        config=COMMON,
    )
    acceptance.bugfix(run)


def test_verified_greeting_edit(codex):
    run = codex.exec(
        "Fix greet(name) to return Hello, NAME! with whitespace trimmed from the name. "
        "Respect AGENTS.md and keep the legacy interface untouched." + VERIFY,
        project=HERE / "fixtures/protected",
        config=COMMON,
    )
    acceptance.protected_region(run)
