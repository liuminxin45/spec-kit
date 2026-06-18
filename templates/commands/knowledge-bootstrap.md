---
description: Bootstrap or replace a workspace knowledge base from generated facts or portable knowledge packs.
scripts:
  ps: scripts/powershell/bootstrap-knowledge.ps1 -Json
  apply_pack_ps: scripts/powershell/apply-knowledge-pack.ps1 -Json
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`,
`.specify/memory/repository-map.md`, `.specify/feature.json` when present, and
`ai/workflows/task-routing.md`.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.

This command is for knowledge framework initialization, not feature delivery.
Do not load old `specs/*`, all source files, or every `ai/knowledge/*` file by
default.
Scripts output `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic
routing, evidence judgment, and promotion decisions.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`.
This command normally stops after creating draft knowledge unless the user
explicitly asks to apply it. If applying, validate the result before returning.
If generated knowledge needs human review before promotion, report
`next_required_human_action`.

## Purpose

Create or replace a workspace-local knowledge base without coupling Spec Kit
templates to any team, product, or repository set. Use generated drafts for new
projects and knowledge packs for known project/team knowledge.

Bootstrap has two first-class modes:

- Pack mount mode: install, compose, and validate an existing knowledge pack.
  This does not generate an AI review packet.
- Generated draft mode: inventory the workspace, create a low-confidence
  draft, and emit an AI review packet for bounded source reading.

Prefer pack mount mode when the user already has an external knowledge base,
team pack, project pack, or migrated private pack:

```text
scripts/powershell/bootstrap-knowledge.ps1 -RepoRoot . -PackPath <pack-dir> -Force -Json
```

Use `-ApplyProfiles` only when the pack should also install its
`.specify/workspace.yml` and `.specify/memory/repository-map.md` profile.

The command produces generated drafts under:

```text
.specify/knowledge-bootstrap/draft/ai/knowledge/
```

It also produces an AI review packet under:

```text
.specify/knowledge-bootstrap/ai-review/
```

That packet contains a bounded source-read plan and a claim ledger. Scripts
collect hard facts; the AI is responsible for semantic synthesis, targeted
source reading, unknown handling, and source references before any confidence or
authority promotion.

These drafts can be copied into `ai/knowledge/` only when the user explicitly
chooses to apply or review them.

## Execution Steps

For pack mount mode:

1. Run:
   - `scripts/powershell/bootstrap-knowledge.ps1 -RepoRoot . -PackPath <pack-dir> -Force -Json`
2. Read:
   - `facts.mode`
   - `facts.applied_pack`
   - `.specify/knowledge/lock.yml`
3. Report the installed pack id, active lock, alias/materialization result, and
   validation status.
4. Do not look for `.specify/knowledge-bootstrap/ai-review/`; this mode reuses
   an existing pack and intentionally skips review-packet generation.

For generated draft mode:

1. Run the prerequisite script:
   - PowerShell: `scripts/powershell/bootstrap-knowledge.ps1 -Json`
2. Read:
   - `.specify/knowledge-bootstrap/facts.json`
   - `.specify/knowledge-bootstrap/inventory.md`
   - `.specify/knowledge-bootstrap/bootstrap-prompt.md`
   - `.specify/knowledge-bootstrap/ai-review/review-brief.md`
   - `.specify/knowledge-bootstrap/ai-review/source-read-plan.md`
   - `.specify/knowledge-bootstrap/ai-review/claim-ledger.json`
   - the generated draft files under `.specify/knowledge-bootstrap/draft/ai/knowledge/`
3. Improve the draft with targeted source reads only when needed.
4. Keep all generated guides at `authority: generated` unless the user explicitly
   approves promotion.
5. If applying the draft, run:
   - `scripts/powershell/bootstrap-knowledge.ps1 -Apply -Json`
6. After applying, run:
   - `scripts/powershell/automation-common.ps1 -Tool validate-knowledge-index -Json`
   - `scripts/powershell/automation-common.ps1 -Tool validate-context-budget -Json`

To export a generated pack in one pass:

1. Run:
   - `scripts/powershell/bootstrap-knowledge.ps1 -RepoRoot . -ExportPack -PackId <id> -IncludeProfiles -Json`
2. Review:
   - `facts.pack.facts.pack_root`
   - `facts.pack.facts.validation`
   - `.specify/knowledge-bootstrap/evaluation/scenarios.json`
3. Treat the exported pack as generated authority until the AI review packet has
   been processed and the user approves any promotion.

For pack application:

1. Prefer `bootstrap-knowledge.ps1 -PackPath <pack-dir> -Force -Json`.
2. Validate the pack with `validate-knowledge-pack.ps1` only when you need a
   preflight before modifying the workspace.
3. Apply it with `apply-knowledge-pack.ps1` directly only when bypassing the
   bootstrap entry point is intentional.
3. Read `.specify/knowledge/lock.yml` and report installed packs plus aliases
   applied.
4. Run the same knowledge and context-budget validation commands.

## Output

Report:

- mode: `mount-pack` or generated draft mode
- installed pack id, lock file, aliases/materialization result, and validation
  status when mounting a pack
- draft knowledge directory when generating a draft
- AI review directory, source-read plan, and claim ledger only when a generated
  draft was produced
- whether anything was applied to `ai/knowledge/`
- repository count and any missing required repositories
- exported pack root, validation status, and evaluation scenario count when
  using `-ExportPack`
- installed pack id and lock file when applying a pack
- validation result after apply, or why validation was not run

## Guardrails

- Generated knowledge is routing help, not proof.
- Generated packs are portable starting points, not authoritative project
  knowledge.
- Ownership must come from `.specify/memory/repository-map.md` when available.
- Do not promote generated guides without human review or source evidence.
- Do not store machine-specific absolute paths.
- Keep the public Spec Kit template generic.
