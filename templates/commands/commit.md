---
description: Prepare and create confirmed local commits with the commit-message rules.
scripts:
  ps: scripts/powershell/check-prerequisites.ps1 -Json -Stage commit -IncludeTasks
  preflight_ps: scripts/powershell/validate-feature-artifacts.ps1 -Json -Stage commit -FeatureDir <feature-dir>
  validate_message_ps: scripts/powershell/validate-commit-message.ps1 -Json -MessageFile <message-file>
---

## User Input
```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load `implementation-summary.md`, `validation.md`, and the active planning artifact needed to classify commit scope. Do not load retrospective, workflow-observer, promotion, rubric, or old specs unless the user explicitly selected those opt-in stages.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, commit scope judgment, and tradeoff decisions.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this opt-in stage cannot continue, report `blockers` and `next_required_human_action`.

## Purpose

Create local commits after implementation validation and user acceptance. This stage is opt-in and changes local git history only when deterministic gates pass. It does not require retrospective, workflow-observer, knowledge candidates, post-commit self-check, rubric, push, or branch completion.

## Execution Steps

1. Run prerequisite script and parse `FEATURE_DIR`.
2. Load:
   - `FEATURE_DIR/implementation-summary.md`
   - `FEATURE_DIR/validation.md`
   - `FEATURE_DIR/workflow-state.json` when present
   - `FEATURE_DIR/workpack.md`, `plan.md`, or `tasks.md` when needed for scope
   - `FEATURE_DIR/acceptance.md` when present
3. Run `validate-feature-artifacts -Stage commit`.
   - Missing `implementation-summary.md` or incomplete implementation summary state is a hard blocker.
   - Missing `validation.md` is a hard blocker.
   - For bugfix work, missing or contradictory Root-Fix Decision Gate closure is a hard blocker.
   - Retrospective/observer/promotion artifacts are optional and must not block commit unless the user selected strict governance.
4. Inspect every affected repository:
   - current branch
   - dirty files
   - untracked files
   - source/test/spec/runtime/generated classification
5. Resolve `spec docs include/exclude`.
   - Use explicit input when `include` or `exclude`.
   - Default to excluding generated spec docs when no feature-level policy exists.
   - Never force-add ignored directories and never stage unrelated user work.
6. Build a per-repository commit scope and show:
   - files to stage
   - files intentionally left unstaged
   - validation evidence supporting the commit
7. Use the `commit-message` skill.
8. Validate the exact commit message with `validate-commit-message`.
9. Stage and commit automatically only when preflight and message validation pass.
   - Use `git commit -F <message-file>`.
   - Re-read the committed message and validate it again.
   - Amend the message immediately if validation fails.
10. Invoke `workflow.speckit.commit.after` hooks when configured; continue only when the hook result has `auto_continue=true`.
11. Do not push, create remote tracking, merge branches, delete branches, or complete branches in this stage.

## Quality Rules

- Do not commit generated build output, temp files, local logs, caches, installed runtime directories, served runtime artifacts, or generated deployment outputs.
- If unrelated dirty work exists, leave it unstaged and call it out.
- If the commit-message skill or validator is unavailable, stop.
- A commit hash is successful only after the post-commit message validates.
- Do not output final Rubric scoring from this stage.

## Output

Report in Chinese:

- Affected repositories.
- Approved staged files.
- Files intentionally excluded.
- Commit message source and validation result.
- Commit hash per repository, or blocker state.
- Confirmation that this stage did not push.
- Optional next stages only when explicitly requested: post-commit self-check, rubric-score, complete-branch, retrospective, or workflow-observer.
