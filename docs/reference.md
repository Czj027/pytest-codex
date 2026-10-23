# Reference

Test what Codex actually does, using ordinary pytest assertions.

Record a real execution once, then replay events and file changes in CI without
a Codex installation, credentials, network access, or model calls.
Test conventions, `AGENTS.md`, Skills, MCP calls and config variations.

[中文参考](reference.zh-CN.md) · [Home](../README.md) · MIT · Python 3.10+ · pytest 7+

The **0.3.0 source release** adds `--codex-recording-set`,
`--codex-results`, `codex_grader_files` and `python -m pytest_codex.compare`.
See the [fresh task regression guide](regression.md) for contracts and examples.
The PyPI instructions below refer to the published 0.2.0 release.

## Quick start

Version **0.2.0** includes the pytest fixture, offline replay, pass-rate checks
and CLI version validation.
Install it from PyPI:

```console
python -m pip install pytest-codex
```

Configure a small test project and write a normal pytest test:

```toml
[tool.pytest.ini_options]
codex_project = "sample_repo"
```

```python
def test_dependency_conventions(codex):
    run = codex.exec("Add requests as a project dependency.")
    assert run.succeeded, run
    assert run.ran("uv add", ok=True), run
    assert not run.ran("pip install"), run
    assert run.modified("pyproject.toml"), run
    assert not any(path.startswith("legacy/") for path in run.changed_files), run
```

```console
# Explicit opt-in to model usage. Requires Git, Codex CLI and Codex login.
python -m pytest tests/test_conventions.py --codex-record
# Offline default. Missing or stale recordings fail; Codex is never called.
python -m pytest tests/test_conventions.py
```

Each `exec` copies the input project to a fresh temporary directory and initializes
a Git baseline. `files={"AGENTS.md": "..."}` overrides files before the baseline
and input fingerprint. The original project is never the execution working directory.

## Included real recording

```console
python -m pytest examples/test_conventions.py --codex-bin=not-installed -q
```

The included cassette was recorded using real Codex execution on Windows. It
demonstrates `uv add --frozen requests` changing `pyproject.toml` without changing
`legacy/`. `--frozen` avoids resolution and environment installation in this
example; this is not an installation test. Replay verifies a historical observation,
not today's model behavior. Re-record when evaluating a model or CLI upgrade.
The example also disables managed-Python discovery/downloads and uses a project-local
uv cache. On Windows, place a sandbox-readable Python interpreter and uv on PATH
before recording. A user-only Python installation may be inaccessible to the sandbox.

## API

```python
run = codex.exec(
    "Fix the failing add function.",
    project="sample_repo",                  # relative to pytest root, or absolute
    files={"AGENTS.md": "Do not change legacy/.\n"},
    model=None,                             # CLI default, or explicit model name
    sandbox="workspace-write",
    config={"model_reasoning_effort": "low"},
    timeout=120,
)
```

| Query | Meaning |
|---|---|
| `run.commands` | Command items with `.command`, `.raw_command`, `.output`, `.exit_code`, `.ok` |
| `run.ran(pattern, ok=None)` | Substring or regex after shell wrappers; `ok=True` requires exit 0, `ok=False` a known nonzero exit |
| `run.modified(glob)` / `run.added(glob)` / `run.deleted(glob)` | Before/after file hashes, including shell edits |
| `run.changed_files` | Sorted relative POSIX paths of added, modified and deleted files |
| `run.read("path")` | UTF-8 text inside this execution's project copy |
| `run.messages` / `run.final_message` | Agent messages / last message |
| `run.mcp_calls` / `run.called_mcp(server, tool=None)` | MCP call items / presence of a server/tool call |
| `run.usage` / `run.tokens` | Token usage; `.total` = input + output, without adding cached input again |
| `run.succeeded` | Exit code 0, a completed turn and no failed turn |
| `run.replayed` / `run.project` | Whether replayed / temporary project path |

Use `assert condition, run` for a concise trace on failure. `succeeded` means the
CLI turn completed, **not** that each command succeeded or the task was achieved.
Check exit codes and file contents separately. Warning items do not fail a turn.
`called_mcp` checks presence, not the result's success. No `used_skill` method is
provided because traces do not reliably establish it.

Globs use case-sensitive `fnmatch` on relative POSIX paths; `*` also matches `/`.
Snapshots track file contents, not empty directories or mode-only changes.
Symlinks and junctions are rejected to avoid access outside the copied tree.

## Repeated runs

```python
import pytest

@pytest.mark.codex(runs=5, pass_rate=0.8, project="sample_repo")
def test_reliability(codex):
    run = codex.exec("Add requests as a dependency.")
    assert run.ran("uv add"), run
```

All five attempts run; at least four must pass. `codex.attempt` is 1-based.
Each attempt/call has a separate cassette and fresh execution project. Assertions
and `pytest.fail` count against the rate. Unexpected exceptions stop immediately;
skip/xfail retain pytest control flow. Terminal output and JUnit properties report
passing attempts and total attempts.

The body is repeated within **one pytest item**: other fixtures and setup/teardown
are shared across attempts. Keep mutable state inside the body or execution project.
Synchronous pytest functions and parametrization are supported; async and unittest
repeated tests are not supported. Avoid combining this marker with retry plugins.
Replay repeats historical observations, not fresh reliability experiments.

## Caveats

### Modes and configuration

| Option | Behavior |
|---|---|
| default / `--codex-mode=replay` | Replay; fail if missing or stale; never call Codex |
| `--codex-record` / `--codex-mode=record` | Run and replace recordings; uses model quota |
| `--codex-live` / `--codex-mode=live` | Run without recording; uses model quota |
| `--codex-mode=auto` | Replay existing; run and record missing only; stale recordings fail |
| `--codex-bin=PATH` | Codex executable; unused in replay |
| `--codex-model=NAME` | Default model, overridden by `exec(model=...)` |
| `--codex-cli-version=VERSION` | Require recording metadata to match this CLI version; stays offline |
| `--codex-check-cli` | Compare against installed `codex --version`; never calls a model |

```toml
[tool.pytest.ini_options]
codex_project = "sample_repo"
codex_isolation = "full"
codex_timeout = "300"
codex_model = "your-model-id"       # optional, required for version-checked runs
codex_cli_version = "0.163.0"       # optional offline version pin
```

`none` inherits user configuration; `config` adds `--ignore-user-config`; `full`
(default) also uses temporary `CODEX_HOME`, copying only `auth.json` from the
parent home. That temporary copy is removed on exit or timeout. Noninteractive
runs require `approval_policy="never"`; Windows full mode also defaults to
`windows.sandbox="elevated"`. Windows needs an existing working Codex sandbox.
Windows live project copies use the user's pytest-codex cache rather than pytest's
user-only temporary parent directories; copies are removed during fixture teardown.
Use an explicit `config` override to select a sandbox implementation permitted
by your machine. The plugin does not install or disable OS sandboxing.

These are **configuration isolation levels**, not hermetic security boundaries:
managed settings, global `.agents/skills`, environment variables and system tools
can still affect execution. The CLI sandbox defaults to `workspace-write`; wider
access must be explicitly requested. A copied project alone is not a security sandbox.

## Cassettes and privacy

Cassettes live beside the test module under
`cassettes/<module-slug>/<test-slug>[-attempt-N]-call-N.json`.
The fingerprint covers prompt, requested model, config, sandbox, isolation and
input file contents. `--codex-cli-version` (or ini `codex_cli_version`) compares
recorded CLI metadata with a committed version pin, entirely offline.
`--codex-check-cli` instead runs the installed CLI's `--version` and checks against
it; it never starts a model turn. Combining both also checks the installed version
against the pin. Version-checked runs require an explicit model (argument, option
or ini `codex_model`). Version checks run before replayed file writes and before a
record/live model call. Update the pin and re-record intentionally when upgrading.
Without either option, old recordings remain compatible and replay needs no CLI.
An unchanged model ID cannot reveal provider-side model updates.
Timeout and inherited environment are not fingerprinted.

Binary changes are stored as base64 and deleted files are removed on replay.
Command text is data, never executed by replay. Paths and payloads are validated
before applying the recording. Base64 is not encryption.

Only temporary project and home prefixes in event strings are replaced with
`<PROJECT>` and `<HOME>`. **Review recordings before committing:** command output,
file payloads and MCP results can contain secrets and are not automatically scrubbed.
Use a small, sanitized project. Copies exclude `.git`, common environments/caches,
`cassettes`, `dist` and `build`. For a source inside a Git repository, Git-ignored
untracked files are excluded too, including nested rules and negations. A tracked
file stays an input even if an ignore pattern matches it. An explicitly selected
project under a Git-ignored parent (for example a temporary test fixture) is treated
as a standalone fixture; ancestor ignore patterns do not remove all its inputs.
`files={...}` overrides
are explicit inputs and can add otherwise excluded files; never put secrets there.

## Development

```console
python -m pip install -e . ruff build twine
python -m pytest -q
python -m pytest examples --codex-bin=not-installed -q
python -m ruff check src tests examples
python -m ruff format --check src tests examples
python -m build
python -m twine check dist/*
```

CI defines Python 3.10–3.13 × Linux/macOS/Windows and a pytest 7.0 compatibility job.
Ordinary CI tests replay or use a local fake CLI. The daily latest-CLI workflow
uses the real CLI against a local canned Responses endpoint. Neither needs model
calls or Codex login. See [evidence](evidence.md) for the distinction between
protocol checks and fresh behavior, and [the opt-in live template](ci/live-examples.yml).

Independent community project, not an official OpenAI product.
