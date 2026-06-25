---
description: Promote only approved retrospective knowledge candidates into ai/knowledge and optionally repack.
scripts:
  promote_ps: scripts/powershell/promote-knowledge-candidates.ps1 -Json -FeatureDir <feature-dir>
  validate_index_ps: scripts/powershell/validate-knowledge-index.ps1 -Json
  repack_ps: scripts/powershell/repack-knowledge-pack.ps1 -Json -Mode delta-overlay
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`,
`.specify/memory/repository-map.md`, `.specify/feature.json` when present, and
`ai/workflows/task-routing.md`.

Read `FEATURE_DIR/knowledge-candidates.md`, `ai/knowledge/index.yml`, and the
target guides selected by approved candidates. Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic
routing, evidence judgment, promotion decisions, and validation sufficiency.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`;
if this stage cannot execute the next required stage, report `blockers` and
`next_required_human_action`.

## Purpose

Promote project knowledge only after explicit human approval. This stage is
conditional: it must skip `pending` and `rejected` candidates, must not invent
new long-term rules, and must validate the knowledge index after changes.

Use the CLI form when available:

```powershell
specify knowledge promote-candidates --project-dir . --feature-dir <feature-dir> --json
```

For redistribution after promotion:

```powershell
specify knowledge promote-candidates --project-dir . --feature-dir <feature-dir> --repack --pack-id <id> --force --json
```

## Execution Steps

1. Inspect `FEATURE_DIR/knowledge-candidates.md`.
2. Confirm candidates to promote have `人工审核结论: approved`.
3. Run `promote-knowledge-candidates`.
4. Verify `validate-knowledge-index` passes.
5. If `--repack` is requested, repack through `delta-overlay`.
6. Write or report `FEATURE_DIR/knowledge-promotion-report.md`.
7. Continue to `speckit.commit`.

## Guardrails

- `pending` candidates are review input, not knowledge.
- `rejected` candidates are retained only as historical context.
- Never write machine-specific absolute paths into `ai/knowledge`.
- Keep promoted guide entries bounded and evidence-linked.
- Promotion edits long-lived knowledge files, so it requires human approval.

## Output

Report in Chinese:

- Approved candidates promoted.
- Pending/rejected candidates skipped.
- `knowledge-promotion-report.md` path.
- `validate-knowledge-index` status.
- Repack status when requested.
- Required next stage: `speckit.commit` / `$speckit-commit`.
