---
description: Classify a request as migration, bugfix, or new-feature before specification.
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

Create an intake record before writing `spec.md`. The intake decides whether
the work is primarily:

- `migration`: moving existing behavior from one implementation, platform,
  integration, or UI surface to another while preserving expected behavior.
- `bugfix`: correcting existing migrated behavior, runtime state, crash,
  contract mismatch, UI inconsistency, or tooling behavior.
- `new-feature`: adding a capability that is not primarily behavior migration.

If the request cannot be classified confidently, set `task_type` to
`needs-routing` and ask for clarification before continuing.

Also assign delivery risk and workflow weight when enough evidence exists:

- `low`: tooling/docs/test-only or small local change.
- `medium`: single-repository change with local validation coverage.
- `high`: public API, identity, service/runtime/UI boundary, cross-repo,
  external-system, or migration parity risk.
- `blocked`: missing source behavior, missing design input, missing validation
  condition, or contradictory requirement.

Also assign `delivery_profile`:

- `micro-fix`: single-repository, normally 1-2 changed files, internal
  implementation change, root cause already evidenced, local validation
  available, and no public API, identity, permission/status semantics,
  external-system behavior, cross-layer, or cross-repo risk.
- `standard-bugfix-lite`: single-repository low/medium-risk bugfix, normally
  1-3 changed files, root cause sufficiently evidenced, one implementation
  slice, local validation available, and no public API, identity,
  permission/status, cross-repo, external-system, or selected gate-pack
  requirement.
- `standard-bugfix`: compact bugfix that still touches runtime state,
  permissions, external-system behavior, compatibility, regression risk, or other
  semantic surfaces where a small patch can still be wrong.
- `full-sdd`: migration, new feature, public API, cross-repo work,
  UI/service/runtime boundary, identity semantics, external-system semantics, or
  broad behavioral change.
- `blocked-investigation`: root cause, source behavior, design input,
  validation condition, or requirements are missing/contradictory. Do bounded
  investigation before planning implementation.
- `validation-only`: reproduce, smoke, audit, or regression validation without
  product-code changes.

## Language Rules

- `intake.md` is a human-reviewed artifact. Write it in Chinese-first style.
- `intake.md` must include a top `## 人类审核摘要` section for fast human
  review. This section is additive only: it must summarize routing conclusion,
  key review points, affected scope, N/A boundaries, and conditions for the
  next stage, and 不得替代或删减 later AI/流程读取区 such as full routing evidence,
  migration/bugfix/new-feature details, UI source maps, and clarification
  questions.
- Preserve technical identifiers in their original form: file paths, module
  names, class names, function names, APIs, fields, enum/status values,
  commands, and test names.
- Keep fixed workflow values such as `migration`, `bugfix`, `new-feature`,
  `needs-routing`, `high`, `medium`, `low`, `N/A`, and
  `NEEDS CLARIFICATION` unchanged.
- Keep delivery profile values unchanged: `micro-fix`, `standard-bugfix-lite`,
  `standard-bugfix`, `full-sdd`, `blocked-investigation`, and
  `validation-only`.

## Execution Steps

1. Resolve the feature directory.
   - Preferred format: `specs/<short-capability-name>`.
   - Use an explicit feature directory if the user provides one.
   - Create the directory if needed.

2. Classify the request.
   - Choose exactly one: `migration`, `bugfix`, `new-feature`, or
     `needs-routing`.
   - Record `routing_confidence` as `high`, `medium`, or `low`.
   - Record `risk_level` as `low`, `medium`, `high`, or `blocked` when the
     request provides enough evidence; otherwise explain what is missing.
   - Record `delivery_profile` and the impact dimensions that justified it:
     repository count, estimated changed files, boundary type, semantic risk,
     validation availability, root-cause confidence, and reversibility.
   - Do not guess silently when the source behavior, defect, or new capability
     boundary is unclear.

3. Create or update `intake.md` using `.specify/templates/intake-template.md`.
   Fill `## 人类审核摘要` after the routing sections are complete, using it as
   a short human entrypoint only. Keep the detailed evidence sections intact.

4. Write or update `.specify/feature.json`:

   ```json
   {
     "feature_directory": "specs/<short-capability-name>",
     "task_type": "migration",
     "routing_confidence": "high",
     "risk_level": "medium",
     "delivery_profile": "standard-bugfix-lite",
     "impact_surface": {
       "repositories": [],
       "estimated_changed_files": "unknown",
       "boundary_type": "internal",
       "semantic_risk": "medium",
       "validation_strength": "unknown",
       "root_cause_confidence": "unknown",
       "reversibility": "medium"
     },
     "human_gates": [
       "user-acceptance",
       "commit",
       "complete-branch"
     ],
      "source_behavior_paths": [],
     "target_modules": [],
     "ui_design_dirs": {
        "source_ui": [],
       "design_exports": [],
        "target_ui": [],
       "assets": [],
       "screenshots": []
     }
   }
   ```

5. Apply type-specific intake rules.

   For `migration`:
   - Identify source behavior, source paths, classes, functions, design/source
     assets, screenshots, or behavioral references.
   - Identify target modules and expected compatibility boundaries.
   - If the migration involves identity, runtime state, RPC/API,
     JS/UI, or public API boundaries, record whether the request can satisfy
     Identity / State / API Boundary before planning: each business entity has
     one canonical identity owner and format, native/external handles remain
     local implementation details, adapter layers do not cache or calculate
     runtime truth, frontend operations use domain identities, and events only
     trigger refresh from the owning domain/runtime layer.
   - If the migration involves UI state, UI interactions, operation availability,
     or runtime display, record the layer split before planning: adapter layers
     are forwarding/integration boundaries only; runtime/status/permission/
     capability facts belong in the owning domain/runtime layer; UI-display-specific
     composition belongs in the frontend/presentation layer.
   - If the migration involves UI interactions or operation availability, build
     a source behavior coverage list before planning. It must include:
     source path/function, object/entity type, state/condition,
     UI element order or action order, visible/enabled rules, action handler,
     keep/change/gap notes, and target layer/contract source. Prefer a table for
     simple cases, but allow grouping by entity type, decision tables, state
     machine notes, fixture matrices, or per-source-function rule lists. Do not
     replace it with a vague "refer to the old implementation" note.
   - If UI is involved, organize UI design/source directories:
     - Original UI/source directory.
     - Design export or mockup directory.
     - Target UI/frontend directory.
     - Shared assets/icons/screenshots directory.
     - Gaps that must be supplied before planning.

   For `bugfix`:
   - Capture actual behavior, expected behavior, repro path, affected layer,
     suspected boundary, and regression-test expectation.
   - If the bug touches runtime status, permission, identity, cache,
     external-system behavior, UI operation availability, or public contracts,
     it cannot be `micro-fix` unless the fix is strictly virtual/simulated or
     otherwise guarded and proven.
   - Record whether root cause is known or only suspected. Known root cause
     requires named evidence, not only similarity to another module.

   For `new-feature`:
   - Explain why the work is not a direct migration.
   - Identify new capability intent, affected contracts, acceptance signal, and
     compatibility risk.
   - If the new feature involves identity, runtime state, RPC/API,
     JS/UI, or public API boundaries, record the Identity / State / API
     Boundary: one canonical cross-boundary identity, native/external handles
     internal only, adapter layers forwarding-only with no runtime cache,
     frontend operations using domain identities, event-triggered refresh from
     the owning domain/runtime layer, legacy API cleanup, and debug/test API isolation.
   - If the new feature involves UI state, UI interactions, operation
      availability, or runtime display, record the required layer split:
      forwarding/adapter API, owning domain/runtime facts, and frontend-only
      display composition.
   - If UI is involved, organize UI design/source directories:
     - Product design/mockup/export directory.
      - Target UI/frontend directory.
     - Shared assets/icons/screenshots directory.
     - Missing design artifacts or approval gaps.

6. Stop before `specify` when:
   - `task_type` is `needs-routing`.
   - A migration lacks any source behavior reference.
   - Identity/runtime/API work lacks an Identity / State / API Boundary
     record or proposes parallel cross-boundary identities, service-owned runtime
     caches, native/external handle leakage, frontend identity fallbacks, or production
     debug/test exports without an owner-approved gap.
   - A UI-interaction or operation-availability migration lacks a source
     behavior coverage list covering the entity/status dimensions that
     affect visible/enabled UI behavior.
   - A UI migration/new-feature depends on design files but no design/source
     directory or explicit N/A reason is recorded.
   - `delivery_profile` is `blocked-investigation`; create the investigation
     notes and do not proceed to full planning.
   - A requested `micro-fix` fails any micro-fix condition. Upgrade it to
     `standard-bugfix-lite`, `standard-bugfix`, `full-sdd`, or
     `blocked-investigation` and explain why.

## Human Gate Policy

- Human review summaries are navigation aids, not technical approval gates.
- Ask humans only for product/business decisions, owner-approved gaps, required
  manual acceptance, commit, or branch-state mutation.
- Do not ask humans to confirm root cause correctness, test sufficiency,
  whether a fallback is code-quality acceptable, or whether a low-level patch is
  right. If AI cannot decide those, mark the request blocked or high risk.

## Output

Report in Chinese:

- Feature directory.
- Intake path.
- Task type and confidence.
- Risk level and whether it blocks the next stage.
- Source behavior paths, bug repro, or new-feature rationale.
- Source behavior coverage status for UI-interaction or operation-availability
  migration, or explicit N/A.
- UI design/source directories for migration or new-feature, or explicit N/A.
- Identity / State / API Boundary status for identity/runtime/API work,
  or explicit N/A.
- Clarifications required before specification.
- Required next stage: `speckit.specify` / `$speckit-specify`. If intake
  blocks the request, ask the user to resolve intake first instead of offering
  later workflow stages.
- Human review prompt:
  - Surface only required human decisions: product/business choices,
    owner-approved gaps, missing external inputs, user acceptance, commit, or
    branch completion.
  - If no required human decision exists, continue without a manual gate.
