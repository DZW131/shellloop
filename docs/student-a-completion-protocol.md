# 学生 A 实践任务：让 Agent 知道何时完成

## 任务背景

真实运行中，Ollama 已经能够返回并执行命令，但有时会出现：

```text
StepLimitExceeded
steps: 8
command_count: 8
```

这通常不是执行器崩溃，而是模型没有发出完成信号。Shellloop 的既有完成约定是：某条命令的**第一行标准输出**为 `SHELLLOOP_DONE` 时，`LocalEnvironment` 会标记任务完成。

你的任务是把这个运行约定清楚地写进 Agent 的系统提示词，并分别适配 Windows 与 POSIX/WSL。

## 目标

完成后，`DefaultAgent` 发给模型的第一条 system message 应明确告诉模型：

1. 每次只返回一个代码块和一条 shell action。
2. 不要在代码块外输出解释性文字。
3. 任务完成时，最终 action 的第一行输出必须为 `SHELLLOOP_DONE`。
4. Windows 与 POSIX/WSL 要采用各自兼容的命令语法。

运行中的目标效果：模型完成“列出当前目录文件”任务后，应能构造类似下列命令。

Windows `cmd.exe`：

```shell
echo SHELLLOOP_DONE & dir
```

POSIX shell / WSL：

```bash
echo SHELLLOOP_DONE && ls
```

注意：完成标记必须先输出，因此不要写成 `dir & echo SHELLLOOP_DONE`。

## 范围与边界

允许修改：

- `src/shellloop/agents/default.py`
- `tests/test_agent.py`
- 如确有必要，`src/shellloop/agents/__init__.py`

不要修改：

- `src/shellloop/environments/local.py`：不要改完成标记的检测逻辑。
- `src/shellloop/models/`：不要改解析器或模型适配器。
- `src/shellloop/cli.py`、`inspect.py`、`README.md`。
- 不增加依赖，不调用真实模型或网络。

建议将提示词生成写成一个可离线测试的纯函数，例如根据 `is_windows: bool` 生成文本；`DefaultAgent` 再以当前平台选择对应文本。具体函数名可先让 AI 提出最小方案，再自行判断。

## 开始前的 Git 操作

```bash
git switch main
git pull --ff-only
git switch -c student-a/completion-protocol
pytest -q
```

开始编码前，确认工作区干净：

```bash
git status --short
```

如果出现不是你创建的修改，不要删除，也不要提交它们。

## 与 AI 协作：第一轮只做设计

把下面提示词原样发给 AI：

```text
请阅读 AGENTS.md、src/shellloop/agents/default.py、tests/test_agent.py，
以及 src/shellloop/environments/local.py 中对 SHELLLOOP_DONE 的处理。

我要完成一个很小的改动：让 DefaultAgent 的 system prompt 明确规定完成协议，
并根据 Windows cmd.exe 与 POSIX shell 生成正确示例。

边界：只能修改 agents/default.py 和 tests/test_agent.py；不能修改环境执行器、
模型、CLI、README；不能增加依赖或联网。

先不要写代码。请输出：
1. 当前完成协议的准确运行过程；
2. 最小实现方案；
3. 将新增或调整的 pytest 清单；
4. 可能破坏既有行为的风险。
```

阅读 AI 的设计后，重点检查：

- AI 是否理解“标记必须是**第一行输出**”。
- Windows 示例是否使用 `cmd.exe` 可执行的 `&`，而非 PowerShell 7 专用的 `&&`。
- POSIX 示例是否使用 `&&`。
- 是否试图修改 `LocalEnvironment` 或引入无关重构；若有，要求它收缩范围。

## 与 AI 协作：第二轮实现

确认设计后，发送：

```text
按刚才确认的最小方案实现。

要求：
- system prompt 必须包含“恰好一个 action / 一个代码块”的约定；
- Windows prompt 必须提到 cmd.exe，并给出以 SHELLLOOP_DONE 开头的 cmd 示例；
- POSIX prompt 必须给出以 SHELLLOOP_DONE 开头的 POSIX 示例；
- 提示词生成逻辑必须可在不依赖当前操作系统的条件下离线测试；
- 保持现有 DefaultAgent 的 run 行为不变；
- 只修改约定文件与测试文件。

完成后请列出修改文件，并给出 pytest、ruff check、ruff format --check 命令。
不要执行 git commit 或 git push。
```

## 必做测试

至少覆盖以下情况：

1. Windows 提示词包含 `SHELLLOOP_DONE`、`cmd.exe`，以及 Windows 兼容示例。
2. POSIX 提示词包含 `SHELLLOOP_DONE`、POSIX shell 说明，以及 `&&` 示例。
3. `DefaultAgent.run()` 的第一条 message 仍是 system message，并使用对应提示词。
4. 原有的成功、失败、步数上限测试继续通过。

执行：

```bash
pytest -q
ruff check src tests
ruff format --check src tests
git diff --check
```

## 提交与 PR

确认差异只包含任务范围内文件：

```bash
git diff --name-only main...HEAD
git status --short
```

提交：

```bash
git add src/shellloop/agents/default.py tests/test_agent.py
git commit -m "feat(agents): define completion protocol"
git push -u origin student-a/completion-protocol
```

PR 标题建议：

```text
feat(agents): define platform-aware completion protocol
```

PR 描述必须包含：

- 为什么会出现 `StepLimitExceeded`；
- Windows 与 POSIX 的完成命令示例；
- 修改范围；
- 三条验证命令及结果；
- 未做真实云端调用的说明。

## 交叉审查清单（由学生 B 审查）

1. 提示词是否真的把 `SHELLLOOP_DONE` 规定为第一行输出？
2. Windows 与 POSIX 示例是否分别可执行？
3. 是否没有修改环境、模型或 CLI？
4. 是否没有改变默认 Agent 的其他控制流？
5. 是否所有测试和 Ruff 检查均通过？
