# pytest-codex

[![PyPI](https://img.shields.io/pypi/v/pytest-codex)](https://pypi.org/project/pytest-codex/)
[![Tests](https://github.com/Czj027/pytest-codex/actions/workflows/tests.yml/badge.svg)](https://github.com/Czj027/pytest-codex/actions/workflows/tests.yml)
[![Python](https://img.shields.io/pypi/pyversions/pytest-codex)](https://pypi.org/project/pytest-codex/)

**你在 `AGENTS.md` 里写了“用 uv”，Codex 真的照做了吗？**

把 agent 规则写成 pytest 断言，检查实际命令、文件改动和 MCP 调用。
真实执行录一次，CI 回放时 **不调用模型**。

![pytest 检出本应使用 uv 却执行 pip 的行为](https://raw.githubusercontent.com/Czj027/pytest-codex/main/docs/assets/failure.png)

*图中是合成命令轨迹产生的真实 pytest 失败输出，制作时没有调用模型。
项目另附一份真实执行、可离线通过的 [录制示例](examples/test_conventions.py)。*

[English](README.md) · [完整中文参考](docs/reference.zh-CN.md)

## 从一个测试开始

```console
python -m pip install pytest-codex
```

```toml
# pyproject.toml：指定让 Codex 操作的小项目
[tool.pytest.ini_options]
codex_project = "sample_repo"
```

```python
def test_agent_follows_project_rules(codex):
    run = codex.exec("Add requests as a project dependency.")
    assert run.ran("uv add", ok=True), run
    assert not run.ran("pip install"), run
    assert run.modified("pyproject.toml"), run
    assert not run.modified("legacy/*"), run
```

```console
# 真实录制，需要已登录的 Codex CLI，会消耗额度
python -m pytest tests/test_conventions.py --codex-record
# 默认离线回放，不需要 Codex 程序或登录信息
python -m pytest tests/test_conventions.py
```

每次调用使用新的项目副本；通过 shell 引起的文件变化同样能检测。
录制缺失或输入发生变化时直接失败，默认模式不会偷偷转为付费执行。

## 多跑几次，看通过率

```python
import pytest

@pytest.mark.codex(runs=5, pass_rate=0.8)
def test_dependency_convention(codex):
    run = codex.exec("Add requests as a dependency.")
    assert run.ran("uv add", ok=True), run
```

跑 5 次、至少 4 次通过，每次分别录制。回放检查的是这些历史观察；
评估新模型或新 CLI 时重新录制。

## 为什么做成 pytest 插件？

- lint 能检查规则文本，本工具检查一次执行产生的真实命令和文件变化。
- 直接复用 pytest 的 fixtures、参数化、失败报告和 CI，不必另建测试框架。
- PR 检查回放已有记录，不花模型额度；需要新证据时显式选择实时运行。

## 试试自带录制

```console
git clone https://github.com/Czj027/pytest-codex.git
cd pytest-codex
python -m pip install .
python -m pytest examples/test_conventions.py --codex-bin=not-installed -q
```

真实录制检查了 uv 成功执行、依赖声明更新和 legacy 未变；故意指定不存在的 CLI，
确认回放不会启动 Codex。

API、模式、Windows 设置、隐私与重复测试边界见 [完整参考](docs/reference.zh-CN.md)。
`run.succeeded` 只表示 CLI 回合完成，实际工作要用命令状态、文件内容断言验收。
MIT 协议，独立社区项目。
