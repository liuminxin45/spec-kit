---
description: Preflight and complete local Spec branches by cherry-picking to the recorded entry branch while keeping the Spec branch.
scripts:
  ps: scripts/powershell/complete-spec-branches.ps1 -Json -PreflightOnly
  closure_ps: scripts/powershell/inspect-workflow-closure.ps1 -Json -FeatureDir <feature-dir> -Stage complete-branch
---

## User Input
```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load only branch completion facts, commit facts, validation summary, and implementation summary. Governance/rubric artifacts are optional strict-mode inputs, not default blockers.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, branch risk judgment, and tradeoff decisions.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this opt-in stage cannot continue, report `blockers` and `next_required_human_action`.

## Purpose

Complete an accepted local Spec branch only when the user explicitly asks for branch completion and approves the exact preflight result. The default action is: preflight, ask for approval, cherry-pick local spec commits into the recorded entry branch, keep the spec branch, do not delete it, and do not push.

## Execution Steps

1. Run `inspect-workflow-closure`; block only on default delivery issues such as missing implementation summary, missing validation, failing root-fix closure, or unresolved commit hook rework. Do not require retrospective, workflow-observer, post-commit self-check, or rubric unless the user selected strict governance.
2. Run preflight:
   - PowerShell: `.specify/scripts/powershell/complete-spec-branches.ps1 -Json -PreflightOnly`
   - Preflight fetches only each recorded existing Gerrit entry branch and blocks missing targets, Spec-range merge commits, upstreams, and ahead/diverged local entry branches.
3. Show every participating repository from workspace configuration and recorded completion targets, including repositories with no changed files or new commits. Never narrow completion to `affected_repositories`:
   - repository path
   - current branch
   - local spec branch
   - target entry branch
   - dirty classification
   - cherry-pick safety
   - remote/upstream divergence
4. Stop on dirty tracked source changes or unclassified files that may be overwritten.
5. Ask for explicit human approval for this preflight result.
6. After approval, run:
   - PowerShell: `.specify/scripts/powershell/complete-spec-branches.ps1 -Json -ConfirmCompletion`
   - Use the workspace-wide completion script; do not replace it with cherry-picks for only changed repositories. Zero-commit repositories must also switch back, and retained Spec branches must not remain checked out.
   - A behind-only local entry branch is fast-forwarded to the fetched remote ref without merge before linear Spec commits are cherry-picked.
   - Inspect `worktree_plans`: sync operates in the worktree that owns the Spec branch; completion detaches retained Spec worktrees at their current commit and returns the original directory to its entry branch. Dirty tracked Spec worktrees and entry branches owned elsewhere block preflight. Do not bypass this with manual resets or unapproved stash.
7. Verify:
   - every participating repository is on its recorded entry branch, including zero-commit repositories (usually master/main; preserve a recorded product branch)
   - actual Git branch checks and switch exit codes passed; a failed switch means incomplete completion
   - local spec branch still exists
   - no remote push occurred
   - no remote tracking was created
   - no merge commit was created

## Quality Rules

- Never cherry-pick when preflight is missing or failing.
- Never cherry-pick without explicit approval for this preflight result.
- Never delete the local spec branch by default.
- Never push from this stage.
- Never run `git pull`, `git merge`, or `--rebase-merges`; an existing merge node requires a separately approved local history repair.
- Ignore only clearly generated/temp/local artifacts; do not hide source work.
- Resolve generated-artifact conflicts by keeping the base artifact when safe; source conflicts require semantic confidence or human input.

## Output

Report in Chinese:

- Preflight result.
- Cherry-pick result per repository.
- Ignored temporary/generated dirty entries.
- Confirmation that the workflow cherry-picked to the recorded entry branch, kept the spec branch, did not delete it, and did not push.
