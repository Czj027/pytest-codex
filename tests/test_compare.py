import json
import subprocess
import sys
from copy import deepcopy

import pytest

from pytest_codex.compare import compare_reports, render_markdown


def report(model="before", statuses=("passed", "failed", "passed")):
    return {
        "schema": 1,
        "context": {"python": "3.13.0", "platform": "win32", "plugin_version": "0.3.0"},
        "attempts": [
            {
                "case": "test_tasks.py::test_task",
                "attempt": attempt,
                "status": status,
                "grader_hash": "a" * 64,
                "runs": [
                    {
                        "model": model,
                        "cli_version": "0.163.0",
                        "replayed": False,
                        "input_hash": "b" * 64,
                        "prompt_hash": "c" * 64,
                        "config_hash": "d" * 64,
                        "sandbox": "workspace-write",
                        "isolation": "full",
                        "timeout": 300.0,
                        "duration_seconds": 1.5,
                        "usage": {
                            "input_tokens": 100,
                            "cached_input_tokens": 80,
                            "output_tokens": 5,
                        },
                    }
                ],
            }
            for attempt, status in enumerate(statuses, 1)
        ],
    }


def test_compare_keeps_attempts_and_reports_observed_changes():
    result = compare_reports(report(), report("after", ("passed", "failed", "failed")))
    row = result["cases"][0]
    assert row["baseline"]["passed"] == 2 and row["candidate"]["passed"] == 1
    assert row["direction"] == "observed_decrease"
    assert row["rate_delta"] == pytest.approx(-1 / 3)
    assert result["usage"]["baseline"]["input_tokens"] == 300
    assert result["usage"]["baseline"]["cached_input_tokens"] == 240
    assert "small sample" in render_markdown(result).lower()
    assert "2/3" in render_markdown(result)


def test_errors_and_skips_are_not_model_failures_or_apparent_improvements():
    candidate = report("after", ("passed", "error", "skipped"))
    candidate["attempts"][1]["runs"] = []
    result = compare_reports(report(), candidate)
    row = result["cases"][0]
    assert row["candidate"]["failed"] == 0
    assert row["candidate"]["error"] == 1 and row["candidate"]["skipped"] == 1
    assert row["candidate"]["rate"] == 1.0
    assert row["direction"] == "inconclusive" and row["rate_delta"] is None


@pytest.mark.parametrize(
    "field",
    ["input_hash", "prompt_hash", "config_hash", "sandbox", "isolation", "timeout", "cli_version"],
)
def test_reject_uncontrolled_changes(field):
    candidate = report("after")
    candidate["attempts"][0]["runs"][0][field] = "changed"
    with pytest.raises(ValueError, match="contract|factor|CLI"):
        compare_reports(report(), candidate)


@pytest.mark.parametrize(
    "change", ["replay", "grader", "python", "duplicate", "missing", "invalid-status", "no-model"]
)
def test_reject_untrustworthy_or_unmatched_reports(change):
    candidate = report("after")
    if change == "replay":
        candidate["attempts"][0]["runs"][0]["replayed"] = True
    elif change == "grader":
        candidate["attempts"][0]["grader_hash"] = "f" * 64
    elif change == "python":
        candidate["context"]["python"] = "3.12.0"
    elif change == "duplicate":
        candidate["attempts"].append(deepcopy(candidate["attempts"][0]))
    elif change == "missing":
        candidate["attempts"].pop()
    elif change == "invalid-status":
        candidate["attempts"][0]["status"] = "maybe"
    else:
        candidate["attempts"][0]["runs"][0]["model"] = None
    with pytest.raises(ValueError):
        compare_reports(report(), candidate)


def test_cli_factor_requires_same_model_and_changed_cli():
    candidate = report()
    for row in candidate["attempts"]:
        row["runs"][0]["cli_version"] = "0.164.0"
    assert compare_reports(report(), candidate, factor="cli")["factor"] == "cli"
    with pytest.raises(ValueError):
        compare_reports(report(), report())
    with pytest.raises(ValueError):
        compare_reports(report(), report("after"), factor="cli")


def test_cli_renders_both_artifacts_without_overwriting(tmp_path):
    for name, model in (("before", "before"), ("after", "after")):
        (tmp_path / (name + ".json")).write_text(json.dumps(report(model)), encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "pytest_codex.compare",
        str(tmp_path / "before.json"),
        str(tmp_path / "after.json"),
        "--output",
        str(tmp_path / "report.md"),
        "--json-output",
        str(tmp_path / "report.json"),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    assert result.returncode == 0, result.stderr
    assert "unchanged" in (tmp_path / "report.md").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["schema"] == 1
    assert subprocess.run(command, capture_output=True, check=False).returncode != 0
