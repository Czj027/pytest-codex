"""Compare two matched, fresh pytest-codex observation sets without model calls."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

STATUSES = {"passed", "failed", "error", "skipped"}
CONTRACT = ("input_hash", "prompt_hash", "config_hash", "sandbox", "isolation", "timeout")


def _indexed(report):
    if not isinstance(report, dict) or report.get("schema") != 1:
        raise ValueError("Unsupported results schema")
    if not isinstance(report.get("context"), dict) or not isinstance(report.get("attempts"), list):
        raise TypeError("Missing results context or attempts")
    rows = {}
    for row in report["attempts"]:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("case"), str)
            or not row["case"]
            or type(row.get("attempt")) is not int
            or row["attempt"] < 1
            or row.get("status") not in STATUSES
            or not isinstance(row.get("grader_hash"), str)
            or not isinstance(row.get("runs"), list)
        ):
            raise ValueError("Invalid attempt row")
        key = row["case"], row["attempt"]
        if key in rows:
            raise ValueError("Duplicate case/attempt")
        if not row["runs"] and row["status"] in {"passed", "failed"}:
            raise ValueError("A completed task needs an observed run")
        for run in row["runs"]:
            if not isinstance(run, dict) or run.get("replayed") is not False:
                raise ValueError("Comparison requires fresh runs, not replayed observations")
            if not run.get("model") or not run.get("cli_version"):
                raise ValueError("Explicit model and CLI version are required")
            if any(field not in run for field in CONTRACT):
                raise ValueError("Missing run contract")
            for field in ("input_tokens", "cached_input_tokens", "output_tokens"):
                value = run.get("usage", {}).get(field)
                if type(value) is not int or value < 0:
                    raise ValueError("Invalid token count")
            if run["usage"]["cached_input_tokens"] > run["usage"]["input_tokens"]:
                raise ValueError("Cached input is a subset of total input")
            duration = run.get("duration_seconds")
            if type(duration) not in {int, float} or not math.isfinite(duration) or duration < 0:
                raise ValueError("Invalid execution duration")
        rows[key] = row
    if not rows:
        raise ValueError("No attempt observations")
    return rows


def _counts(rows):
    counts = {status: 0 for status in sorted(STATUSES)}
    counts.update(Counter(row["status"] for row in rows))
    completed = counts["passed"] + counts["failed"]
    return {
        **counts,
        "completed": completed,
        "rate": counts["passed"] / completed if completed else None,
    }


def _usage(rows):
    counts = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    seconds = 0.0
    for row in rows.values():
        for run in row["runs"]:
            for field in counts:
                counts[field] += run["usage"][field]
            seconds += run["duration_seconds"]
    return {**counts, "duration_seconds": round(seconds, 6)}


def compare_reports(baseline, candidate, *, factor="model"):
    if factor not in {"model", "cli"}:
        raise ValueError("factor must be model or cli")
    left, right = _indexed(baseline), _indexed(candidate)
    if left.keys() != right.keys():
        raise ValueError("Case/attempt sets differ; collect matching observations")
    for field in ("python", "platform", "plugin_version"):
        value = baseline["context"].get(field)
        if not value or value != candidate["context"].get(field):
            raise ValueError(f"Environment contract differs: {field}")
    cohorts = []
    for rows in (left, right):
        models = {run["model"] for row in rows.values() for run in row["runs"]}
        versions = {run["cli_version"] for row in rows.values() for run in row["runs"]}
        if len(models) != 1 or len(versions) != 1:
            raise ValueError("Each factor cohort needs exactly one model and CLI version")
        cohorts.append({"model": models.pop(), "cli": versions.pop()})
    fixed = "cli" if factor == "model" else "model"
    if cohorts[0][fixed] != cohorts[1][fixed] or cohorts[0][factor] == cohorts[1][factor]:
        raise ValueError("Only the selected factor may change (fixed model/CLI must match)")
    groups = defaultdict(lambda: [[], []])
    for key, before in left.items():
        after = right[key]
        if before["grader_hash"] != after["grader_hash"]:
            raise ValueError(f"Grader contract differs: {key[0]}")
        # Setup errors/skips may have no execution; retain them as inconclusive evidence.
        if before["runs"] and after["runs"]:
            if len(before["runs"]) != len(after["runs"]):
                raise ValueError(f"Run count contract differs: {key[0]}")
            for a, b in zip(before["runs"], after["runs"]):
                if any(a[field] != b[field] for field in CONTRACT):
                    raise ValueError(f"Run contract differs: {key[0]}")
        groups[key[0]][0].append(before)
        groups[key[0]][1].append(after)
    cases = []
    for name, (before, after) in sorted(groups.items()):
        a, b = _counts(before), _counts(after)
        delta = None
        direction = "inconclusive"
        if not (a["error"] or a["skipped"] or b["error"] or b["skipped"]):
            delta = b["rate"] - a["rate"]
            direction = (
                "observed_increase"
                if delta > 0
                else "observed_decrease"
                if delta < 0
                else "unchanged"
            )
        cases.append(
            {
                "case": name,
                "baseline": a,
                "candidate": b,
                "rate_delta": delta,
                "direction": direction,
                "attempts": [
                    {
                        "attempt": x["attempt"],
                        "baseline": x["status"],
                        "candidate": y["status"],
                        "baseline_error": x.get("error_type"),
                        "candidate_error": y.get("error_type"),
                        "baseline_behavior": [run.get("behavior", {}) for run in x["runs"]],
                        "candidate_behavior": [run.get("behavior", {}) for run in y["runs"]],
                    }
                    for x, y in zip(
                        sorted(before, key=lambda x: x["attempt"]),
                        sorted(after, key=lambda x: x["attempt"]),
                    )
                ],
            }
        )
    return {
        "schema": 1,
        "factor": factor,
        "cohorts": cohorts,
        "cases": cases,
        "context": baseline["context"],
        "usage": {"baseline": _usage(left), "candidate": _usage(right)},
    }


def render_markdown(result):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    def score(value):
        rate = "n/a" if value["rate"] is None else f"{value['rate']:.1%}"
        return f"{value['passed']}/{value['completed']} ({rate}); errors={value['error']}, skipped={value['skipped']}"

    lines = ["# Fresh Codex task comparison", "", f"Factor: **{cell(result['factor'])}**.", ""]
    for label, cohort in zip(("Baseline", "Candidate"), result["cohorts"]):
        lines.append(f"{label}: {cell(cohort['model'])} / CLI {cell(cohort['cli'])}.")
    lines += ["", "| Task | Baseline | Candidate | Observation |", "|---|---|---|---|"]
    for row in result["cases"]:
        lines.append(
            f"| {cell(row['case'])} | {score(row['baseline'])} | {score(row['candidate'])} | {row['direction']} |"
        )
    lines += [
        "",
        "Each score uses completed attempts only; execution/grader errors and skips are separate.",
        "Any case with errors/skips is inconclusive rather than an apparent model improvement.",
        "This is a small sample of observed outcomes, not a model ranking or statistical proof of regression.",
        "A model alias may change server-side; these are requested model IDs, not verified weight snapshots.",
        "Environment hashes cover recorded inputs/configuration, not all inherited machine state.",
        "",
        "## Execution totals",
        "",
        "| Cohort | Input (includes cached) | Cached subset | Output | Seconds |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, row in result["usage"].items():
        lines.append(
            f"| {label} | {row['input_tokens']} | {row['cached_input_tokens']} | {row['output_tokens']} | {row['duration_seconds']:.2f} |"
        )
    lines += [
        "",
        "Times include invocation/recording overhead. Token counters are not an API invoice.",
        "",
        "## Per-attempt observations",
        "",
    ]
    for row in result["cases"]:
        lines.append(f"### {cell(row['case'])}")
        for item in row["attempts"]:
            lines.append(
                f"- Attempt {item['attempt']}: {item['baseline']} → {item['candidate']}"
                f" (error types: {cell(item['baseline_error'])} / {cell(item['candidate_error'])})."
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--factor", choices=("model", "cli"), default="model")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    try:
        targets = [path for path in (args.output, args.json_output) if path is not None]
        if len({p.resolve() for p in targets}) != len(targets) or any(p.exists() for p in targets):
            raise ValueError("Output paths must be distinct and must not already exist")
        data = [
            json.loads(path.read_text(encoding="utf-8")) for path in (args.baseline, args.candidate)
        ]
        result = compare_reports(*data, factor=args.factor)
        markdown = render_markdown(result)
        for path, text in (
            (args.output, markdown),
            (args.json_output, json.dumps(result, indent=2) + "\n"),
        ):
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(text)
        if args.output is None:
            print(markdown, end="")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Cannot compare results: {exc}\n")


if __name__ == "__main__":
    main()
