# Five-task regression pilot

Included in pytest-codex 0.3.0; use the source checkout. This is a
small demonstration of outcome verification and matched fresh observations,
not a model leaderboard. [Full guide](../../docs/regression.md).

| Task | Trusted acceptance |
|---|---|
| Dependency declaration | Pinned requests declaration, successful uv add, no unrelated edits |
| Arithmetic bug | Independent fractional/negative/empty-input behavior checks |
| Protected code | Greeting behavior, unchanged legacy sentinel, allowed file boundary |
| MCP lookup | Exact tool/arguments/result, returned value in answer, no shell substitution |
| Skill artifact | Exact release content, unchanged input and no dependency operations |

### Prompt-assisted acceptance, not isolated instruction receipt

`test_dependency_declaration` explicitly requests `uv add --frozen` and its other
flags in the task prompt. Its success is **prompt-assisted task acceptance**;
the AGENTS.md input repeats the uv convention, so this case alone cannot isolate
instruction-file receipt. The older `examples/test_conventions.py` has the same
prompt assistance. Do not infer missing guidance from a failed task or startup
error without another observation.

Separate examples exercise **unprompted instruction-file receipt/following**:
`examples/test_project_rules.py` asks only for a release checklist, and
`examples/test_unprompted_rules.py` states a dependency goal without `uv` or `pip`
in its prompt. Exact outputs or tool/flag rules come only from their AGENTS.md
inputs. This removes explicit prompt hints; it is behavioral evidence, not direct
proof of reading a file or a matched causal ablation. The new single observation
is outside the original 30+6 pilot and does not replace any failures or reports.
See [recorded evidence](../../docs/evidence.md#task-acceptance-versus-instruction-file-evidence)
and [issue #4](https://github.com/Czj027/pytest-codex/issues/4).

`acceptance.py` and the tests remain outside every copied task input. The
configuration includes the acceptance helper in the report's grader fingerprint.
Tasks are synthetic, public and nonsecret. Only reviewed generated code is run
by the bounded Python acceptance subprocess; it is not a hostile-code sandbox.

## Explicit fresh runs

In a disposable environment with Python, Git and uv on PATH, an existing working
Codex sandbox and a logged-in CLI 0.163.0:

```console
python -m pytest -c examples/regression/pytest.ini examples/regression --codex-record --codex-model=gpt-6-luna --codex-recording-set=YOUR-NEW-LUNA-SET --codex-results=results/YOUR-NEW-LUNA-SET.json -q
python -m pytest -c examples/regression/pytest.ini examples/regression --codex-record --codex-model=gpt-6.1-sol --codex-recording-set=YOUR-NEW-SOL-SET --codex-results=results/YOUR-NEW-SOL-SET.json -q
```

Each command requests 15 fresh agent turns, even if assertions fail. Use model IDs
available to your account and new set/output names. Ordinary root tests do not
collect `tasks.py`; this suite is explicitly selected through its pytest config.
Reports are written relative to `examples/regression`, the selected pytest root.
Recordings can contain sensitive outputs; review events and decoded file payloads.

## Included observations

The included cohorts use CLI 0.163.0, low reasoning effort and workspace-write
on Windows/Python 3.13, with five cases and three attempts per model. Shell
startup errors observed during collection are separated from task failures.
The first collection ran both model groups concurrently; do not attribute an
environment startup failure to a model's ability to follow instructions.

Collected on 2026-10-23: requested `gpt-6-luna` and `gpt-6.1-sol`, 15 turns each.
No attempt was selectively rerun. Both cohorts were collected concurrently.

| Cohort | Passed | Task failures | Startup-contaminated | Skipped |
|---|---:|---:|---:|---:|
| gpt-6-luna | 8 | 2 | 5 | 0 |
| gpt-6.1-sol | 14 | 0 | 1 | 0 |

This does not establish a model ranking. Four cases have contaminated attempts
and are inconclusive; the MCP case passed all three attempts in each cohort.
The two task failures claimed changes to `mathx.py` or `app.py` without actually
changing the files. The trusted behavior checks caught both failures.

Six turns contained an exit `-1` command with `Failed to create unified exec
process: CreateProcessWithLogonW failed: 1326`. Some subsequently recovered and
passed task acceptance. Conservatively, *any* turn with that signature is exported
as `error`, with the original task status retained in the report's explicit
`diagnostic_reclassification` metadata. This classifier was added after collection;
the original report SHA-256 is recorded, and original private captures were retained.
This is an offline diagnostic correction of those same fresh runs, not new sampling.
One no-model sandbox preflight before collection and another serial probe afterwards
succeeded. They do not establish whether concurrency caused the intermittent errors.

Public cassettes replace thread IDs with `<THREAD>` and omit nonbehavioral diagnostic
stderr. Item events, failed commands, usage and decoded changed files were reviewed
and retained. No prompt, task input, grader or outcome was changed to improve scores.

[Per-task comparison](results/comparison.md) · [Machine-readable comparison](results/comparison.json)

An [annotated comparison](results/comparison-annotated.md) now displays original
task acceptance alongside execution health. Annotation files add the acceptance
outcomes already present in the explicit correction metadata; original reports,
recordings, timestamps and conservative statuses are unchanged. Six contaminated
turns include four accepted and two rejected artifacts. The other two rejected
artifacts are the unexecuted editing scripts described above.

Follow-up no-model diagnosis reproduced 1326 in four of eight concurrent launches,
while eight serial launches passed actual write/readback. See the
[environment experiment](results/environment-diagnosis.md). Run live cohorts
serially on this Windows/CLI setup; do not start both record commands together.

A [six-turn serial follow-up](results/verified-edits.md) of the two editing tasks
passed all independent acceptance checks without recognized startup errors. Its
prompts require actual edits and self-verification. It uses a separate module,
config, recording set and report; it does not replace the original experiment.

Reproduce history without Codex, login or model calls:

```console
python -m pytest -c examples/regression/pytest.ini examples/regression --codex-model=gpt-6-luna --codex-recording-set=luna-20261023 --codex-bin=not-installed --codex-results=results/luna-replay-NEW.json -q
python -m pytest -c examples/regression/pytest.ini examples/regression --codex-model=gpt-6.1-sol --codex-recording-set=sol-20261023 --codex-bin=not-installed --codex-results=results/sol-replay-NEW.json -q
python -m pytest_codex.compare examples/regression/results/luna-live.json examples/regression/results/sol-live.json
```

Luna replay intentionally exits 1 (three failing pytest items); Sol replay exits 0.
The exported attempt statuses reproduce the table above, because task acceptance
and execution-error classification are distinct. Replay summaries have
`replayed=true` and the comparator refuses to present them as new measurements.
