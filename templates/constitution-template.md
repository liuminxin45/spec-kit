# [PROJECT_NAME] 工程宪章

> 语言规范：本文档面向人工审核，使用中文为主。仓库名、文件路径、模块名、
> API、字段名、枚举值、状态值、命令、测试名等技术标识必须保留英文原文。

## 核心原则

本宪章是 L0 原则摘要与冲突裁决入口。更细的长期规则拆分在：

- `ai/rules/engineering-principles.md`
- `ai/rules/architecture-constraints.md`
- `ai/rules/ai-coding-rules.md`

正常 feature workflow 不得静默修改 L0 规则文件。原则更新必须来自人工确认的
retrospective/promote-lessons 候选，并说明来源证据、变更原因和预期影响。

### 1. 最小范围变更

变更必须限制在当前 spec 描述的能力、缺陷、迁移或工具诉求内。除非已在
`plan.md` 中明确列出，否则不允许无关重构、格式化噪声、生成元数据扰动或
顺手清理。

### 2. 既有模式优先

实现前必须先阅读附近代码、既有 helper APIs、项目 scripts、build files 和集成约定。
只有在能消除真实复杂度、匹配既有项目模式，或由明确 contract 要求时，才允许新增抽象。

### 3. 兼容边界是一等约束

Public API、SDK/API、CLI、脚本接口、integration contracts、serialized fields、
runtime status 和 permission semantics 都是兼容边界。任何破坏兼容或改变行为的更新，
都必须在 `spec.md` 和 `plan.md` 中说明影响、迁移方式和验证证据。

### 4. 运行时真实状态优先

系统必须保留真实 external-system、cache、transport、handle、permission 和 runtime
state。只有在明确限定的 simulation boundary 内，才允许 fake status、placeholder handles
或 optimistic UI state。

### 5. UI 展示、Service 转发与 Runtime 事实边界

当项目存在 frontend/service/runtime 或 adapter 分层时，forwarding/adapter layer 只能转发
请求和响应；不得实现业务规则、状态推导、权限/可用性判断、UI 行为计算或业务模型沉淀。
非 UI 专属的业务能力、runtime/cache/handle/transport/permission 事实和可复用规则必须落在
对应 domain/runtime owner。仅服务于当前 UI 展示的组合代码，例如展示结构、条目顺序、
视觉禁用态组织、交互入口编排，应落在 UI/frontend 层，但必须基于 domain/runtime owner
暴露的事实和能力数据；不得用 label/string 推断真实状态，不得伪造 runtime/permission 事实，
或长期缓存业务状态作为事实来源。

### 6. 接口与数据实现必须按职责拆分

当新增或扩展 domain/runtime owner、frontend/UI 层或 forwarding/adapter layer
的接口、DTO、permission model、UI display model、cache adapter 或数据转换逻辑时，Agent 必须先搜索既有
目录结构、相邻模块、helper APIs 和 ownership 边界，选择最合适的位置落代码。不得为了
省事把接口层、数据层、转换层、业务规则和 UI 适配全部堆进单个已有文件。若当前没有
合适承载文件，必须新增职责清晰的 header/source/module 文件，并在 `plan.md` 说明新增
文件的 ownership、依赖方向和替代方案。

### 7. 身份、状态和 API 只有一个归属

跨 runtime facade、adapter、RPC/JSON、JS 和 UI 边界的业务实体身份必须只有一个规范来源。
不得在跨语言、跨进程或跨服务合同中为同一实体引入平行身份。身份生成规则只能归属单一 owner；
manager、service 或 UI 层只能使用该身份，不得各自生成规则。底层 native id、runtime handle、
list index、cache key 或 UI node id 只能作为局部实现细节，不得泄漏为业务实体身份。

功能等价旧 API 不得与新 API 长期并存。旧的 forwarding path、facade、RPC 或 helper
应删除或明确迁移，不得形成调用方分裂。调试 API、测试 facade、临时 passthrough 能力不得进入
生产 service layer exports；验证需求应放在测试、脚本或明确隔离的 debug-only tooling 中。
事件只能触发刷新，不能成为真相源；状态变化后仍必须通过 owning domain/runtime layer
重新获取事实。命名必须表达真实语义，避免把索引、展示节点、缓存键或外部句柄命名为业务身份。
`dist/`、`build/`、`export/` 等构建产物不得参与接口判断、diff 判断或交付来源判断。

修改产品行为时必须修改仓库源码，不得把已安装运行目录、部署目录或构建产物当作长期修复位置。
若为紧急诊断临时修改产物，验收/提交前必须回写到源码，并排除产物补丁。

### 8. 验证证据必须闭环

每个 `plan.md` 都应识别合适验证方式：build、unit、integration、smoke、UI flow、
target-environment check、manual review 或 downstream consumer verification。
无法执行验证时，必须记录 gap 和明确后续动作。

### 9. 编码与本地化边界必须显式

Native string encoding、UTF-8 conversion、localized display text 和 protocol field
encoding 必须在文档化边界处理。不得在无关层级增加 ad hoc conversion。

### 10. 本地 Spec 分支工作流

每个 Spec 都必须从本地 `NNN-short-name` Spec branch 开始。当任务涉及多个仓库时，
每个受影响仓库都必须使用同名本地 Spec branch。Spec Kit 不得 push branches、
创建 remote tracking branches，或依赖 GitHub issue generation。Spec workflow
在通过用户验收、必要提交完成、每个受影响仓库都将本地 Spec branch 的提交
cherry-pick 回创建 Spec branch 时记录的入口分支后才算完成；默认保留本地 Spec branch，不删除。
Commit 是 AI-owned technical gate：通过 deterministic preflight、scope/message
validation、用户验收和 retrospective 后可以自动执行本地提交。Complete-branch 是
state mutation gate：preflight 可以自动执行，但 cherry-pick 分支完成前必须请求并获得用户明确确认。
Push、force-push 和 remote tracking 属于远端状态变更，默认禁止；如维护者例外要求，必须先通过
`preflight-push` 并获得明确人工确认，优先走 PR。

## 项目结构指引

宪章描述边界，而不是冻结的目录树。每个 `plan.md` 必须识别当前能力实际影响的
模块和文件 ownership，例如 SDK/API headers、integration/adapter implementation、
frontend/UI code、scripts、generated assets、tests 或 documentation。

## 治理

- 当宪章与生成模板默认规则冲突时，以宪章为准。
- 当 `ai/rules/*` 与宪章冲突时，以宪章为准，并记录待人工修订项。
- 修订宪章必须摘要说明变更原则、受影响产物和预期迁移影响。
- 原则变更后，应重新检查既有 feature specs 和 plans。
- 任何原则例外都必须记录在 `plan.md` 的 complexity 或 risk tracking 中。
- L0.5 项目事实文件位于 `ai/knowledge/*` 与 `.specify/memory/*`。AI 只能在有来源证据、
  变更原因、验证证据和人工批准时推广长期事实。

**Version**: [CONSTITUTION_VERSION] | **Ratified**: [RATIFICATION_DATE] | **Last Amended**: [LAST_AMENDED_DATE]
