# Add a behavior check to a Python project

Start with one small, nonsecret fixture project. For MCP integration use
[examples/mcp_repo](../examples/mcp_repo) and [test_mcp.py](../examples/test_mcp.py)
as an executable starting point. The server uses only Python's standard library.
`catalog.lookup` is read-only and needs no remote account.

1. Install pytest-codex (version pinning below requires 0.2.0, currently available
   from this source checkout). Copy the MCP fixture into `tests/agent/project/`.
2. Copy the test into `tests/agent/test_catalog.py` and point its marker's `project`
   to that fixture. Keep an explicit model ID available to your Codex account.
3. Record intentionally:

   ```console
   python -m pytest tests/agent/test_catalog.py --codex-record
   ```

4. Review every event, tool result and decoded file payload in
   `tests/agent/cassettes/`. Publish only reviewed data. Commit the test, fixture
   and recording together. A recording includes more than stdout and is not an
   encrypted secret store.
5. Replay on every PR:

   ```yaml
   # Inside an existing GitHub Actions job, after checkout and Python setup:
   - run: python -m pip install pytest-codex
   - run: python -m pytest tests/agent --codex-bin=not-installed -q
   ```

This CI needs neither Codex credentials nor a CLI. It checks the saved observation.
Re-record explicitly when checking a changed model, CLI or MCP implementation.

For version-aware replay, commit `codex_cli_version = "0.163.0"` in pytest's ini
options, update that pin when intentionally upgrading, and keep an explicit model.
Locally `--codex-check-cli` checks the installed version without a model call.
Model changes and copied fixture input changes also invalidate recordings.
Do not place secrets in fixtures just because their directory is Git-ignored.

For your own MCP server replace the `mcp_servers.catalog.*` config with your
server's stdio command, and assert on tool arguments and returned values as well
as `run.called_mcp(...)`. Presence alone does not prove success. For a Skill,
assert the files or messages it should produce as in [test_skill.py](../examples/test_skill.py).

For fresh scheduled behavior checks, the [live workflow template](ci/live-examples.yml)
is off by default and requires a dedicated, logged-in self-hosted runner plus an
explicit repository variable. Do not place personal auth files in this repository.
The built-in [daily protocol check](../.github/workflows/cli-compat.yml) uses no login
or model calls and is suitable for a public hosted runner.
