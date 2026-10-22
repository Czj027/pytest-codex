from pathlib import Path

import pytest


@pytest.mark.codex(project=str(Path(__file__).parent / "sample_repo"))
def test_uses_uv_and_preserves_legacy(codex):
    run = codex.exec(
        "Add requests as a project dependency using uv add --frozen --no-managed-python "
        "--no-python-downloads --cache-dir .uv-cache requests. "
        "Do not change legacy/. Reply briefly.",
        config={"model_reasoning_effort": "low"},
    )
    assert run.succeeded, run
    assert run.ran("uv add", ok=True), run
    assert not run.ran("pip install"), run
    assert run.modified("pyproject.toml"), run
    assert "requests" in run.read("pyproject.toml"), run
    assert not any(path.startswith("legacy/") for path in run.changed_files), run
