# Spec Kit

Spec Kit is a Codex-first workflow scaffold for AI-assisted software delivery.
It keeps the default context small, installs reusable workflow scripts and
skills, and lets each workspace own its project knowledge outside the open
source core.

## Quick Start

Initialize a workspace:

```powershell
specify init --here
```

Start the workflow from the installed Codex entry skill:

```text
$speckit-specify
```

The generated project contains:

```text
AGENTS.md
.agents/
.specify/
ai/
specs/
```

## Start With A Knowledge Pack

If you already have a project, team, or repository knowledge pack, mount it
during initialization:

```powershell
specify init --here --knowledge-pack <pack-dir>
```

This installs the pack, materializes it into `ai/knowledge/`, writes
`.specify/knowledge/lock.yml`, and validates the active knowledge index. It does not generate an AI review packet because the knowledge already came from an external pack.

To also adopt the pack's workspace profile and repository map:

```powershell
specify init --here --knowledge-pack <pack-dir> --knowledge-pack-apply-profiles
```

Use profile application only when the pack is meant to define the target
workspace layout. Without that flag, Spec Kit keeps the initialized
`.specify/workspace.yml` and `.specify/memory/repository-map.md`.

## Start Without A Pack

If no pack exists yet, initialize first:

```powershell
specify init --here
```

Then generate a low-confidence draft knowledge base:

```powershell
pwsh -NoProfile -File .specify/scripts/powershell/bootstrap-knowledge.ps1 -RepoRoot . -Json
```

Generated draft mode creates:

```text
.specify/knowledge-bootstrap/draft/ai/knowledge/
.specify/knowledge-bootstrap/ai-review/
```

The AI review packet contains a bounded source-read plan and claim ledger. Use
it to improve the draft with targeted source reads before promoting confidence
or exporting a reusable pack.

## Generate A Knowledge Pack With AI

For a new or arbitrary project, prefer the AI-assisted generator over a raw
draft export:

```powershell
pwsh -NoProfile -File .specify/scripts/powershell/generate-knowledge-pack.ps1 -RepoRoot . -PackId <id> -IncludeProfiles -Json
```

This creates an AI synthesis workspace at:

```text
.specify/knowledge-pack-generation/ai-synthesis/ai/knowledge/
```

It also writes a generation contract, source-read queue, candidate pack, and
pack validation result under `.specify/knowledge-pack-generation/`. The script
handles deterministic facts, quality reports, equivalence checks, and pack
mechanics; the AI handles targeted source reads, layered synthesis, source
references, unknowns, and noise removal.

The quality loop writes:

```text
.specify/knowledge-pack-generation/quality/source-coverage-ledger.json
.specify/knowledge-pack-generation/quality/claim-verification-report.json
.specify/knowledge-pack-generation/quality/synthesis-quality-summary.md
.specify/knowledge-pack-generation/equivalence/equivalence-summary.md
```

After AI synthesis, re-export from the reviewed workspace:

```powershell
pwsh -NoProfile -File .specify/scripts/powershell/generate-knowledge-pack.ps1 -RepoRoot . -PackId <id> -ReviewedKnowledgeDir .specify/knowledge-pack-generation/ai-synthesis/ai/knowledge -IncludeProfiles -Json
```

When `-ReviewedKnowledgeDir` is supplied, the generator enforces the quality
score and pack equivalence gates before treating the pack as ready to mount.

## Capability Pack Boundary

The open source core ships framework assets: templates, validators, selectors,
workflow scripts, and generic starter knowledge. Project-specific facts belong
in workspace-local `ai/knowledge/` or portable capability packs.

A capability pack may include:

```text
ai/knowledge/          layered project knowledge
skills/                namespaced Codex skills loaded by progressive disclosure
tools/                 tool policies and MCP/tool usage guidance
scripts/               explicit scripts that return facts/blockers/unknowns/hints
commands/              pack-specific command prompts
prompts/               reusable prompt templates
resources/             large docs, examples, diagrams, and generated maps
profiles/              workspace.yml and repository-map.md
evaluation/            routing canaries and semantic eval inputs
capabilities/index.yml progressive-disclosure registry
```

Pack scripts are never auto-run during install or compose. Applying a pack
publishes behavioral layers under namespaced workspace-local paths such as
`.agents/spec-kit/skills/<pack-id>__<skill>`, `ai/tools/<pack-id>/`, and
`.specify/scripts/packs/<pack-id>/`.

Pack lifecycle operations preserve the current active pack set. Updating a
mounted pack replaces the installed pack, clears stale published layers for the
same pack id, then re-composes the active set. Uninstalling a mounted pack
removes its installed source and namespaced published layers, then re-composes
remaining active packs or restores the base knowledge snapshot.

Useful pack commands:

```powershell
pwsh -NoProfile -File .specify/scripts/powershell/generate-knowledge-pack.ps1 -RepoRoot . -PackId <id> -IncludeProfiles -Json
pwsh -NoProfile -File .specify/scripts/powershell/evaluate-knowledge-pack-synthesis.ps1 -RepoRoot . -KnowledgeDir .specify/knowledge-pack-generation/ai-synthesis/ai/knowledge -MinimumScore 70 -FailBelowMinimum -Json
pwsh -NoProfile -File .specify/scripts/powershell/bootstrap-knowledge.ps1 -RepoRoot . -PackPath <pack-dir> -Force -Json
pwsh -NoProfile -File .specify/scripts/powershell/update-knowledge-pack.ps1 -RepoRoot . -PackPath <pack-dir> -Json
pwsh -NoProfile -File .specify/scripts/powershell/uninstall-knowledge-pack.ps1 -RepoRoot . -PackId <id> -Json
pwsh -NoProfile -File .specify/scripts/powershell/select-capability.ps1 -RepoRoot . -Layer skills -Json
pwsh -NoProfile -File .specify/scripts/powershell/export-knowledge-pack.ps1 -SourceKnowledgeDir ai/knowledge -PackId <id> -OutputDir <pack-dir> -Force -Json
pwsh -NoProfile -File .specify/scripts/powershell/repack-knowledge-pack.ps1 -RepoRoot . -PackId <id> -Mode full-snapshot -IncludeProfiles -Force -Json
pwsh -NoProfile -File .specify/scripts/powershell/validate-knowledge-pack.ps1 -PackRoot <pack-dir> -Json
pwsh -NoProfile -File .specify/scripts/powershell/compare-knowledge-pack-equivalence.ps1 -SourceKnowledgeDir ai/knowledge -PackRoot <pack-dir> -Json
```

## Validation

After changing generated context or knowledge assets, run:

```powershell
pwsh -NoProfile -File .specify/scripts/powershell/automation-common.ps1 -Tool validate-generated-context -RepoRoot . -Json
pwsh -NoProfile -File .specify/scripts/powershell/automation-common.ps1 -Tool validate-knowledge-index -RepoRoot . -Json
pwsh -NoProfile -File .specify/scripts/powershell/automation-common.ps1 -Tool validate-context-budget -RepoRoot . -Json
```

Scripts report `facts`, `blockers`, `unknowns`, and `hints`. The AI remains
responsible for semantic routing, source-evidence judgment, and validation
sufficiency.
