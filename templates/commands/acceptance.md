---
description: Produce concise user acceptance steps after implementation validation.
scripts:
  ps: scripts/powershell/check-prerequisites.ps1 -Json -Stage acceptance -IncludeTasks
  preflight_ps: scripts/powershell/validate-feature-artifacts.ps1 -Json -Stage acceptance -FeatureDir <feature-dir>
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load only lean `workpack.md` `Outcome` or strict `implementation-summary.md` plus `validation.md`, and the active planning artifact needed to write user-facing checks.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, validation sufficiency, and user-facing acceptance judgment.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this stage cannot continue, report `blockers` and `next_required_human_action`.

## Purpose

Provide human acceptance steps after AI-owned implementation validation has passed.
This stage does not change product code and does not create `acceptance-checklist.md` by default.

## Execution Steps

1. Run prerequisite and `validate-feature-artifacts -Stage acceptance`.
2. Load:
   - For lean profiles: `FEATURE_DIR/workpack.md` `Outcome`.
   - For strict/non-lean profiles: `FEATURE_DIR/implementation-summary.md` and `FEATURE_DIR/validation.md`.
   - `FEATURE_DIR/workpack.md`, `plan.md`, or `tasks.md` when needed for user-facing scope.
   - `evidence.md`, `fact-pack.md`, or screenshots only when referenced by validation.
3. Confirm validation status:
   - If lean `workpack.md` `Outcome` is incomplete, return to `speckit.implement`.
   - If strict `validation.md` is missing, return to `speckit.implement`.
   - If AI changed code and validation does not record PASS or a true external blocker, return to `speckit.implement`.
   - If strict `implementation-summary.md` is missing or does not describe the actual change, return to `speckit.implement`.
4. Write `acceptance.md` only when durable user-facing acceptance evidence is useful. Otherwise report the acceptance steps directly in the response.
5. Include:
   - what changed
   - exact user test steps
   - expected results
   - failure signals
   - validation already collected by AI
   - known gaps requiring user/product judgment
6. Do not mark acceptance as passed yourself. Stop until the user explicitly confirms acceptance.

## Quality Rules

- Acceptance steps must be executable without reading every design artifact.
- Do not turn AI-owned technical validation into manual checklist work.
- Keep validation gaps visible.
- UI/UX acceptance should cite available screenshots, DOM/runtime evidence, or owner-approved automation gaps.
- Do not commit, merge, delete branches, push, or create remote tracking.

## Output

Report in Chinese:

- `acceptance.md` path, or `N/A` when steps were reported inline.
- Existing validation evidence.
- Known gaps or manual checks.
- Required user action: explicitly confirm whether acceptance passes.
