# Spec Kit 官方 v0.12.5 → v0.16.2 跟进报告

## 结论

本地从 `github/spec-kit@v0.12.5` 选择性跟进到 `github/spec-kit@v0.16.2`。这里的“对齐”表示
已审查版本范围内的主要产品、工作流、安装、集成、安全、测试和文档变化，并完成适合本地
Codex 工作流的实现与瘦身；不表示逐文件复制官方实现。

官方目标版本通过 GitHub Releases 最新稳定版本接口确认：`v0.16.2`，非 draft、非
prerelease，发布时间为 2026-08-10。本次调查同时核对了版本比较、CHANGELOG、目标 Tag
源码与测试，未仅依赖 Release 摘要。

## 证据与调查范围

- 最新稳定版：<https://github.com/github/spec-kit/releases/tag/v0.16.2>
- 版本差异：<https://github.com/github/spec-kit/compare/v0.12.5...v0.16.2>
- 目标版本 CHANGELOG：<https://github.com/github/spec-kit/blob/v0.16.2/CHANGELOG.md>
- 工作流实现：<https://github.com/github/spec-kit/blob/v0.16.2/src/specify_cli/workflows/engine.py>
- CLI、安装与集成：目标 Tag 的 `src/specify_cli`、README、命令及测试。
- 本地事实：CLI、工作流引擎与节点、catalog、knowledge/capability pack、安装脚本、模板、
  测试和用户文档。

已检查新增、修改、删除、替换、弃用及简化，覆盖产品能力、CLI、Spec 驱动流程、节点职责、
Prompt/模型上下文、安装升级、分发集成、配置状态、安全验证、维护和文档。没有发现需要
照搬的官方核心阶段或 Prompt 重构。

## 变化与处置

| 官方变化方向 | 本地关系 | 处置 |
|---|---|---|
| 工作流输入/步骤校验、错误处理和状态恢复 | 部分覆盖 | 适配引入；补齐类型、结构、非有限数字、损坏状态和执行前校验 |
| Shell/Prompt timeout | Shell 固定 300 秒，Prompt 无超时 | 引入统一可配置正有限秒数，默认 300 秒 |
| Gate 文件展示、`verdict_input` | 已有 `show_file` 字段但未展示 | 实现有界、控制字符清理的展示；不引入自动 verdict 输入 |
| HTTP、重定向、响应体和下载安全 | 已有 HTTPS 和跨域凭据隔离，读取无边界 | 适配引入响应上限、重定向降级阻断和严格 UTF-8/JSON 错误 |
| Extension 提供模板、脚本和 init 脚手架 | 与 knowledge/capability pack 重叠 | 不引入 |
| PyPI、自定义索引、tar 安装、在线 self-upgrade | 与受控/离线分发冲突 | 不引入，保留本地 bundle 和只读 self check |
| Native agent runtime/context injection | 本地已有 workflow hooks 和 agent chain | 不引入重复机制 |
| 固定 SDD Prompt 和阶段职责 | 本地已有风险/画像驱动的精简路由 | 不覆盖本地流程 |
| 通用 Agent 与社区 catalog 增量 | 本地定位为 Codex-only、默认无远程目录 | 不引入 |
| `.specify/.gitignore` | 运行状态参与本地 preflight 治理 | 不引入，避免隐藏未闭环状态 |
| Roo、Windsurf、iflow 删除及 agent context 改为 opt-in | 本地无这些公开集成，且上下文已按需加载 | 无迁移；验证本地方向一致 |

## 本地瘦身

- 删除根 CLI 中未注册、不可从公开命令到达的 extension、preset 和 integration catalog
  应用及其命令实现；保留 integration 切换仍调用的 `ExtensionManager` 内部兼容能力。
- 删除无效隐藏参数 `--skip-tls`、`--github-token`、`--offline`；保留实际输出失败详情的
  `--debug` 并使帮助说明与行为一致。
- 不删除本地风险路由、人工 gate、知识选择器和 preflight。它们仍保护真实治理边界，模型
  能力增强不足以证明这些约束已经失去价值。

## 实现结果与兼容影响

- Workflow YAML 的 Shell/Prompt 节点新增可选 `timeout`；旧文件继续使用 300 秒默认值。
- 畸形 Workflow 在创建运行目录前失败；损坏运行记录在单次加载时给出明确错误，在列表中
  被隔离，不再破坏全部查询。
- `gate.show_file` 现在展示最多 200 行并清理终端控制字符；人工审批语义不变。
- `github-release` hook 依赖现在必须使用绝对 HTTPS URL 和 64 位十六进制 SHA-256。缺少
  校验值的旧 pack 需要补齐摘要后才能安装。
- 本地包版本由 `0.10.4` 升为 `0.10.5`；官方基线由 `v0.12.5` 升为 `v0.16.2`。

## 未知与观察项

- 官方 extension 生态的长期稳定性、第三方 catalog 的实际采用率尚无本地需求证据，继续
  观察，不为潜在需求预置维护成本。
- 官方 agent runtime hooks 与本地 workflow-agent-chain 的未来收敛空间需要在出现真实跨
  Agent 用户后复查。
- 本次未引入官方 `.specify/.gitignore`；若将来运行状态完全迁出治理链，再重新评估。
