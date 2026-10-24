# Recorded behavior checks

The original observations below were recorded on Windows on 2026-10-22 with
Codex CLI 0.163.0, full configuration
isolation, workspace-write, and low reasoning effort. Real calls use an existing
Codex login. Default tests and every PR replay offline.

| Scenario | Model | Fresh attempts | Result |
|---|---|---:|---|
| This project's own AGENTS release checklist | gpt-6-luna | 2 | 2/2; exact JSON, no file edits |
| Same checklist | gpt-6.1-sol | 2 | 2/2; exact JSON, no file edits |
| Local stdio MCP catalog | gpt-6-luna | 1 | Correct lookup arguments and result, no shell substitution |
| brief-release project Skill | gpt-6-luna | 1 | Exact RELEASE.md content; source input unchanged |
| uv convention (earlier, prompt-assisted recording) | CLI default at recording time | 1 | uv exit 0, dependency file changed, legacy untouched |

The two-attempt checks exercise repetition and model selection. They are too small
to support a reliability estimate or model ranking. Model IDs and account access
can change; these recordings are historical observations, not availability promises.
The Skill test verifies the resulting artifact, not a `used_skill` event.

Replay the current examples, including historical observations and the synthetic
Desktop example, without a CLI:

```console
python -m pytest examples --codex-bin=not-installed -q
```

Check the new examples against the recorded CLI version, still offline:

```console
python -m pytest examples/test_project_rules.py examples/test_mcp.py examples/test_skill.py --codex-cli-version=0.163.0 --codex-bin=not-installed -q
```

To gather fresh evidence, explicitly replace the last options with `--codex-record`.
This invokes six model turns. Each test uses a fresh project copy; other fixtures
are shared within a repeated item. Review outputs before publishing a new recording.

Public recordings replace home/project path prefixes, anonymize thread IDs, and
omit nonbehavioral startup stderr. Events, tool results, assertions, and decoded
file payloads were checked before publication. Original startup diagnostics stay
private. This is an audit of these files, not a promise of automatic secret removal.

## Task acceptance versus instruction-file evidence

The original `examples/test_conventions.py` prompt explicitly supplies `uv add`
and its flags. The five-task pilot's `test_dependency_declaration` also supplies
the pinned command. These are **prompt-assisted task acceptance** observations:
they check execution and artifacts, but a pass does not isolate the AGENTS.md
instruction path. A failed task alone likewise does not show that guidance was
missing or ignored. Historical recordings and pilot results are unchanged.

In `examples/test_project_rules.py`, the prompt asks only for the release
checklist. The exact JSON and no-command requirements come from the project
AGENTS.md input. The new [unprompted dependency example](../examples/test_unprompted_rules.py)
similarly uses a goal-only prompt containing neither `uv` nor `pip`; only its
AGENTS.md override supplies the exact pinned command, flags and protected paths.
We call this **unprompted instruction-file receipt/following evidence** to
distinguish it from prompt-assisted acceptance: the prompt's tool/answer hint has
been removed, rather than task acceptance being redefined.

This is observed behavior consistent with receiving and following the project
instructions, not direct instrumentation of file receipt. The dependency goal
still names the requested package/version. There is no matched no-AGENTS control,
and a model could know common conventions independently; one success cannot
establish causality or a general reliability rate.

The new example is a separate source addition after 0.4.0. It does not alter the
published 0.1.0-0.4.0 archives, existing cassettes or regression reports. Its local
acceptance code is outside the copied project, checks the pinned declaration and
exact successful command, and rejects unrelated file changes.

[The new observation](../examples/unprompted-rules/README.md) was collected on
2026-10-24 with CLI 0.163.0, requested `gpt-6.1-sol`, low effort, full configuration
isolation and Windows workspace-write/elevated sandbox. A no-model preflight
passed first. One fresh attempt passed; the exact prescribed command exited 0,
the pinned declaration was verified, and only `pyproject.toml` changed. Offline
replay also passed with `--codex-bin=not-installed`. No attempt was rerun or
replaced. The original startup warning remains private; only the nonbehavioral
unsupported PowerShell shell-snapshot notice was omitted from public stderr.

This clarification follows [community methodological feedback](https://github.com/openai/codex/discussions/56181#discussioncomment-19153358),
tracked in [issue #4](https://github.com/Czj027/pytest-codex/issues/4).
The commenter identifies as an AI developer account and states they have not run
or integrated this project. This is feedback, not independent adoption. We did
not download or run their external tool.

## CLI protocol compatibility

The daily `Latest CLI contract` workflow installs the latest published CLI and
executes it against a loopback-only canned Responses endpoint. It checks JSONL
completion, final message, and token parsing without a login or model service.
This catches CLI/protocol integration regressions. It does not test current model
behavior, MCP selection, or Skill compliance; those require an explicit live run.

The contract uses [custom-provider no-auth support](https://learn.chatgpt.com/docs/auth)
and the [Responses gateway contract](https://learn.chatgpt.com/docs/enterprise/gateway-compatibility).
The MCP example follows [stdio transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
and [tool messages](https://modelcontextprotocol.io/specification/2025-06-18/server/tools),
configured through [Codex MCP settings](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
