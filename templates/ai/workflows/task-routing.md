# Spec Kit Task Routing
Load with `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, and current `.specify/feature.json` only.

## Default Rule
Start lean. Prefer source reading, code edits, and validation over process documents. Upgrade only when evidence, risk, or scope requires it; do not route by keyword matching alone.

## Profiles
- `micro-fix`: 1-3 files, single repo, evidenced internal fix. Use no `spec.md`, `plan.md`, or `tasks.md` by default.
- `standard-bugfix-lite`: default bugfix path. Use `workpack.md` and close lean delivery in `workpack.md` `Outcome`; split out `validation.md` and `implementation-summary.md` only for commit, branch completion, strict governance, handoff, or high-risk evidence.
- `standard-bugfix`: use `plan.md` with compact Implementation Slices when behavior or compatibility needs a durable decision map. Skip `tasks.md` unless slices are too broad.
- `full-sdd`: use `spec.md -> plan.md -> checklist -> tasks.md -> analyze` for public API, architecture, migration, cross-repo, identity/permission/status, external-system, or broad UI/service/runtime boundary work.
- `blocked-investigation`: root cause, source behavior, runtime facts, or validation condition is missing. Collect `fact-pack.md` or `investigation.md`; do not patch by guessing.
- `validation-only`: no product-code change; write `validation.md`.

## Default Path
`preflight -> intake -> smallest planning artifact -> implement -> lean workpack Outcome or strict validation.md + implementation-summary.md -> optional acceptance.md -> human acceptance`

`retrospective`, `workflow-observer`, `promote-*`, `commit`, `post-commit-self-check`, `rubric-score`, and `complete-branch` are opt-in. They are not required for normal delivery closure.

## Stage Continuation
Prefer `resolve-next-stage` and consume `current_stage`, `next_stage`, `can_continue`, `auto_continue`, blockers and evidence. A single stage command stops after its stage unless the user authorized automatic continuation, including in natural language (for example, “进入自动模式，不要逐步停”). Record that authorization with `update-workflow-state.ps1 -ContinuationMode automatic -AuthorizationEvidence <user instruction>`. A workflow-runner invocation is also explicit authorization. Continue structurally required default stages while `auto_continue` is true; do not ask again for an already authorized operation. Stop for human acceptance, a required clarification/owner decision, unavailable capability, failing validation, unresolved blocker, or explicit pause. Optional governance, commits, branch mutations and push require their own explicit authorization; automatic mode does not grant it. Report the concrete blocker and the smallest needed user action when stopping.

Use `update-workflow-state.ps1 -Stage <stage> -Status <status> -Evidence <reference>` for stage transitions. `stage_statuses` is canonical; top-level legacy nodes are synchronized by this writer, and readers report conflicts. Resolve the next stage again after a transition. Keep acceptance separate from validation failures or accepted gaps; never infer test success from user acceptance. Refresh the current implementation/delivery summary after commit, completion, push, or amendment, linking each repository's current SHA and review/patch set while preserving historical evidence.

## New Workflow Start
Before intake writes feature state, run `preflight-new-workflow`. Dirty worktrees, non-base branches, unfinished `.specify/feature.json`, and unresolved workflow runs block a new workflow. Do not stash, clean, switch branches, delete specs, archive state, or overwrite `.specify/feature.json` unless the user authorizes that named action.

## Artifact Rules
- `workpack.md`: default bugfix planning and lean closure artifact; include root cause, Root-Fix Decision Gate, one bounded slice, write scope, forbidden scope, validation, and final `Outcome`.
- `implementation-summary.md`: final actual implementation index for non-lean, handoff, commit, branch completion, or strict governance paths; read this first when asking what shipped on those paths.
- `validation.md`: concrete validation commands/results/evidence for non-lean, handoff, commit, branch completion, strict governance, or evidence-heavy paths. Lean paths may record equivalent concise evidence in `workpack.md` `Outcome`.
- `progress.md`, `review.md`, `convergence.md`, `acceptance-checklist.md`, `workflow-record.md`, `improvement-candidates.md`, `knowledge-candidates.md`, `workflow-observation.md`, and `rubric-score.md` are not default artifacts.
- `fact-pack.md` and `evidence.md` are created only when raw facts would bloat `validation.md` or runtime evidence is needed.

## Hard Upgrade Gates
- Public API, service/runtime/UI boundary, cross-repo, identity, permission, external-system, architecture, or migration work: do not use `micro-fix`.
- `full-sdd` must pass `checklist -> tasks -> analyze` before implementation.
- `standard-bugfix-lite` may skip `spec.md`, `plan.md`, `tasks.md`, `analysis.md`, and checklist when `workpack.md` is complete.
- Missing root cause, validation condition, or second same-class failure without new facts routes to `blocked-investigation` or `speckit-fact-layer`.
- Bugfix work must record Root-Fix Decision Gate before implementation. Mitigation, containment, cleanup, release, reset, retry, fallback, and limits are not root fix unless evidence proves the failure mechanism is eliminated.

## Optional Capabilities
- Use `skill-routing.yml` first, then load only the selected `.agents/spec-kit/skills/<skill>/SKILL.md`.
- Use `select-gates` before loading specialized gate packs.
- Use `select-knowledge` or `ai/knowledge/index.yml` before reading knowledge guides; do not use full-text/BM25 search to load knowledge by default.
- Load `speckit-test-plan`, `quality-vision`, `acceptance-rubric`, and `ai-self-acceptance` only when the changed behavior requires them.

## Workflow Hooks
Workflow hooks are optional and default off. Load `.specify/workflow-hooks.yml` only when present. Dispatch selected hooks with `specify workflow invoke-hooks`; `workflow-agent-chain` hooks run serially and may continue only when `auto_continue=true`.

## Drift Checks
At every feature stage entry, after a failed attempt, and on the first
continuation after context compaction, run `inspect-workflow-drift`, then rerun
`select-gates` and `select-knowledge` from explicit current scope. If target
component, repository, build scope, or delivery mode changed, stop for a scope
amendment; route an independent issue to a follow-up workflow. After Spec Kit
template or shared-context changes, run `validate-generated-context`,
`validate-knowledge-index`, and `validate-context-budget` before relying on
regenerated defaults.

## Delivery Rules
- Always read repository-map before broad source scanning.
- Treat `.specify/feature.json` as current-feature state, not global truth; do not apply stale feature risk flags to unrelated tasks.
- Do not load `ai/knowledge/*`, `ai/tools/*`, `ai/workflows/gates/*`, old specs, roadmap/design docs, templates, or internal skills unless selected.
- For implement, read `workpack.md` or `plan.md` `AI Context Contract` before broad artifact reading.
- Durable fixes must target repository source, not generated outputs, installed runtime directories, caches, or built artifacts.
- Source/runtime artifact mismatch must be fixed in source before acceptance or commit when a selected gate requires runtime delivery evidence.
- Push, remote tracking, branch completion, and destructive operations require explicit human approval.
- Active local Spec branches never use `git pull`, `git merge`, or
  `--rebase-merges`. Route mid-workflow base updates through
  `sync-spec-branches` fetch/rebase preflight; any merge commit in the Spec
  range blocks commit, complete-branch, and push preflight.

## Final Response Guard
Run `inspect-workflow-closure` before final response only when feature state indicates accepted implementation, commit, strict self-check, or rubric work. If it reports a default-stage blocker, execute or report that blocker. Opt-in governance artifacts are not required unless the selected path requested them.

## Output Contract
When reporting routing, include selected profile, affected repositories, next default stage, selected internal skill when loaded, and concrete blockers/unknowns.
