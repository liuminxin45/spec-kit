---
description: Export, install, and apply portable Spec Kit knowledge packs.
scripts:
  export_ps: scripts/powershell/export-knowledge-pack.ps1 -Json
  install_ps: scripts/powershell/install-knowledge-pack.ps1 -Json
  apply_ps: scripts/powershell/apply-knowledge-pack.ps1 -Json
  validate_ps: scripts/powershell/validate-knowledge-pack.ps1 -Json
  compare_ps: scripts/powershell/compare-knowledge-pack-equivalence.ps1 -Json
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`,
`.specify/memory/repository-map.md`, `.specify/feature.json` when present, and
`ai/workflows/task-routing.md`.

This command manages workspace knowledge packs. Do not load old feature specs,
all source files, or every `ai/knowledge/*` guide by default. Read only pack
manifests, selected profiles, and validation output unless a blocker requires
targeted source evidence.

Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or
design-history docs only when this command explicitly needs them.
Scripts output `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic
routing, evidence judgment, and promotion decisions.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`.
This command normally stops after exporting, installing, applying, or validating
the requested pack. If generated or mounted knowledge needs human review before
promotion, report `next_required_human_action`.

## Purpose

Move project or team knowledge out of Spec Kit core templates and into portable
packs that can be installed and materialized into a workspace-local
`ai/knowledge` layer.

## Pack Workflow

1. Export an existing knowledge tree:
   - `scripts/powershell/export-knowledge-pack.ps1 -SourceKnowledgeDir <path> -PackId <id> -OutputDir <pack-dir> -Json`
   - add `-EvaluationScenariosFile <json>` when the pack should carry routing
     canaries for equivalence checks
   - for a new arbitrary project, prefer
     `scripts/powershell/bootstrap-knowledge.ps1 -RepoRoot <workspace> -ExportPack -PackId <id> -IncludeProfiles -Json`
     so the pack is paired with an AI review packet and generated routing
     scenarios
2. Validate a pack before sharing or installing:
   - `scripts/powershell/validate-knowledge-pack.ps1 -PackRoot <pack-dir> -Json`
3. Install and apply a pack to the current workspace:
   - `scripts/powershell/apply-knowledge-pack.ps1 -RepoRoot . -PackPath <pack-dir> -Force -Json`
   - add `-ApplyProfiles` when the pack should also replace
     `.specify/workspace.yml` and `.specify/memory/repository-map.md`
4. For already installed packs, re-compose:
   - `scripts/powershell/compose-knowledge-packs.ps1 -RepoRoot . -PackId <id> -Json`
5. Compare a pack with its source knowledge tree:
   - `scripts/powershell/compare-knowledge-pack-equivalence.ps1 -SourceKnowledgeDir <source-ai-knowledge> -PackRoot <pack-dir> -UseSpecKitInit -Json`
   - the comparison reads `<pack-dir>/evaluation/scenarios.json` by default;
     use `-ScenarioFile <json>` to override the routing canaries

## Semantics

- Pack source lives under `.specify/knowledge/packs/<pack-id>/`.
- The active knowledge layer is materialized to `ai/knowledge/`.
- The original active layer is snapshotted under `.specify/knowledge/base/` on
  first install and backed up under `.specify/knowledge/backups/` on compose.
- `.specify/knowledge/lock.yml` records installed pack ids, versions, and tool
  aliases applied during materialization.
- Pack `aliases/tools.yml` may map legacy team tool names to open-source core
  tool names without mutating the pack source.
- Pack `profiles/` can carry workspace and repository-map profiles. Apply them
  only when the target workspace is intended to take that pack's repository
  layout.
- Pack `evaluation/scenarios.json` can carry routing canaries for parity
  evaluation. Project-specific repository names belong there, not in the
  open-source evaluator script.

## Guardrails

- Open-source Spec Kit core must stay free of project or team facts.
- Do not promote pack knowledge to authoritative without source evidence or
  human review.
- Do not store machine-specific absolute paths in long-term pack knowledge.
- After applying a pack, run `validate-knowledge-index` and
  `validate-context-budget`.

## Output

Report:

- pack id and installed path
- active `ai/knowledge` path
- lock file path
- aliases applied
- profiles applied, when requested
- validation status and blockers, if any
- equivalence scores when comparing a pack to a source knowledge tree
- evaluation scenario source used for routing parity
