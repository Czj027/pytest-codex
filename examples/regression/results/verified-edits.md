# Serial verified-edit follow-up

2026-10-23, CLI 0.163.0, requested gpt-6-luna, low reasoning effort,
workspace-write/full isolation on Windows/Python 3.13.14. Fixed six fresh turns,
one collector process, no retries. [Per-attempt JSON](luna-verified-live.json).

| Task | Independent acceptance | Recognized execution errors |
|---|---:|---:|
| Arithmetic average fix | 3/3 passed | 0 |
| Greeting fix / protected legacy | 3/3 passed | 0 |

The new prompts explicitly require editing the actual file, rather than printing
an editing script, and ask for readback, diff inspection and a behavior check before
claiming completion. The external acceptance helper is unchanged and remains
outside the agent's copied project. Acceptance checks actual artifacts and behavior;
this report does not claim that every self-check request was followed perfectly.

All six attempts completed and changed the intended implementation. The trusted
subprocess verified fractional/negative averages and empty-input errors, or the
trimmed greeting and protected legacy sentinel. The six events/file payloads were
reviewed; public recordings anonymize thread IDs and omit startup stderr while
retaining commands, item/turn events, usage and artifacts. Originals stay private.

This is a small workflow follow-up, **not** a controlled estimate of prompt effect
or a model ranking: prompts and collection scheduling both changed, and task IDs
differ. Do not combine its six successes with the original model comparison or
replace its historical failures. The original 30-turn evidence remains intact.

## Reproduce offline

From a 0.3.0 candidate source checkout:

```console
python -m pytest -c examples/regression/verified.ini examples/regression/verified_edits.py --codex-model=gpt-6-luna --codex-recording-set=luna-verified-20261023 --codex-bin=not-installed -q
```

Expected: two passing pytest items, three attempts each; no CLI, login or model call.
Ordinary repository tests also check that these six outcomes reproduce offline.

## Collect a new sample explicitly

Use a sandbox-readable Python interpreter on PATH and the pinned, logged-in CLI.
Run this command by itself, with new set/output names; it requests six model turns:

```console
python -m pytest -c examples/regression/verified.ini examples/regression/verified_edits.py --codex-record --codex-model=gpt-6-luna --codex-recording-set=YOUR-NEW-VERIFIED-SET --codex-results=results/YOUR-NEW-VERIFIED-SET.json -q
```

Keep all outcomes and review recordings before sharing. This is opt-in; no scheduled
or automatic retry loop is installed.
