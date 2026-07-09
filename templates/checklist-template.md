# [CHECKLIST TYPE] 检查清单: [CAPABILITY NAME]

> 语言规范：本文档面向人工审核，使用中文为主。文件路径、模块名、
> API、字段名、枚举值、状态值、命令、测试名等技术标识必须保留英文原文。

**目的**: [本检查清单验证什么]
**创建时间**: [DATE]
**Feature**: [Link to spec.md]

## 人类审核摘要

> 该区是给人类 reviewer 的快速入口；不得替代或删减后续 AI/流程读取区。
> AI Agent 必须继续读取完整检查项、生成策略、证据说明和阻塞项后再判断是否进入下一阶段。

- **检查结论**: [Pass/Blocked/Needs adjustment，并说明一句话原因]
- **阻塞项**: [未勾选或需要 owner 决策的 CHK ID；无则写 N/A]
- **重点风险**: [最需要人工复核的兼容、验证、边界或分支风险]
- **N/A 总览**: [大量不适用项的压缩说明；具体原因仍保留在检查项中]
- **验证入口**: [校验脚本、人工检查或下一步 gate]
- **下一步**: [进入哪个 speckit stage，或先调整哪些上游文档]
- **必需人工决策**: [仅产品/业务取舍、owner-approved gap、外部验证、验收、commit/cherry-pick completion；无则写 N/A]

## 生成策略

- 结构来源：本文件提供稳定章节和基础 `CHK` 项，避免不同模型输出漂移过大。
- 规则来源：生成时必须读取 `.specify/checklist-rules/common.yml`，并按
  `.specify/feature.json` 的 `task_type` 选择 `new-feature.yml`、`migration.yml`
  或 `bugfix.yml`；涉及 CLI、脚本、生成物或文档工具时，同时读取 `tooling.yml`。
- Gate 来源：专项证据只来自 `select-gates` 返回的 selected gate packs，
  不写入默认清单。
- 证据原则：每个勾选、未勾选或 `N/A` 判断都必须能追溯到 `spec.md`、
  `intake.md`、`.specify/feature.json`、`.specify/memory/constitution.md`、
  selected gate packs 或被规格点名的项目文件。
- 弹性原则：可以补充任务专属检查项和说明，但不得删除适用的安全、兼容、
  验证或本地 Spec 分支检查项。`N/A` 必须说明原因，未勾选项必须说明缺口。
- 质量门：生成后应运行 `.specify/scripts/powershell/validate-checklist.ps1`
  检查 `CHK`、无原因 `N/A`、无说明未勾选项等问题。

## 需求质量

- [ ] CHK001 `intake.md` 已将任务分为 `migration`、`bugfix`、`new-feature`
  或 `needs-routing`，并说明原因。
- [ ] CHK002 `needs-routing` 不会继续进入实现阶段。
- [ ] CHK003 能力场景可以被独立理解。
- [ ] CHK004 需求是可观察、可审核或可测试的。
- [ ] CHK005 待确认问题已标记为 `NEEDS CLARIFICATION`。

## 工程边界

- [ ] CHK006 已识别影响模块、仓库和 ownership boundaries。
- [ ] CHK007 如相关，已覆盖 Public API、service/runtime/UI state、data model、
  script contracts 或 external-system contracts。
- [ ] CHK008 已记录兼容性、迁移和下游影响，或明确标记为 `N/A`。
- [ ] CHK009 权威状态、身份、权限、缓存和刷新来源已明确；adapter/bridge 层没有
  静默拥有业务规则或源事实。
- [ ] CHK010 已记录 encoding、localization、serialization 和 generated-output
  boundaries。
- [ ] CHK010A 改动落在仓库源码；没有把生成输出、缓存、安装目录或构建产物作为长期修复位置。
- [ ] CHK010B 新增或扩展接口层/数据层前，已搜索既有目录和相邻模块。
- [ ] CHK010C contract、DTO、availability model、cache adapter、serialization
  和 UI adapter 已按职责落到合适文件；若没有合适文件，已规划新增职责清晰的文件。
- [ ] CHK010D 等价旧 API、debug/test API、临时 facade 或兼容入口已删除、迁移，
  或有 owner-approved temporary gap。
- [ ] CHK010E 字段命名表达真实语义；未新增含混或平行身份/状态字段。
- [ ] CHK010F selected gate packs 中列出的专项边界已被纳入检查项或明确 `N/A`。

## 分流专项就绪度

- [ ] CHK011 `migration` 已说明源行为、等价预期和迁移风险，或记录 owner-approved `N/A`。
- [ ] CHK012 `bugfix` 已包含实际行为、预期行为、复现路径和回归预期。
- [ ] CHK013 `new-feature` 已说明为什么不是直接迁移，并给出验收信号。
- [ ] CHK014 UI/UX/copy 相关工作已列出可靠依据；如依据缺失，已阻塞到 clarify /
  bounded investigation，没有凭空实现。
- [ ] CHK014A `delivery_profile` 与影响面匹配；`micro-fix` 仅用于单仓、小范围、
  内部、根因已证实、有本地验证且不涉及 public API、身份、权限、外部系统或跨层风险的改动。
- [ ] CHK014B Bugfix 进入实现前已有 `Root Cause Evidence`：Symptom、Call Path、
  Evidence、Excluded Alternatives、Counterexample、Blast Radius、Validation Mapping
  和 Confidence。
- [ ] CHK014C 计划和任务没有把未证实方案提前写死；核心路径 known gap 未被当作 PASS。
- [ ] CHK014D 如涉及 UI parity、截图对齐或 0px 级视觉修复，`plan.md` 已包含
  UI element traversal inventory / 0px alignment matrix，并覆盖 dynamic states、
  computed style 和 box metrics（如运行时证据可用）。

## 验证

- [ ] CHK015 已描述 build、test、smoke、manual 或 selected-gate validation。
- [ ] CHK016 每个已验证行为都有计划补充 unit test、regression test、fixture、
  contract test、smoke case，或明确 `N/A` 原因。
- [ ] CHK017 test-case updates 后会重新运行受影响测试。
- [ ] CHK018 无法执行的验证已记录为 known gap，并区分 agent 可修复缺口和外部 blocker。
- [ ] CHK018A 搜索范围被限制在受影响仓库和已知目录；没有默认扫描整个
  `workspace_root`，简单本地查找没有交给 explorer/subagent。
- [ ] CHK018B 如 selected gate packs 要求运行时、浏览器、包或外部系统证据，
  已列出对应命令、证据路径和 PASS/FAIL/BLOCKED 条件。

## 本地 Spec 分支工作流

- [ ] CHK019 该能力使用本地 Spec branch，不需要 remote push、remote tracking
  或外部 issue generation。
- [ ] CHK020 多仓任务已识别每个受影响仓库，并要求它们使用同名本地 Spec branch，
  完成前 cherry-pick 回创建 spec 分支时记录的入口分支。
- [ ] CHK021 分支 cherry-pick 完成动作必须在 agent 执行 completion command 前取得
  用户明确确认；默认保留 spec branch，不删除，不 push。
- [ ] CHK022 当前阶段完成后的衔接遵守 `ai/workflows/task-routing.md` 中央
  Stage Continuation Contract；若停止，必须写明 `blockers` 和
  `next_required_human_action`。

## 说明

- 可以增删检查项，使最终清单贴合当前能力。
- 优先使用具体检查项，避免泛泛的质量建议。
