# 学生 A 实践方案：实时教学轨迹（Teaching Trace）

## 1. 这次任务为什么重要

Shellloop 的定位不只是“让模型自动执行命令”，而是一个供初学者理解 **Agent Harness** 的实践项目。

学生运行一次任务时，应能在终端看到 Agent 正在经历什么：任务开始、请求模型、收到可执行动作、选择命令、命令结束，以及最终为何成功或停止。这个过程叫 **teaching trace（教学轨迹）**。

本任务交付一个最小、可实时显示、可保存到 trajectory 的事件流。它展示可验证的运行事实，**不展示或伪造模型的隐藏推理过程**。

完成后，一次离线运行的终端体验大致如下（具体文案可更简洁）：

```text
[trace] run_started: task accepted
[trace] step 1 model_request: waiting for model
[trace] step 1 model_response: one shell action parsed
[trace] step 1 action_selected: echo SHELLLOOP_DONE
[trace] step 1 command_finished: returncode=0, finished=True
[trace] run_finished: Submitted
Submitted: ...
```

## 2. 学习目标

完成后，你应能解释：

1. Agent 的循环由哪些状态组成；
2. 为什么“模型回复”“解析到的动作”“命令执行结果”必须区分；
3. 什么是事件（event）和事件接收器（sink）；
4. 为什么 trajectory 除了 messages，还应保存一份面向教学的、脱敏后的事件摘要；
5. 为什么看见模型的命令文本不等于执行了命令，只有 `command_finished` 才说明环境实际返回了结果。

## 3. 本次边界

### 可以修改

- `src/shellloop/core.py`
- 新增 `src/shellloop/tracing.py`
- `src/shellloop/agents/default.py`
- `src/shellloop/cli.py`
- `src/shellloop/serialize.py`
- 对应的 `tests/`

### 不要修改

- `src/shellloop/models/`
- `src/shellloop/environments/`
- `src/shellloop/inspect.py`
- `README.md`
- `start.ps1`、`start.bat`
- 依赖列表

不要增加依赖、不要联网、不要写入或打印 API Key、环境变量、配置全文、完整模型消息、完整工具输出。

本任务以 `docs/student-a-completion-protocol.md` 已合并为前提；先 `git pull` 确认主分支包含它。

## 4. 固定事件协议（先看懂，不能自行换字段名）

为了让学生 B 能基于此做回放，事件必须是普通 JSON 字典，至少包含下面字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `event` | `str` | 事件名称 |
| `step` | `int` | Agent 步数；运行刚开始时为 `0` |
| `summary` | `str` | 面向学生的简短说明，不含敏感原文 |

按需要再加入下列安全字段：`command`、`returncode`、`finished`、`exit_status`。不要放 `task`、API Key、环境变量、完整 `messages`、完整命令输出。

必须支持的事件及出现顺序：

| 事件 | 何时发出 | 建议安全字段 |
| --- | --- | --- |
| `run_started` | 收到任务、循环尚未开始 | 无 |
| `model_request` | 每次调用 `model.query()` 前 | 无 |
| `model_response` | 收到模型消息并完成动作解析后 | 无 |
| `action_selected` | 确认将执行唯一 action 后 | `command` |
| `command_finished` | `environment.execute()` 返回后 | `returncode`、`finished` |
| `run_finished` | 所有退出路径 | `exit_status` |

`command` 仅可保存将执行的单条命令，最长 160 个字符；超过时截断并加 `...`。若今后实现了脱敏函数，应在写入事件前调用它。终端绝不能打印工具输出正文。

`format_error`、`StepLimitExceeded`、`Submitted` 都必须以 `run_finished` 结束。这样回放工具永远能显示一个明确终点。

## 5. 开始前：建分支与阅读代码

```bash
git switch main
git pull --ff-only origin main
git switch -c student-a/teaching-trace
pytest -q
```

依次阅读：

1. `AGENTS.md`：仓库规则；
2. `src/shellloop/core.py`：`Model`、`Environment`、`Message` 协议；
3. `src/shellloop/agents/default.py`：循环真正在哪里执行；
4. `src/shellloop/cli.py`：如何创建 Agent、如何保存 trajectory；
5. `src/shellloop/serialize.py`：JSON 文件结构；
6. `tests/test_agent.py`、`tests/test_cli.py`：已有行为的保护网。

在纸上画出这一条链：

```text
CLI → DefaultAgent → Model.query → 解析 action → Environment.execute → tool message → trajectory JSON
```

Teaching Trace 要沿着这条链记录状态；它不是第二个 Agent，也不能改变命令执行结果。

## 6. 如何向 AI 询问：先让它做设计，不要立刻写代码

把以下提示复制给 AI，并把它的回答与真实代码逐项核对：

```text
我在一个极简 Python Agent Harness 中实现教学轨迹。请先阅读以下文件后只给出最小设计方案，不要写代码：
- AGENTS.md
- src/shellloop/core.py
- src/shellloop/agents/default.py
- src/shellloop/cli.py
- src/shellloop/serialize.py
- tests/test_agent.py
- tests/test_cli.py

限制：Python 3.10+；不加依赖；保持现有 Agent 结果不变；事件是可 JSON 序列化的字典；
不记录任务文本、完整模型消息、工具输出、环境变量或密钥。

固定事件字段为 event、step、summary；可选 command、returncode、finished、exit_status。
必须事件为 run_started、model_request、model_response、action_selected、command_finished、run_finished。

请回答：
1. 最少需要新增哪些类/函数，各自放在哪个文件？
2. DefaultAgent 的每一个事件应插在什么位置？
3. CLI 如何在不破坏旧 trajectory 的前提下保存 events？
4. 需要哪些非平凡 pytest 用例？
5. 哪些地方最容易意外泄露敏感内容？
```

先检查 AI 的方案是否满足以下判断：

- 事件的记录不能散落在 CLI；核心循环发生什么，`DefaultAgent` 最清楚；
- 事件记录器必须可选，已有 `DefaultAgent(...)` 调用不应全部被迫修改；
- 输出格式化必须独立于 Agent，避免把 `print()` 散落在循环里；
- `save_trajectory()` 新增 `events` 应是可选参数，老调用仍可用；
- model 查询、环境执行各只发生一次，不能为了 trace 重复调用。

如果 AI 的方案违反其中一条，不要让它直接实现；指出具体条目，让它给出更小的修正方案。

## 7. 推荐的最小设计

你可以采纳或让 AI 提出等价的更小实现：

1. 在 `core.py` 定义 `TraceSink` 协议：只有 `emit(event: dict) -> None`；
2. 在 `tracing.py` 放三个小对象：
   - `TraceRecorder`：将事件追加到 `events: list[dict]`；
   - `ConsoleTraceSink`：将一个事件格式化为一行 `[trace] ...` 后输出；
   - `CompositeTraceSink`：同时通知 recorder 与 console；
3. 给 `DefaultAgent` 增加可选 `trace_sink` 参数，并暴露 `agent.events`；未提供 sink 时仍记录事件，或以一个内存 recorder 作为默认值；
4. CLI 默认创建“记录 + 终端显示”的组合 sink；增加 `--no-trace` 关闭实时终端显示，但仍保存 events；
5. `save_trajectory()` 以可选的顶层 `events` 写入 JSON。原有的 `messages`、`result`、`config` 不改变。

`CompositeTraceSink` 不是必须的类名；核心是：**一次状态变化可以同时显示和记录，且 Agent 不知道显示细节。**

## 8. 让 AI 在确认设计后实现

确认自己的设计后，使用这个提示：

```text
现在按刚才确认的最小设计实现 teaching trace。请直接修改代码并新增测试。

验收要求：
- 默认 CLI 运行时按时间顺序显示 [trace] 事件；
- 默认 Agent 调用仍兼容；
- 每次模型调用前有 model_request，模型消息解析后有 model_response；
- 只在真正准备执行 action 时发 action_selected；
- environment.execute 返回后才发 command_finished；
- 每一种退出结果都以 run_finished 收尾；
- trajectory JSON 有 events，且 events 中没有 task、完整 message、tool output、环境变量或 API Key；
- --no-trace 不显示实时轨迹，但保存 events；
- 不修改 models、environments、inspect、README，不加依赖。

先运行相关 pytest；失败时说明失败原因和最小修复，不要重写无关文件。
```

AI 改完后，你必须亲自执行 `git diff`，逐个检查：

- 是否真的只修改了允许范围；
- `command_finished` 是否只在 `execute()` 返回之后出现；
- 是否在 `format error` 等早退路径漏掉 `run_finished`；
- 是否把 `message["content"]` 或 `output["output"]` 原样写进 event；
- `--no-trace` 是否只是关闭显示，而不是关闭记录。

## 9. 必须编写和运行的测试

至少覆盖：

1. ScriptedModel 的成功路径：事件顺序完整，最后是 `run_finished/Submitted`；
2. 无 action 的格式错误路径：不执行环境，但仍有 `run_finished/FormatError`；
3. 命令返回非零：`command_finished.returncode` 正确，Agent 仍保留原本行为；
4. 保存的 trajectory 含 `events`；
5. events 序列化为 JSON 后，不含测试用的假 API Key、工具输出正文和任务全文；
6. CLI 默认会显示 trace，`--no-trace` 不显示 `[trace]` 但仍保存 events。

建议命令：

```bash
pytest tests/test_agent.py tests/test_cli.py -q
ruff check src tests
ruff format --check src tests
pytest -q
```

再做一次离线人工演示：

```bash
shellloop --task "Show the teaching trace" --yolo --output artifacts/teaching-trace.traj.json
```

打开生成的 JSON，只检查 `events` 的字段与顺序；不要把带有真实信息的 trajectory 上传到仓库。

## 10. 提交 PR

```bash
git status
git add src/shellloop/core.py src/shellloop/tracing.py src/shellloop/agents/default.py src/shellloop/cli.py src/shellloop/serialize.py tests
git commit -m "feat(agents): add teaching trace events"
git push -u origin student-a/teaching-trace
```

PR 标题：`feat(agents): add observable teaching trace`

PR 描述请写清：

1. 事件协议与事件顺序；
2. 终端显示与 JSON 保存分别如何工作；
3. `--no-trace` 的含义；
4. 没有保存哪些敏感内容；
5. 运行过哪些测试和一次手工演示。

## 11. 提交前自查

- [ ] 每个 agent 运行都有 `run_started` 和最终的 `run_finished`。
- [ ] `model_request`、`model_response`、`action_selected`、`command_finished` 位置正确。
- [ ] 事件顺序可以让没有读过源码的同学解释一次运行。
- [ ] trace 不会改变模型调用次数、命令执行次数或原有退出状态。
- [ ] trajectory 的 `events` 可以被 `json.loads()` 读取。
- [ ] 没有原始 API Key、任务、完整模型消息、完整工具输出或环境变量。
- [ ] 所有测试、Ruff 检查通过。

## 12. 给老师的演示话术

“这一行不是模型的隐藏思考，而是 Harness 记录的可观察事件。模型被请求了吗？解析到了什么动作？环境真正执行了吗？执行结果如何？Agent 为什么停止？这些才是我们能够复现、测试和调试的中间态。”
