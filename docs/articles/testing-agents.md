# Does your AGENTS.md actually work?

“Use uv, not pip” expresses an intention. To check whether an agent followed it,
inspect the command it executed. A final “done” message does not prove a command
succeeded or that protected files stayed unchanged.

pytest-codex makes that behavior an ordinary pytest test:

```python
def test_dependency_rule(codex):
    run = codex.exec("Add requests as a project dependency.")
    assert run.ran("uv add", ok=True), run
    assert not run.ran("pip install"), run
    assert run.modified("pyproject.toml"), run
    assert not any(path.startswith("legacy/") for path in run.changed_files), run
```

`ok=True` requires exit zero. File queries compare before/after contents, including
changes made through shell tools. Each execution uses a new project copy. Copies
respect the source Git repository's ignore rules and exclude common environments,
caches and recordings; review your test inputs as well.

## Record once, replay on ordinary PRs

Recording explicitly invokes a logged-in Codex CLI and saves events and file changes.
Default execution only replays:

```console
python -m pytest tests/agent --codex-record
python -m pytest tests/agent --codex-bin=not-installed
```

The second command intentionally names a missing CLI. Passing without it shows the
test does not need a local Codex login or model call. Missing/stale recordings fail
instead of silently spending quota. Replay checks a historical observation, not
today's model behavior. Re-record when evaluating an upgrade.

Version 0.2.0 adds an offline CLI version pin and an installed-version check.
Version-checked runs require an explicit model so an unintentional default-model
change is not hidden. An unchanged model ID cannot detect server-side updates;
fresh observations still require an explicit live run.

## Commands, MCP calls, Skills and project rules

The repository includes a local stdio MCP catalog example. Its test checks the tool
name, arguments, returned value and final answer. Another example invokes a project
Skill and checks the generated RELEASE.md. There is no speculative `used_skill()`
query: the test asserts the resulting behavior.

We also test this project's own AGENTS.md. On 2026-10-22, two models each passed two
fresh release-checklist attempts. That small sample exercises model selection and
repetition; it does not establish a reliability estimate or model ranking.
`runs` and `pass_rate` support larger experiments, but replaying saved attempts
does not create additional observations.

## Try it

Version 0.2.0 is published on PyPI. Install it with
`python -m pip install pytest-codex`. Clone the repository to try the included
recordings and example tests.

- [Repository and quick start](https://github.com/Czj027/pytest-codex)
- [Recorded evidence and limits](../evidence.md)
- [Add a behavior test to a Python/MCP project](../integration.md)

Before publishing a recording, inspect command output, tool results and decoded
file payloads. Path replacement is not general secret redaction; base64 is not
encryption. Use offline replay on ordinary PRs and explicit real runs for new evidence.
