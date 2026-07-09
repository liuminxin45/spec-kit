# Spec Kit Task Routing
Load with `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, and current `.specify/feature.json` only.

## Default Rule
Start lean. Prefer source reading, code edits, and validation over process documents. Upgrade only when evidence, risk, or scope requires it; do not route by keyword matching alone.

## Profiles
- `micro-fix`: 1-3 files, single repo, evidenced internal fix. Use no `spec.md`, `plan.md`, or `tasks.md` by default.
- `standard-bugfix-lite`: default bugfix path. Use `workpack.md`, `implementation-summary.md`, and `validation.md`.
- `standard-bugfix`: use `plan.md` with compact Implementation Slices when behavior or compatibility needs a durable decision map. Skip `tasks.md` unless slices are too broad.
- `full-sdd`: use `spec.md -> plan.md -> tasks.md` for public API, architecture, migration, cross-repo, identity/permission/status, real-device, or broad UI/service/runtime boundary work.
- `blocked-investigation`: root cause, source behavior, runtime facts, or validation condition is missing. Collect `fact-pack.md` or `investigation.md`; do not patch by guessing.
- `validation-only`: no product-code change; write `validation.md`.

## Default Path
`preflight -> intake -> smallest planning artifact -> implement -> validation.md + implementation-summary.md -> optional acceptance.md -> human acceptance`

`retrospective`, `workflow-observer`, `promote-*`, `commit`, `post-commit-self-check`, `rubric-score`, and `complete-branch` are opt-in. They are not required for normal delivery closure.

## Stage Continuation
Prefer `resolve-next-stage` when available and consume `current_stage`, `next_stage`, `can_continue`, `blockers`, `required_human_action`, `commands_to_run`, and `missing_artifacts`. Auto-continue only along required default stages. Stop for human acceptance, clarification, owner decision, high-risk confirmation, unavailable host/device/permission/tooling, build or validation failure, unresolved blocker, source/runtime delivery-chain gap, explicit pause, or any opt-in governance/branch mutation stage.

## New Workflow Start
Before intake writes feature state, run `preflight-new-workflow`. Dirty worktrees, non-base branches, unfinished `.specify/feature.json`, and unresolved workflow runs block a new workflow. Do not stash, clean, switch branches, delete specs, archive state, or overwrite `.specify/feature.json` unless the user authorizes that named action.

## Artifact Rules
- `workpack.md`: default bugfix planning artifact; include root cause, Root-Fix Decision Gate, one bounded slice, write scope, forbidden scope, and validation.
- `implementation-summary.md`: final actual implementation index; read this first when asking what shipped.
- `validation.md`: concrete validation commands/results/evidence. Do not leave validation only in chat.
- `progress.md`, `review.md`, `convergence.md`, `acceptance-checklist.md`, `workflow-record.md`, `improvement-candidates.md`, `knowledge-candidates.md`, `workflow-observation.md`, and `rubric-score.md` are not default artifacts.
- `fact-pack.md` and `evidence.md` are created only when raw facts would bloat `validation.md` or runtime evidence is needed.

## Hard Upgrade Gates
- Public API, service/runtime/UI boundary, cross-repo, identity, permission, connection, acquisition, real-device, architecture, or migration work: do not use `micro-fix`.
- `full-sdd` must pass `tasks -> analyze -> checklist` before implementation.
- `standard-bugfix-lite` may skip `spec.md`, `plan.md`, `tasks.md`, `analysis.md`, and checklist when `workpack.md` is complete.
- Missing root cause, validation condition, or second same-class failure without new facts routes to `blocked-investigation` or `speckit-fact-layer`.
- Bugfix work must record Root-Fix Decision Gate before implementation. Mitigation, containment, cleanup, release, reset, retry, fallback, and limits are not root fix unless evidence proves the failure mechanism is eliminated.

## Optional Capabilities
- Use `skill-routing.yml` first, then load only the selected `.agents/spec-kit/skills/<skill>/SKILL.md`.
- Use `select-gates` before loading host CDP, frontend runtime sync, native bridge, plugin package, Qt parity, or real-device gate packs.
- Use `select-knowledge` or `ai/knowledge/index.yml` before reading knowledge guides; do not use full-text/BM25 search to load knowledge by default.
- Load `speckit-test-plan`, `quality-vision`, `acceptance-rubric`, and `ai-self-acceptance` only when the changed behavior requires them.

## Workflow Hooks
Workflow hooks are optional and default off. Load `.specify/workflow-hooks.yml` only when present. Dispatch selected hooks with `specify workflow invoke-hooks`; `workflow-agent-chain` hooks run serially and may continue only when `auto_continue=true`.

## Drift Checks
After Spec Kit template or shared-context changes, run `validate-generated-context`, `validate-knowledge-index`, and `validate-context-budget` before relying on regenerated defaults.

## Delivery Rules
- Always read repository-map before broad source scanning.
- Treat `.specify/feature.json` as current-feature state, not global truth; do not apply stale feature risk flags to unrelated tasks.
- Do not load `ai/knowledge/*`, `ai/tools/*`, `ai/workflows/gates/*`, old specs, roadmap/design docs, templates, or internal skills unless selected.
- For implement, read `workpack.md` or `plan.md` `AI Context Contract` before broad artifact reading.
- Product/plugin fixes must target repository source, not installed runtime plugin directories or built artifacts.
- Source/runtime artifact mismatch must be fixed in source before acceptance or commit.
- Push, remote tracking, branch completion, and destructive operations require explicit human approval.

## Final Response Guard
Run `inspect-workflow-closure` before final response only when feature state indicates accepted implementation, commit, strict self-check, or rubric work. If it reports a default-stage blocker, execute or report that blocker. Opt-in governance artifacts are not required unless the selected path requested them.

## Output Contract
When reporting routing, include selected profile, affected repositories, next default stage, selected internal skill when loaded, and concrete blockers/unknowns.
