# 学生 A 下午实践方案：OpenAI-compatible 文本模型

## 你的角色

你负责让 Shellloop 能从一个 OpenAI-compatible 模型取得文本回复，
并安全地将其中唯一合法的 Shell 代码块转换为标准 action。

今天不需要让模型完成复杂真实任务，也不接入多个供应商。你要交付一个可离线
测试的模型适配器 PR。

## 今天结束时的交付物

1. 当前文本解析器 PR 只保留解析器和解析器测试。
2. 一个新 PR，标题为：

~~~text
feat(models): add OpenAI-compatible text model
~~~

3. 新模型实现现有 Model 协议，可以将模型文本转换为 Shellloop 标准消息。
4. 测试、Ruff 检查和格式检查全部通过。

## 第一阶段：清理当前 PR

当前解析器 PR 仍含有 LocalEnvironment 测试，它不属于解析器 Issue。先将它
移出当前 PR，再开始新功能：

~~~bash
git switch student-a/text-action-parser
git pull --ff-only
git rm tests/test_local_environment.py
pytest -q
ruff check src tests
ruff format --check src tests
git add -A
git commit -m "chore: keep parser PR focused"
git push
~~~

不要修改解析器实现，除非测试发现真实问题。通知老师复核并合并该 PR。

## 第二阶段：创建新分支

解析器 PR 合并后执行：

~~~bash
git switch main
git pull --ff-only
git switch -c student-a/openai-compatible-model
~~~

不要从旧分支直接创建新功能分支。

## 功能契约

模型适配器应当：

- 实现现有 Model.query(messages) 协议；
- 调用一个 OpenAI-compatible chat completions API；
- 从回复中取得 assistant 文本；
- 调用已有文本动作解析器，生成 extra.actions；
- 保留 assistant 文本，供 Agent 写入 trajectory；
- 只允许一条合法 Shell action；
- 格式错误时抛出明确异常，绝不猜测或执行命令；
- 不把 API Key、Authorization header、完整 HTTP 响应写进消息、异常或 trajectory。

本 PR 不应：

- 修改 Agent、CLI、Environment；
- 新增第二个模型供应商；
- 新增 Docker、Sandbox 或 Benchmark；
- 在单元测试中访问网络；
- 在配置或 README 中写入真实 API Key。

## 与 AI 的第一轮对话：只做设计

完整发送给 AI：

~~~text
你负责 Shellloop 的第一个 OpenAI-compatible 文本模型适配器。

先阅读 AGENTS.md、README、核心 Model 协议、文本动作解析器及其测试。
不要修改任何文件。

请设计一个最小实现，并说明：
1. 模型类的构造参数；
2. API 地址、模型名、API Key 应如何传入；
3. 如何构造 chat completions 请求；
4. 如何从响应取出 assistant 文本；
5. 如何把文本交给现有解析器；
6. 如何通过可注入 transport 在离线测试中模拟响应；
7. 将修改哪些文件。

约束：
- 不修改 Agent、CLI、Environment；
- 不新增依赖，优先使用 Python 标准库；
- 不调用真实网络来测试；
- API Key 和原始 HTTP 响应不得进入 trajectory；
- 只支持一个 OpenAI-compatible 接口。

输出不超过 12 条的设计计划和风险清单，等待我确认。
~~~

学生先审查 AI 的计划，满足边界后才进入实施。

## 与 AI 的第二轮对话：实施

~~~text
按已确认的设计实施最小改动。

要求：
- 只创建或修改模型模块及对应测试；
- 使用可注入的 fake transport，而不是 mock 或真实 HTTP；
- 模型 query 返回的消息必须含 assistant content 和 extra.actions；
- 解析器拒绝回复时，错误必须向上抛出；
- 所有异常信息不得包含 API Key；
- 添加离线测试：
  1. 请求格式正确；
  2. 正常模型文本产生一条 action；
  3. 非法模型文本失败；
  4. 响应缺失 assistant content 失败；
  5. API Key 不出现在返回对象或异常文本中。

完成后运行：
pytest -q
ruff check src tests
ruff format --check src tests

最后报告：修改文件、每项测试的作用、验证结果、未解决风险。
~~~

## PR 前验收

- [ ] 没有修改 Agent、CLI 或 Environment。
- [ ] 没有增加未获批准的依赖。
- [ ] 没有真实 API Key、URL 中的密钥或完整响应进入仓库。
- [ ] 所有测试在离线环境通过。
- [ ] 非法文本不能生成 action。
- [ ] pytest、ruff check、ruff format --check 全部通过。
- [ ] PR 描述记录 AI 的计划、测试结果和风险。

## 交叉审查

请学生 B 审查：

1. API Key 是否可能经过异常、日志或返回消息泄露？
2. 格式错误时是否真的不会产生 action？
3. fake transport 是否保证测试没有网络依赖？
4. 是否意外修改了不属于模型层的模块？

