---
description: Create an implementation plan for a CoreServicesLib capability while preserving upstream design artifacts.
scripts:
  sh: scripts/bash/setup-plan.sh --json
  ps: scripts/powershell/setup-plan.ps1 -Json
  select_knowledge_sh: scripts/bash/select-knowledge.sh --json --stage plan --feature-dir <feature-dir>
  select_knowledge_ps: scripts/powershell/select-knowledge.ps1 -Json -Stage plan -FeatureDir <feature-dir>
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

Create `plan.md` from the active `spec.md`, and keep the upstream artifact
model: `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`.
Also update `review.md` as the human navigation page without replacing the
AI-readable plan and design artifacts.

The plan should be concrete enough for task generation, but not overfit to one
developer's local implementation idea.

For `micro-fix`, do not expand the full upstream artifact set unless the
evidence shows the bug is not actually micro. Use the lightweight evidence
contract instead and let later full stages auto-skip. For `blocked-investigation`,
do not plan implementation; plan bounded investigation only.

## Layered Artifact Contract

- This command creates the L2 artifact set from `templates/layer-manifest.yml`.
- Required L2 outputs are `plan.md` and `workflow-state.json`, with
  `research.md`, `data-model.md`, `contracts/`, and `quickstart.md` created
  when applicable or marked `N/A` with reasons.
- `plan.md` must include the `L2 Artifact Contract` section from
  `.specify/templates/plan-template.md`.
- `workflow-state.json` is the structured source for attempts, validations,
  fact-layer status, acceptance state, retrospective state, and promotion state.

## Language Rules

- Human-reviewed artifacts MUST use Chinese-first style:
  - `plan.md`
  - `quickstart.md`
  - Stage completion summaries shown to the user
- `plan.md` must include a top `## 人类审核摘要` section for fast human
  review. This section is additive only: it must summarize the selected
  approach, key review points, real change scope, N/A boundaries, main risks,
  validation entry, and next step, and 不得替代或删减 later AI/流程读取区 such as
  technical context, affected modules, boundary sections, risk tables,
  validation plan, and design artifact notes.
- AI-oriented artifacts SHOULD use English-first style:
  - `research.md`
  - `data-model.md`
  - `contracts/`
- Preserve technical identifiers in their original form: file paths, module
  names, class names, function names, APIs, fields, enum/status values,
  commands, and test names.
- In `contracts/`, never translate interface names, event names, JSON keys,
  DTO fields, status values, operation names, or protocol terms.

## Execution Steps

1. Run the setup script and parse:
   - `FEATURE_SPEC`
   - `IMPL_PLAN`
   - `SPECS_DIR`
   - `BRANCH` / active spec branch, when emitted by the script.

2. Load context.
   - `FEATURE_SPEC`
   - `SPECS_DIR/intake.md`, if present.
  - `.specify/feature.json` task type and routing fields, if present.
   - `.specify/memory/constitution.md`
   - `.specify/templates/plan-template.md`
   - Existing design artifacts in `SPECS_DIR`, if present.
   - If repository-map is not enough for repository, domain, build, or
     validation context, run `select-knowledge` for stage `plan` and read only
     the returned `ai/knowledge/*` guide paths. Do not load every guide and do
     not use full-text/BM25 search for knowledge routing.

3. Fill `plan.md`.
   Include:
   - Human review summary near the top. Keep it concise and reviewer-focused;
     do not use it as a substitute for the complete AI-readable plan sections.
   - Technical context.
   - Intake task type and routing assumptions.
   - Delivery profile and whether this plan is a full plan, compressed
     standard-bugfix plan, micro-fix evidence, validation-only note, or
     blocked-investigation handoff.
   - Affected modules and ownership boundaries.
   - Public interface and contract impact.
   - Migration, bugfix, or new-feature planning focus.
   - UI design/source directory map for migration or new-feature when UI is
     involved.
   - Compatibility and migration risk.
   - Validation plan.
   - Project structure notes.
   - Knowledge Routing: when `select-knowledge` was used, record the returned
     guide paths and why they were enough; otherwise write `N/A - repository-map
     and active feature artifacts were sufficient`.
   - Complexity notes only when the solution deviates from existing patterns.
   - For UI state/UI interaction/operation availability work, include the
     UI/Biz/Libs layering boundary: `NativeBridge` forwarding-only APIs,
     `CoreServicesLib` runtime/business facts, frontend display composition,
     what the UI may hold, what UI must not infer/cache, refresh timing, and
     exact contract/interface locations.
   - For UI parity, frontend visual, or host-embedded UI work, include a
     runtime layout ownership map: static visual sources, dynamic UI states,
     exact geometry constraints, parent/sibling host containers, scroll owner,
     overflow/flex/grid grow-shrink behavior, clipping/compression boundaries,
     and host-level validation route. If this evidence is missing for a
     clipping, blank area, compression, scrollbar, or embedded-layout symptom,
     route to `blocked-investigation` before implementation.
     For host-embedded frontend plugins, explicitly record the plugin root's
     runtime top offset, viewport height, root/shell/panel/detail-panel bottom
     edges, scroll owner, and last visible row/control. Do not treat bare
     `100vh` or standalone plugin preview height as reliable evidence for an
     Electron-hosted plugin that starts below host chrome or headers.
   - For UI parity or 0px-level visual repair, include a UI element traversal
     inventory before implementation. The inventory must enumerate every
     affected visible element and state from outer container to inner control,
     choose baseline anchors, map each element to source reference and target
     selector/component, list expected x/y/width/height/padding/margin/font/
     icon/color/border/line-height values when available, record unknowns as
     blockers, and name one batch patch strategy that updates shared layout
     constants/tokens before local overrides. This is the mechanism for
     avoiding one-symptom-at-a-time CSS fixes.
   - For device identity, runtime state, RPC/N-API, JS/UI, or public API work,
     include Identity / State / API Boundary decisions: UUID decimal string as
     the only cross-boundary device identity, `device::identity::generateUUID()`
     as the only generation owner, SDK native ids/handles kept internal,
     frontend operations using `node.uuid`, event refresh semantics, legacy API
     removal/migration, debug/test API isolation, semantic naming, and generated
     artifact cleanup/ignore status.
   - For UI-interaction or operation-availability `migration`, carry forward the
     Qt source behavior coverage into `plan.md`. It must explicitly connect
     device type/status conditions to UI element order or action order,
     visible/enabled behavior, action handlers, and target layer/contract
     fields.
     Recommend a table for simple cases, but allow grouping, decision tables,
     state-machine notes, fixture matrices, or per-Qt-function rule lists.
   - For `CoreServicesLib`, frontend plugin, or `NativeBridge` bridge API work,
     include file ownership decisions. The agent must search existing structure
     first; if no suitable file exists, plan new focused header/source/module
     files instead of expanding one file with unrelated contract, DTO, adapter,
     cache, permission facts, UI display composition, and bridge logic.
   - For `bugfix`, include `## Root Cause Evidence` with:
     - Symptom.
     - Call Path.
     - Evidence.
     - Excluded Alternatives.
     - Counterexample.
     - Blast Radius.
     - Validation Mapping.
     - Confidence.
     If any field is missing, lower confidence or route to
     `blocked-investigation`; do not ask the user to validate the technical
     conclusion.

4. Update `review.md`.
   - Summarize selected approach, affected repositories, highest-risk
     boundaries, validation entry, and known gaps for human review.
   - Link or name `spec.md`, `plan.md`, `quickstart.md`, and any important
     design artifact.
   - State that AI implementation still requires the full plan, tasks, and
     design artifacts.

5. Produce or update `research.md`.
   Use it for unknowns, trade-offs, prior art in the repo, toolchain decisions,
   and alternatives rejected.
   Write this file in English-first style because it is mainly used by AI
   agents and implementers.
   For `migration`, include source Qt behavior discovery and parity decisions.
   For `bugfix`, include repro/root-cause discovery and regression strategy.
   Similarity to another module is prior art, not root-cause evidence by
   itself. If the proposed fix changes a fallback, status, permission, or
   device behavior for real devices, prove the blast radius is guarded or
   mark it blocking/high risk.
   For `new-feature`, include why the capability is not a direct migration and
   any new contract decisions.

6. Produce or update `data-model.md` when the capability has durable state,
   DTOs, serialized fields, SDK structs, UI state, or database-like records.
   Write this file in English-first style.
   If not applicable, write "N/A" with a short reason.

7. Produce or update `contracts/` when the capability changes:
   - Public headers or SDK APIs.
   - ProductNativePlugin/NativeBridge forwarding request/response shapes.
   - Frontend plugin props/events/state fields.
   - CLI/script input/output.
   - Device/runtime status or permissions.
   Write contract files in English-first style and keep all interface/field
   identifiers unchanged.

8. Produce or update `quickstart.md`.
   Describe how a reviewer or teammate can exercise the capability. Include
   build, smoke, runtime, UI, virtual-device, or real-device validation where
   applicable. A command is useful but not mandatory. Include how validated
   behavior should be preserved as a unit test, regression test, fixture,
   contract test, smoke case, or documented N/A.
   Write this file in Chinese-first style because it is reviewed by the team.

9. For UI-related `migration` or `new-feature`, ensure the plan names:
   - Source Qt UI directory or explicit N/A.
   - Product design/mockup/export directory or explicit N/A.
   - Target frontend/plugin directory.
   - Shared assets/icons/screenshots directory or explicit N/A.
   - Missing design inputs that block implementation.
   - UI element traversal inventory location, or explicit N/A when visual
     parity is not part of the request.

## Planning Rules

- Prefer existing architecture and helper APIs.
- Use bounded search. Do not search the whole `workspace_root` by default.
  Start from affected repositories from the repository map, then known module
  directories and named symbols/files. Prefer `rg` and `rg --files`, for
  example `rg --files <repo> | rg "HeaderName.h"` or
  `rg -n "symbol" <known-dir>`.
- Do not spawn a subagent/explorer for a simple local code lookup. Use
  subagents only for clearly independent, bounded work.
- If root cause is unknown, write a bounded investigation slice with search
  scope, command budget, stop conditions, and evidence to collect.
- Keep GitHub issue and remote push flows out of the plan.
- Preserve the local spec branch as the workflow boundary. If the plan affects
  additional repositories, record that they must use the same local spec branch
  from `.specify/workspace.yml`.
- Plan downstream acceptance, simplify, optional test-hardening,
  retrospective/留痕, optional promote-lessons, commit, and complete-branch as
  separate stages. Do not merge branch completion into implementation tasks.
- If real-device, connection, acquisition, permission, status, SDK/Biz, or
  host-embedded runtime verification is required, plan it as AI-owned
  validation first: launch or reuse the real host when available, select the
  CDP/browser target, perform the operation, inspect logs/process liveness, and
  assert refreshed runtime/UI state. Record a gap only after probing proves the
  device, host, permissions, or automation target is unavailable; do not turn
  the core changed behavior into a routine manual acceptance item.
- Plan the validation as an agent-owned adjust-and-rerun loop: after each code
  change, rebuild/deploy source output when needed, run the real host/CDP/device
  smoke, inspect evidence, and repeat until the behavior passes or a concrete
  blocker is proven. Human review is last and covers acceptance/owner decisions,
  not primary technical validation.
- Treat encoding and localization decisions as boundary decisions.
- For migration, do not plan implementation without a source Qt behavior
  reference or an explicit owner-approved N/A.
- For UI-interaction or operation-availability migration, do not plan
  implementation without Qt source behavior coverage that covers the device
  type/status dimensions affecting visible/enabled UI behavior.
- For UI-related migration, new-feature, or bugfix that changes visible UI,
  UX, icons, tooltips, labels, menu text, buttons, layout, spacing, or style,
  do not proceed with an empty design/source directory map or empty UI / UX /
  文案 evidence gate. Every visible change must cite a reliable source:
  original Qt UI/source/delegate/QSS/resource, product design/mockup/export,
  screenshot, existing target-app convention, or explicit owner/user decision.
  If the evidence is missing, stop for clarify or blocked investigation rather
  than planning an imagined UI.
- For UI parity or host-embedded frontend work, do not plan implementation from
  static design files alone. The plan must identify dynamic states, geometry
  constraints, runtime DOM / computed style / box metrics evidence needs, and
  host-level validation. If ownership of height, scroll, overflow, flex/grid
  shrink/grow, or clipping is unclear, plan a bounded UI runtime investigation
  first.
- Do not add new abstractions unless the spec forces them or they remove real
  complexity.
- Do not plan `NativeBridge` business logic. It is forwarding-only. Non-UI
  runtime facts, permissions, capabilities, and reusable business rules must be
  planned in `CoreServicesLib`. UI-display-specific structure, order,
  visible/enabled presentation, and action entry composition must be
  planned in the frontend plugin, based on `CoreServicesLib` facts obtained
  through the bridge.
- Do not plan parallel device identities across Libs facade, Biz, N-API/JSON/RPC,
  JS, or UI. Cross-boundary device identity is UUID decimal string only.
- Do not plan SDK native id, virtual id, or handle exposure above the bottom
  SDK/service layer.
- Do not plan equivalent old APIs, debug/test APIs in production Biz exports,
  or event-driven local state as a truth source.
- Do not plan interface/data-layer work by dumping unrelated responsibilities
  into one file. Prefer existing ownership locations; create focused files when
  the current structure has no suitable home.
- Do not use `Known Gaps` to pass the exact risk introduced by the fix. A gap
  on the changed core behavior is blocking or high risk, not PASS.
- Do not convert real-device permission/status failures into a friendlier fake
  state unless the change is explicitly scoped to virtual/simulated devices or
  otherwise guarded and proven.

## Human Review Rules

- `## 人类审核摘要` must be concise and useful: goal, real scope, validation
  entry, remaining risk, and next stage.
- Add `## 必需人工决策` when human input is truly required. Valid entries are
  product/business choices, owner-approved gaps, external validation that AI
  cannot perform, user acceptance, commit, or branch completion.
- Do not ask the developer to confirm root cause correctness, test sufficiency,
  code-level fallback quality, or whether an ordinary technical plan is
  acceptable. If those are uncertain, mark the plan blocked/high risk.

## Fact Layer Planning

- Use `speckit.fact-layer` and plan a `fact-pack.md` when the work may require
  runtime DOM, console, computed style, box metrics, latest SDK/Biz logs, or
  source/runtime/build/install consistency evidence.
- Treat a second same-class fix without new facts as a planning risk. Route to
  `speckit.fact-layer` before implementation when a first patch has already
  failed, UI runtime structure may differ from source assumptions, Chrome
  debugging/chrome-devtools evidence is needed, or the real host container chain
  is unknown.

## Output

Report in Chinese:

- Plan path.
- Review path.
- Local spec branch and any cross-repo branch gaps.
- Design artifacts created or updated.
- Main risks.
- Validation plan and known gaps.
- Required next stage:
  - `full-sdd`: `speckit.tasks` / `$speckit-tasks`; do not skip directly to
    `analyze`, `checklist`, or `implement`.
  - `standard-bugfix`: `speckit.analyze` / `$speckit-analyze` when `plan.md`
    contains complete `Implementation Slices`; otherwise `speckit.tasks`.
  - `micro-fix`: `speckit.implement` only when the lightweight evidence names
    changed files, validation, stop conditions, and root cause; otherwise return
    to `speckit.micro-fix` or this planning stage.
  - `blocked-investigation`: `speckit.fact-layer` or
    `speckit.bounded-investigation`; do not implement.
  - `validation-only`: `speckit.validation`.
- Human review prompt:
  - Only ask for required human decisions listed by the Human Review Rules.
  - If no required human decision exists and no blocked/high-risk owner gap
    remains, continue to the required next stage without adding a manual gate.
