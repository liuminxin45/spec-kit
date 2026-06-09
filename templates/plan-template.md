# 实施计划: [CAPABILITY]

> 语言规范：`plan.md` 面向人工审核，使用中文为主。文件路径、模块名、
> 类名、函数名、API、字段名、枚举值、状态值、命令、测试名等技术标识
> 必须保留英文原文。`research.md`、`data-model.md`、`contracts/` 主要给
> AI Agent 和实现过程使用，优先使用英文；`quickstart.md` 面向人工验收，
> 使用中文为主。

**Feature Directory**: `specs/[feature-name]`
**日期**: [DATE]
**Spec**: [link to spec.md]
**Constitution**: `.specify/memory/constitution.md`

## L2 Artifact Contract

- **Layer**: L2 Technical Specification
- **Purpose**: translate L1 behavior into implementation approach, affected
  modules, contract boundaries, root-cause evidence, design artifacts, and
  validation strategy.
- **Required sections**: `人类审核摘要`, `概览`, `Root Cause Evidence`, `技术上下文`,
  `影响模块与边界`, `接口与数据层落点`, `验证计划`, `项目结构说明`, `复杂度跟踪`.
- **Design artifacts**: use `research.md`, `data-model.md`, `contracts/`, and
  `quickstart.md` when applicable; write explicit `N/A` reasons otherwise.
- **Structured state**: update `workflow-state.json` attempts, validations,
  fact-layer status, acceptance state, retrospective state, and promotion state
  as the workflow progresses.
- **Implementation slices**: for `standard-bugfix`, this `plan.md` may carry
  complete `Implementation Slices` directly and replace a separate `tasks.md`.
  For `full-sdd`, generate L3 `tasks.md` from those decisions.

## 人类审核摘要

> 该区是给人类 reviewer 的快速入口；不得替代或删减后续 AI/流程读取区。
> AI Agent 必须继续读取完整的技术上下文、影响模块、边界、风险、验证计划和设计产物后再生成任务或实施。

- **一句话方案**: [选定技术方案和交付结果]
- **重点审核**: [最需要人工确认的 1-3 个架构取舍、影响模块、兼容边界或验证策略]
- **真实改动范围**: [主要文件/模块/仓库；详细 ownership 仍写在后续表格]
- **不涉及 / N/A 汇总**: [压缩列出不涉及的 SDK/Biz/UI/runtime/device/design 等边界]
- **主要风险与缓解**: [最高风险及对应验证/降级/回滚策略]
- **验证入口**: [最短 build/test/smoke/manual review 命令或步骤]
- **当前状态 / 下一步**: [Ready for tasks/Needs adjustment/Blocked 及原因]
- **必需人工决策**: [仅产品/业务取舍、owner-approved gap、外部验证、验收、commit/cherry-pick completion；无则写 N/A]

## 概览

[用中文概述能力目标和选定技术方案。]

## 分流对齐

**Task Type**: migration / bugfix / new-feature / needs-routing
**Routing Confidence**: high / medium / low
**Risk Level**: low / medium / high / blocked
**Delivery Profile**: micro-fix / standard-bugfix / full-sdd / blocked-investigation / validation-only
**Intake Source**: [link to intake.md]
**计划关注点**:

- **Migration**: Qt 源行为、平迁等价性、兼容性、迁移残留。
- **Bugfix**: 复现、预期行为、根因边界、回归验证。
- **New Feature**: 新意图、契约设计、兼容性、新增覆盖。

## Root Cause Evidence

Bugfix 必填；非 bugfix 标记 `N/A` 并说明原因。不得把“与某模块相似”
当作根因证据本身。

| Field | Evidence |
|-------|----------|
| Symptom | [用户可见问题] |
| Call Path | [入口到问题代码的调用链] |
| Evidence | [代码、日志、测试、复现或可观察事实] |
| Excluded Alternatives | [排除过的可能原因及证据] |
| Counterexample | [什么情况会证明当前方案错了] |
| Blast Radius | [改动影响哪些真实路径、设备、API 或状态] |
| Validation Mapping | [每个风险由哪个测试/smoke/人工验收覆盖] |
| Confidence | high / medium / low |

若 `Confidence` 不是 `high`，任务不得写死具体补丁；应先进入证据补全
或 `blocked-investigation`。

## 技术上下文

**Languages/Toolchains**: [C++/CMake/MSVC/Node/etc. or N/A]
**Primary Dependencies**: [SDKs, frameworks, plugins, scripts, or N/A]
**Target Runtime**: [Windows, DesktopShell, SDK, browser plugin, device
runtime, or N/A]
**Affected Build Targets**: [projects, solutions, packages, or N/A]
**Existing Patterns To Follow**: [附近模块、helper APIs、约定]

## 影响模块与边界

| Area | Path / Module | 预期变更 | Owner / Boundary |
|------|---------------|-----------------|------------------|
| SDK/API | [path] | [变更] | [边界] |
| ProductNativePlugin / NativeBridge bridge | [path] | [转发接口变更] | [仅 API forwarding，无业务逻辑] |
| Frontend/Plugin | [path] | [变更] | [边界] |
| Scripts/Tools | [path] | [变更] | [边界] |
| Tests/Validation | [path] | [变更] | [边界] |

## UI 展示、Biz 转发与 Libs 事实边界

UI 相关能力必须填写；不涉及 UI 时标记 `N/A` 并说明原因。

- **NativeBridge 边界**: [仅转发哪些 API request/response；不得实现哪些业务逻辑]
- **CoreServicesLib 事实来源**: [提供哪些 device/runtime/cache/handle/transport/permission/
  capability 数据或非 UI 专属业务规则]
- **Frontend display composition**: [前端插件如何组织仅用于 UI 展示的结构、顺序、
  visible/enabled、交互入口和视觉降级]
- **UI 可持有状态**: [仅允许 display state、hover/open/selection/loading 等临时状态；
  如需例外，说明原因]
- **UI 禁止伪造/推断**: [permission、device connected state、runtime availability 等真实事实
  不得由 UI 硬编码、label/string 推断或长期缓存]
- **UI interaction 展示契约**: [frontend-owned interaction/action id、label key、order、visible/enabled、
  reason、action id，以及依赖的 CoreServicesLib facts/source fields]
- **获取时机**: [用户触发、Biz bridge 事件到达后主动 refresh、数据刷新后同步等]
- **契约文件/接口位置**: [具体 header/source/module/contract 文件]

## Identity / State / API Boundary

涉及设备身份、设备列表、运行态、连接/采集状态、UI operation availability、RPC/N-API
或 public API 时必填；否则标记 `N/A` 并说明原因。

- **Canonical device identity**: [UUID decimal string；跨 Libs facade、Biz、N-API/JSON/RPC、
  JS/UI 边界只允许这一种语义]
- **Internal native ids**: [SDK handle/native id/virtual id 的底层私有存放位置；不得跨到
  Libs facade/Biz/UI]
- **UUID generation owner**: [`device::identity::generateUUID()`；`DeviceManager`、
  `SdkService`、UI 只使用，不生成规则]
- **Truth source**: [`CoreServicesLib` snapshot/runtime facts；Biz 不缓存、不计算状态]
- **Biz boundary**: [forwarding、参数校验、JSON/RPC/N-API 边界转换、事件转发；无业务逻辑]
- **Frontend operation identity**: [业务操作只读 `node.uuid`；不得用 `node.id`、
  `entityId`、`metadata.uuid` 兜底]
- **Event semantics**: [事件只触发刷新；刷新后重新从 Libs 获取 snapshot/runtime facts]
- **Deprecated API handling**: [remove / migrate / owner-approved temporary gap；不得功能等价并存]
- **Debug/test API handling**: [test/script/debug-only tooling / N/A；不进入生产 Biz exports]
- **Naming boundary**: [`uuid` / `deviceUuids` / `nodeId` / `listIndex` 等真实语义命名]
- **Generated artifacts**: [`build/`、`export/`、`plugin-out/` 是否已忽略/清理，避免污染判断]

## Qt 源 UI 行为平迁覆盖清单

`migration` 涉及 UI interaction、operation availability 或设备运行态 UI 时必填；否则写 `N/A`
并说明原因。该清单必须来自 Qt 源代码/设计输入，且用于约束 `CoreServicesLib` 事实契约、
`NativeBridge` 转发接口和 frontend display composition。
不强制使用固定表格格式，但必须覆盖：

- Qt source path/function。
- 对象/设备类型与状态/条件。
- UI element 顺序或 action 顺序。
- visible/enabled 规则。
- action id / handler。
- 目标契约字段或接口：`CoreServicesLib` facts、`NativeBridge` bridge API、
  frontend display composition。
- 缺口 / owner / `N/A`。

推荐使用表格；复杂场景可以按设备类型分组、使用决策表、状态机说明、
fixture matrix 或按 Qt 函数分段的规则清单。

## 接口与数据层落点

Agent 必须先搜索既有结构，再决定落点。避免单文件膨胀。

| 职责 | Existing candidate | Decision | 新增文件? | 说明 |
|------|--------------------|----------|-----------|------|
| Public/API contract | [path or N/A] | [reuse/new] | [yes/no] | [ownership] |
| NativeBridge bridge API | [path or N/A] | [reuse/new] | [yes/no] | [forwarding only] |
| Runtime/permission facts model | [path or N/A] | [reuse/new] | [yes/no] | [CoreServicesLib ownership] |
| UI display model | [path or N/A] | [reuse/new] | [yes/no] | [frontend plugin ownership] |
| Adapter/serialization | [path or N/A] | [reuse/new] | [yes/no] | [ownership] |
| UI integration | [path or N/A] | [reuse/new] | [yes/no] | [只做展示/事件/请求] |

## UI 设计来源目录

UI 相关的 `migration` 和 `new-feature` 必填；否则标记为 `N/A` 并说明原因。

| 目录类型 | Path | 适用类型 | 计划用途 | 缺口 / Owner |
|----------------|------|--------------|--------------|-------------|
| Original Qt UI/source | [path or N/A] | migration | 平迁来源 | [缺口/owner] |
| Product design/mockup/export | [path or N/A] | migration/new-feature | 视觉/产品验收 | [缺口/owner] |
| Target frontend/plugin | [path or N/A] | migration/new-feature | 实现目标 | [缺口/owner] |
| Shared assets/icons/screenshots | [path or N/A] | migration/new-feature | 视觉平迁 / assets | [缺口/owner] |
| Missing design inputs | [path or N/A] | migration/new-feature | 实现前阻塞项 | [缺口/owner] |

## UI Parity Runtime Layout Evidence

UI parity、frontend visual 或 host-embedded UI 任务必填；否则标记为 `N/A` 并说明原因。
该区用于避免只依据静态设计稿猜 CSS。

- **Real host route/page**: [真实宿主页/路由；单插件预览是否不足]
- **Host/plugin ownership chain**: [从 host container 到目标元素的父子/兄弟容器及所属仓库/插件]
- **Static references**: [设计稿、Qt `.ui`、delegate、qss、source、截图]
- **Dynamic states**: [hover、selected、disabled、expanded/collapsed、loading、empty、
  many-item、scrollbar appear/disappear]
- **Geometry constraints**: [固定宽高、padding/margin、line-height、border、title/header/footer、
  sibling 容器、信息栏/树等平级关系]
- **Layout mechanics**: [scroll owner、overflow、position、display、flex/grid、flex-shrink、
  flex-grow、min/max size、scrollbar reservation]
- **Runtime evidence needed**: [runtime DOM / computed style / box metrics，包括 DOM ancestry、
  截图/Inspector evidence]
- **Stop-loss rule**: [首轮实现后若布局/滚动/裁剪/空白/挤压仍失败，先补 runtime evidence
  或进入 bounded UI runtime investigation，不继续猜测样式]
- **Host-level validation**: [真实宿主页中如何验证大量条目、滚动条出现/消失、动态状态、
  sibling/header/footer 不被压缩或重排]

## UI Element Traversal Inventory / 0px Alignment Matrix

UI parity、0px 级视觉修复、截图对齐或复杂 UI/UX 改动必填；否则标记为 `N/A` 并说明原因。
该区用于让 AI 在实现前自动遍历相关 UI 元素和状态，按外到内、父到子、共享 token 到局部样式的顺序一次性收敛。

- **Baseline anchors**: [用于对齐的固定基准，如窗口左上角、标题行、工具栏、容器边框、首个列表项]
- **Traversal order**: [outer container -> header/toolbar -> scroll owner -> repeated items -> nested labels/icons -> footer/detail panel]
- **0px target**: [哪些坐标/尺寸要求 0px 偏差；哪些视觉项允许人工判断或 N/A]
- **Batch patch strategy**: [优先修改 shared layout constants/tokens/row-height/indent/icon-size，再处理局部例外；避免一处偏差一个补丁]
- **Unknowns that block first patch**: [缺失设计坐标、缺失运行态 DOM、无法连接 host、状态无法触发等]

| Order | Element / State | Source reference | Target selector/component | Expected geometry/style | Current runtime evidence | Delta | Fix owner |
|-------|-----------------|------------------|---------------------------|-------------------------|--------------------------|-------|-----------|
| 1 | [container/default] | [design/Qt/screenshot] | [selector/component] | [x/y/w/h, padding, margin, font, icon, color, border] | [DOM/computed/box/screenshot] | [dx/dy/dw/dh] | [file/module] |
| 2 | [state variant] | [source] | [target] | [expected] | [actual] | [delta] | [owner] |

## UI / UX / 文案 Evidence Gate

所有 UI 开发、UI 变更、UI 修复、UX、图标、tooltip、按钮、菜单、可见文案、
样式和布局变更必填；否则标记为 `N/A` 并说明没有任何可见 UI 变化。
不得凭空设计 UI。若缺少可靠依据，计划必须停在 clarify / blocked-investigation，
不能进入实现。

| Change | Reliable source | Required exact behavior/text/style | Implementation target | Missing evidence / clarification |
|--------|-----------------|------------------------------------|-----------------------|----------------------------------|
| [button/icon/tooltip/copy/layout/state] | [Qt source/QSS/resource, design, screenshot, existing convention, or owner decision] | [exact expected result] | [file/component/selector] | [none or blocker] |

## 宪章检查

| 原则 | Status | 说明 |
|-----------|--------|-------|
| Minimal scoped change | PASS/REVIEW | [说明] |
| Existing patterns first | PASS/REVIEW | [说明] |
| Compatibility boundaries | PASS/REVIEW | [说明] |
| Runtime truth | PASS/REVIEW | [说明] |
| UI/Biz/Libs layering | PASS/REVIEW/N/A | [NativeBridge 是否仅转发；Libs 是否提供事实；frontend 是否只做 UI 展示组合] |
| Interface/data file ownership | PASS/REVIEW/N/A | [是否避免接口/数据层单文件膨胀] |
| Validation evidence | PASS/REVIEW | [说明] |
| Encoding/localization boundary | PASS/REVIEW/N/A | [说明] |
| Local-only Spec branch workflow | PASS/REVIEW | [branch, affected repos, cherry-pick-back notes] |

## 设计产物语言策略

保留上游产物模型，但按用途区分语言：

### research.md

给 AI Agent 和实现者记录技术取舍、现有代码发现、工具链决策与被拒方案。
优先使用英文，技术标识保持原文。

### data-model.md

给 AI Agent 和实现者记录 durable state、DTOs、SDK structs、serialized fields、
UI state、device state 或 permission models。优先使用英文；不适用时写
`N/A` 并说明原因。

### contracts/

给 AI Agent 和实现者记录 public headers、SDK APIs、ProductNativePlugin/NativeBridge
forwarding input/output、plugin contracts、frontend state/events、CLI/script interfaces、
runtime/device status fields。优先使用英文，接口、字段、事件名不得翻译。

### quickstart.md

面向人工验收，使用中文为主。命令、路径、测试名、状态值保持英文原文。

## 兼容性与迁移风险

| 风险 | 影响 | 缓解措施 | 验证 |
|------|--------|------------|------------|
| [风险] | [影响] | [缓解措施] | [验证] |

## 验证计划

- **Build**: [命令或说明]
- **Automated Tests**: [命令或说明]
- **Test-Case Update**: [unit/regression/fixture/contract/smoke case 或 N/A
  及原因]
- **Runtime/UI Smoke**: [AI-owned host/CDP/browser/API smoke steps first; after each code change, rebuild/deploy source output when needed, rerun smoke, and repeat until pass or proven blocked; include target URL, action, process/log/state assertions, or N/A reason]
- **Device Validation**: [real/virtual/N/A; for real-device/status/runtime changes, explain the agent-run smoke or the probed unavailable condition]
- **Manual Review**: [final human review only after agent-owned technical validation evidence; only user-visible acceptance, product/owner decisions, or external conditions the agent proved unavailable]
- **Known Gaps**: [当前无法验证什么]

> `Known Gaps` 不能覆盖本次改动正好引入的核心行为风险。若 gap 落在
> status/permission/device/API 等核心路径，状态必须是 `Blocked` 或 `High risk`
> 并进入必需人工决策或 bounded investigation。

## 项目结构说明

只记录与本能力相关的真实结构，不粘贴无关完整目录树。

```text
[relevant paths only]
```

## 复杂度跟踪

仅当方案偏离既有模式或扩大范围时填写。

| 决策 | 为什么需要 | 拒绝的更简单方案 |
|----------|------------|------------------------------|
| [决策] | [原因] | [替代方案] |
