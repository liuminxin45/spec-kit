---
description: Optionally run one automated post-commit delivery self-check.
scripts:
  ps: scripts/powershell/post-commit-self-check.ps1 -Json -FeatureDir <feature-dir>
  closure_ps: scripts/powershell/inspect-workflow-closure.ps1 -Json -FeatureDir <feature-dir> -Stage post-commit-self-check
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`. Load only stage-required artifacts and selected knowledge/gate packs.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, evidence sufficiency, and strict/release judgment.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this opt-in stage cannot continue, report `blockers` and `next_required_human_action`.

## Purpose

This is an opt-in strict/release stage after `speckit.commit`. It verifies delivery evidence and commit-hook state. It does not require retrospective, workflow-observer, or rubric artifacts unless strict governance explicitly selected them.

## Execution Steps

1. Run `post-commit-self-check` for the active `FEATURE_DIR`.
2. Confirm required default artifacts exist: `implementation-summary.md`, `validation.md`, and `workflow-state.json`.
3. Run `inspect-workflow-closure`; if it reports a default-stage blocker, return to `facts.next_required_stage`.
4. Confirm `implementation_summary.status = completed`.
5. For bugfix work, confirm final fix type and root-fix closure are explicit.
6. Confirm applicable AI self-acceptance, API/E2E plan, selected gate-pack evidence, runtime evidence, and post-commit message validation when those gates were selected.
7. If a deterministic fix is required, apply it, amend the commit once, and do not run another self-check.

## Quality Rules

- One self-check pass only.
- Do not complete the branch from this stage.
- Do not emit final Rubric scores from this stage.

## Output

Report in Chinese:

- Self-check result.
- Any deterministic amend made.
- Remaining blockers.
- Optional next stage: `speckit.rubric-score` only when strict/rubric mode was requested.
