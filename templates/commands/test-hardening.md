---
description: Optionally add focused regression protection after accepted delivery.
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
`workpack.md`/`plan.md`/`tasks.md` needed to judge regression risk. Optional
older artifacts such as `progress.md`, `acceptance.md`, and
`acceptance-checklist.md` are read only when present and directly relevant.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or
design-history docs only when this command explicitly needs them. Scripts
provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic
routing, regression-risk judgment, and validation sufficiency.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`;
if this opt-in stage cannot continue, report `blockers` and
`next_required_human_action`.

## Purpose

Perform optional extra test-hardening after required implementation validation
and user acceptance are complete. Required tests and substitute evidence belong
to `speckit.implement`; this stage is only for additional regression protection
that reduces real risk without inflating scope.

## Execution Steps

1. Run the prerequisite script and parse `FEATURE_DIR`.
2. Load `implementation-summary.md`, `validation.md`, and the active planning
   artifact.
3. Confirm required tests or substitute evidence are already closed by
   `speckit.implement`. If missing, return to `speckit.implement`.
4. Decide whether optional hardening is worthwhile.
   - Good candidates: cheap regression test for a high-risk boundary, missing
     fixture around a bugfix, contract test for public API behavior, or smoke
     script that replaces a fragile manual check.
   - Poor candidates: broad rewrites, unrelated coverage chasing, fragile UI
     snapshots, or tests requiring unavailable hardware without clear owner
     value.
5. If useful, add or adjust the focused test artifact and run the narrowest
   affected verification.
6. If not useful, record optional N/A in `implementation-summary.md`.
7. Update `validation.md` with new commands/results only when new validation
   ran.
8. Do not commit, merge, delete branches, push, or create remote tracking.

## Quality Rules

- This stage must not become a second implementation phase.
- Do not change product behavior to make optional tests easier.
- Keep optional hardening smaller than the feature implementation.
- If the user declines optional hardening, record N/A and stop.

## Output

Report in Chinese:

- Optional hardening decision.
- Test artifacts changed, or N/A reason.
- Verification commands and results.
- Updated `implementation-summary.md` path and `validation.md` path when
  changed.
- Required next stage: explicit opt-in governance/commit stage when requested.
