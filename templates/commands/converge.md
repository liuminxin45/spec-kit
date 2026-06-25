---
description: Close implementation gaps before human acceptance.
scripts:
  preflight_ps: scripts/powershell/validate-feature-artifacts.ps1 -Json -Stage converge -FeatureDir <feature-dir>
  select_gates_ps: scripts/powershell/select-gates.ps1 -Json -Stage converge -FeatureDir <feature-dir>
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, root-cause judgment, validation sufficiency, and tradeoff decisions.
Load only active feature artifacts needed to compare promised behavior with delivered evidence.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`. If this stage finds fixable gaps, return to `speckit.implement` in the same turn; do not move to human acceptance.

## Purpose

Converge is the post-implementation reconciliation stage. It verifies that implementation, tests, runtime evidence, and progress notes still match the accepted spec/plan/tasks before asking the human to accept the work.

## Required Inputs

- `FEATURE_DIR/spec.md` when present
- `FEATURE_DIR/plan.md` when present
- `FEATURE_DIR/tasks.md` when present
- `FEATURE_DIR/progress.md`
- `FEATURE_DIR/validation.md`
- `FEATURE_DIR/acceptance-rubric.md` when code was changed

## Execution Steps

1. Run `validate-feature-artifacts` with stage `converge` when available; otherwise inspect the listed artifacts directly.
2. Build a compact promised-vs-delivered table:
   - requirement or slice
   - source evidence
   - delivered code/test/runtime evidence
   - status: `closed`, `open`, `blocked`, or `accepted-gap`
3. For every `open` item, decide whether it is fixable by this agent.
   - If fixable, return to `speckit.implement` with the exact missing item and required validation.
   - If not fixable, write the external blocker and required human action.
4. For every `accepted-gap`, require explicit owner/user evidence in progress or acceptance artifacts.
5. Write or update `FEATURE_DIR/convergence.md`.

## Output Contract

`convergence.md` must include:

- `status: passed | blocked | returned-to-implement`
- promised-vs-delivered table
- open gaps and their next stage
- accepted gaps with evidence reference
- validation commands or runtime evidence used
- `next_required_human_action` only for true external blockers or acceptance

Only `status: passed` allows `speckit.acceptance`.
