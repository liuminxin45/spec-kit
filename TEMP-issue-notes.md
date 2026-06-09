# tools/spec-kit 临时问题记录

> 临时记录 Deepseek + cc 使用 `tools/spec-kit` 过程中暴露的待修复问题。
> 旧问题已清空；本文件只保留后续需要统一处理的新问题。

## DSCC-001 specify 完成且无阻塞级澄清，但未自动继续执行

- 记录时间：2026-06-09
- 运行组合：Deepseek + cc
- 来源阶段：`/speckit-specify`
- 来源 feature：`specs/014-fix-devicelist-contextmenu-ui`
- Local Spec Branch：`014-fix-devicelist-contextmenu-ui`
- Workspace Root：`<workspace-root>`
- Default Base Branch：`master`
- Repository Map：`.specify/memory/repository-map.md`

### 现场表现

`/speckit-specify` 完成后输出 `Speckit-Specify 完成报告`，报告明确写明：

- `待确认问题`：无阻塞级 `NEEDS CLARIFICATION`，所有期望行为已由用户明确描述。
- `下一阶段`：`Auto-capable speckit-clarify`。
- 说明文案：由于无阻塞级歧义，将通过 `/speckit-clarify` 自动确认后进入 `/speckit-plan`。

实际结果：命令停在完成报告页，没有真实执行 `/speckit-clarify`，用户仍需手动输入 `/speckit-clarify`。

### specify 输出上下文

- 8 个 workspace 仓库已切换到同名本地 spec branch。
- 仅 `ProductUIPlugin` 需要源码修改。
- 已生成或更新产物：
  - `specs/014-fix-devicelist-contextmenu-ui/spec.md`
  - `specs/014-fix-devicelist-contextmenu-ui/review.md`
  - `specs/014-fix-devicelist-contextmenu-ui/checklists/requirements.md`（已验证通过）
  - `specs/014-fix-devicelist-contextmenu-ui/workflow-state.json`

### 本次需求中的四个缺陷场景

- CS1 / P1：不可用条目 hover 时缺少背景色变化效果。
- CS2 / P1：不可用条目错误显示 `"当前权限不允许出现..."` tooltip。
- CS3 / P2：`"保存为GenICamXML"` 文字被截断显示省略号。
- CS4 / P2：子菜单条目 hover 光标错误变为手型，应保持箭头。

### 已记录关键假设

- 四个缺陷修复点均位于 frontend plugin (`ProductUIPlugin`) 源码中，主要是 Vue 模板/CSS。
- 无需触及 `NativeBridge` 或 `CoreServicesLib`。
- 修复不应影响菜单条目语义、顺序或 enabled/disabled 判定逻辑。
- `"保存为GenICamXML"` 截断问题预计可通过 `text-overflow` / `white-space` / `overflow` 等 CSS 修正。

### 伴随提示

- 终端显示：`Auto-update failed · Run /doctor`
- 初步记录：该提示可能是 cc 自身环境或更新噪声，暂不直接判断为 stage handoff 根因；后续复盘时可检查是否影响命令续跑能力。

### 期望行为

当 `speckit-specify` 已完成，且无阻塞级澄清、无人工确认项、无外部依赖或工具失败时，应真实继续执行下一结构化阶段，而不是只在报告中声明“自动进入”。

### 后续修复候选

- 检查 Deepseek + cc 场景下 prompt-only slash command 是否具备跨 command 调度能力。
- 若具备调度能力：强化 `specify -> clarify` handoff，要求无 gate 时真实触发下一阶段。
- 若不具备调度能力：禁止报告“自动进入”，改为明确输出 `blockers` / `next_required_human_action` 或可执行的人工下一步。
- 增加回归测试：`speckit-specify` 结束且 `blockers=[]`、无 blocking clarification 时，不能只输出“自动进入 clarify”的终态报告后停止。

## DSCC-002 commit 阶段未严格套用中文提交说明模板

- 记录时间：2026-06-09
- 运行组合：Deepseek + cc
- 来源阶段：`/speckit-commit`
- 来源仓库：`ProductUIPlugin`
- 来源提交：`654cd47ee0e8c8b928b2153939a622e97d60ed7a`
- CommitDate：2026-06-09 15:29:29 +0800
- 唯一批准模板：team `commit-message` skill 中编码的中文模板

### 现场表现

`ProductUIPlugin` 最新提交说明未完全符合 Spec Kit / `commit-message` 的中文模板要求。

本地读取到的提交说明开头为：

```text
DeviceContextMenu: Fix hover, tooltip, cursor, and ellipsis

修复设备列表右键菜单 disabled 条目 hover 无效果、
错误 tooltip、文字省略号、光标手型和圆角问题
```

`【提交类型】` 当前为：

```text
修复 - UI 交互
```

### 发现的问题

- 标题/概述存在换行合规风险：用户观察到标题换行问题；本地 `git log -1 --format=fuller` 显示英文 subject 为单行，但中文概述被拆成两行，需要确认提交生成器是否把 subject、中文概述和 68 显示列规则分别校验。
- `【提交类型】` 过于泛化，未严格落到模板要求的 `<类型> - <范围或问题域>`。当前 `修复 - UI 交互` 范围偏粗，不能清楚表达这是设备列表右键菜单 UI 缺陷修复。
- commit 阶段没有在提交前强制校验标题格式、提交类型格式、行宽、技术 token 不拆分等规则。

### 期望行为

`speckit-commit` 在真正创建提交前必须严格套用唯一批准的中文模板，并执行模板级校验：

- 首行必须为单行 `<Module>: <concise English summary>`。
- 第二段为中文一句话概括；如需换行，应按 68 显示列语义换行，且不得被误判或误生成到标题中。
- `【提交类型】` 必须为清晰的 `<类型> - <范围或问题域>`，例如 `缺陷修复 - 设备列表右键菜单 UI`。
- 所有非空行必须满足 68 显示列限制。
- 不得拆分路径、命令、类名、文件名、版本号等技术 token。
- `【自测结果】` 通过时必须以 `相关测试通过，自测通过` 收尾。

### 后续修复候选

- 强化 `speckit-commit`：提交前必须读取唯一批准模板并调用 `commit-message` 规则。
- 扩展 `validate-commit-message`：检查 subject 是否单行、提交类型是否足够具体、是否误用泛化类型、是否存在标题/概述换行混淆。
- 增加回归测试：以 `654cd47ee0e8c8b928b2153939a622e97d60ed7a` 的提交说明作为反例，确保标题换行、提交类型不正确等问题能在 commit 前被拦截。

## DSCC-003 代码完成并准备提交前未进入复盘环节

- 记录时间：2026-06-09
- 运行组合：Deepseek + cc
- 来源阶段：`/speckit-implement` -> `/speckit-commit`

### 现场表现

AI 完成代码、验证或准备提交时，没有先进入 `speckit-retrospective` 复盘/留痕环节，导致复盘变成提示性要求，而不是 commit 前硬门禁。

### 期望行为

- standard/full Spec Kit 工作流在 commit 前必须完成 `workflow-record.md` 和 `improvement-candidates.md`。
- `workflow-state.json` 中 `retrospective.status` 必须为 `completed`。
- commit 阶段在 inspect、stage、commit 之前必须先运行 artifact preflight；未通过时返回 `speckit.retrospective`。

### 本轮修复落点

- `validate-feature-artifacts --stage commit` 增加 retrospective gate。
- `speckit-commit` 模板和生成上下文要求先跑 preflight。
- 回归测试覆盖“只有复盘文件但 workflow-state 未完成也不得提交”。

## DSCC-004 CDP 宿主已运行或端口占用时，AI 直接停止自验并转人工验收

- 记录时间：2026-06-09
- 运行组合：Deepseek + cc
- 来源阶段：`/speckit-implement` / `/speckit-validation`

### 现场表现

让 AI 自动执行 CDP 验证时，如果启动宿主发现进程正在运行或端口已占用，AI 停止自验并进入人工验收，而不是先探测已运行 CDP target、复用有效宿主、识别端口占用者或尝试安全恢复。

### 期望行为

- CDP 验证前先探测 `/json/list`，记录 target inventory。
- 如果已有有效 DesktopShell business target，优先复用。
- 如果 CDP 不可达且端口无人占用，启动宿主并重试。
- 如果端口被占用，先识别 owner 并寻找安全恢复路径；破坏性终止进程必须有人明确批准。
- 只有完成上述 CDP host recovery ladder 后仍不可用，才允许停止并给出 `blockers` / `next_required_human_action`。

### 本轮修复落点

- 新增 `ensure-desktop-shell-cdp-host` PowerShell/Bash 脚本。
- `implement`、`validation`、workflow、AGENTS、task-routing、AI rules、CDP/build knowledge 均接入该恢复阶梯。
- 回归测试覆盖可复用 target 和仅有 workbench target 的阻断行为。

## DSCC-005 复盘 spec-kit 时可能盲目追加新约束

- 记录时间：2026-06-09
- 运行组合：Deepseek + cc
- 来源阶段：`/speckit-retrospective`

### 现场表现

复盘阶段容易直接追加新规则，而没有先检查已有约束是否存在但表述不清、要求过弱、互相矛盾、没有接到脚本 preflight、没有同步到生成 skill 副本，或只是 LLM 未执行。

### 期望行为

复盘必须先做 Existing Constraint Audit：

- 检查 `ai/workflows/task-routing.md`、stage command templates、`workflow.yml`、scripts、tests、generated skill copies、selected knowledge guides。
- 归因为 missing constraint、weak wording、contradictory wording、script/preflight not wired、generated-context drift、unavailable tool、LLM execution miss。
- 优先修复已有约束的清晰度或接线问题，其次才新增规则。

### 本轮修复落点

- `speckit-retrospective` 模板新增 Existing Constraint Audit。
- `validate-generated-context` 开始检查 `.agents/skills` 和 `.claude/skills` 中 commit/implement/retrospective/tasks 的关键门禁短语。
- 回归测试覆盖 retrospective 模板和生成上下文漂移检查。

## DSCC-006 复盘经验的自动化与 LLM 分工边界不明确

- 记录时间：2026-06-09
- 运行组合：Deepseek + cc
- 来源阶段：`/speckit-retrospective` / `speckit-promote-lessons`

### 现场表现

复盘后的 spec-kit 修复可能倾向于把所有经验都规则化或自动化，存在用弱自动化替代 LLM 语义判断、牺牲质量的风险。

### 期望行为

- 近乎 100% 确定的结构性条件优先脚本化、模板化、preflight 化。
- 需要语义判断、取舍、质量评估、上下文解释的内容保留为 LLM-owned review item，并要求证据。
- 团队知识候选只记录稳定、长期有效、需要大量查阅才能得到的事实，并保持 pending，等待人工批准后再落盘。

### 本轮修复落点

- retrospective 模板新增 `AI workflow self-check`、`Team knowledge candidates`、`自动化 / LLM 分工判断`。
- improvement candidates 规则增加 “nearly deterministic” 自动化边界。
- 回归测试覆盖复盘模板中的自动化/LLM 分工要求。
