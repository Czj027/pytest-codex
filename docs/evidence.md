# Recorded behavior checks

Recorded on Windows on 2026-10-22 with Codex CLI 0.163.0, full configuration
isolation, workspace-write, and low reasoning effort. Real calls use an existing
Codex login. Default tests and every PR replay offline.

| Scenario | Model | Fresh attempts | Result |
|---|---|---:|---|
| This project's own AGENTS release checklist | gpt-6-luna | 2 | 2/2; exact JSON, no file edits |
| Same checklist | gpt-6.1-sol | 2 | 2/2; exact JSON, no file edits |
| Local stdio MCP catalog | gpt-6-luna | 1 | Correct lookup arguments and result, no shell substitution |
| brief-release project Skill | gpt-6-luna | 1 | Exact RELEASE.md content; source input unchanged |
| uv convention (earlier recording) | CLI default at recording time | 1 | uv exit 0, dependency file changed, legacy untouched |

The two-attempt checks exercise repetition and model selection. They are too small
to support a reliability estimate or model ranking. Model IDs and account access
can change; these recordings are historical observations, not availability promises.
The Skill test verifies the resulting artifact, not a `used_skill` event.

Replay all seven observations (five pytest items) without a CLI:

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
