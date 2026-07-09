---
description: Run a validation-only Spec Kit path without changing product code.
scripts:
  select_knowledge_ps: scripts/powershell/select-knowledge.ps1 -Json -Stage validation -FeatureDir <feature-dir>
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

Use this command when `.specify/feature.json` selects
`delivery_profile: validation-only`. It is for reproducing, auditing, smoke
checking, or regression validation without product-code changes.

## Validation Contract

Create or update these evidence artifacts:

- `FEATURE_DIR/validation.md`: normalized validation summary using
  `ai/templates/validation-template.md`.
- `FEATURE_DIR/evidence.md`: optional tool/test-facing evidence ledger using
  `ai/templates/evidence-template.md` when raw evidence would bloat
  `validation.md`.

`validation.md` must include:

- Scope and affected repositories.
- Commands or manual checks run.
- Expected results.
- Actual results.
- Evidence links or logs.
- Validation Context Contract: decision-critical facts used, evidence sources
  actually loaded, context intentionally not loaded, missing facts, sufficiency
  judgment, and why the evidence is enough for AI acceptance.
- AI Self-Acceptance: rubric rows judged, Essential/Pitfall result, UI baseline
  status, selected gate/log/runtime evidence, and `PASS | FAIL | BLOCKED`.
- Gaps and who can close them.
- Whether the result changes routing to `micro-fix`, `standard-bugfix-lite`,
  `standard-bugfix`, `full-sdd`, or `blocked-investigation`.

## Rules

- Do not edit production code.
- No validation claim is complete without evidence in `evidence.md`,
  `fact-pack.md`, logs, screenshots, named command output, or inline evidence
  links in `validation.md`.
- For selected gate-pack validation, follow the selected gate's target
  selection, recovery, screenshot, build/package, runtime sync, and evidence
  rules. Record the selected gate id, target identity, commands run, evidence
  paths, and any unresolved gaps. Do not substitute isolated previews or manual
  acceptance when the selected gate requires a real runtime target.
- For visible UI validation, capture the baseline/reproduced and final validated
  states for visible behavior, plus intermediate dialog/error/hover/scroll
  states only when they decide acceptance. Record screenshot paths or the
  owner-approved reason they could not be collected.
- For source edits that require build/deploy/runtime verification, validation
  must show source edit -> build -> runtime/deployment verification evidence.
  Record build command/result, deploy/sync command/result when applicable, and
  loaded-resource or runtime proof from the selected target. Runtime hot
  replacement remains validation evidence, not final delivery evidence unless
  the project explicitly treats it as source delivery.
- For height, clipping, scrollbar, bottom spacing, detail/footer panel, or
  information-panel validation, include box metrics for the relevant embedded
  root, shell, main panel, detail/footer panel, scroll owner, and last visible row/control.
  State whether each relevant bottom edge is `<= window.innerHeight`. Treat
  bare `100vh` in an embedded surface as a risk requiring measured container-offset
  evidence, not as proof that the layout fits.
- For external-system, connection, permission, status, service/runtime, or
  embedded runtime validation, the agent owns the primary smoke when local
  target resources and automation tools are available. Start or reuse the
  required target when safe and configured, execute the user flow or equivalent
  API operation, and verify process liveness,
  latest service/runtime logs, console errors, and refreshed runtime/UI state. Do not
  mark validation complete by assigning these technical checks to human manual
  acceptance. If the smoke cannot run, record the concrete unavailable resource,
  permission, or automation condition and route to investigation or a
  visible validation gap.
- If agent-owned smoke fails or the original symptom remains, validation is not
  complete. Return to implementation/investigation, collect fresh log/runtime
  evidence, adjust source, rebuild/deploy as needed, and rerun the smoke until it
  passes or a concrete blocker is proven. Human review is the final acceptance
  layer after this evidence, not the fallback debugger.
- When code changed, validation-only evidence may supplement but not replace
  `speckit-ai-self-acceptance`. Missing rubric judgment routes back to
  implementation/self-acceptance before human acceptance.
- Keep optional `evidence.md` factual and tool/test-facing.
- When repository-map and active artifacts do not identify enough validation
  commands, smoke routes, selected gate evidence requirements, or repository-specific
  caveats, run `select-knowledge` for stage `validation` and read only the
  returned `ai/knowledge/*` guide paths, especially `validation-matrix.yml`.
  Do not load the whole knowledge tree and do not use full-text/BM25 search.
- Do not generate full implementation tasks unless validation discovers an
  actionable change and the profile is explicitly re-routed.
- Use bounded search only inside affected repositories and known directories.
- Do not search the whole workspace root.
- Do not commit, merge, push, or mutate branches.

## Output

Report in Chinese:

- `validation.md` path.
- `evidence.md` path when created.
- Screenshot directory when screenshots were used.
- Checks run and results.
- Remaining gaps.
- Recommended next delivery profile.
