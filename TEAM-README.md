# CoreServicesLib 团队 Spec Kit

本目录以 GitHub Spec Kit v0.8.11 为基础，作为项目内维护的团队版
源码包。团队版面向真实 AI Coding 场景做了约束：默认上下文保持小、
修复必须优先改源码、需要时采集运行态证据，并通过本地 cherry-pick
完成分支交付，禁止产生 merge commit。

## 核心规则

- 默认上下文必须小。Agent 启动任务时只读取 `AGENTS.md`、
  `.specify/workspace.yml`、`.specify/memory/repository-map.md`、
  存在时的 `.specify/feature.json`，以及
  `ai/workflows/task-routing.md`。
- 默认不要读取 `TEAM-README.md`、设计历史文档、旧 `specs/*`、
  `ai/knowledge/*`、`ai/tools/*` 或 `ai/templates/*`。
- 需要团队知识时，先读 `ai/knowledge/index.yml` 或运行
  `select-knowledge`，再只读取返回的少数 guide。知识层不使用
  full-text/BM25 search，也不替代 `.specify/memory/repository-map.md`
  的仓库归属权威。
- 仓库角色以 `.specify/memory/repository-map.md` 为准，不要通过扫描
  整个工作区来推断归属。
- 产品和插件修复必须改仓库源码，不能只改已安装的运行时插件目录或
  构建产物。
- Spec Kit 阶段默认自动往下推进。只有人工验收、澄清/owner 决策、
  高风险操作确认、外部条件缺失、构建/验证失败、明确 blocker、
  source/runtime delivery-chain gap 或用户要求暂停时才停下；停下时必须写
  `blockers` 和 `next_required_human_action`。
- AI 修改 host-embedded frontend plugin 源码时，固定链路是
  source edit -> frontend build -> direct runtime replacement -> real host CDP
  verification。Native 插件源码改动则是 source edit -> `.plugin` build，
  因为 native 产物不能安全热更新。
  Gate phrase: source edit -> frontend build -> direct runtime replacement -> real host CDP verification.
- 脚本只输出 `facts`、`blockers`、`unknowns`、`hints`。语义路由、
  根因判断、验证是否充分、取舍决策仍由 LLM 负责。
  Scripts output `facts`, `blockers`, `unknowns`, and `hints`.
  LLM owns semantic routing, root-cause judgment, validation sufficiency, and
  tradeoffs.
- `acceptance.md` 是常规面向用户的收尾产物，`validation.md` 记录验证
  证据。`acceptance.md` is the user acceptance record. `fact-pack.md` 和
  `evidence.md` 只在运行态或工具证据较重时
  使用，不作为默认文书。
- 没有证据就不能声称验证完成。证据可以是命令输出、日志、截图、
  运行态事实，或明确记录的验证缺口。
  No validation claim is complete without concrete evidence.
- UI/CSS/layout 修复失败一次后，必须停止猜测；第二次补丁前要通过
  Chrome DevTools/CDP 采集 DOM、CSS、box metrics、dynamic states，或让
  用户提供复制的 DOM/CSS 证据。
  UI parity should be verified in the real host route/page when parent
  containers or sibling plugins affect layout.
  Use runtime DOM/CSS/computed style/box metrics as evidence.
- DesktopShell CDP 验证必须先列出 `/json/list` page targets，记录
  `id/title/url/webSocketDebuggerUrl` 和选中的 target id/URL。产品 UI
  验证不能使用 Plugin Workbench、`base-win.html`、`devtools://`、blank
  或无关 target；这些只能记为 `wrong-target / insufficient`。
- Qt-to-frontend UI parity 任务应先读
  `.specify/memory/qt-source-behavior-map.md` 或
  `ai/knowledge/qt-source-behavior-map.md`，再做有界源码调查，避免每次
  全仓库重新搜索 Qt 源行为。
- DeviceSdk 与 NativeBridge 日志从以下目录读取最新文件：
  `C:\Windows\Temp\ExampleSdkLog\SDK_*.log` 和
  `C:\Windows\Temp\NativeBridgeLog\NativeBridge_*.log`。读日志不需要 MCP。
- `complete-branch` 将本地 spec 分支提交 cherry-pick 到配置的 base 分支，
  默认保留本地 spec 分支，所有受影响仓库最终切回 base，不 push。
  It keeps the local spec branch and does not push.

## 安装与初始化

使用项目包装脚本：

```powershell
.\script\SpecKit\install.ps1
.\script\SpecKit\init.ps1
```

所有 `script\SpecKit\*.ps1` 包装脚本都支持 `-Help`。团队初始化目前以
Codex 为主，并将可执行 skills 安装到 `.agents/skills`。

默认 init 会配置与 `-Ai` 匹配的 MCP Agent；`-Ai codex` 配置 Codex，
`-Ai claude` 配置 Claude Code。写入配置前会校验全局 Node.js 版本。
需要跳过时使用 `-SkipMcpAgentConfig`。

显式配置其它 MCP Agent：

```powershell
.\script\SpecKit\init.ps1 -McpAgents ClaudeCode,Codex
```

已知 MCP 配置目标：

- Claude Code (`ClaudeCode`): 优先使用 `claude mcp add -s local` 写入
  当前项目 local config，确保 `/mcp` 可发现；无 Claude CLI 或测试环境下
  才回退到 `~/.claude.json`
- Codex: `~/.codex/config.toml`
- Gemini CLI (`GeminiCli`): `~/.gemini/settings.json`
- OpenCode: `~/.config/opencode/opencode.json`
- OpenClaw: 当前跳过；参考模型中未暴露稳定的实时 MCP 配置格式

默认 Chrome DevTools MCP 命令使用团队统一的 npm 方式：

```text
npm exec --yes --package=chrome-devtools-mcp@latest -c "chrome-devtools-mcp --browserUrl http://127.0.0.1:9222 --slim"
```

请求 MCP Agent 配置时，init 会先校验全局 Node.js 版本。
`chrome-devtools-mcp@latest` 要求 Node.js `^20.19.0 || ^22.12.0 || >=23`。
如需只安装/初始化 Spec Kit 而不配置 MCP，可传入 `-SkipMcpAgentConfig`。

需要 Agent 检查 DOM、console、运行态 CSS 或 box metrics 前，先在
DesktopShell 中执行 `npm run debug`。

## 当前架构

当前架构将旧的 L-1/L0/L0.5/L1-L5 模型压缩成四个实用分组。旧分层文档
只作为设计历史，不进入默认 AI 上下文。

| 分组 | 用途 | 长期资产 | 单次任务资产 |
| --- | --- | --- | --- |
| Foundation | 最小入口、仓库映射、路由、长期红线 | `AGENTS.md`、`.specify/workspace.yml`、`.specify/memory/repository-map.md`、`.specify/memory/pitfalls.md`、`ai/workflows/task-routing.md`、`ai/rules/ai-coding-rules.md` | `.specify/feature.json` |
| Work Item | 当前任务意图、计划、切片、进度 | `tools/spec-kit/templates` 下的源模板 | `spec.md`、`plan.md`、可选 `tasks.md`、`progress.md`、`workflow-state.json` |
| Knowledge | Claude/Codex 初始化资产沉淀后的按需团队知识 | `ai/knowledge/index.yml`、`ai/knowledge/workspace/*`、`ai/knowledge/repositories/*`、`ai/knowledge/domains/*`、`ai/knowledge/build/*` | 默认无；由 `select-knowledge` 返回少数 guide |
| Capabilities | 可执行 skills 与可选工具/MCP 策略 | `.agents/skills/*`、`ai/tools/*`、`templates/subskills/*` | 默认无 |
| Evidence | 验证、验收、运行态事实、交付证据 | 验证/证据模板与脚本 | `validation.md`、`acceptance.md`、可选 `fact-pack.md`、`evidence.md`、可选复盘产物 |

初始化后的项目布局：

```text
AGENTS.md
.agents/skills/*
.specify/
  workspace.yml
  feature.json
  memory/
    repository-map.md
    pitfalls.md
  templates/
    spec-template.md
    plan-template.md
    tasks-template.md
    workflow-state-template.json
    layer-manifest.yml
    fact-pack-template.md
  scripts/
ai/
  rules/
    ai-coding-rules.md
    architecture-constraints.md
    engineering-principles.md
  workflows/
    task-routing.md
  knowledge/        # 仅在需要引用长期事实时读取
    index.yml       # deterministic guide index; no full-text/BM25 search
    workspace/
    repositories/
    domains/
    build/
  tools/            # 仅在需要工具/MCP 操作时读取
  templates/        # 仅在创建验证/证据产物时读取
specs/<feature>/
  spec.md
  plan.md
  tasks.md          # 仅 full-sdd，或 plan 切片不足时使用
  progress.md
  workflow-state.json
  validation.md
  acceptance.md
  fact-pack.md      # 可选
  evidence.md       # 可选
```

## 工作流路径

不要只靠用户文本关键词路由。路由应结合硬事实、结构化状态、受影响仓库
和 LLM 判断。

风险级别为 `low / medium / high / blocked`，用于决定任务是否要从轻量
路径升级到标准路径、重型路径或阻塞调查。

### 轻量路径

适用于小型内部修复、简单 UI 调整、已有证据且可本地验证的 bugfix。

```text
intake -> plan/micro note -> implement -> validation.md -> acceptance.md
-> retrospective/留痕 -> commit -> complete-branch
```

特点：

- 不强制生成 `tasks.md`。
- retrospective/留痕 是 commit 前的必经记录；轻量修复可以只写
  简短记录，不扩展成大文档。
- 不加载大范围长期知识。

### 标准路径

适用于中等改动、多文件改动、状态/权限/设备行为或验证敏感的修复。

```text
intake -> specify -> plan with Implementation Slices -> implement
-> validation.md -> acceptance.md -> retrospective/留痕
-> optional promote-lessons -> commit -> complete-branch
```

特点：

- `plan.md` 可以承载执行切片，`tasks.md` 可选。
- 只有重复失败或运行态证据不足时才需要 `fact-pack.md`。
- `simplify` 和 `test-hardening` 只在确实降低风险时运行。

### 重型路径

适用于架构升级、跨仓改动、public API 变化、迁移、平台/工作流能力、
或大范围 UI/Biz/SDK 边界改造。

```text
intake -> specify -> plan -> tasks -> analyze/checklist when useful
-> implement -> validation.md/evidence.md -> acceptance.md
-> retrospective/留痕 -> optional promote-lessons -> commit -> complete-branch
```

特点：

- 通常需要 `tasks.md`。
- 可以接受更多证据产物，但必须服务于真实风险降低。
- retrospective/留痕 是 commit 前默认收尾；promote-lessons 只有人工批准
  候选时才运行。

### 阻塞调查

适用于缺少根因、源码行为、运行态事实、设计输入或验证条件的场景。

```text
bounded-investigation -> fact-layer/logs/DevTools as needed -> resume routing
```

## UI 对齐与运行态布局

UI parity 不能只在隔离插件预览中判断完成，必须在真实宿主容器中验证。
静态设计稿有参考价值，但动态状态、滚动条出现/消失、裁剪、压缩、hover、
disabled、兄弟节点和头尾区域稳定性，都需要在第一次 CSS/layout 补丁失败后，
通过运行态 DOM/CSS/computed style/box metrics 验证。
Static design files are reference inputs; runtime evidence owns final layout
judgment.

## 上下文加载策略

Context Loading Policy.

Agent 应逐步装配上下文：

1. 始终只加载：
   - `AGENTS.md`
   - `.specify/workspace.yml`
   - `.specify/memory/repository-map.md`
   - 存在时的 `.specify/feature.json`
   - `ai/workflows/task-routing.md`
2. 确认工作流路径后，再加载当前 feature 文件：
   - 轻量：micro/progress note、相关代码、验证目标。
   - 标准：`spec.md`、`plan.md`、`progress.md`，可选 `tasks.md`。
   - 重型：`spec.md`、`plan.md`、`tasks.md`、选定证据。
3. 只有工具动作前才加载 `ai/tools/*`。
4. 只有引用或更新长期事实时才加载 `ai/knowledge/*`。
5. 旧 specs、roadmap/设计历史文档、模板，只在维护 Spec Kit 时读取。

该策略用于避免旧决策、过期知识和元设计历史不断膨胀 prompt。

## 长期资产策略

| 资产 | 是否长期保留 | 规则 |
| --- | --- | --- |
| Constitution / rules | 是，小而精 | 只放红线，不静默修改 |
| Repository map | 是 | 仓库归属事实源 |
| Pitfalls / memory | 是，需筛选 | 只在有证据和人工批准时新增 |
| Skills | 是，只保留可执行项 | 源在 `templates/subskills`，安装副本在 `.agents/skills` |
| MCP policy | 是，保持最小 | 只写工具可用性和确认策略 |
| Prompt templates | 有限保留 | 只保留脚本/命令实际使用的模板 |
| Eval/checklist | 条件保留 | 能拦截重复失败才保留 |
| Workflow state | 单 feature 生命周期 | 短生命周期结构化状态，不当知识库 |
| Retrospective | 每个交付收尾 | branch completion 前记录关键输入、AI 输出、验证、错误/返工；轻量任务保持简短 |
| ADR/设计历史 | 不进默认上下文 | 可作参考，但不作为默认 AI 上下文 |

## 已删除或降级的设计

- 默认 16 步工作流：替换为 8 步主链路加条件阶段，避免小修复承担重流程成本。
- commit 前强制 retrospective：standard/full workflow 在 commit 前强制
  retrospective/留痕；promote-lessons 仍只处理人工批准候选。
- `validation-report.md`：从默认验证模型中移除。validation-only 也使用 `validation.md`。
- `ai/skills/*` 复制型治理 skill 文档：已移除。可执行 skills 放在 `.agents/skills`，源 skills 放在 `templates/subskills`。
- 通用 `knowledge-entry-template.md` 和 `skill-template.md`：已移除，避免鼓励维护低信号抽象。
- 命令模板里的旧 L-1/L0/L0.5/L1-L5 表述：替换为短上下文契约。详细分层只作为设计历史，不作为任务上下文。

## 仍存在的风险

- 为兼容既有能力，command 数量仍偏多。workflow 默认只路由少数命令，低频命令保持 opt-in。
- 长期 memory 如果缺少严格证据仍会腐化，因此继续要求人工批准和来源证据。
- MCP 可用性取决于 AI 客户端。DevTools MCP 不可用时，workflow 支持退回用户提供的 DOM/CSS。
- 旧 feature specs 可能含有过期流程假设。除非直接相关，否则不要加载。

## 与上游的团队差异

- 初始化默认使用 Codex；需要 Claude Code 时使用 `specify init --ai claude` 或 `script/SpecKit/init.ps1 -Ai claude`。Claude 初始化会保留 `AGENTS.md` 作为 canonical context，并生成只导入 `AGENTS.md` 的薄 `CLAUDE.md` shim；主要工作流仍安装在 `.claude/skills/speckit-*`。
- Spec Kit init supports `--ai codex|claude` in this team distribution, with Codex as the default.
- 不分发 bundled git extension 和 `taskstoissues`。
- 本地 spec 分支通过 cherry-pick 完成，不使用 merge。
- MCP Agent 配置可选，并采用 npm 方式。
- `OpenClaw` is reported as not exposing live MCP config.
- source/runtime artifact 一致性是一级门禁。
