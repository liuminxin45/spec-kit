---
description: Create a compact CoreServicesLib implementation plan.
---

## User Input

```text
$ARGUMENTS
```

## Outline

1. Read `.specify/feature.json` to find the feature directory and task type.
2. Read `.specify/memory/constitution.md`, `<feature_directory>/intake.md`,
   and `<feature_directory>/spec.md`.
3. Create `<feature_directory>/plan.md` with:
   - Intake task type and planning focus
   - Technical context
   - Affected modules
   - Local Spec branch, affected repositories, and any cross-repo branch gaps
   - Qt source behavior coverage for UI interaction or operation availability
     migration, including device type/status, UI element order or action order,
     visible/enabled rules, action handlers, and target contract fields
   - UI/Biz/Libs layering and UI interaction display source when UI work
     is involved
   - Identity / State / API Boundary for device identity/runtime/API work:
     UUID decimal string only across boundaries, single
     `device::identity::generateUUID()` owner, SDK IDs/handles internal only,
     `node.uuid` frontend operations, event-triggered refresh, legacy API
     cleanup, debug/test API isolation, semantic naming, and generated artifact
     cleanup/ignore
   - Interface/data file ownership decisions, including new focused files when
     no suitable existing module owns the responsibility
   - UI design/source directory map for UI-related migration or new-feature
   - Compatibility and runtime boundaries
   - Validation plan
   - Known risks and gaps
4. For migration, include source Qt behavior and parity expectations.
   For UI interaction or operation availability migration, this must be explicit
   coverage, not a vague reference, when device type/status affects UI
   behavior. A fixed table is not required when grouping, decision tables,
   state-machine notes, fixture matrices, or per-Qt-function lists are clearer.
5. For bugfix, include repro and regression strategy.
6. For new-feature, include new acceptance and compatibility coverage.
7. Do not plan `NativeBridge` business logic. `NativeBridge` is forwarding
   only. Non-UI permissions, capabilities, and device/runtime facts belong in
   `CoreServicesLib`; UI-display-specific structure, order, and
   visible/enabled presentation belongs in the frontend plugin.
8. Do not plan interface/data-layer changes by dumping unrelated
   responsibilities into one file; find the proper existing location or add
   focused files.
9. Do not plan parallel device identities, Biz-owned runtime caches, SDK
   ID/handle leakage, frontend identity fallbacks, equivalent legacy production
   APIs, debug/test APIs in production Biz exports, or build artifact based ownership
   decisions unless the gap is explicitly owner-approved.
10. Keep branch handling local-only: no remote push, no remote tracking, and no
   GitHub issue dependency.
11. Use Chinese-first style for human-reviewed `plan.md`, `quickstart.md`, and
   user-facing summaries. Use English-first style for AI-oriented
   `research.md`, `data-model.md`, and `contracts/`. Preserve technical
   identifiers such as file paths, APIs, fields, enum/status values, commands,
   and test names.
12. Output a Chinese stage overview and ask the developer to review whether the
   plan artifacts need adjustment. If no adjustment is needed, state that the
   only next stage is task generation.
