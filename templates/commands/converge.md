---
description: Optionally reconcile promised behavior with delivered evidence before human acceptance.
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
Load only active artifacts needed to compare promised behavior with delivered evidence.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, validation sufficiency, and gap judgment.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this opt-in stage cannot continue, report `blockers` and `next_required_human_action`.

## Purpose

`converge` is opt-in. Use it for full-sdd/high-risk work when a separate promised-vs-delivered reconciliation is worth the context cost. Lean bugfixes should close this in `workpack.md` `Outcome`.

## Required Inputs

- `FEATURE_DIR/implementation-summary.md`
- `FEATURE_DIR/validation.md`
- `FEATURE_DIR/workpack.md`, `plan.md`, or `tasks.md` when needed

## Execution Steps

1. Run `validate-feature-artifacts -Stage converge` when available.
2. Build a compact promised-vs-delivered table:
   - requirement or slice
   - source evidence
   - delivered code/test/runtime evidence
   - status: `closed`, `open`, `blocked`, or `accepted-gap`
3. For every `open` item, return to `speckit.implement` with the exact missing item and required validation.
4. For every `accepted-gap`, require explicit owner/user evidence.
5. Update `implementation-summary.md` with reconciliation status.
6. Write `convergence.md` only when the user selected strict/full-sdd governance or the reconciliation table is too large for `implementation-summary.md`.

## Output

Report in Chinese:

- Reconciliation status.
- Updated `implementation-summary.md` path.
- Optional `convergence.md` path, or `N/A`.
- Open gaps and next stage.
- Accepted gaps with evidence.
