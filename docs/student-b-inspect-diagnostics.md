# 学生 B 实践任务：让 trajectory 说明任务为何结束

## 任务背景

现有命令：

```bash
shellloop inspect artifacts/run.traj.json
```

已经能安全输出 `exit_status`、`steps`、`message_count` 和 `command_count`。但当运行结果为 `StepLimitExceeded` 时，教师和学生仍需要猜测：到底是命令失败、模型没完成，还是根本没有完成信号？

你的任务是扩展这份**只读、安全摘要**，让它能够解释运行状态，而不泄露原始命令、模型回复、环境变量或 API Key。

## 目标

在原有摘要中新增三个字段：

```text
completion_detected: true | false
failed_command_count: 0
last_returncode: 0 | unknown
```

字段语义必须固定：

| 字段 | 含义 | 数据来源 |
|---|---|---|
| `completion_detected` | 任一 tool observation 是否包含 `finished: true` | trajectory 的 tool message `extra` |
| `failed_command_count` | `returncode` 存在且不等于 `0` 的 tool observation 数量 | trajectory 的 tool message `extra` |
| `last_returncode` | 最后一条带有 `returncode` 的 tool observation 的返回码；若没有则为 `unknown` | trajectory 的 tool message `extra` |

例如，一次因没有完成标记而跑满步数的任务可以显示：

```text
exit_status: StepLimitExceeded
steps: 8
command_count: 8
completion_detected: false
failed_command_count: 0
last_returncode: 0
```

## 范围与边界

允许修改：

- `src/shellloop/inspect.py`
- `src/shellloop/cli.py`
- `tests/test_inspect.py`
- `tests/test_cli.py`
- `README.md`

不要修改：

- Agent 控制流、模型适配器、命令解析器、环境执行器、序列化格式。
- 不增加依赖，不联网。
- 不执行 trajectory 内任何命令。
- 不输出 message content、action command、tool output、config 内容、环境变量、API Key。

兼容性要求：旧 trajectory 可能没有 `returncode` 或 `finished` 字段；对这类文件不能报错，必须输出保守结果：`completion_detected: false`、`failed_command_count: 0`、`last_returncode: unknown`。

## 开始前的 Git 操作

```bash
git switch main
git pull --ff-only
git switch -c student-b/inspect-diagnostics
pytest -q
```

开始前检查工作区：

```bash
git status --short
```

不要删除或提交其他人遗留的修改。

## 与 AI 协作：第一轮只做设计

把下面提示词原样发给 AI：

```text
请阅读 AGENTS.md、src/shellloop/inspect.py、src/shellloop/cli.py、
tests/test_inspect.py、tests/test_cli.py 和 README.md。

我要在 trajectory 的只读安全摘要中增加三个字段：completion_detected、
failed_command_count、last_returncode。

字段只能从 role == "tool" 的 message.extra 中推导；旧 trajectory 缺字段时
必须兼容，并显示 false、0、unknown。不得输出或保存任何原始消息、命令、
工具输出、配置或密钥；不得执行 trajectory 中的命令；不得增加依赖。

先不要写代码。请给出最小设计、字段推导伪代码、测试场景和潜在兼容风险。
```

阅读 AI 方案时，检查它是否：

- 错把 assistant message 中的 `actions` 当成“已执行命令”；只有 tool message 才代表执行结果。
- 在缺少 `returncode` 的旧文件上抛异常。
- 为了调试而输出 message content、command 或 tool output；这不允许。
- 试图修改 Agent 或 Environment；这不属于本任务。

## 与 AI 协作：第二轮实现

确认设计后，发送：

```text
按刚才确认的最小方案实现 inspect diagnostics。

要求：
- 只从 role == "tool" 的 extra 中读取 finished 与 returncode；
- completion_detected 始终是布尔值；
- failed_command_count 始终是整数；
- 没有 returncode 时，CLI 显示 last_returncode: unknown；
- 保持旧的 inspect 输出字段与 shellloop --task 行为兼容；
- README 增加一个不含敏感内容的示例；
- 添加离线 pytest，不发真实网络请求。

完成后列出修改文件、验证命令和已知限制。不要执行 git commit 或 git push。
```

## 必做测试

至少创建或覆盖三类 trajectory fixture：

1. **正常完成**：包含 `finished: true` 与 `returncode: 0`；三个新字段为 `true`、`0`、`0`。
2. **命令失败后仍继续**：至少一条 tool observation 的 `returncode` 非 0；统计失败数且最后返回码正确。
3. **旧文件或步数耗尽**：没有 `finished` 或 `returncode`；不报错，输出 `false`、`0`、`unknown`。

同时验证 CLI：

- 正确显示三个新字段；
- 错误文件仍然非零退出；
- 输出中没有 API Key、命令文本、完整 message content 或工具输出。

执行：

```bash
pytest -q
ruff check src tests
ruff format --check src tests
git diff --check
```

## 提交与 PR

提交前确认范围：

```bash
git diff --name-only main...HEAD
git status --short
```

提交：

```bash
git add README.md src/shellloop/inspect.py src/shellloop/cli.py tests/test_inspect.py tests/test_cli.py
git commit -m "enh(cli): expand trajectory diagnostics"
git push -u origin student-b/inspect-diagnostics
```

PR 标题建议：

```text
enh(cli): explain trajectory completion and command outcomes
```

PR 描述必须包含：

- 三个字段的精确定义；
- 对旧 trajectory 的兼容策略；
- 安全边界：哪些原始内容绝不输出；
- 测试命令与结果；
- 一个 `StepLimitExceeded` 的示例摘要。

## 交叉审查清单（由学生 A 审查）

1. 三个字段是否只读取 tool observation，而不是 assistant action？
2. 旧 trajectory 缺少字段时是否仍可 inspect？
3. 输出是否绝不泄露命令、模型内容、tool output 或密钥？
4. 是否没有执行 trajectory 内的任何内容？
5. 是否保持 `shellloop --task` 和原有 inspect 字段兼容？
