# 你的 AGENTS.md 真的生效了吗？

在规则里写“用 uv，不要用 pip”，只是表达了意图。要知道 agent 是否照做，还需要检查它实际
执行的命令。最终回复一句“完成了”，既不能证明命令成功，也不能证明它没有修改不该动的文件。

pytest-codex 把这些行为变成普通的 pytest 断言：

```python
def test_dependency_rule(codex):
    run = codex.exec("Add requests as a project dependency.")
    assert run.ran("uv add", ok=True), run
    assert not run.ran("pip install"), run
    assert run.modified("pyproject.toml"), run
    assert not any(path.startswith("legacy/") for path in run.changed_files), run
```

`ok=True` 检查退出码为零。文件断言比较执行前后的内容，所以通过 shell 造成的变化也能被发现。
每次执行都操作一个新的项目副本，原项目不作为执行目录。复制会遵守源 Git 仓库的忽略规则，
同时排除常见环境、缓存和已有录制；这仍然不能代替审查测试输入。

## 录一次，普通 CI 离线检查

第一次用 `--codex-record` 显式调用已登录的 Codex CLI，保存事件与文件变化。后续默认只回放：

```console
python -m pytest tests/agent --codex-record
python -m pytest tests/agent --codex-bin=not-installed
```

第二条故意指定不存在的 CLI。测试仍能通过，才证明它不依赖本机的 Codex 登录或网络模型调用。
缺少录制、输入变化或版本校验不通过时，插件直接报错，不自动转成消耗额度的运行。

回放证明的是历史执行仍满足断言。它不能证明今天的模型仍会作出相同选择，不能代替升级后的真实验证。
0.2.0 新增离线 CLI 版本固定和本机版本检查；严格校验要求显式模型，避免无意依赖变化的默认模型。
同名模型的服务端更新仍需要主动重录来检查。

## 不只检查命令

项目还附带一个本地 stdio MCP 服务。测试检查模型确实调用了 `catalog.lookup`，参数正确，结果存在，
并在回复中使用了返回值。另一个示例调用项目 Skill，再检查生成的 RELEASE.md 是否符合规定格式。
我们不提供猜测性的 `used_skill()`：有正确文件输出，才算这个示例要验证的行为得到满足。

我们也用这个插件检查了本项目自己的 AGENTS.md。2026-10-22 的实测中，两个模型各两次都生成了规定的
发布检查清单。这个样本很小，只能作为功能冒烟验证，不能拿来宣布模型可靠性为 100% 或比较模型优劣。
`runs` 和 `pass_rate` 可以用于更大的实际实验，但重复回放不会增加新的实验样本。

## 开始使用

已发布的 0.1.0 可以通过 `python -m pip install pytest-codex` 安装。本文的版本校验和新增示例位于
待发布的 0.2.0 源码中，可以克隆仓库后执行 `python -m pip install .`。

- [项目与快速开始](https://github.com/Czj027/pytest-codex)
- [真实录制与验证范围](../evidence.md)
- [给 Python/MCP 项目加一个行为测试](../integration.md)

提交录制前，检查命令输出、MCP 返回值和文件内容。路径替换不是通用密钥脱敏，base64 也不是加密。
适合普通 PR 的是离线回放；需要新证据时，再显式安排真实调用。
