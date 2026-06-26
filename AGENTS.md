# AGENTS.md

This is the Spec Kit source repository. Keep default context small and use the
source templates/scripts in this repository as the authority for workflow
changes.

## Default Context

For source changes in this repository, start with:

1. `workflows/speckit/workflow.yml`
2. `templates/ai/workflows/task-routing.md`
3. `templates/ai/rules/ai-coding-rules.md`
4. The specific script, template, or test file being changed

Do not rely on parent-workspace instructions; source repository behavior must
remain self-contained for open-source users.

## Operating Rules

- Keep default templates generic. Project-specific host, plugin, native bridge,
  or device rules belong in selected gate packs, optional knowledge guides, or
  user-maintained repository maps.
- For workflow or template changes, run:
  - `pwsh -NoProfile -File scripts/powershell/validate-generated-context.ps1 -RepoRoot . -Json`
  - `pwsh -NoProfile -File scripts/powershell/validate-knowledge-index.ps1 -RepoRoot . -Json`
  - `pwsh -NoProfile -File scripts/powershell/validate-context-budget.ps1 -RepoRoot . -Json`
- Do not add bundled project knowledge packs to this repository. Knowledge pack
  generation and installation are runtime/user actions, not source-tree defaults.
- Do not push directly as part of ordinary workflow repair. Prefer PR-first;
  exceptional push paths must pass `preflight-push` and explicit human approval.
