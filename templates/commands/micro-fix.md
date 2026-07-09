---
description: Execute a lightweight bugfix path when the change is small, internal, evidenced, and locally verifiable.
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load only repository-map, source files, and the compact `workpack.md`/current feature state needed for this fix.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, root-cause judgment, validation sufficiency, and tradeoff decisions.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this stage cannot continue, report `blockers` and `next_required_human_action`.

## Purpose

Use this command when `.specify/feature.json` selects `delivery_profile: micro-fix`.
It replaces the heavy `spec -> plan -> checklist -> tasks -> analyze` chain with one compact `workpack.md`.

Upgrade out of `micro-fix` when the fix touches public API, identity, runtime status, permission semantics, external-system behavior, UI/service/runtime boundaries, cross-repo behavior, or lacks local validation.

## Required Micro-Fix Contract

Create or update `FEATURE_DIR/workpack.md` with:

- `## 人类审核摘要`: goal, changed scope, validation entry, remaining risk.
- `## Root Cause`: symptom, call path, evidence, excluded alternatives, confidence.
- `## Root-Fix Decision Gate`: compare Root fix, Mitigation, Compatibility fallback, and Containment when applicable.
- `## Change Slice`: allowed files, forbidden files/behaviors, minimal implementation objective.
- `## Validation`: commands or substitute evidence, expected result, failure signal.
- `## Acceptance Summary`: user-visible check when needed.

Do not create `micro-fix.md`, `progress.md`, `spec.md`, `plan.md`, `tasks.md`, `analysis.md`, or implementation-readiness checklist by default.

## Execution Rules

- Use bounded search only: affected repo, known dirs, `rg`, and `rg --files`.
- Do not use an explorer/subagent for simple local lookup.
- Do not ask the user to confirm root cause correctness, test sufficiency, or code-level fix quality.
- Ask the user only for acceptance, owner-approved gaps, commit, or branch completion.
- Required tests and validation belong to implementation.
- Do not commit, merge, push, create remote tracking, or delete branches.

## Output

Report in Chinese:

- `workpack.md` path.
- Whether the profile remained `micro-fix` or was upgraded, with reason.
- Root-cause confidence.
- Changed/allowed scope.
- Validation to run.
- Required next stage: `speckit.implement`.
