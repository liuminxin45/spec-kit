---
description: Block unsafe Spec Kit workflow starts before intake writes active feature state.
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or
design-history docs only when this command explicitly needs them.
Do not load source trees, old specs, broad knowledge, or implementation artifacts for this stage.
Scripts provide hard `facts`, `blockers`, `unknowns`, and `hints`; the LLM
only explains blockers and asks for a user decision.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`.
If this preflight blocks, do not continue to intake; report blockers and
`next_required_human_action`.

## Purpose

Run the deterministic new workflow preflight before `speckit.intake` creates a
new feature directory or overwrites `.specify/feature.json`.

This stage protects an existing user work area. It blocks when the workspace is
dirty, a repository is not on an allowed base branch, `.specify/feature.json`
points to unfinished or invalid state, or workflow run state is unresolved.

## Execution Steps

1. Run:

   ```powershell
   pwsh -NoProfile -File .specify/scripts/powershell/preflight-new-workflow.ps1 -RepoRoot . -Json
   ```

   If running from a source checkout before init, use
   `scripts/powershell/preflight-new-workflow.ps1`.

2. If the result is `ok`, continue to `speckit.intake`.

3. If the result is `blocked`, stop before writing any feature state. Report:
   - `facts.decision`
   - current branch and dirty files per repository
   - active feature path/status when present
   - unresolved workflow runs when present
   - `blockers`
   - suggested manual actions

4. Do not automatically run `git stash`, `git clean`, branch switches, resets,
   deletes, archive moves, or `.specify/feature.json` overwrites.

5. If the user explicitly authorizes AI handling, the authorization must name
   the exact action, such as cleaning generated files, stashing all changes,
   committing current work, switching to a base branch, resuming the old feature,
   or creating a separate worktree. Perform only that named action, then rerun
   this preflight.

## Output Contract

- If passed: say the workspace is safe to start a new Spec Kit workflow and
  continue to `speckit.intake`.
- If blocked: do not claim intake has started. Ask for the user's decision or
  continue the existing feature only when the user requested resume.
