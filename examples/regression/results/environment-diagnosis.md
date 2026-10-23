# Windows sandbox startup diagnosis

2026-10-23, Codex CLI 0.163.0, isolated CODEX_HOME per launch,
`windows.sandbox="elevated"`, workspace-write. No model endpoint, model turn or
quota was used. [All 16 probe results](sandbox-probes.json).

| Launch mode | Attempts | Actual write/readback passed | Startup errors |
|---|---:|---:|---:|
| Serial | 8 | 8 | 0 |
| Two concurrent processes | 8 | 4 | 4 (1326) |

The fixed schedule was four serial launches, four launches in two concurrent
pairs, then the same block again. Each launch used a fresh copied fixture project
and isolated home. Its Python subprocess wrote `probe.txt`, printed a marker and
exited; the parent checked marker, exit status and the actual file content. No
attempt was retried. Projects/homes were removed afterwards.

Representative command (replace the interpreter with a sandbox-readable path):

```console
codex -c windows.sandbox="elevated" -c sandbox_mode="workspace-write" sandbox PYTHON -I -B -c "from pathlib import Path; Path('probe.txt').write_text('ok'); print('PROBE_OK')"
```

The concurrent failures reproduce the original `CreateProcessWithLogonW failed:
1326` symptom without a model. Concurrency is an observed trigger in this local
configuration; this experiment does not identify the underlying Windows account
or credential mechanism, nor prove that serial execution can never fail.

For this CLI/sandbox combination, collect live cohorts serially in one pytest
process, without xdist or concurrent collector terminals. Replay can still run
offline without this native sandbox. The plugin does not enforce a machine-wide
lock across independent processes. No global configuration, Windows account,
permissions, credentials or security boundary was changed.

Current [official Windows sandbox documentation](https://learn.chatgpt.com/docs/windows/windows-sandbox)
describes native sandbox implementations and troubleshooting. The pilot remains
pinned to its original CLI/elevated implementation to avoid silently changing the
experiment's execution contract.
