# 学生 B 实践方案：教学轨迹回放（Teaching Trace Replay）

## 1. 任务背景

学生 A 会让 Shellloop 在运行时记录 `events`，并在终端输出实时 `[trace]` 行。实时输出适合看“现在发生了什么”，但一次运行结束后，教师还需要暂停、逐步回顾、讨论某一步为什么出现。

你负责实现安全的回放命令：

```bash
shellloop replay artifacts/teaching-trace.traj.json
```

它只读取 JSON 内已经保存的教学事件，再以清晰的时间线打印。**它绝不执行 trajectory 里的命令、绝不调用模型、绝不联网。**

最终学生能同时理解两件事：

```text
实时 trace：运行中的“此刻发生什么”
replay：运行结束后的“按顺序复盘发生过什么”
```

## 2. 前置条件与分支

本任务依赖学生 A 的 PR `feat(agents): add observable teaching trace` 已合并到 `main`。原因是 `events` 的字段和事件名称是 A 负责的固定协议。

不要从旧 main 开工，也不要把自己的改动混进学生 A 的分支。

```bash
git switch main
git pull --ff-only origin main
git log -1 --oneline
git switch -c student-b/trace-replay
pytest -q
```

确认主分支已有：

- `src/shellloop/tracing.py`
- trajectory 顶层的可选 `events`
- `run_started`、`model_request`、`model_response`、`action_selected`、`command_finished`、`run_finished`

如果没有，就暂停并告诉老师：你依赖的事件协议尚未合并。不要私自设计第二套事件字段。

## 3. 学习目标

完成后你应能解释：

1. 为什么实时终端输出不是唯一的可观察性工具；
2. 为什么 replay 只读 events，而不应根据完整 messages 猜测 Agent 过程；
3. 为什么保存的“命令文本”绝不能被 replay 再执行；
4. 如何让旧 trajectory 的失败提示清楚、可教学；
5. 如何把结构化事件与显示格式分离。

## 4. 回放格式与安全边界

命令成功时的输出应类似下面格式；文案可简洁，但信息与顺序必须保留：

```text
Shellloop teaching replay: artifacts/teaching-trace.traj.json
01. [step 0] run_started — task accepted
02. [step 1] model_request — waiting for model
03. [step 1] model_response — one shell action parsed
04. [step 1] action_selected — echo SHELLLOOP_DONE
05. [step 1] command_finished — returncode=0, finished=True
06. [step 1] run_finished — Submitted
```

### 必须遵守

- 只读取 trajectory 顶层 `events`；不要读取、打印或分析 `messages` 内容；
- `events` 中的 command 只能显示，绝不能交给 `subprocess`、`Environment.execute()` 或 shell；
- 不调用 `Model.query()`，不调用网络；
- 不显示 `config`、环境变量、API Key、工具输出正文或任务文本；
- 轨迹中没有 `events` 时，以 exit code `1` 给出清晰提示：`This trajectory has no teaching trace. Rerun it with the latest Shellloop.`；
- JSON 损坏、文件不存在时，沿用或对齐现有 `inspect` 的友好错误行为；
- 不新增第三方依赖。

### 本次允许修改

- `src/shellloop/cli.py`
- `src/shellloop/tracing.py`（仅为复用或补充纯格式化函数；不要改事件协议）
- 新增 `src/shellloop/replay.py`
- 对应的 `tests/`

### 本次不要修改

- `src/shellloop/agents/`
- `src/shellloop/environments/`
- `src/shellloop/models/`
- `src/shellloop/serialize.py`
- `src/shellloop/inspect.py`
- `README.md`、启动脚本、依赖列表

## 5. 先读代码，再向 AI 要设计

必须先阅读：

1. `AGENTS.md`；
2. `src/shellloop/cli.py`：当前 Typer 命令如何组织；
3. `src/shellloop/inspect.py`：现有只读 JSON 检查风格；
4. `src/shellloop/tracing.py`：事件协议与现有单行格式化函数；
5. `src/shellloop/serialize.py`：trajectory JSON 的整体结构；
6. `tests/test_cli.py`、`tests/test_inspect.py` 和 A 新增的 trace 测试。

然后对 AI 使用下面提示。不要让 AI 一开始就批量修改项目。

```text
我需要在 Shellloop 中实现 `shellloop replay trajectory.json`，用于初学者复盘 Agent 的 teaching trace。

请先阅读：AGENTS.md、src/shellloop/cli.py、src/shellloop/inspect.py、
src/shellloop/tracing.py、src/shellloop/serialize.py、tests/test_cli.py、tests/test_inspect.py。

事件是 trajectory 顶层可选的 events 列表；每个事件至少有 event、step、summary，
可能有 command、returncode、finished、exit_status。事件协议不能改变。

约束：replay 只读 events；不能执行命令、调用模型或联网；不能打印 messages、config、
工具输出、任务文本、环境变量或 API Key；不增加依赖；保持 inspect 行为不变。

请只给出最小实现计划：
1. 哪个纯函数负责读和校验 events？
2. 如何与现有 Typer app 增加 replay 子命令而不破坏 shellloop --task 与 inspect？
3. 旧 trajectory、缺 events、坏 JSON、文件不存在分别怎样报错？
4. 给出至少五个 pytest 场景。
不要写代码。
```

审查 AI 的回答：

- 如果它提出 `subprocess.run`、`Environment.execute`、`model.query`，方案立即不合格；
- 如果它打算从 `messages` 重新解析 command，也不合格；
- 如果它要改 `DefaultAgent` 或 event 字段，也超出任务范围；
- 如果它把 JSON 校验、格式化、Typer 命令混在一个大函数里，要求拆成最小的纯函数。

## 6. 推荐实现设计

新增 `replay.py`，提供两个可独立测试的函数：

1. `load_events(path: Path) -> list[dict]`：读取 JSON，确认顶层 `events` 是非空 list，并为缺失或错误的数据抛出清晰的 `ValueError`；
2. `format_replay(events: list[dict]) -> str`：按原顺序为每个 event 生成一行带编号、step、event、summary 的文本；仅在字段存在时显示 command、returncode、finished、exit_status。

`cli.py` 的 `replay` 子命令只负责调用这两个函数并 `typer.echo()`。这样阅读函数就不依赖终端，格式化函数也不依赖文件。

为避免显示非常长的命令，即使 A 已截断，也请在 formatter 中再次限制 `command` 最长 160 字符；这是一层显示保护，而不是修改事件数据。

## 7. 让 AI 实现：可直接复制的提示词

在你确认最小设计后，把下面提示给 AI：

```text
现在实现已确认的 `shellloop replay` 功能，并新增有意义的 pytest。

严格验收：
- 新命令是 `shellloop replay PATH`；
- 正常事件按 JSON 原有顺序显示编号、step、event 和 summary；
- command/returncode/finished/exit_status 仅在存在时显示，command 显示长度不超过 160；
- 只读取顶层 events；不得读取/显示 messages 或 config；
- trajectory 缺 events 时，显示：
  This trajectory has no teaching trace. Rerun it with the latest Shellloop.
  并以退出码 1 结束；
- 不存在文件和无效 JSON 的报错与 inspect 保持清楚一致；
- 绝不执行 command、调用 Model 或联网；
- 不改 Agent、Environment、Model、serialize、inspect、README、启动脚本或依赖。

先修改最少文件，再运行相关 pytest。失败时做最小修复并报告修改原因。
```

## 8. 必须完成的测试

至少完成这些场景：

1. 一份含六类事件的 JSON：输出保持输入顺序，且有编号；
2. `action_selected.command` 显示，但长命令被截断；
3. `command_finished` 显示 returncode 与 finished；
4. legacy trajectory 没有 events：exit code 为 1，且提示重新运行；
5. 文件不存在：exit code 为 1；
6. 无效 JSON：exit code 为 1；
7. 事件 `summary` 里不应被 formatter 改写或与其他 event 混排；
8. CLI 输出不包含伪造的 `messages` 内秘密字符串、`config` 内 API Key 或工具输出正文。

测试数据可写入 `tmp_path`，并故意在 `messages`、`config` 填入如 `should-not-appear` 的假敏感字符串，然后断言 CLI 输出不含它。不要使用真实 key，也不要 mock 任何未被要求 mock 的对象。

运行：

```bash
pytest tests/test_cli.py tests/test_inspect.py -q
ruff check src tests
ruff format --check src tests
pytest -q
```

## 9. 人工教学演示

在学生 A 功能已合并后，先生成一个离线 trajectory：

```bash
shellloop --task "Show teaching events" --yolo --output artifacts/teaching-trace.traj.json
shellloop replay artifacts/teaching-trace.traj.json
```

演示时请老师或同学回答：

1. 第几步开始向模型发起请求？
2. 哪个事件说明“模型给出了可执行 action”？
3. 哪个事件证明环境真正执行完成？
4. 最终为什么停止？

如果只靠 replay 输出就能回答四题，说明功能达成了教学目的。

## 10. 提交 PR

```bash
git status
git add src/shellloop/cli.py src/shellloop/tracing.py src/shellloop/replay.py tests
git commit -m "feat(cli): add teaching trace replay"
git push -u origin student-b/trace-replay
```

PR 标题：`feat(cli): replay observable teaching traces`

PR 描述请写：

1. `shellloop replay` 展示哪些事件；
2. 它为什么不会重新执行命令；
3. legacy trajectory 的提示方式；
4. 测试与人工演示结果；
5. 事件协议由学生 A 的 PR 提供，自己未修改协议。

## 11. 提交前检查清单

- [ ] `replay` 只读取顶层 `events`。
- [ ] 没有 `subprocess`、`Environment.execute`、`Model.query` 或网络调用。
- [ ] 不显示完整 messages、config、工具输出、环境变量或 API Key。
- [ ] 正常轨迹按事件原顺序回放。
- [ ] 缺 events 的旧轨迹有明确、可行动的提示。
- [ ] `inspect` 与原有 `shellloop --task` 调用仍通过测试。
- [ ] Ruff 与全部 pytest 通过。

## 12. 给老师的演示话术

“实时 trace 用来观察 Agent 正在经历的状态；replay 用来把已经发生的状态按顺序复盘。两者都只处理 Harness 记录的事实事件，不会重新执行 AI 产生过的命令。”
