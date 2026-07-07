---
description: Run the single automated post-commit Spec Kit self-check before final Rubric scoring.
scripts:
  ps: scripts/powershell/post-commit-self-check.ps1 -Json -FeatureDir <feature-dir>
  closure_ps: scripts/powershell/inspect-workflow-closure.ps1 -Json -FeatureDir <feature-dir> -Stage post-commit-self-check
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`,
`.specify/memory/repository-map.md`, `.specify/feature.json` when present, and
`ai/workflows/task-routing.md`. Load only stage-required artifacts and selected
knowledge/gate packs.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or
design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic
routing, root-cause judgment, validation sufficiency, and tradeoff decisions.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from
`ai/workflows/task-routing.md`; if this stage cannot execute the next required
stage, report `blockers` and `next_required_human_action`.

## Purpose

Run exactly one automated post-commit self-check after `speckit.commit` and
before final Rubric scoring. This stage verifies workflow closure and delivery
evidence; it does not output the final Rubric score.

## Execution Steps

1. Run `post-commit-self-check` for the active `FEATURE_DIR`. This script must
   execute any missing active `workflow.speckit.commit.after` hook through
   `specify workflow invoke-hooks` before reporting success.
2. Confirm required artifacts exist: `implementation-summary.md`,
   `validation.md`, `acceptance.md`, `workflow-record.md`, `improvement-candidates.md`,
   `knowledge-candidates.md`, `workflow-observation.md`, and
   `workflow-state.json`.
3. Run `inspect-workflow-closure`; if it reports a stage before this self-check,
   return to `facts.next_required_stage`.
4. Confirm `implementation_summary.status = completed` and
   `retrospective.status = completed`.
   For bugfix work, confirm the final fix type is explicit and the
   implementation summary does not label mitigation / containment /
   compatibility fallback as root fix.
5. Confirm `AI Self-Acceptance = PASS`, API/E2E test-plan status, applicable
   `.plugin` package evidence, CDP/host/runtime evidence or true blockers, and
   post-commit message validation are recorded in the feature evidence. If an
   active commit-after hook exists, confirm `workflow-state.json` contains
   `hook_results.workflow.speckit.commit.after.auto_continue = true`.
6. If a deterministic fix is required, apply it, amend the commit once, and do
   not run another self-check.

## Quality Rules

- One self-check pass only. Do not loop self-check after an amend.
- Do not complete the branch from this stage.
- Do not emit final Rubric scores from this stage; prepare evidence for
  `speckit.rubric-score`.

## Output

Report in Chinese:

- Self-check result.
- Any deterministic amend made.
- Remaining blockers, if any.
- Required next stage: `speckit.rubric-score` / `$speckit-rubric-score`.
