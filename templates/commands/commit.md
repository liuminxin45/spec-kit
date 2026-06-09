---
description: Prepare and create confirmed multi-repository commits with the CoreServicesLib commit-message rules.
scripts:
  sh: scripts/bash/check-prerequisites.sh --json --include-tasks
  ps: scripts/powershell/check-prerequisites.ps1 -Json -IncludeTasks
  validate_message_sh: scripts/bash/validate-commit-message.sh --json --message-file <message-file>
  validate_message_ps: scripts/powershell/validate-commit-message.ps1 -Json -MessageFile <message-file>
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

Commit accepted Spec Kit work after implementation, validation, user acceptance,
and retrospective/留痕 are complete. Lesson promotion remains conditional and
only applies to human-approved retrospective candidates. This stage changes git
history only after explicit user confirmation.

## Language Rules

- Human-facing summaries use Chinese-first style.
- Commit messages follow the `commit-message` skill.
- DesktopShell / project commits must use the unified team template with
  68 display columns for every non-empty line. Do not offer a simplified
  fallback format.
- Preserve technical identifiers in their original form.

## Execution Steps

1. Run the prerequisite script and parse `FEATURE_DIR` and `AVAILABLE_DOCS`.
2. Load:
   - `FEATURE_DIR/tasks.md` when present; optional for `standard-bugfix` that
     used plan-embedded slices.
   - `FEATURE_DIR/plan.md`
   - `FEATURE_DIR/progress.md`
   - `FEATURE_DIR/acceptance.md`
   - `FEATURE_DIR/acceptance-checklist.md`
   - `FEATURE_DIR/workflow-record.md` when present
   - `FEATURE_DIR/improvement-candidates.md` when present
   - `FEATURE_DIR/promotion-report.md` when present
   - `FEATURE_DIR/lessons.md` when present
3. Confirm acceptance, quick acceptance, and retrospective are passed.
   If any of them is missing, stop and return to the required stage.
   Require `workflow-record.md` and `improvement-candidates.md` before commit.
   If retrospective artifacts are missing, stop and return to
   `speckit.retrospective`.
   If approved promotion candidates already exist from a prior retrospective,
   require that promotion was handled before committing Spec Kit process
   changes.
4. Inspect every affected repository:
   - Current branch.
   - Dirty files.
   - Untracked files.
   - Whether files belong to code, tests, generated spec docs, local runtime
     artifacts, or unrelated user work.
5. Ask once whether spec 文档是否随代码提交 when the workflow input did not
   already choose `include` or `exclude`.
   - Apply the same choice consistently within the current feature.
   - If feature artifacts are ignored by `.gitignore`, report the exact ignored
     path(s) and ask for one decision: keep them local-only as the default, or
     force-add exact spec artifacts. Never force-add a whole ignored directory.
   - Never stage unrelated user work.
6. Build a per-repository commit scope.
   - Show the scope first: affected repositories, files to stage, files
     intentionally excluded, spec-doc include/exclude decision, ignored
     retrospective/acceptance artifacts, and the commit-message validation plan.
   - Show files to stage.
   - Show files intentionally left unstaged.
   - Show validation evidence that supports the commit.
7. Use the `commit-message` skill to generate the commit message.
   - For DesktopShell / project, use the unified template, 68 display columns,
     and no simplified fallback.
8. Validate the exact commit message text before committing:
   - PowerShell: `.specify/scripts/powershell/validate-commit-message.ps1 -Json -MessageFile <message-file>`
   - Bash: `.specify/scripts/bash/validate-commit-message.sh --json --message-file <message-file>`
   - Treat any missing section, empty section body, truncated message, or
     over-width line as a hard blocker. Do not continue with `git commit`
     until validation passes.
   - Treat Conventional Commit subjects, wrapped/multiline subjects, missing
     `<Module>: <concise English summary>` subject format, missing Chinese
     summary line, `【提交类型】` without `<类型> - <范围或问题域>`, missing
     `相关测试通过，自测通过` final self-test conclusion, or obvious split
     technical tokens as hard blockers.
9. Ask for explicit user confirmation before staging or committing.
   - The early confirmation does not count when it happened before the scope,
     exclusions, spec-doc decision, and commit-message validation plan were
     shown. Treat it as commit intent only; ask for final confirmation after
     showing the complete scope.
10. After confirmation:
   - Stage only the approved files.
   - Commit in each affected repository that has approved changes.
   - MUST write the complete approved commit message to a UTF-8 message file
     and use `git commit -F <message-file>` or
     `git commit --amend -F <message-file>`.
   - NEVER pass multi-line template sections through `git commit -m`,
     especially from PowerShell. On Windows, embedded newlines in `-m`
     arguments can be truncated to the first line, silently dropping required
     template bodies.
   - Re-read `git show --no-patch --format=%B HEAD` into a temporary message
     file and run the same `validate-commit-message -MessageFile` script after
     commit or amend. Do not pipe Chinese commit messages through another
     PowerShell process because host encoding can corrupt template headings.
     If validation fails, amend the commit message before reporting success.
   - Record commit hashes in the response and `progress.md` when useful.
11. 不 push, do not create remote tracking, do not merge branches, and do not
    delete branches in this stage.

## Quality Rules

- Do not commit generated build output, temp files, local logs, or cache files.
- Do not commit installed runtime plugin directories, built artifacts, or
  host-served plugin artifacts (`app-data/plugins/**`, `frontend/plugins/**`,
  `dist/`, `build/`, `export/`, `plugin-out/`) when the corresponding
  repository source is the real change owner.
- Do not include spec documents by default without the feature-level choice.
- If a repository contains unrelated dirty work, leave it unstaged and call it
  out in the confirmation summary.
- If the commit-message skill is unavailable, stop and report the blocker
  rather than inventing a simplified commit format for DesktopShell / project.
- If `validate-commit-message` is unavailable or failing, stop and report the
  blocker. Never treat commit-message validation as advisory.
- A commit hash is not a successful commit-stage result until the post-commit
  message file validates. If validation fails, amend the message immediately or
  report the commit stage as failed.

## Output

Report in Chinese:

- Affected repositories.
- Approved staged files.
- Files intentionally excluded.
- Commit message source: `commit-message` skill.
- Commit message validation: `validate-commit-message`.
- Commit hash per repository, or pending confirmation state.
- Confirmation that this stage did 不 push.
- Required next stage: `speckit.complete-branch` / `$speckit-complete-branch`.
