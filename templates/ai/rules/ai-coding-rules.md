# AI Coding Rules

Stable rules only. Do not load broad project knowledge or historical process documents unless the current task needs them.

## Context Budget

- Default context is `AGENTS.md`, workspace config, repository map, active feature state, and current feature artifact.
- Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, design-history docs, and old specs only on demand.
- Knowledge guides are routed through `ai/knowledge/index.yml` or `select-knowledge`; read only returned guide paths and do not use full-text/BM25 search to load knowledge by default.
- Gate packs are routed through `select-gates`; read only selected gate files.
- Prefer scripts for hard facts instead of adding prose to prompts.

## Script / LLM Boundary

- Scripts output hard facts, blockers, unknowns, and hints.
- LLM owns semantic routing, root-cause judgment, risk explanation, validation sufficiency, and tradeoff decisions.
- Automation must not make final routing decisions from natural-language keyword matching.
- Workflow hooks are dispatched through `specify workflow invoke-hooks`; continue only when hook results allow continuation.
- New workflow hooks for external tools must be scaffolded and validated, not hand-written into `.specify/workflow-hooks.yml`.

## Repository Fact Source

- Use `.specify/memory/repository-map.md` for repository path, role, and capability ownership.
- Do not infer repository purpose by scanning source trees during early specification.
- Inspect source files only after affected repositories are identified.

## Workflow Weight

- Starting a new Spec Kit workflow must run `preflight-new-workflow` before intake writes feature state.
- Use lean implementation paths by default:
  - `micro-fix`: no `spec.md`, `plan.md`, or `tasks.md`; use `workpack.md`.
  - `standard-bugfix-lite`: default bugfix path; use `workpack.md` and close lean delivery in `workpack.md` `Outcome`; split out `validation.md` and `implementation-summary.md` only for commit, branch completion, strict governance, handoff, or high-risk evidence.
  - `standard-bugfix`: use `plan.md` with compact Implementation Slices; skip `tasks.md` unless slices are too broad.
  - `full-sdd`: use `spec.md -> plan.md -> checklist -> tasks.md -> analyze`.
  - `blocked-investigation`: collect facts before editing.
  - `validation-only`: write `validation.md` without product-code changes.
- `progress.md`, `review.md`, `acceptance-checklist.md`, `convergence.md`, retrospective, workflow-observer, promotion, post-commit self-check, rubric, and complete-branch are opt-in or conditional artifacts, not default delivery.
- Bugfix work must complete a Root-Fix Decision Gate before implementation. Do not call cleanup, release, reset, retry, fallback, rate/quantity limiting, or impact narrowing a root fix unless evidence shows the failure mechanism is eliminated.
- `workpack.md` `Outcome` is enough to close micro-fix and standard-bugfix-lite work when there is no commit, branch completion, strict governance, handoff, or high-risk evidence need.
- `implementation-summary.md` is the final actual implementation index for non-lean, handoff, commit, branch completion, or strict governance paths. It records final approach, changed files, mechanism changes, final fix type, validation result, residual risk, compatibility impact, follow-up root-fix route, and evidence links.

## Runtime Investigation Hard Gates

- If repeated fixes do not change the symptom, run fact-layer collection before editing more code.
- For UI parity/layout issues, a first failed CSS/layout patch triggers fact-layer: collect runtime DOM/CSS/computed style/box metrics through available browser/runtime inspection tools from the real target, or ask for copied evidence, before making a second patch.
- For service/runtime issues, prefer latest configured logs after the relevant process exits.

## UI / UX / Copy Evidence Gate

- UI changes, UX changes, icons, tooltips, labels, visible copy, layout, spacing, and style changes need a reliable reference before implementation.
- Reliable references include source UI files, design/mockup/Figma/export files, screenshots, existing target-app conventions, or explicit owner/user approval.
- Do not invent UI shape, controls, text, icons, tooltip style, hierarchy, or interaction behavior from general taste.
- If no reliable source is found, route to clarify or blocked investigation.

## Stage Continuation Contract

- Use `ai/workflows/task-routing.md` as the single source of truth for auto-continue and stop rules.
- Use `resolve-next-stage` when available so continuation consumes structured `next_stage` and blocker facts.
- A single slash-command or stage skill stops after its own stage and reports the next command. Only an explicit workflow-runner invocation may auto-continue through default delivery stages. Opt-in governance, commit, rubric, and branch mutation stages require explicit user request.

## Gate-Pack Routed Evidence

- Use `select-gates` before loading specialized gate-pack details.
- Read only selected gate packs, and keep command templates as stage contracts rather than full manuals.
- A selected gate can add required build, runtime, browser, package, external-system, or source-parity evidence; unselected gate details are not default context.

## Generated Context Drift

- `AGENTS.md`, `.specify/memory/repository-map.md`, `.specify/templates/layer-manifest.yml`, `ai/workflows/task-routing.md`, and `ai/rules/ai-coding-rules.md` may lag behind `spec-kit` templates.
- After template/tooling changes, run `validate-generated-context`, `validate-knowledge-index`, and `validate-context-budget`.

## Git and Branch Policy

- Spec branches are local-only.
- Do not push, create remote tracking branches, or create GitHub issues as part of the default workflow.
- Commit is opt-in after validation and user acceptance. It does not require retrospective or workflow-observer artifacts.
- Branch completion is opt-in and requires explicit human approval for the exact preflight result.
- Push is outside the default workflow. Use PR-first; any exceptional push must pass `preflight-push` and explicit human approval.
- Run `inspect-workflow-closure` before final response only when feature state
  indicates accepted implementation, commit, strict self-check, or rubric work.

## Long-Term Asset Protection

- Do not silently edit durable rules during feature implementation.
- Durable fact updates require source evidence, reason, and validation evidence.
- Retrospective, knowledge candidates, and lesson promotion are opt-in governance stages and must not block lean delivery unless explicitly selected.
