# One unprompted project-rule observation

Recorded on 2026-10-24: Codex CLI 0.163.0, requested `gpt-6.1-sol`, low reasoning
effort, Windows workspace-write/elevated sandbox and full configuration isolation.
The orchestrating Python was 3.13.14; the command selected Python 3.12.14 with
uv 0.13.5. A no-model sandbox preflight verified the pinned declaration first.
No external diagnostic tool was downloaded or executed.

The exact prompt was:

> Add requests==2.32.5 as a project dependency. Reply briefly.

Only the overridden AGENTS.md input supplied the required command and protected
paths. The [test](../test_unprompted_rules.py) keeps the acceptance checks outside
the copied task input. The real command, rather than an echoed script, executed:

```console
uv add --frozen --no-managed-python --no-python-downloads --cache-dir .uv-cache requests==2.32.5
```

Result: one attempt, accepted. The command exited 0; only `pyproject.toml` changed,
with the pinned dependency. A subsequent Git diff check exited 0. No pip command
or legacy edit was observed. The ordinary PowerShell shell-snapshot unsupported
warning was the only startup stderr; it was removed from the public cassette,
with the original retained privately. Thread IDs are anonymized; events and the
one decoded changed-file payload were reviewed. There was no selective rerun.

[Fresh result](fresh-result.json) records the single CLI-login run; it is not
an API bill or a comparison cohort. Its task-acceptance and execution-health
checks both passed. The four checklist observations in `test_project_rules.py`
are earlier, separate examples, not repetitions of this dependency task.

After collection, review strengthened the command assertion from a substring to
an exact unwrapped command/exit check, with echo and Write-Output negative tests.
The original fresh report and its grader fingerprint are retained.
[Strict offline validation](replay-validation.json) rechecks that same observation
under the stronger grader; it is marked replayed, not another fresh model turn.
Different grader hashes prevent treating these two reports as a matched cohort.

This removes the tool-name hint from the prompt and provides behavioral evidence
consistent with the project instructions. It is not direct file-receipt
instrumentation, a matched no-AGENTS experiment or a reliability estimate. It does
not reinterpret the original 30+6 pilot or replace any published recording/report.

Replay without Codex or login:

```console
python -m pytest examples/test_unprompted_rules.py --codex-bin=not-installed -q
```

For a separate fresh attempt, use an audited, working local environment with
Codex login and select a **new** recording set/report. This consumes one turn:

```console
python -m pytest examples/test_unprompted_rules.py --codex-record -o codex_isolation=full --codex-recording-set=YOUR-NEW-RULES-SET --codex-results=YOUR-NEW-RULES-RESULT.json -q
```

The example explicitly requests `gpt-6.1-sol` and low effort; account availability
can change. Full isolation is configuration isolation, not a hermetic OS or
environment. On Windows, uv and a sandbox-readable Python must be on PATH.
Review the fresh recording before publishing it.

[Methodological feedback](https://github.com/openai/codex/discussions/56181#discussioncomment-19153358)
and [issue #4](https://github.com/Czj027/pytest-codex/issues/4) explain the change.
The commenter self-identifies as an AI developer account and has not run or
integrated pytest-codex. This is a feedback-to-improvement record, not adoption.
