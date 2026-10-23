# 完整参考

用 pytest 检查 Codex 的实际行为，支持真实执行录制、离线回放和多次运行通过率。
MIT 协议，Python 3.10+，pytest 7+。

**0.3.0 源码版**新增 `--codex-recording-set`（录制集隔离）、
`--codex-results`（逐次结果导出）、`codex_grader_files`（验收文件指纹）及
`python -m pytest_codex.compare`（真实运行对比）。用法和边界见
[任务回归指南](regression.md)。下方 PyPI 安装说明仍指已发布的 0.2.0。

**0.2.0 已在 PyPI 发布**，包含 fixture、录制回放、通过率检查和 CLI 版本校验：

```console
python -m pip install pytest-codex
```

示例附带 Windows 上真实录制的 cassette，检查成功执行 `uv add --frozen requests`、
修改依赖声明、不使用 pip、不改动 `legacy/`。`--frozen` 避免解析和安装环境，不代表依赖已安装。
回放验证历史记录符合断言，不证明现在的模型仍会表现相同。
真实录制还会关闭托管 Python 探测与下载、使用项目内 uv 缓存。Windows 录制时需在 PATH
提供沙箱可读取的 Python 和 uv；只有当前用户可访问的 Python 安装可能不可用。

## 写测试

```toml
[tool.pytest.ini_options]
codex_project = "sample_repo"
codex_isolation = "full"
codex_timeout = "300"
```

```python
def test_rules(codex):
    run = codex.exec("Add requests as a project dependency.")
    assert run.succeeded, run
    assert run.ran("uv add", ok=True), run
    assert not run.ran("pip install"), run
    assert run.modified("pyproject.toml"), run
    assert "requests" in run.read("pyproject.toml"), run
    assert not any(p.startswith("legacy/") for p in run.changed_files), run
```

```console
python -m pytest tests/test_rules.py --codex-record
python -m pytest tests/test_rules.py
```

第一条需要 Git、已登录 Codex CLI 并消耗额度；第二条默认仅回放，缺少或过期录制会失败，
绝不自动调用模型。`--codex-live` 实时执行不保存；`--codex-mode=auto` 只对缺少的录制调用模型，
已有但过期的录制仍失败。支持 `--codex-bin`、`--codex-model`。

每次 exec 都复制新项目并建立 Git 基线；`files={"AGENTS.md": "..."}` 在基线前覆盖输入。
`project` 和 marker 项目路径相对于 pytest 根目录，也接受绝对路径。

## 查询与判断

- `commands`：命令、输出、退出码、`ok`；`ran` 匹配去掉 shell 包装后的字符串或正则，`ok=True` 筛选退出码 0，`ok=False` 筛选已知非零退出码。
- `added/modified/deleted(glob)`、`changed_files`：前后内容哈希对比，可检测 shell 修改。
- `read(path)`：读取临时项目 UTF-8 文件，禁止越界路径。
- `messages/final_message`、`mcp_calls/called_mcp(server, tool=None)`。
- `tokens/usage`：总量为输入加输出，缓存输入不重复计数。
- `succeeded`：退出码 0、有 turn.completed、无 turn.failed；不等于命令成功或任务完成。
- `replayed`、`project`：是否回放、临时项目位置。

`assert 条件, run` 在失败时展示摘要。MCP 查询仅证明调用存在，结果成功需另查返回值。
不提供 `used_skill`，因为事件不能可靠证明技能触发。glob 区分大小写，`*` 也匹配 `/`。
快照不记录空目录和仅权限变更，拒绝符号链接与目录联接。

## 多次运行

```python
import pytest

@pytest.mark.codex(runs=5, pass_rate=0.8, project="sample_repo")
def test_reliability(codex):
    run = codex.exec("Add requests as a dependency.")
    assert run.ran("uv add"), run
```

全部执行 5 次，至少 4 次通过；`codex.attempt` 从 1 开始。每次、每个调用分别录制。
只将断言和 pytest.fail 计入通过率失败，其他异常立即暴露，skip/xfail 保持 pytest 控制流。
同一 item 内其他 fixtures 与 setup/teardown 共享，只有每次 exec 的项目副本独立。
支持同步 pytest 函数和参数化，不支持异步、unittest 重复测试或叠加重试插件。
回放不产生新实验依据，评估当前模型必须重新录制。

## 隔离与隐私

默认 full 临时创建 CODEX_HOME，只复制 auth.json，退出或超时后删除；config 只忽略用户配置，
none 继承用户配置。非交互执行要求 approval_policy=never。Windows 默认另外设置
windows.sandbox=elevated，需要机器已有可工作的 Codex 沙箱。
Windows 实时运行项目放在用户 pytest-codex 缓存中，避免 pytest 私有临时父目录权限阻碍，
测试 fixture 结束时删除。
配置隔离不等于安全隔离：系统/托管配置、全局 .agents/skills、环境变量和工具仍会影响行为。
默认 CLI 沙箱为 workspace-write，复制项目本身不是安全沙箱。

cassette 保存事件、变更、base64 文件内容和 CLI 版本。提示词、请求的模型、config、sandbox、
隔离级别、输入文件内容决定 key；超时和环境变量不计入。回放不会执行事件里的命令。

0.2.0 新增 `--codex-cli-version=0.163.0`（或 ini `codex_cli_version`），离线比较录制版本；
`--codex-check-cli` 则执行本机 `codex --version` 比较，不调用模型。同时使用会先比较本机与固定
版本，再比较录制。两种严格检查均要求显式模型，可通过 `exec(model=...)`、`--codex-model` 或
ini `codex_model` 指定。版本不符会在恢复文件前、录制/实时模型调用前失败；主动升级时更新固定
版本并重新录制。不使用新选项时保持原有离线行为，不要求安装 CLI。同名模型的服务端更新仍需重录检查。

**提交录制前检查隐私**：仅事件字符串中的临时项目和用户目录前缀会被替换；命令输出、MCP 结果、
文件内容中的密钥不自动脱敏，base64 不是加密。使用小型无秘密的项目；复制时排除 .git、
常见环境与缓存、cassettes、dist、build。源目录在 Git 仓库中时，还排除 Git 忽略的未跟踪文件，
包含嵌套规则与反向匹配；已跟踪文件仍视为输入。如果显式选中的项目本身位于 Git 忽略的父目录内
（如临时 fixture），则当作独立 fixture，不套用祖先仓库的忽略规则。`files={...}` 是显式输入，可能重新加入被排除的文件，
不要在其中提供秘密。

新增真实示例与验证范围见 [evidence.md](evidence.md)。每日最新 CLI 检查连接本地固定响应端点，
不登录、不消耗模型额度；新鲜模型行为需主动选择实时运行，或配置 [默认关闭的模板](ci/live-examples.yml)。

全部参数、开发命令及限制见 [英文参考](reference.md)。本项目独立于 OpenAI，并非官方产品。
