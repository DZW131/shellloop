# 学生 B 下午实践方案：trajectory inspect CLI

## 你的角色

你负责把已经合并的 trajectory summary 工具变成正式 CLI 功能。用户应能用一条
命令查看运行结果，而不会暴露原始模型回复、Shell 命令或敏感信息。

## 今天结束时的交付物

提交一个新 PR：

~~~text
feat(cli): add trajectory inspect command
~~~

用户应同时能使用：

~~~bash
shellloop --task "Demonstrate the loop"
shellloop inspect artifacts/demo.traj.json
~~~

第二条命令只输出：

~~~text
exit_status
steps
message_count
command_count
~~~

## 第一阶段：同步基线

先确认从包含 trajectory summary 工具的最新 main 开始：

~~~bash
git switch main
git pull --ff-only
pytest -q
git switch -c student-b/inspect-command
~~~

不要在已合并的 student-b-inspect 分支继续提交。

## 功能契约

新的 inspect CLI 应当：

- 支持 shellloop inspect trajectory-file；
- 调用已有 trajectory summary 函数；
- 以易读文本输出四项摘要；
- 文件不存在、JSON 无效、JSON 缺少必要字段时显示清晰错误；
- 不输出消息正文、Shell 命令正文、环境变量、API Key、完整 config 或模型响应；
- 保持现有 shellloop --task 调用方式不变；
- 更新 README，提供可复制的示例。

本 PR 不应：

- 修改 Agent、Environment、模型模块；
- 修改 trajectory summary 的核心计算逻辑；
- 添加依赖；
- 添加图形界面或 Web 服务；
- 输出调试对象的完整 repr。

## 与 AI 的第一轮对话：兼容性设计

完整发送给 AI：

~~~text
你负责为 Shellloop 添加 trajectory inspect CLI 子命令。

先阅读 AGENTS.md、README、当前 CLI、trajectory summary 模块和已有 CLI 测试。
不要修改文件。

请回答：
1. 当前 shellloop --task 的入口结构是什么？
2. 如果直接增加一个 Typer 子命令，是否会破坏现有调用？
3. 如何同时支持：
   - shellloop --task "..."
   - shellloop inspect path/to/run.traj.json
4. 怎样把 ValueError、FileNotFoundError、JSONDecodeError 转成用户可理解的 CLI 输出？
5. 需要增加哪些测试？
6. 将修改哪些文件？

约束：
- 保持旧 CLI 调用兼容；
- 不修改 Agent、Environment 或模型模块；
- 输出绝不包含原始消息、命令、密钥或完整 config；
- 不新增依赖。

输出不超过 12 条的最小实现计划和风险清单，等待我确认。
~~~

如果 AI 让 shellloop --task 变成 shellloop main --task，说明它破坏兼容性，
必须要求重新设计。

## 与 AI 的第二轮对话：实施

~~~text
按确认后的设计实现 inspect CLI。

要求：
- 保持 shellloop --task "..." 继续可用；
- 新增 shellloop inspect file；
- inspect 正常输出四项摘要；
- 文件不存在、非法 JSON、字段缺失时返回非零退出码和清晰错误；
- 只修改 CLI、CLI 测试、README，以及必要的 CLI 辅助模块；
- 不修改 Agent、Environment、模型模块、summary 核心逻辑；
- 不新增依赖。

新增或更新测试：
1. 旧的 --task 调用仍成功；
2. inspect 正常 trajectory 成功；
3. inspect 文件不存在失败；
4. inspect 非法 JSON 失败；
5. inspect 输出不含消息内容、命令或 API Key。

完成后运行：
pytest -q
ruff check src tests
ruff format --check src tests

最后报告：修改文件、兼容性策略、测试结果和剩余风险。
~~~

## 人工端到端验收

~~~bash
shellloop --task "Create an inspectable trajectory" --output artifacts/demo.traj.json --yolo
shellloop inspect artifacts/demo.traj.json
~~~

人工确认：

- 输出只含四项摘要；
- 命令正文没有出现；
- 原始消息文本没有出现；
- 旧的 --task 命令仍可运行。

## PR 前检查

- [ ] 分支基于最新 main。
- [ ] shellloop --task 没有被破坏。
- [ ] shellloop inspect 已有正常与失败路径测试。
- [ ] README 有 inspect 示例和安全说明。
- [ ] 没有新增依赖。
- [ ] pytest、ruff check、ruff format --check 全绿。
- [ ] PR 描述包含修改范围、验证命令、AI 使用方式和风险。

## 交叉审查

请学生 A 审查：

1. 新的 Typer 结构是否破坏旧 CLI 兼容性？
2. 错误信息是否泄露完整 trajectory 内容？
3. inspect 是否只读取文件而不执行其中任何命令？
4. README 示例是否与实际 CLI 完全一致？

