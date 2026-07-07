---
description: Prepare and create confirmed multi-repository commits with the commit-message rules.
scripts:
  ps: scripts/powershell/check-prerequisites.ps1 -Json -IncludeTasks
  preflight_ps: scripts/powershell/validate-feature-artifacts.ps1 -Json -Stage commit -FeatureDir <feature-dir>
  closure_ps: scripts/powershell/inspect-workflow-closure.ps1 -Json -FeatureDir <feature-dir> -Stage commit
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

Commit accepted Spec Kit work automatically after implementation, validation,
user acceptance, and retrospective/留痕 are complete. Lesson promotion remains
conditional and only applies to human-approved retrospective candidates.
Project knowledge promotion remains conditional and only applies to approved
`knowledge-candidates.md` entries. This stage changes local git history only
when all deterministic gates pass; it does not require a second manual
confirmation.

## Language Rules

- Human-facing summaries use Chinese-first style.
- Commit messages follow the `commit-message` skill.
- application commits must use the unified team template with
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
   - `FEATURE_DIR/implementation-summary.md`
   - `FEATURE_DIR/acceptance.md`
   - `FEATURE_DIR/acceptance-checklist.md`
   - `FEATURE_DIR/workflow-record.md` when present
   - `FEATURE_DIR/improvement-candidates.md` when present
   - `FEATURE_DIR/knowledge-candidates.md` when present
   - `FEATURE_DIR/workflow-observation.md` when present
   - `FEATURE_DIR/promotion-report.md` when present
   - `FEATURE_DIR/knowledge-promotion-report.md` when present
   - `FEATURE_DIR/lessons.md` when present
3. Confirm acceptance, quick acceptance, AI self-acceptance, test-plan review,
   plugin delivery evidence, and retrospective are passed.
   First run `validate-feature-artifacts` with `--stage commit` /
   `-Stage commit` for the active `FEATURE_DIR`. Treat missing
   `workflow-record.md`, missing `improvement-candidates.md`, missing
   `knowledge-candidates.md`, missing `workflow-observation.md`, or
   `workflow-state.json` `retrospective.status` not equal to `completed` as a
   hard blocker. Missing `implementation-summary.md` or incomplete
   `workflow-state.json` `implementation_summary` is a hard blocker; return to
   `speckit.implement` or `speckit.converge` before committing. For bugfix
   work, missing or contradictory Root-Fix Decision Gate closure is also a hard
   blocker: final fix type must be explicit, root fix must eliminate the
   failure mechanism, and non-root-fix outcomes must keep residual risk plus
   follow-up root-fix route. Return to `speckit.retrospective` or
   `speckit.workflow-observer` according to `inspect-workflow-closure`; do not
   inspect, stage, or commit repository files until this preflight passes.
   Require `workflow-record.md`, `improvement-candidates.md`,
   `knowledge-candidates.md`, `workflow-observation.md`, and
   `implementation-summary.md` before commit.
   If retrospective artifacts are missing, stop and return to
   `speckit.retrospective`.
   If workflow-observer artifacts are missing, stop and return to
   `speckit.workflow-observer`.
   If approved promotion candidates already exist from a prior retrospective,
   require that promotion was handled before committing Spec Kit process
   changes.
   If approved knowledge candidates already exist, require
   `speckit.promote-knowledge` or an explicit decision to defer them before
   committing knowledge-layer changes.
   Run `validate-test-plan` and require API plus E2E/interface rows, or an
   explicit E2E `N/A` reason with review status.
   Run `validate-ai-self-acceptance` and require `AI Self-Acceptance = PASS`.
   For any affected frontend/native/JS/plugin integration, require
   `inspect-plugin-build-plan` and `validate-plugin-package` evidence for a
   final `.plugin` artifact. Source build/export/runtime replacement is
   prerequisite evidence only.
4. Inspect every affected repository:
   - Current branch.
   - Dirty files.
   - Untracked files.
   - Whether files belong to code, tests, generated spec docs, local runtime
     artifacts, or unrelated user work.
5. Resolve `spec 文档是否随代码提交` without stopping for a new confirmation.
   - Use the explicit workflow input when it is `include` or `exclude`.
   - If the workflow input is `ask` and the feature already recorded a
     feature-level decision, apply it consistently.
   - If no feature-level decision exists, default to excluding generated spec
     docs from source commits and report exact ignored/local-only paths.
   - If feature artifacts are ignored by `.gitignore`, report the exact ignored
     path(s) and keep them local-only unless the feature-level policy explicitly
     includes exact spec artifacts.
   - Never force-add a whole ignored directory and never stage unrelated user
     work.
6. Build a per-repository commit scope.
   - Show the scope first: affected repositories, files to stage, files
     intentionally excluded, spec-doc include/exclude decision, ignored
     retrospective/acceptance artifacts, and the commit-message validation plan.
   - Show files to stage.
   - Show files intentionally left unstaged.
   - Show validation evidence that supports the commit.
7. Use the `commit-message` skill to generate the commit message.
   - For application, use the unified template, 68 display columns,
     and no simplified fallback.
8. Validate the exact commit message text before committing:
   - PowerShell: `.specify/scripts/powershell/validate-commit-message.ps1 -Json -MessageFile <message-file>`
   - Treat any missing section, empty section body, truncated message, or
     over-width line as a hard blocker. Do not continue with `git commit`
     until validation passes.
   - Treat Conventional Commit subjects, wrapped/multiline subjects, missing
     `<Module>: <concise English summary>` subject format, missing Chinese
     summary line, `【提交类型】` without `<类型> - <范围或问题域>`, missing
     `相关测试通过，自测通过` final self-test conclusion, obvious split
     technical tokens, or deterministic too-generic commit types such as
     `修复 - UI 交互` as hard blockers.
9. Stage and commit automatically when all preflight gates and commit-message
   validation pass.
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
10. After the commit hash and post-commit message validation are complete, run
    the unified workflow hook dispatcher for `workflow.speckit.commit.after`:
    `specify workflow invoke-hooks commit --workflow-id speckit --phase after --feature-dir <feature-dir> --json`.
    Continue only when the recorded hook result has `auto_continue=true`.
    `requires_rework` returns to implementation and must not be hidden by an
    amend or cleanup inside this stage.
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
  out in the scope summary.
- If the commit-message skill is unavailable, stop and report the blocker
  rather than inventing a simplified commit format for application.
- If `validate-commit-message` is unavailable or failing, stop and report the
  blocker. Never treat commit-message validation as advisory.
- A commit hash is not a successful commit-stage result until the post-commit
  message file validates. If validation fails, amend the message immediately or
  report the commit stage as failed.
- Do not output final Rubric scoring in this stage. Rubric scoring is only
  generated after the one post-commit self-check.

## Output

Report in Chinese:

- Affected repositories.
- Approved staged files.
- Files intentionally excluded.
- Commit message source: `commit-message` skill.
- Commit message validation: `validate-commit-message`.
- Commit hash per repository, or blocker state.
- Confirmation that this stage did 不 push.
- Required next stage: `speckit.post-commit-self-check` /
  `$speckit-post-commit-self-check`.
