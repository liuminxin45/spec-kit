# Spec Kit Task Routing

This file is the compact routing guide for AI coding. It is not a full process
manual. Load it with `AGENTS.md`, `.specify/workspace.yml`, and
`.specify/memory/repository-map.md`.

## Default Rule

Start light. Upgrade only when evidence, risk, or scope requires it. Do not
route by matching user text keywords alone.

## Stage Continuation

Auto-continue is a stage contract, not report wording. When the current stage is
complete and the next stage is structurally known, execute the next required
stage in the same agent turn without asking the user to type the next command:
invoke the next command/skill when available, or load that command template and
perform its steps inline. Stop only for human acceptance, human clarification,
owner decision, high-risk operation confirmation, missing host/device/
permission/tooling, build failure, validation failure, unresolved blocker,
unclosed source/runtime delivery chain, or explicit user pause. If stopping, do
not claim automatic entry; record `blockers` and `next_required_human_action`.
A plain completion summary or "自动进入"/"continue to" promise without execution
is non-compliant.

## Stage Progress Displays

When the user asks for Spec Kit progress, the current stage, or the next stage,
show stage rows with three columns: `阶段`, `状态`, and `阶段目标`. Use these
canonical one-sentence objectives:

| Stage | Objective |
|-------|-----------|
| `speckit-intake` | Classify request risk/profile and write current feature routing state. |
| `speckit-specify` | Capture scope, acceptance criteria, affected repositories, and known risks. |
| `speckit-clarify` | Resolve or record only blocking high-impact ambiguities before planning. |
| `speckit-plan` | Create the smallest executable implementation and validation plan. |
| `speckit-tasks` | Break full-sdd or broad plans into ordered implementation tasks. |
| `speckit-analyze` | Check spec/plan/task consistency, blockers, and implementation readiness. |
| `speckit-checklist` | Validate implementation-readiness gates before source changes. |
| `speckit-implement` | Apply source changes and collect required AI-owned validation evidence. |
| `speckit-validation` | Record validation evidence for validation-only work. |
| `speckit-fact-layer` | Collect runtime, source, log, DOM, CSS, or CDP facts before risky fixes. |
| `speckit-acceptance` | Produce user acceptance steps after AI validation is complete. |
| `speckit-simplify` | Do behavior-preserving cleanup after accepted functionality. |
| `speckit-test-hardening` | Add focused regression protection when it reduces real risk. |
| `speckit-retrospective` | Record workflow evidence and improvement candidates before commit. |
| `speckit-promote-lessons` | Promote only human-approved process improvements. |
| `speckit-commit` | Stage and commit confirmed source scope with validated message format. |
| `speckit-complete-branch` | Cherry-pick local spec commits back to base after confirmation. |

## Profiles

- `micro-fix`: small, evidenced, low-blast-radius source change.
- `standard-bugfix`: compact behavior fix with `spec.md` + `plan.md`; `plan.md`
  may contain executable slices and skip `tasks.md`.
- `full-sdd`: public API, architecture, broad migration, cross-repo, real
  device semantics, or large UI/Biz/Libs boundary work.
- `blocked-investigation`: source behavior, runtime evidence, root cause, or
  validation condition is missing.
- `validation-only`: no product-code change; write validation evidence only.

Auxiliary labels such as `ui-parity`, `public-api`, and `cross-repo` are risk
flags, not separate default workflows.

## Hard Upgrade Gates

- Public API, SDK/Biz/UI boundary, cross-repo, identity, permission, connection,
  acquisition, or real-device behavior: do not use `micro-fix`.
- `full-sdd` must pass `tasks -> analyze -> checklist` before implementation.
  Implementation preflight blocks when `tasks.md`, `analysis.md`, or
  `checklists/implementation-readiness.md` is missing.
- `standard-bugfix` may skip `tasks.md` only when `plan.md` has complete
  `Implementation Slices`; it still runs `analyze` before implementation.
  Run `checklist` as well for high-risk, UI/runtime, cross-repo, SDK/Biz
  boundary, or non-trivial validation-readiness work.
- First failed UI/CSS/layout patch: before a second patch, collect DevTools/CDP
  DOM/CSS/computed style/box metrics from the real target, or ask the user for
  copied DOM/CSS evidence.
- Host-embedded UI validation: after repository source is built and, when
  needed, synced to the host runtime, prefer the real DesktopShell Electron
  host through CDP at `http://127.0.0.1:9222`. For frontend plugin source
  edits, the AI delivery chain is source edit -> frontend build -> direct
  runtime replacement -> real host CDP verification. Native plugin source edits
  use source edit -> `.plugin` build because native output cannot be hot
  replaced safely.
- DesktopShell CDP validation: run `inspect-desktop-shell-cdp-target`
  or inspect `/json/list` first and record page target
  `id/title/url/webSocketDebuggerUrl`. Select targets matching
  `product-homepage`, `product-main-window`, or
  `frontend/static/index.html`; reject `Plugin Workbench`, `base-win.html`,
  `devtools://`, blank, and unrelated targets for product UI validation.
  Isolated plugin preview is fallback evidence, not the primary acceptance
  target.
- Qt-to-frontend UI parity: read `.specify/memory/qt-source-behavior-map.md` or
  `ai/knowledge/qt-source-behavior-map.md` before broad search. If the relevant
  module row is missing/stale, create bounded source evidence in the active
  feature before implementation.
- Repeated same-class failure or unchanged symptom: run `speckit.fact-layer`.
- Missing root cause or missing validation condition: use `blocked-investigation`.
- Source/runtime artifact mismatch: fix repository source before acceptance or
  commit.
- If `.specify/feature.json` says `delivery_profile`, `risk_level`, or
  `risk_flags`, use those structured fields for gates instead of the user's
  last natural-language phrase such as "进入下一阶段".

## Context Budget

- Always read repository-map before scanning source.
- Treat `.specify/feature.json` as current-feature state, not global truth. For
  `tools/spec-kit`, shared workflow/governance, or unrelated repository tasks,
  do not apply stale feature risk flags or load `specs/<feature>/*` artifacts
  unless the user explicitly resumes that feature.
- Do not load `ai/knowledge/*`, `ai/tools/*`, old specs, roadmap/design docs, or
  templates unless the current gate requires them.
- When repository-map is too small for the task, run `select-knowledge` or read
  `ai/knowledge/index.yml` first. Select by affected repositories, risk flags,
  capability tags, stage, or explicit task terms; read only the returned guide
  paths. This knowledge layer is deterministic and does not require
  full-text/BM25 search.
- For `analyze` and `checklist`, read the `artifact_sections` listed in
  `.specify/templates/layer-manifest.yml` first. Expand to full files only when
  the section pass exposes a blocker, ambiguity, missing traceability, or an
  artifact explicitly needed by the stage.
- Prefer scripts for hard facts: log discovery, DevTools target detection,
  source/runtime consistency, changed-file classification, and validation
  command suggestions.
- After changing `tools/spec-kit` templates or refreshing shared infra, run
  `validate-generated-context` and `validate-knowledge-index` before trusting
  generated default context or generated knowledge routing.

## Output Contract

When reporting routing, include:

- selected profile
- affected repositories from repository-map
- next command
- stage progress table with `阶段`, `状态`, and one-sentence `阶段目标` when
  reporting workflow progress or next-stage status
- facts
- blockers
- unknowns
- ignored hints, if any
