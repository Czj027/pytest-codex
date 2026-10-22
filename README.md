# pytest-codex

[![PyPI](https://img.shields.io/pypi/v/pytest-codex)](https://pypi.org/project/pytest-codex/)
[![Tests](https://github.com/Czj027/pytest-codex/actions/workflows/tests.yml/badge.svg)](https://github.com/Czj027/pytest-codex/actions/workflows/tests.yml)
[![Python](https://img.shields.io/pypi/pyversions/pytest-codex)](https://pypi.org/project/pytest-codex/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Your `AGENTS.md` says “use uv.” Did Codex actually use it?**

Turn agent instructions into pytest assertions. Check the commands Codex ran,
the files it changed, and the MCP tools it called. Record a real run once; replay
it in CI with **zero model calls**.

![pytest catches pip install where uv add was required](https://raw.githubusercontent.com/Czj027/pytest-codex/main/docs/assets/failure.png)

*Illustration: a synthetic command trace, rendered from actual pytest failure output.
No model call was used to make this image. A separate [real recording](examples/test_conventions.py)
is included and passes offline.*

[中文](README.zh-CN.md) · [Full reference](docs/reference.md)

## Start with one test

```console
python -m pip install pytest-codex
```

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
python -m pytest examples/test_conventions.py --codex-bin=not-installed -q
```

This is a real Windows recording: successful `uv add`, changed dependency
declarations, and untouched legacy code. The deliberately missing CLI proves
the example can replay without launching Codex.

## Learn more

| Need | Read |
|---|---|
| Commands, files, messages, MCP calls, tokens | [Run API](docs/reference.md#api) |
| Record / replay / live / auto modes | [Configuration](docs/reference.md#modes-and-configuration) |
| Repeat semantics and fixture sharing | [Repeated runs](docs/reference.md#repeated-runs) |
| Windows setup, isolation, privacy, stale recordings | [Caveats](docs/reference.md#caveats) |
| Contributing and local checks | [Development](docs/reference.md#development) |

`run.succeeded` means the CLI turn completed; use command status and file
assertions to check the work. Recordings may contain sensitive output, so review
them before committing. MIT licensed; independent community project.
