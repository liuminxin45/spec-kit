# Codex Skill + 知识包模式

这是 Spec Kit 2.0 提供的可选模式。Codex 负责开发；一个 `$speckit` 总 Skill
负责发现项目知识、选择 workflow、记录需求与澄清、检查证据并交付。
旧版初始化默认值和已有项目保持兼容，不自动迁移 UF 或其他工作区。

## 开始

安装 Spec Kit 2.0 CLI 后，在目标项目运行：

```powershell
specify init --here --mode codex-skill --no-git --json
specify pack doctor --json
specify context --json
```

初始化只添加总 Skill、短 AGENTS 管理区域、配置、锁文件和通用能力包。
它不会创建产品源码、Git 仓库、旧版 `ai/` 模板或规格文档树。
保留用户文件与 AGENTS 区域外的规则；遇到受管文件定制时报告冲突。

重新打开项目中的 Codex 对话后：

```text
$speckit 修复导出 CSV 时中文列名乱码的问题。先查明原因，完成后实际验证。
```

总 Skill 按需加载自己的 references，候选知识只显示元数据。不会预加载
所有 workflow、历史任务、知识正文或 UI 设计稿。

## 包、层级和资源

包是版本、来源和依赖的管理单元。资源是实际按需加载或执行的单元。
个人、组织、项目、组件、任务层级作为显式绑定元数据保留；用声明的 scope
过滤候选。目录深度不授予优先级，互相冲突的强制要求需要澄清。

| 类型 | 用途 | 生效方式 |
| --- | --- | --- |
| reference | 仓库地图、运行调试、架构、踩坑 | 按需读正文 |
| policy | 项目强制要求 | 绑定 required 后总 Skill 必须读取；语义符合性由 AI 审查 |
| asset | 设计稿、图片、基准文件 | 返回文件路径，按需读取 |
| workflow | 任务阶段和门禁 | 选中并记录原因，CLI 检查必需门禁 |
| check | 确定性的项目校验 | runner 执行锁定 argv 描述，生成真实收据 |
| action | 运行、构建、诊断等操作 | 显式 task run 执行；安装时不执行 |
| skill | 专用 Skill 及其 supporting files | 总 Skill 通过 context 读取；不自动注册为独立原生 Skill |
| tool | 主机工具的使用说明和目标条件 | 发现并调用真实可用主机工具 |
| mcp / hook | 连接/适配描述 | 仅为描述，必须核验实际连接或注册 |

最小项目包由用户在运行时创建，源码仓库不携带 UF 等项目知识：

```yaml
schema_version: "2.0"
id: myteam/myproject
version: "0.1.0"
layer: project
description: "本项目的地图、调试方法和约束"
requires: []
contents:
  - {id: map, type: reference, path: repository-map.md}
  - {id: design, type: asset, path: designs/settings.png}
  - {id: rules, type: policy, path: requirements.md}
  - {id: smoke, type: check, path: checks/smoke.yml}
```

所有声明路径限制在包内，拒绝越界、符号链接和 junction。身份为
`myteam/myproject::map`，同名资源通过命名空间区分。依赖必须指定完整包 ID
和精确版本；缺失、冲突和循环在写入前阻塞，多个来源可一次事务安装。

```powershell
specify pack validate ./knowledge/myproject --json
specify pack add ./knowledge/myproject --dry-run --json
specify pack add ./knowledge/myproject --json
specify pack bind myteam/myproject --scope "src/**" --layer component --require myteam/myproject::rules --json
specify context --file src/main.py --select myteam/myproject::map --json
```

required policy 不会被可选能力过滤静默隐藏。它保守地保持必读，不推断规则
冲突已经解决。业务语义仍需要 Codex 判断；机器门禁只执行明确写出的检查。

远程安装必须固定完整 commit：

```text
specify pack add git+https://example.org/team/knowledge.git@<40位commit> --json
```

锁文件保存精确身份、版本、来源和内容 hash。本地目录来源只在该机器上可恢复；
团队共享应使用固定 Git 来源。更新必须递增版本，同一版本不能替换内容。
`pack restore` 按锁定来源恢复缺失缓存，来源内容不同会阻塞。
删除包先检查反向依赖；缓存保留以支持历史调查。卸载不会删除用户知识源。

## Workflow 与强制校验

内置 8 个通用 workflow：coding-lite、engineering-change、investigation、
validation-only、delivery，以及 knowledge 的 bootstrap、maintain、release。
这是模型选择的候选集，允许用户扩展自己的 workflow。

```yaml
schema_version: "2.0"
id: "myteam/myproject::fix"
version: "0.1.0"
phases: [contract, implement, ai_accept]
human_acceptance: {required_for_close: true, allow_accepted_gaps: false}
gates:
  - {id: request, phase: contract, kind: machine, check: builtin/request-contract}
  - {id: smoke, phase: ai_accept, kind: machine, check: "myteam/myproject::smoke"}
  - {id: review, phase: ai_accept, kind: judgment, check: builtin/criteria-review}
```

check 文件是 argv 描述，不是可手填的“成功证明”：

```yaml
argv: [python, -m, unittest, -v]
cwd: .
timeout_seconds: 120
structured: false
```

`{pack}` 可引用该描述文件所在目录，`{project}` 可引用项目根目录。
runner 不使用 shell 字符串插值。已登记 check 不能被调用者换成另一条命令。
动作同理，通过 action_resource 显式选择；操作权限仍来自用户和主机。

contract、implement、ai_accept 按所选 workflow 的阶段顺序累计检查前置门禁。
代码修改要求当前通过的执行收据；UI 和运行时变更要求真实目标的对应观察。
无论自定义 workflow 是否声明 review gate，finish 都要求当前 AI 验收通过。
delivery workflow 不自动提交或发布，发布目标、授权和远端验证必须作为任务
要求，通过项目自己的 check 提供证据。

## 完整任务证据链

命令与事件 JSON 详见安装后的
`.agents/skills/speckit/references/commands.md`。典型流程：

```text
task start → clarification.recorded → workflow.selected → contract.recorded
→ task check --phase contract → Codex 实现 → task run / evidence.added
→ ai.reviewed → knowledge.recorded → task finish → human.recorded → task finish
```

每个任务保存：

```text
.specify/tasks/<id>/
  events.jsonl       原始需求、修订、澄清、选型理由、操作、验收历史
  task.json          从事件生成的当前投影
  artifacts/         执行收据、截图、日志等副本及 hash
  report.md          finish 时生成的人类可读交付报告
```

原始需求带来源引用。澄清用 Codex 当前可用的原生问题工具，工具不可用时
直接在会话中询问。记录 human / host-auto / agent-assumption / unknown，
待用户决定的事项不能用自动默认值替代。清楚的需求可记录无需澄清及理由。

契约明确每条可观察需求、源码范围、诊断输入和证据类型。快照绑定**声明的
文件范围**，不保证发现范围外改动；Agent 必须完整声明影响面。范围内源码、
输入、需求修订、选中包版本或证据文件变动，旧证明失效。

runner 记录实际命令、工作目录、起止时间、退出码、stdout/stderr。负向 JSON
状态优先于退出码 0；structured 模式还要求 stdout 是正向状态的 JSON。
超时、启动失败和执行中输入改变均不会通过。测试/构建/check 收据只由 runner
生成。诊断允许失败探针作为 observed 证据，报告仍保留探针真实失败状态。

截图、CDP、浏览器扩展、Computer use、MCP 等外部观察保存 artifact、
tool_ref 和 target.identity，再逐条映射到需求。不能用 AI 编造的图片当运行
证据；界面外观和交互行为是不同的验收项。主机引用属于来源记录，当前版本
不独立证明消息或工具调用身份。日志有常见秘密值脱敏，分享前仍需复核。

AI 逐条判定需求并引用当前证据。人工验收单独记录真实来源和原话。
正常开发到 `delivered-awaiting-human` 就可以交付并结束当前回合，不自动
标为人工通过，也不循环催促。只读调查可由 workflow 允许在 AI 验收后关闭。

## 知识维护与版本

```powershell
specify pack bootstrap --id myteam/myproject --output knowledge/myproject --json
specify pack import-legacy --source ai/knowledge --id myteam/imported --output knowledge/imported --json
```

bootstrap 根据实际文件、manifest 和声明脚本生成地图与运行调试候选。
架构边界、UI 设计源、设备能力等无法证明的项标为未知。import 复制旧资料，
保留 provenance，全部作为待审 reference，不把旧 prose 自动升级为 policy。
两个命令都不自动安装或切换现有项目。

踩坑候选需包含：现象、适用范围/版本、证据、根因、解决方法和验证。
稳定经验经审查后可转成 policy/check；普通临时任务不塞入永久知识。
每个交付记录 maintained、candidate、deferred 或 none 及理由。

知识发布使用 patch / minor / major，workflow 版本随包版本同步。
review.json 必须包含真实人工来源、原话和当前 `pack validate` 返回的
content_sha256（字段名为 sha256，写入 review 时用 content_sha256）：

```json
{"status":"passed","origin":"human","source_ref":"user:message-id","quote":"实际审查结果","content_sha256":"当前包内容hash"}
```

```powershell
specify pack release knowledge/myproject --bump patch --reason "核实并修正调试步骤" --review-file review.json --json
```

该命令生成新版本、CHANGELOG 和发布指纹；不操作 Git tag 或远端。
已发布内容修改后不能直接安装旧版本，需重新审查并发布新版本。

## 恢复和主机适配边界

包写入用事务和备份，异常回滚；进程被终止留下的事务由 doctor 报告。
`pack recover <transaction-id>` 预览，`--apply` 恢复；发现后续用户修改则保护
现场并阻塞。任务事件 hash 链检测意外破坏，不能对抗可重写整个目录的写入者。

`task guard <id> --native` 是可选 Stop-hook 适配器，需要在真实主机注册。
同一需求/契约/源码状态最多请求一次继续；人工等待、明确阻塞、取消、已交付
直接允许结束。初始化不改主机 hooks/MCP，也不把这个适配器当完整安全隔离。

旧项目先运行 `pack migration-plan`，隔离试装、导入并检查知识，再明确处理
旧版 AGENTS/skills。此版本不自动改写活动 legacy 项目。新模式项目通过
`pack refresh` 或 `specify upgrade` 更新受管资产，自定义内容保留并报冲突。

## 贡献者验证

```powershell
python -m pytest tests/test_codex_skill_runtime.py
python scripts/python/smoke_codex_skill.py --source --output dist/my-new-trial
```

第二条命令要求新的输出目录，真实调用 CLI 跑缺陷修复、只读调查、知识生成
和 UI 缺证据阻塞场景。UI 场景需另接真实浏览器工具完成点击与截图后才能
通过；脚本不伪造界面或人工验收。省略 `--source`、指定 `--python <wheel环境python>`
可验证安装包，避免因开发机的源码环境而漏掉打包问题。
