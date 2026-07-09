---
description: Create the smallest execution artifact for a capability.
scripts:
  ps: scripts/powershell/setup-plan.ps1 -Json
  select_knowledge_ps: scripts/powershell/select-knowledge.ps1 -Json -Stage plan -FeatureDir <feature-dir>
  select_gates_ps: scripts/powershell/select-gates.ps1 -Json -Stage plan -FeatureDir <feature-dir>
---

## User Input
```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load only the artifacts needed for the selected delivery profile. Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, root-cause judgment, validation sufficiency, and tradeoff decisions.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this stage cannot continue, report `blockers` and `next_required_human_action`.

## Purpose

Create the smallest useful planning artifact:

- `micro-fix` and `standard-bugfix-lite`: write `workpack.md`; do not create `spec.md`, `plan.md`, or `tasks.md` by default.
- `standard-bugfix`: write `plan.md` with compact Implementation Slices; skip `tasks.md` unless slices are too broad.
- `full-sdd`: use `spec.md`, `plan.md`, and possibly `tasks.md`, `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`.
- `blocked-investigation`: plan facts to collect instead of implementation.

## Layered Artifact Contract

- Lean profiles produce `workpack.md` plus `workflow-state.json`.
- `plan.md` is a decision map, not a design manual.
- Supporting artifacts are created only when they reduce implementation risk or preserve a public contract.
- `workflow-state.json` is the structured source for attempts, validations, fact-layer, acceptance, optional governance, and commit state.

## Language Rules

- Planning artifacts are human-reviewed. Write summaries, risks, decisions,
  validation expectations, and N/A reasoning in Chinese-first style.
- `workpack.md` or `plan.md` must include a top `## 人类审核摘要` section for
  fast human review. This section is additive only: it must summarize goal,
  chosen profile, root cause correctness, test sufficiency, validation entry,
  highest risks, and next step, and 不得替代或删减 later AI/流程读取区 such as
  root-cause evidence, implementation slices, selected gates, validation plan,
  assumptions, blockers, and unknowns.
- Do not ask humans to restate root cause correctness or test sufficiency when
  the artifacts already provide enough evidence; surface only concrete
  blocking decisions.
- Preserve technical identifiers in their original form: file paths, module
  names, class names, function names, APIs, fields, enum/status values,
  commands, and test names.

## Execution Steps

1. Run the setup script and parse `FEATURE_SPEC`, `IMPL_PLAN`, `SPECS_DIR`, and branch facts.
2. Load `.specify/feature.json`, repository-map, and only the active feature artifact needed by the selected profile.
3. Run `select-gates` for stage `plan`; record selected gate ids, not full gate text.
4. Run `select-knowledge` only when repository-map and selected gates are not enough.
5. For changed behavior that needs API/E2E/interface/regression/fixture/smoke/UI/device planning, load `speckit-test-plan`; if choices are ambiguous or costly, stop for human review.
6. For UI/UX/copy/parity work, load `speckit-quality-vision` and create `quality-vision.md` only when a baseline or quality tier is needed.
7. Create `acceptance-rubric.md` only for complex acceptance, UI quality, public contracts, high-risk work, or when AI self-acceptance needs a durable judge contract.
8. For lean bugfixes, fill `workpack.md`:
   - human summary
   - root cause evidence
   - Root-Fix Decision Gate
   - one bounded change slice
   - allowed and forbidden scope
   - validation command or substitute evidence
   - acceptance summary
9. For `plan.md`, keep only decision-critical sections:
   - human summary
   - AI Context Contract
   - Root Cause Evidence and Root-Fix Decision Gate when applicable
   - affected modules and ownership boundaries
   - selected gate/knowledge ids
   - test-case plan when needed
   - Implementation Slices
   - validation plan and AI self-acceptance contract when needed
10. Produce optional supporting artifacts only when applicable:
    - `research.md` for unknowns/tradeoffs.
    - `data-model.md` for durable state or DTOs.
    - `contracts/` for public APIs, bridge payloads, CLI/script IO, or protocols.
    - `quickstart.md` for reviewer exercise paths.
11. Do not create `review.md`, `progress.md`, `analysis.md`, `checklists/implementation-readiness.md`, retrospective, observer, or rubric artifacts from this stage.

## Planning Rules

- Prefer existing architecture and helper APIs.
- Put avoided context under `Context To Avoid`; do not stuff plans with broad background.
- Use bounded search from repository-map and affected repositories with `rg`.
- If root cause is unknown, write a bounded fact-layer slice before source edits.
- For bugfixes, prefer a root fix. If selecting mitigation, containment, or compatibility fallback, record residual risk and follow-up root-fix route.
- Do not call cleanup/release/reset/retry/fallback/limit-only approaches root fixes unless they eliminate the failure mechanism.
- For UI/UX/parity, cite the reliable source for visible changes or record owner-approved `N/A`.
- Plan acceptance, optional governance, optional commit, and optional branch completion as separate opt-in stages; do not add their documents to default delivery.

## Output

Report in Chinese:

- Artifact path: `workpack.md` or `plan.md`.
- Selected profile and any upgrade reason.
- Selected gate packs and selected knowledge guides.
- Main risks and missing facts.
- Validation plan.
- Optional artifacts created.
- Required next stage:
  - `micro-fix` / `standard-bugfix-lite`: `speckit.implement` when `workpack.md` is complete.
  - `standard-bugfix`: `speckit.implement` when `plan.md` has complete slices; otherwise `speckit.tasks`.
  - `full-sdd`: `speckit.tasks`.
  - `blocked-investigation`: `speckit.fact-layer` or `speckit.bounded-investigation`.
  - `validation-only`: `speckit.validation`.
