# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

## L2 Artifact Contract

Required L2 sections: `人类审核摘要`, `概览`, `分流对齐`, `AI Context Contract`, `Root Cause Evidence`, `Root-Fix Decision Gate`, `技术上下文`, `影响模块与边界`,
`Quality Vision Link`, `测试用例计划`, `Acceptance Rubric Link`, `Implementation Slices`, `验证计划`, `AI Self-Acceptance Contract`.

Keep this plan as a decision map. Put detailed runtime facts in `fact-pack.md`,
raw command evidence in `evidence.md`, and durable facts in code or selected
knowledge/gate maps.

## 人类审核摘要

该摘要只用于人工导航，不得替代或删减后续 AI/流程读取区。

- 目标 / 实际范围 / 主要风险 / 验证入口 / 下一阶段:

## 必需人工决策

- N/A

## 概览

[Summarize the planned implementation in one short paragraph.]

## 分流对齐

- task_type:
- delivery_profile:
- risk_level:
- risk_flags:
- affected_repositories:
- selected gate packs:
- selected knowledge guides:

## AI Context Contract

### Required Facts

| Fact | Source or Command | Why Needed | Status |
|------|-------------------|------------|--------|
|  |  |  | known/missing |

### Context To Load / Avoid

| Context | Load or Avoid | Trigger / Reason |
|---------|---------------|------------------|
|  | load/avoid |  |

### Missing Context / Blockers

- N/A

## Root Cause Evidence

For bugfix work, fill the fields below. For non-bugfix work, write `N/A` with a
short reason.

- Symptom:
- Call Path:
- Evidence:
- Excluded Alternatives:
- Counterexample:
- Blast Radius:
- Validation Mapping:
- Confidence:

## Root-Fix Decision Gate

Use this gate for bugfix work. For non-bugfix work, write `N/A` with a reason.
Definitions: Root fix eliminates the mechanism/class under reasonable scale;
Mitigation reduces probability/impact while it remains; Containment temporarily
limits impact; Compatibility fallback preserves old behavior/interface/data for
migration, rollout, or rollback and does not replace a root fix.

| Candidate | Type | Eliminates failure mechanism? | Scale-growth failure path | Complexity / implementation risk | Compatibility / migration impact | Validation | Select / reject reason | Residual risk | Follow-up root-fix route |
|-----------|------|-------------------------------|---------------------------|----------------------------------|----------------------------------|------------|------------------------|---------------|--------------------------|
| A | Root fix | yes/no/partial |  |  |  |  |  |  |  |
| B | Mitigation | yes/no/partial |  |  |  |  |  |  |  |
| C | Compatibility fallback | yes/no/partial |  |  |  |  |  |  |  |
| D | Containment / N/A | yes/no/partial |  |  |  |  |  |  |  |

- Selected fix type: root fix / mitigation / containment / compatibility fallback
- Eliminated failure mechanism: yes / no / partial
- If not root fix, residual risk and follow-up root-fix route:
- High-risk prompt: for environment variables, global state, caches, locks,
  queues, resource handles, lifecycle, persisted state, singletons/registries,
  shared state, dynamic dependency resolution, retry, cleanup, reset, fallback,
  or limits, verify the mechanism itself is eliminated before claiming root fix.

## 技术上下文

- Existing pattern/API/helper to reuse:
- Source behavior or design source:
- Build/package/runtime facts:
- External constraints:

## 影响模块与边界

| Repository | Files / Areas | Responsibility | Write Scope | Forbidden Scope |
|------------|---------------|----------------|-------------|-----------------|
|  |  |  |  |  |

## UI 展示、Service 转发与 Runtime 事实边界

Fill only when UI/service/runtime boundaries are relevant; otherwise `N/A`.
- Runtime/domain facts, forwarding APIs, display composition, no-infer/cache
  constraints, refresh/event timing:

## Identity / State / API Boundary

Fill only when identity, state, bridge, RPC/N-API, JS/UI, or public API is
affected; otherwise `N/A`.
- Cross-boundary identity, runtime state owner, API/DTO/field owner,
  legacy/debug/test API handling:

## Gate Pack Plan

Use `select-gates` and cite selected gate ids. Do not paste full gate details
here.

| Gate | Why Selected | Required Evidence | Missing Facts |
|------|--------------|-------------------|---------------|
|  |  |  |  |

## Source Behavior Execution Map

Required for UI/service/SDK or target-environment state migrations; otherwise `N/A`.

| Source UI Behavior | Native/service/API Path | State/DTO/API Fact | Frontend Runtime Proof |
|--------------------|---------------------|--------------------|------------------------|
|  |  |  |  |

## UI / UX / 文案 Evidence Gate

Required only for visible UI/UX/copy/style changes; otherwise `N/A`. For parity
or layout repair, cite selected gates plus runtime DOM/computed-style/box facts.
UI parity or embedded UI work must cover dynamic states, target validation,
scrollbar, clipping, compression, and runtime DOM / computed style / box metrics.

| Visible Change | Evidence Source | Target Selector/Component | Status |
|----------------|-----------------|---------------------------|--------|
|  |  |  |  |
### UI Element Traversal Inventory / 0px Alignment Matrix
Required for UI parity or 0px-level visual repair; otherwise `N/A`; track baseline anchors and batch patch strategy.
| Element / State | Baseline Anchors | Runtime Selector | Box Metrics | Batch Patch Strategy |
|-----------------|------------------|------------------|-------------|----------------------|
## Quality Vision Link

Required for UI/UX/copy/parity work; otherwise `N/A`.

- `quality-vision.md`:
- Quality tier:
- UI baseline status:

## 宪章检查

- N/A

## 测试用例计划

> 由 `speckit-test-plan` 协商生成；每行追溯到场景、需求、契约或风险。
> 若存在歧义，先停下等待人工审核。

| ID | Type | Scenario/Requirement | Test Intent | Target Path/Command | Fixture/Data | Review Status |
|----|------|----------------------|-------------|---------------------|--------------|---------------|
| TP-001 | api-test / e2e/interface-test / unit / regression / fixture / smoke / manual/device / N/A |  |  |  |  | approved-by-ai-obvious / needs-human-review / owner-approved-gap |

## Acceptance Rubric Link

- `acceptance-rubric.md`:
- Essential gate count:
- Pitfall count:

## Implementation Slices

| Slice | Goal | Allowed Write Scope | Forbidden Scope | Validation | Stop Condition |
|-------|------|---------------------|-----------------|------------|----------------|
| 1 |  |  |  |  |  |

## Supporting Artifacts

Record only used optional artifacts: `research.md`, `data-model.md`,
`contracts/`, `quickstart.md`, `fact-pack.md`, `evidence.md`.

## 兼容性与迁移风险

- Compatibility risk:
- Migration risk:
- Rollback or containment:

## 验证计划

| Validation | Command / Tool | Evidence Location | AI-Owned? |
|------------|----------------|-------------------|-----------|
|  |  |  | yes/no |

## AI Self-Acceptance Contract

- Judge skill: `speckit-ai-self-acceptance`
- Rubric source: `acceptance-rubric.md`
- Required evidence:
- PASS condition:
- FAIL loop target: `speckit-implement` / `speckit-fact-layer`
- BLOCKED condition:
