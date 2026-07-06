---
description: Generate self-contained acceptance rubrics from requirements, test plans, and quality vision.
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, root-cause judgment, validation sufficiency, and tradeoff decisions.
Keep this command stage-specific. Do not duplicate long-term governance prose here.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this stage cannot execute the next required stage, report `blockers` and `next_required_human_action`.

## Purpose

Create `acceptance-rubric.md` before implementation when code changes or
non-trivial validation are planned. The rubric turns requirements, negotiated
test cases, and quality vision into independent judgeable checks for AI
self-acceptance.

## Language Rules

- `acceptance-rubric.md` is normally human-reviewed. Write headings, criteria,
  evidence descriptions, pass conditions, blockers, and summaries in
  Chinese-first style.
- Preserve technical identifiers in their original form: file paths, commands,
  API names, DTO fields, selectors, status values, and test names.
- AI-only raw evidence or script JSON may stay English, but human-facing review
  documents such as `acceptance-rubric.md` and `acceptance.md` should be
  Chinese-first unless the user asks otherwise.

## Rubric Model

- `Essential` (weight 1.0): must pass.
- `Important` (weight 0.7): expected quality.
- `Optional` (weight 0.3): useful improvement, never masks failures.
- `Pitfall` (weight 0.9): must not trigger.
- Layers:
  - `L1 功能与需求闭合`: requirements, acceptance items, user confirmation, and scoped source changes.
  - `L2 验证与证据`: build/test/API/E2E/CDP/log/runtime/plugin package evidence.
  - `L3 工作流阶段合规`: stage order, mandatory artifacts, retrospective, self-check, and final Rubric timing.
  - `L4 交付与仓库状态`: commit/amend state, dirty classification, message validation, and complete-branch readiness.
  - `L5 上下文与自动化治理`: minimal context, selected knowledge/skills/gates, scripts first, and no temporary guessing.
- Actual workflow audit scoring:
  - L1/L2/L3/L4/L5 use weights `0.30 / 0.25 / 0.25 / 0.10 / 0.10`.
  - AI acceptance closure is a hard gate: `PASS` is required before human
    acceptance unless a true external blocker is recorded.
  - Retrospective completion, API/E2E plan, `.plugin` package evidence when
    applicable, CDP/runtime evidence when applicable, commit-message validation,
    and one post-commit self-check are hard gates before complete-branch.
  - Final Rubric scores are emitted only after post-commit self-check. Scores
    below 90 block complete-branch; any dimension below 80 requires a blocker
    or owner/user accepted-gap evidence.

## Execution Steps

1. Load `spec.md`, `plan.md`, `quality-vision.md` when present, and the
   negotiated `测试用例计划`.
2. Derive concise rubric rows. Each row must be self-contained: criterion,
   evidence required, pass condition, and source requirement/risk.
   Include rows that allow scoring the actual workflow, AI validation closure,
   plugin package evidence when applicable, and UI/UX quality after
   implementation.
   For bugfix work, include an Essential Root-Fix Decision Gate row and a
   Pitfall row for mitigation / containment / compatibility fallback being
   mislabeled as root fix.
3. Include negative `Pitfall` rows for high-risk errors such as false UI-only
   state, wrong API payload, stale runtime artifact, wrong CDP target, XSS,
   duplicate submit, or unhandled network/device failure when relevant.
   Also include the generic bugfix pitfall when a plan only cleans, releases,
   resets, retries, falls back, limits quantity/scope, or narrows impact
   without evidence that the failure mechanism itself is eliminated.
4. For UI rows, cite the baseline source from `quality-vision.md` or mark a
   blocker when no approved baseline exists.
5. Write `acceptance-rubric.md` using
   `.specify/templates/acceptance-rubric-template.md` when present.
6. Link the rubric from `plan.md` and make it the judge input for
   `speckit-ai-self-acceptance`.

## Rules

- Do not create vague criteria such as "works well" or "UI looks good".
- Do not let Optional rows compensate for failed Essential rows or triggered
  Pitfall rows.
- If test/rubric choices affect public contracts, devices, fixtures, cost, or
  accepted gaps, stop for human review before implementation.
- Keep detailed commands and evidence outside the rubric; cite evidence types
  and pass conditions only.
- Missing Root-Fix Decision Gate is an Essential failure for bugfix work. If the
  final approach is not root fix, require explicit mitigation / containment /
  compatibility fallback labeling, residual risk, and follow-up root-fix route.
- Do not accept "current project is enough" as a root-fix reason unless the
  rubric cites future compatibility cost, scale boundary, and the trigger for
  upgrading to root fix.

## Output

Report in Chinese:

- `acceptance-rubric.md` path.
- Essential/Pitfall counts.
- Human-review blockers.
- Required next stage or `next_required_human_action`.
