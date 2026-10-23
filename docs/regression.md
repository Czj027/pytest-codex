# Compare fresh Codex task outcomes

This feature is included in 0.3.0. PyPI 0.2.0 does not provide the result export
or comparison command. Install this source checkout to try it:

```console
python -m pip install .
```

## Start with a checkable task

The [five-task pilot](../examples/regression/tasks.py) covers a uv dependency
declaration, arithmetic bug fix, protected legacy code, MCP lookup and Skill
artifact. The dependency case checks metadata and successful `uv add`; it does
not claim the dependency was installed or usable in an isolated environment.

The independent [acceptance code](../examples/regression/acceptance.py) stays
outside the copied agent project. The code tasks must pass predefined behavior
checks, not merely exit successfully. Checks also restrict changed files. A Skill
is judged by its output, not an inferred activation event.

The arithmetic and greeting graders run reviewed generated Python in a bounded
subprocess with a reduced environment. This is not a security sandbox for hostile
code. Do not point this example at unreviewed arbitrary repositories or secrets.
Each attempt gets a fresh project; ordinary pytest fixtures are still shared by
the repeated-test marker.

## Export every attempt

```console
python -m pytest tests/test_agent.py --codex-record --codex-model=baseline-model --codex-recording-set=baseline-001 --codex-results=results/baseline-001.json
python -m pytest tests/test_agent.py --codex-record --codex-model=candidate-model --codex-recording-set=candidate-001 --codex-results=results/candidate-001.json
```

Use model IDs available to your account. Recording uses your existing Codex login
and model quota; no live calls happen without explicitly selecting a live mode.
Named sets are stored under `cassettes/SET/` beside each test module. An existing
named recording cannot be replaced by another record run; use a new set name.
Existing behavior without `--codex-recording-set` is unchanged, including explicit
replacement by `--codex-record`. Results files are created exclusively and never
silently overwritten. Relative result paths are relative to pytest's rootdir.

To include acceptance helpers in the comparison contract:

```ini
[pytest]
codex_grader_files =
    acceptance.py
```

Paths must name files inside pytest's root. The test module and listed helpers
are hashed at collection; changes during execution mark the report as a grader
error. List all relevant external acceptance helpers. Hashing does not discover
arbitrary transitive imports and is not cryptographic proof of an untampered run.

JSON export includes every completed repeated attempt, including failures hidden
by a passing aggregate `pass_rate` threshold. It separates passed/failed task
assertions, execution/grader errors and skips. Incomplete Codex turns and the
observed Windows unified-exec startup failure signature are execution errors.
`task_status` and `task_error_type` retain the independent acceptance outcome;
`execution_errors` separately lists recognized execution failures. A recovered
turn can therefore have `task_status="passed"` and `status="error"`. It remains
excluded from clean model comparison. A failed assertion following a startup
failure is visible too, without claiming that the model caused it.
Other environmental failures may still require review; automatic classification
is intentionally narrow. Pytest's own outcomes are not replaced by this report.
Runtime `pytest.skip()` and `pytest.xfail()` stop repetition and export a skipped
attempt; unexecuted attempts are not invented. Use ordinary assertions, rather
than xfail markers, when collecting a matched task-outcome comparison.

Each run includes requested model, CLI version, input/prompt/config hashes,
sandbox/isolation/timeout, usage and duration. Context includes Python, platform,
package version and creation time. Raw prompt text, command output and exception
messages are excluded. Project-relative changed filenames, command exit codes and
MCP tool names are included. Parameter IDs in exported case names are hashed:
pytest's default IDs can otherwise contain an entire prompt. Module/function names
and relative filenames remain readable; review reports and recordings before publishing.

## Compare one change at a time

```console
python -m pytest_codex.compare results/baseline-001.json results/candidate-001.json --factor model --output results/comparison.md --json-output results/comparison.json
```

The comparator requires matching case/attempt sets, test/helper fingerprints,
task inputs, prompt/config, Python/platform/package version and execution limits.
For `--factor model`, the CLI version must stay fixed and the requested model must
change. For `--factor cli`, the model must stay fixed and the CLI version must
change. Neither comparison substitutes an old replay for a fresh execution.
Replay-only/mixed observations are rejected. The comparator is a reporting tool:
its exit status indicates valid comparison/output, not a statistically established
upgrade decision. Any task with errors/skips is explicitly inconclusive.
The additional acceptance/health table shows both dimensions, including recovered
turns. For older reports without `task_status`, their original conservative status
is used; the comparator does not guess missing acceptance outcomes.

These checks do not capture every inherited tool version, environment variable,
managed setting or provider change. Record external tool versions separately and
control the environment. A requested model alias is not a verified frozen model
snapshot. Small repeated samples show observations, not a reliable model ranking.

## Reproduce the included pilot offline

The pilot's reviewed recordings/results and commands are documented in
[the pilot README](../examples/regression/README.md). Replay verifies historical
behavior against the acceptance checks. If a saved attempt failed, faithful replay
should reproduce that failure rather than turn the suite green. The ordinary
repository tests check this consistency without calling Codex.
