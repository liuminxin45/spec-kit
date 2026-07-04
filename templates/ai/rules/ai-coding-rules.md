# AI Coding Rules

This file records stable AI coding rules. Do not load broad project knowledge
or historical process documents unless the current task needs them.

## Context Budget

- Default context is `AGENTS.md`, workspace config, repository map, active
  feature state, and current feature artifacts.
- Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, design-history docs,
  and old specs only on demand.
- Knowledge guides are routed through `ai/knowledge/index.yml` or
  `select-knowledge`; select by structured fields and read only the returned
  guide paths. The knowledge layer is deterministic and does not use
  full-text/BM25 search.
- Prefer scripts for hard facts instead of adding prose to prompts.

## Script / LLM Boundary

- Scripts output hard facts, blockers, unknowns, and hints.
- LLM owns semantic routing, root-cause judgment, risk explanation, validation
  sufficiency, and tradeoff decisions.
- Automation must not make final routing decisions from natural-language
  keyword matching.
- Command templates must cite this file for the script/LLM boundary instead of
  restating the full rule block in every stage template.
- Workflow shell hooks are script-owned. `invoke-workflow-hooks`
  synchronously runs matching `type: workflow-shell` hooks and normalizes
  status/action/artifacts; LLMs may explain hook results but must not infer
  success when `auto_continue` is false.
- Workflow agent-chain hooks are engine-owned. `type: workflow-agent-chain`
  runs Codex skills serially, passes `previous_result`/`previous_results`
  between steps, and pauses on the first non-continuable result.
- New workflow hooks for external tools must be created as portable hook packs
  through deterministic scaffolding (`specify hook scaffold` or
  `new-workflow-hook-pack.ps1`), then validated and applied. Do not directly
  hand-write `.specify/workflow-hooks.yml`.

## Repository Fact Source

- Use `.specify/memory/repository-map.md` for repository path, role, and
  capability ownership.
- Do not infer repository purpose by scanning source trees during early
  specification.
- Inspect source files only after affected repositories are identified.

## Runtime Investigation Hard Gates

- If repeated fixes do not change the symptom, run fact-layer collection before
  editing more code.
- For UI parity/layout issues, a first failed CSS/layout patch triggers a hard
  fact-layer gate: collect runtime DOM/CSS/computed style/box metrics through
  Chrome DevTools/CDP from the real target, or ask for copied DOM/CSS evidence,
  before making a second patch.
- For service/runtime issues, prefer latest configured logs after the relevant process
  exits.

## UI / UX / Copy Evidence Gate

- All UI development, UI changes, UI fixes, UX changes, icons, tooltips,
  labels, menu text, visible copy, layout, spacing, and style changes must have
  a reliable reference before implementation.
- Reliable references include original Qt UI/source/delegate/QSS/resource
  files, product design/mockup/Figma/export files, screenshots, existing
  product conventions in the target app, or explicit owner/user approval for a
  deliberate change.
- Do not invent UI shape, controls, icons, labels, tooltip text, tooltip style,
  visual hierarchy, or interaction behavior from general taste. A migration
  reference such as "icon plus tooltip" must not be implemented as a text
  button unless the spec records an explicit approved change.
- Before editing UI/UX/copy, perform a bounded search for the reference in the
  affected repositories and known design/source directories. If no reliable
  source is found, stop and route to `speckit.clarify` or
  `blocked-investigation`; do not patch by imagination.
- Every planned UI/UX/copy change must record the source path or evidence
  artifact, the target element, the expected text/icon/style/behavior, and any
  intentional delta from the source. Owner-approved `N/A` is allowed only when
  the absence of a reference is itself recorded as a product decision.

## Workflow Weight

- Starting a new Spec Kit workflow must run `preflight-new-workflow` before
  intake writes feature state. Dirty worktrees, non-base branches, unfinished
  `.specify/feature.json`, or unresolved workflow runs block the new workflow
  until the user manually resolves them or explicitly authorizes a named AI
  action. Do not auto-stash, auto-clean, switch branches, delete specs, archive
  state, or overwrite `.specify/feature.json`.
- Use five primary implementation paths: `micro-fix`, `standard-bugfix-lite`,
  `standard-bugfix`, `full-sdd`, and `blocked-investigation`.
- `validation-only` is a non-implementation mode.
- `standard-bugfix-lite` uses `workpack.md` for compact low/medium-risk fixes:
  root cause, one bounded slice, validation, and acceptance-rubric summary.
  Upgrade it when high-risk gates, public API, identity/permission/status
  semantics, cross-repo work, real-device behavior, or missing evidence appears.
- `standard-bugfix` may combine L2/L3 by keeping implementation slices in
  `plan.md`; only `full-sdd` requires a separate `tasks.md` by default.
- `full-sdd` must complete `tasks`, `analyze`, and `checklist` before
  implementation. The implementation preflight blocks if `tasks.md`,
  `analysis.md`, or `checklists/implementation-readiness.md` is missing.
- `standard-bugfix` still runs `analyze` before implementation. Run
  `checklist` too when risk is high, UI/runtime evidence is involved,
  validation readiness is non-trivial, or the change crosses service/runtime/UI
  boundaries.
- A user's "next stage" instruction does not override structured gates in
  `.specify/feature.json`, `workflow-state.json`, or
  `.specify/templates/layer-manifest.yml`.

## Stage Continuation Contract

- Use `ai/workflows/task-routing.md` as the single source of truth for
  auto-continue gates and stop reporting.
- Use `resolve-next-stage` when available so Agent continuation consumes
  structured `next_stage` and blocker facts instead of prose inference.
- Command templates should cite the central contract instead of restating or
  weakening it.

## Host Frontend Delivery Chain

- After AI changes host-embedded frontend plugin source, follow source edit ->
  frontend build -> direct runtime replacement -> real host CDP verification,
  then final `.plugin` build/package evidence before commit/complete-branch.
- Runtime replacement must be scoped to the explicit plugin runtime directory
  and should remove stale split chunks by default.
- All plugin types, including frontend, native, JS, and integrated plugin
  changes, use the shared `.plugin` build/package system as final delivery
  evidence. Local build/export/runtime replacement is prerequisite validation
  evidence only.

## host CDP Target Gate

- Before declaring host/CDP validation unavailable, run
  `ensure-host-cdp` or equivalent probes. Reuse an existing
  valid host target when one is running. If CDP is unreachable and
  no process owns the port, start the configured host command and rerun the
  probe. If another process owns the port, identify it and stop with a real
  blocker unless the user explicitly approves a destructive recovery action.
  A running process or occupied port is not enough reason to skip to manual
  acceptance.
- Before host UI CDP evidence, inspect `/json/list` or run
  `inspect-host-cdp-target`.
- Record all page target `id/title/url/webSocketDebuggerUrl` values and the
  selected target id/URL.
- Product UI validation must reject Plugin Workbench, `base-win.html`,
  `devtools://`, blank, and unrelated targets as `wrong-target / insufficient`.
- `Plugin Workbench|plugin-workbench.html` is valid only for plugin-host
  workbench validation.

## Qt Source Behavior Map

- For Qt-to-frontend UI parity, read `.specify/memory/qt-source-behavior-map.md`
  or `ai/knowledge/qt-source-behavior-map.md` before broad source search.
- Placeholder, missing, or stale map rows require bounded source investigation
  and active feature evidence; do not infer behavior from absence. New Qt facts
  belong in the active feature first and move to memory/knowledge only through
  retrospective/promote-lessons with explicit human approval.

## Generated Context Drift

- `AGENTS.md`, `.specify/memory/repository-map.md`,
  `.specify/templates/layer-manifest.yml`, `ai/workflows/task-routing.md`, and
  `ai/rules/ai-coding-rules.md` are generated or shared context that may lag
  behind `spec-kit` templates.
- After template/tooling changes, run `validate-generated-context` before
  relying on default context. Report missing gate phrases as blockers or
  explicit drift, not as a reason to silently skip the rule.
- After changing `ai/knowledge/index.yml` or any guide under `ai/knowledge/*`,
  run `validate-knowledge-index`. Missing guides, oversized guides, unknown
  repository keys, or machine-specific knowledge paths are context drift.

## Git and Branch Policy

- Spec branches are local-only.
- Do not push, create remote tracking branches, or create GitHub issues as part
  of the default workflow.
- Commit is automated after hard gates and deterministic preflight pass.
- Branch completion is a state mutation gate: preflight is automated, but the
  cherry-pick path requires explicit human approval and `-ConfirmCompletion`.
- Push is outside the default workflow. Use PR-first; any exceptional push must
  pass `preflight-push` and explicit human approval.
- Branch completion cherry-picks spec commits back to the recorded entry branch
  and keeps local spec branches by default.
- After commit, run exactly one post-commit self-check, then final Rubric
  scoring. `validate-rubric-score` must pass before complete-branch.
- Before final response after human acceptance or commit evidence, run
  `inspect-workflow-closure`; if it reports `next_required_stage`, continue
  that stage instead of claiming completion. Local branch/push policy does not
  skip retrospective, workflow-observer, post-commit self-check, or rubric.

## Long-Term Asset Protection

- Do not silently edit durable rules during feature implementation.
- Durable fact updates require source evidence, reason, and validation evidence.
- Retrospective/留痕 is mandatory before commit for standard-bugfix and
  full-sdd delivery. Lesson promotion remains optional and only applies to
  human-approved candidates or explicit audit/promotion requests.
- `knowledge-candidates.md` is candidate-only. Promote project knowledge into
  `ai/knowledge` only after explicit human approval, then run
  `validate-knowledge-index` and optional delta-overlay repack.
