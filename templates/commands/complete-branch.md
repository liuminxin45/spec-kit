---
description: Preflight and complete local Spec branches by cherry-picking to master while keeping the Spec branch.
scripts:
  sh: scripts/bash/complete-spec-branches.sh --json --preflight-only
  ps: scripts/powershell/complete-spec-branches.ps1 -Json -PreflightOnly
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

Complete the accepted local Spec branch only after commit and
retrospective/留痕 are complete. This is the final local delivery operation. The
default is: preflight, ask for confirmation, cherry-pick into `master`, 保留
spec branch, 不删除 the local Spec branch, and 不 push.

## Language Rules

- Human-facing summaries and confirmation prompts use Chinese-first style.
- Preserve technical identifiers in their original form: branch names,
  repository names, script names, commands, and commit hashes.

## Execution Steps

1. Run the configured preflight-only completion script from the Spec Kit
   repository root:
   - PowerShell: `.specify/scripts/powershell/complete-spec-branches.ps1 -Json -PreflightOnly`
   - Bash: `.specify/scripts/bash/complete-spec-branches.sh --json --preflight-only`
2. Parse and show the preflight result for every affected repository:
   - Repository path.
   - Current branch.
   - Base branch, default `master`.
   - Local spec branch.
   - Dirty state.
   - Dirty classification: tracked source changes, generated/temp/excluded
     untracked entries, and unclassified untracked files.
   - Whether the spec branch exists.
   - Whether cherry-pick is safe.
   - Whether any upstream/remote tracking exists.
   - Remote divergence for the base branch when an upstream exists: ahead,
     behind, or no upstream.
   - Retrospective gate status. `workflow-record.md` and
     `improvement-candidates.md` must both exist for the active feature; if
     either is missing, stop and run `speckit.retrospective` before completing
     the branch.
3. If preflight reports dirty files, classify before asking the user:
   - Tracked modifications, staged changes, deleted files, or untracked files
     in repositories that still have spec commits to cherry-pick are blockers
     unless the correct handling is clear from source evidence.
   - Untracked files in repositories that are already up to date, have no spec
     commits to cherry-pick, or are clearly temporary/generated/intermediate
     local output are not blockers. Automatically pass them, record the
     classification, and continue without asking for manual confirmation just
     to ignore those files.
   - Stop only when the dirty file may be source work that belongs to this
     feature, may be overwritten by branch switching/cherry-pick, or cannot be
     semantically classified from repository-map, path category, git status,
     and local evidence.
4. If any remaining preflight item fails, stop and report the blocker. Do not
   partially cherry-pick repositories.
5. Ask the user for explicit confirmation before branch-state mutation.
   The confirmation text must state:
   - Cherry-pick target is `master` unless the feature explicitly configured
     another base branch.
   - The local spec branch will be kept.
   - The command will not delete local branches.
   - The command will not push or create remote tracking.
   - The command will not create merge commits.
6. After explicit confirmation, complete the branch:
   - Run the completion script or native git commands in a way that
     cherry-picks the local spec branch commits into the base branch across all
     affected repositories.
   - Ignore untracked temporary/generated artifacts and semantically unrelated
     no-commit repository noise when deciding whether dirty state blocks
     completion. Examples include cache folders, build output, installed plugin
     artifacts, local spec-kit init output, logs, evidence/memory scratch
     output, workbench screenshots, and host descriptor mocks. Do not ignore
     tracked source changes or unclassified dirty files that may belong to the
     spec branch being completed.
   - Switch every affected repository that can be safely handled back to the
     base branch, including repositories that are already up to date or have no
     commits to cherry-pick.
   - Pass or emulate keep-branch behavior so the spec branch remains available.
   - If the packaged script only supports deletion by default, do not use the
     deleting path; perform a safe cherry-pick sequence that preserves the
     branch and record that choice.
7. Verify final repository state:
   - Current branch is the base branch in every affected repository, including
     repositories that did not produce a new cherry-pick commit.
   - Spec branch still exists.
   - No remote push occurred.
   - No remote tracking was created by this stage.
8. Update `progress.md` with completion result when present.

## Quality Rules

- Never cherry-pick when the preflight result is missing or failing.
- Never run before `speckit.retrospective` / 留痕 is complete for the feature.
- Treat missing `workflow-record.md` or `improvement-candidates.md` as a hard
  completion blocker, even if the user says "进入下一阶段".
- Never delete the local spec branch by default.
- Never push from this stage.
- Do not hide unrelated dirty source work; report it and stop only if it blocks
  a safe cherry-pick and cannot be classified as temporary/generated output.
- If a cherry-pick conflict occurs, automatically resolve generated-artifact
  conflicts by keeping the base artifact and continuing. For source conflicts,
  continue resolving when the correct result is clear from spec/plan/tasks,
  commits, or local source evidence; only ask for human intervention when the
  semantic choice is genuinely ambiguous.

## Output

Report in Chinese:

- Preflight result.
- User confirmation status.
- Cherry-pick result per repository.
- Any ignored temporary/generated dirty entries or automatically resolved
  artifact conflicts.
- Confirmation that the workflow cherry-picked to `master` or the configured
  base branch.
- Confirmation that it did 保留 spec branch, 不删除 it, and 不 push.
