# 任务清单: [CAPABILITY NAME]

> `tasks.md` 仅用于 full-sdd、迁移或 plan slices 无法紧凑表达的工作。
> micro-fix 和 standard-bugfix-lite 不应生成本文件。

**输入**: `spec.md`, `plan.md`, and selected design artifacts from `specs/[feature-name]/`
**前置条件**: `plan.md` 足够明确，可以识别影响模块、写入范围和验证预期

## L3 Artifact Contract

- **Layer**: L3 Executable Task Slices
- **Purpose**: convert L1/L2 decisions into executable work units only when a separate task artifact is justified.
- **Required sections**: `人类审核摘要`, `格式`, `Implementation Slices`, validation/test closure, dependencies, and parallelization notes.
- **Slice requirements**: every slice must state target, linked tasks, allowed write scope, forbidden scope, validation, search scope, and stop conditions.
- **Structured state**: update `workflow-state.json`; do not rely on chat history as the only state store. `progress.md` is optional, not required.

## 人类审核摘要

本摘要只用于快速审核，不得替代或删减后续 AI/流程读取区。

- **执行目标**:
- **优先阅读**:
- **剩余/阻塞任务**:
- **验证入口**:
- **测试用例闭环**:
- **必需人工决策**:

## 格式: `[ID] [P?] [Scenario?] Description`

- `[P]`: can run in parallel without touching the same files or dependent contracts.
- `[Scenario]`: capability scenario tag such as `[CS1]`.
- Each task names a file, module, artifact, or validation target.
- Bugfix tasks must not hard-code an unproven patch before Root Cause Evidence is high.

## Implementation Slices

### Slice S1 - [Name]

- **目标**:
- **关联任务**:
- **允许写入范围**:
- **禁止范围**:
- **验证命令/证据**:
- **搜索范围**:
- **停止条件**:

## Phase 1: 上下文与边界

- [ ] T001 审核 `spec.md`、`plan.md`、selected gate packs，以及附近既有代码模式。
- [ ] T002 确认精确影响文件/模块，并确认不需要无关清理。
- [ ] T003 审核 public API、identity/state、runtime/service/UI、external-system 或 cross-repo 边界。

## Phase 2: 实现

- [ ] T010 [CS1] 更新 [module/path] 以提供 [behavior]。
- [ ] T011 [CS1] 更新 [test/fixture/path] 以固化验证行为，或记录 explicit N/A reason。
- [ ] T012 [CS1] 执行 [build/test/smoke/manual/device check] 并记录结果到 `validation.md`。

## Phase N: 横切事项与交付

- [ ] T900 更新 `validation.md`，记录命令、结果、证据路径和解释。
- [ ] T901 更新 `implementation-summary.md`，记录实际改动、最终修复类型、残余风险和证据链接。
- [ ] T902 如需要，生成用户验收步骤或 `acceptance.md`。
- [ ] T903 等待用户明确验收结论。
- [ ] T904 如用户显式要求，进入 opt-in commit / retrospective / rubric / complete-branch。

## 依赖说明

- Shared contracts block downstream implementation.
- Public contract changes precede downstream integration.
- A scenario should be independently verifiable unless explicitly marked otherwise.

## 并行说明

- Different files with no shared contract may be `[P]`.
- Shared headers, contracts, DTOs, permission/availability models, UI state sources, and generated state files are not parallel unless ownership is clearly split.
