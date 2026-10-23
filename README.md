# pytest-codex

[![PyPI](https://img.shields.io/pypi/v/pytest-codex)](https://pypi.org/project/pytest-codex/)
[![Tests](https://github.com/Czj027/pytest-codex/actions/workflows/tests.yml/badge.svg)](https://github.com/Czj027/pytest-codex/actions/workflows/tests.yml)
[![Python](https://img.shields.io/pypi/pyversions/pytest-codex)](https://pypi.org/project/pytest-codex/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Your `AGENTS.md` says “use uv.” Did Codex actually use it?**

Turn agent instructions into pytest assertions. Check the commands Codex ran,
the files it changed, and the MCP tools it called. Record a real run once; replay
it in CI with **zero model calls**.

![pytest catches pip install where uv add was required](https://raw.githubusercontent.com/Czj027/pytest-codex/main/docs/assets/failure.gif)

*Illustration: a synthetic command trace, rendered from actual pytest failure output.
No model call was used to make this image. A separate [real recording](examples/test_conventions.py)
is included and passes offline.*

[中文](README.zh-CN.md) · [Full reference](docs/reference.md)

**0.3.0** adds [fresh task regression comparisons](docs/regression.md), available
from [PyPI](https://pypi.org/project/pytest-codex/0.3.0/) and the GitHub release.

## Start with one test

```console
python -m pip install --upgrade pytest-codex
```

Version 0.3.0 includes version-checked replay and fresh task comparison reports.

Point pytest at the small project you want Codex to work on:

```toml
# pyproject.toml
[tool.pytest.ini_options]
codex_project = "sample_repo"
```

```python
# tests/test_conventions.py
def test_agent_follows_project_rules(codex):
    run = codex.exec("Add requests as a project dependency.")
    assert run.ran("uv add", ok=True), run
    assert not run.ran("pip install"), run
    assert run.modified("pyproject.toml"), run
    assert not run.modified("legacy/*"), run
```

```console
# Record once — needs Codex CLI + login and uses model quota.
python -m pytest tests/test_conventions.py --codex-record
# Replay in CI — no Codex binary, credentials, or model calls.
python -m pytest tests/test_conventions.py
```

Each call gets a fresh project copy. Shell edits count as file changes too.
Missing or stale recordings fail with a re-record instruction; the default mode
never falls back to a paid call.

## Check reliability across attempts

```python
import pytest

@pytest.mark.codex(runs=5, pass_rate=0.8)
def test_dependency_convention(codex):
    run = codex.exec("Add requests as a dependency.")
    assert run.ran("uv add", ok=True), run
```

Record five attempts, require four to pass, and save each one separately. Replay
checks those saved observations; re-record to measure a new model or CLI version.

## Why a pytest plugin?

- **A linter checks instruction text.** This checks the commands and file changes
  from an execution, including edits made through shell tools.
- **A one-off agent script needs its own test machinery.** This fits pytest
  fixtures, parametrization, failure reports, and your existing CI.
- **Calling a model on every PR spends quota.** Checked-in recordings let ordinary
  PR checks replay without model calls. Use explicit live runs for fresh evidence.

## Try the included recording

```console
git clone https://github.com/Czj027/pytest-codex.git
cd pytest-codex
python -m pip install .
python -m pytest examples --codex-bin=not-installed -q
```

This is a real Windows recording: successful `uv add`, changed dependency
declarations, and untouched legacy code. The deliberately missing CLI proves
the example can replay without launching Codex.

The included recordings also cover our own [project rules](AGENTS.md) with two
models and two attempts each, a [local MCP call](examples/test_mcp.py), and a
[Skill's file output](examples/test_skill.py). These are small smoke checks,
not estimates of general model reliability. See [recording evidence](docs/evidence.md).

## Catch stale recordings

Pin both the model and the CLI version for portable offline replay:

```toml
[tool.pytest.ini_options]
codex_model = "your-model-id"
codex_cli_version = "0.163.0"
```

Use `--codex-check-cli` locally to compare with the installed `codex --version`.
Version or input mismatches fail before applying recorded file changes; strict
checks require an explicit model. Default replay stays offline and needs no CLI.
An unchanged model ID cannot detect a provider updating that model; re-record
when checking current behavior.

The [daily latest-CLI check](.github/workflows/cli-compat.yml) uses a local canned
response endpoint without login or model calls. For fresh behavior checks, use the
[opt-in live CI template](docs/ci/live-examples.yml).

## Learn more

| Need | Read |
|---|---|
| Commands, files, messages, MCP calls, tokens | [Run API](docs/reference.md#api) |
| Record / replay / live / auto modes | [Configuration](docs/reference.md#modes-and-configuration) |
| Repeat semantics and fixture sharing | [Repeated runs](docs/reference.md#repeated-runs) |
| Windows setup, isolation, privacy, stale recordings | [Caveats](docs/reference.md#caveats) |
| Contributing and local checks | [Development](docs/reference.md#development) |
| Adding behavior tests to another project | [Integration guide](docs/integration.md) |
| Motivation and a worked example | [Article](docs/articles/testing-agents.md) |

`run.succeeded` means the CLI turn completed; use command status and file
assertions to check the work. Recordings may contain sensitive output, so review
them before committing. MIT licensed; independent community project.
