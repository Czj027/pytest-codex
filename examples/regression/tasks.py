"""Five small real tasks. Acceptance code remains outside every agent workspace."""

from pathlib import Path

import pytest

from examples.regression import acceptance

HERE = Path(__file__).parent
EXAMPLES = HERE.parent
COMMON = {"model_reasoning_effort": "low"}
pytestmark = pytest.mark.codex(runs=3)


def test_dependency_declaration(codex):
    run = codex.exec(
        "Add requests==2.32.5 to the project dependencies using uv add --frozen "
        "--no-managed-python --no-python-downloads --cache-dir .uv-cache requests==2.32.5. "
        "Respect AGENTS.md and preserve all unrelated files. Reply briefly.",
        project=EXAMPLES / "sample_repo",
        config=COMMON,
    )
    acceptance.dependency(run)


def test_fix_average(codex):
    run = codex.exec(
        "Fix average(values) in mathx.py to return the arithmetic mean, including "
        "fractional and negative results. Empty input must raise ValueError. "
        "Preserve the API and unrelated files. Reply briefly.",
        project=HERE / "fixtures/bugfix",
        config=COMMON,
    )
    acceptance.bugfix(run)


def test_preserve_legacy(codex):
    run = codex.exec(
        "Fix greet(name) to return Hello, NAME! with whitespace trimmed from the name. "
        "Respect AGENTS.md and keep the legacy interface untouched. Reply briefly.",
        project=HERE / "fixtures/protected",
        config=COMMON,
    )
    acceptance.protected_region(run)


def test_mcp_result(codex):
    run = codex.exec(
        "Use the catalog MCP lookup tool once to look up pytest-codex and report its mode. "
        "Do not execute shell commands or edit files.",
        project=EXAMPLES / "mcp_repo",
        config={
            **COMMON,
            "mcp_servers.catalog.command": "python",
            "mcp_servers.catalog.args": ["server.py"],
            "mcp_servers.catalog.enabled_tools": ["lookup"],
        },
    )
    acceptance.mcp_lookup(run)


def test_skill_artifact(codex):
    run = codex.exec(
        "$brief-release Create the release summary from release.json.",
        project=EXAMPLES / "skill_repo",
        config=COMMON,
    )
    acceptance.skill_output(run)
