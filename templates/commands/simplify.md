---
description: Optionally simplify accepted code changes while preserving behavior and validation evidence.
scripts:
  ps: scripts/powershell/check-prerequisites.ps1 -Json
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`,
`.specify/memory/repository-map.md`, `.specify/feature.json` when present, and
`ai/workflows/task-routing.md`.
Load only `implementation-summary.md`, `validation.md`, and the active
`workpack.md`/`plan.md`/`tasks.md` needed to confirm accepted scope. Optional
older artifacts such as `progress.md`, `acceptance.md`, and
`acceptance-checklist.md` are read only when present and directly relevant.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or
design-history docs only when this command explicitly needs them. Scripts
provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic
routing, behavior-preservation judgment, and validation sufficiency.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`;
if this opt-in stage cannot continue, report `blockers` and
`next_required_human_action`.

## Purpose

After user acceptance, run a constrained cleanup pass only when it clearly
reduces maintenance cost. This stage is opt-in and behavior-preserving: it must
not add behavior, expand scope, alter public contracts, or replace required
validation from `speckit.implement`.

Use the `code-simplifier` subskill for simplification judgment and editing
guidance. Keep this command as orchestration: accepted scope, validation rerun,
and quick acceptance handoff.

## Execution Steps

1. Run the prerequisite script and parse `FEATURE_DIR`.
2. Load `implementation-summary.md`, `validation.md`, and the active planning
   artifact.
3. Verify explicit user acceptance. If acceptance is absent, stop and return to
   `speckit.acceptance`.
4. Inspect the already changed files and accepted validation evidence.
5. Apply a small simplification pass only inside accepted write scope.
6. Rerun the affected validation commands from `validation.md` or the active
   planning artifact.
7. Update `implementation-summary.md` with simplified files, N/A rationale when
   no useful cleanup exists, behavior-preservation rationale, validation
   result, and remaining risk.
8. Update `validation.md` only when validation evidence changed.
9. Do not commit, merge, delete branches, push, or create remote tracking.

## Quality Rules

- If simplification would change behavior, stop and report it as a follow-up.
- If validation fails after simplification, fix only your simplification or
  revert only your simplification changes. Do not revert unrelated user or
  teammate work.
- If no useful simplification exists, record N/A in `implementation-summary.md`
  and stop; do not create a separate simplification document.

## Output

Report in Chinese:

- Simplified files, or N/A reason.
- Behavior-preservation rationale.
- Validation rerun commands and result.
- Updated `implementation-summary.md` path and `validation.md` path when
  changed.
- Required next stage: quick `speckit.acceptance` only if user-visible behavior
  or validation evidence changed; otherwise explicit opt-in governance/commit
  stage.
