# Codex Desktop

Available in the **0.4.0 development branch**. PyPI 0.3.0 does not contain these
APIs. Install this checkout with `python -m pip install .` to try them.

## Check an existing desktop task without another model call

Supply one local session JSONL file explicitly. Nothing searches your history,
resumes a conversation, reads credentials, or calls a model.

```console
python -m pytest_codex.desktop list /path/to/rollout-session.jsonl
```

Select a `turn_id` from that list. A file containing multiple turns requires a
selection; it never silently picks the newest successful task.

```python
def test_desktop_task(codex):
    run = codex.from_desktop_session("/path/to/rollout-session.jsonl", turn_id="TURN_ID")
    assert run.succeeded, run
    assert run.ran("uv add", ok=True), run
    assert run.called_mcp("demo", "lookup"), run
    # Check coverage before asserting that an action never occurred.
    assert run.commands_complete, run.unsupported_items
    assert not run.ran("pip install"), run
```

Outside pytest, use `from pytest_codex import from_desktop_session`. The imported
`DesktopRun` is a `Run` subtype: commands, MCP calls and final messages use the
same queries. `succeeded` means a completed historical turn, not independent task
acceptance. An aborted or unfinished turn is unsuccessful. Unsupported tool
items and opaque code-mode calls make coverage incomplete; negative command/MCP
queries then raise instead of silently claiming absence.

`usage_complete` reports whether an attributed cumulative `turn_token_usage`
record was available. Its last snapshot is used once, without double-counting
token-count notifications or another turn's usage. When unavailable, token
counts are zero placeholders, not evidence of free execution. Per-request and
thread totals are not substituted for per-turn usage.

## Historical observations and file evidence

Logs alone do not contain trustworthy before/after project snapshots. Imported
observations therefore have `project=None`, `diff=None`, and
`file_state="unavailable"`. `changed_files`, `modified`, `added`, `deleted` and
`read` raise an explicit error. `reported_changed_files` contains only recorded
FileChange path claims; shell edits might not appear there. Current Git changes
are never attributed retrospectively to a particular desktop turn.

To test actual file artifacts and task acceptance, use the existing live/record
fixtures, which capture their own before/after files. An imported observation
cannot be saved as a full execution cassette or used as evidence of a fresh
model/CLI regression comparison.

## Export a selected observation for offline tests

```console
python -m pytest_codex.desktop import-session /path/to/rollout-session.jsonl --turn-id TURN_ID --output observation.json --include-content
```

Then use `codex.from_desktop_session("observation.json")` in CI. Or call
`run.save("observation.json", include_content=True)` from Python. The distinct
event-only schema preserves the selected observation and its source digest; it
never restores or executes recorded commands/files. Existing outputs are never
overwritten. Keep the `.json` extension for exports, `.jsonl` for source logs.

Export deliberately requires content opt-in: command arguments, outputs, MCP
results and final replies may contain private information. System/developer/user
messages, rules, reasoning, raw tool code and source metadata are omitted.
Project/home paths and common credential patterns/keys are redacted. These
filters do not recognize every secret or personal detail: inspect the exported
text before committing it. No original session or private capture is included
in this package. The [runnable example](../examples/desktop/test_observation.py)
uses synthetic data only.

## Use the desktop-bundled engine for a new execution

An explicit option reuses the existing noninteractive runner:

```console
python -m pytest_codex.desktop engine
python -m pytest tests/test_conventions.py --codex-record --codex-desktop
```

The diagnostic only locates the executable and runs `--version`. New record/live
executions consume model quota and need compatible login access. `--codex-desktop`
does not import Desktop settings, resume GUI tasks or control the app window.
Default replay stays offline and does not discover or launch any engine (unless
you explicitly request `--codex-check-cli`).

Discovery is best-effort: macOS `/Applications/Codex.app` or
`~/Applications/Codex.app`, and the current Windows `OpenAI.Codex` Appx package.
The bundled executable layout is an implementation detail and may change.
For other installations, set `PYTEST_CODEX_DESKTOP_BIN` to an absolute executable
path, or use `--codex-bin /explicit/path` instead of `--codex-desktop`. Multiple
installs require an explicit path. Linux/custom bundles use explicit paths.

Existing config/auth isolation still applies. Login stored only in a desktop
credential store may be unavailable to an isolated child; no auth migration or
weaker isolation is attempted automatically. Errors do not silently switch
engines, credentials or model providers. No app-server listener is started.

## Compatibility boundary

The source adapter supports the `session_meta`, `task_started`, `task_complete`,
`turn_aborted`, canonical `item_completed` and attributed `token_usage_record`
shapes observed in Desktop's 0.163.0-alpha.11 engine logs. Malformed lines and
unsupported required structures fail explicitly. Imports are limited to 256 MiB.
This is a local log adapter, not a stable official history-export API.

OpenAI documents [read-only history methods and version-specific schemas](https://learn.chatgpt.com/docs/app-server)
for app-server. This implementation reads only explicitly supplied local files;
it does not attach to a running Desktop process or assume its internal JSONL
format will remain stable. Windows discovery/version and read-only import have
been checked locally; macOS discovery uses synthetic tests, not an installed
macOS Desktop test. The local Windows bundled engine also passed the JSONL
runner contract against a localhost canned endpoint, with an empty login home
and no real model service. Cross-platform CI tests the parser and runner with synthetic
fixtures, not fresh model execution.
