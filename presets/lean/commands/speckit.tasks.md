---
description: Create focused implementation tasks for a small CoreServicesLib change.
---

## User Input

```text
$ARGUMENTS
```

## Outline

1. Read `.specify/feature.json` to find the feature directory and task type.
2. Read constitution, `intake.md` when present, `spec.md`, and `plan.md`.
3. Create `<feature_directory>/tasks.md` with:
   - Context and boundary tasks
   - One section per capability scenario
   - File/module-specific implementation tasks
   - Migration parity, bugfix repro/regression, or new-feature acceptance tasks
   - UI design/source directory inspection tasks for UI-related migration or
     new-feature
   - A blocking Qt source behavior coverage review task for UI interaction or
     operation availability migration; missing device type/status coverage
     sends the workflow back to spec/plan instead of implementation
   - `NativeBridge` forwarding-only API tasks, `CoreServicesLib`
     runtime/permission/capability facts tasks, and frontend plugin display
     composition tasks when UI state/operation permission is involved
   - Identity / State / API Boundary tasks when device identity/runtime/API work
     is involved: UUID decimal string only across boundaries, single
     `device::identity::generateUUID()` owner, SDK IDs/handles internal only,
     frontend operations using `node.uuid`, Biz no runtime cache/state
     calculation, event refresh only, legacy API cleanup, debug/test API
     isolation, semantic naming, and generated artifact cleanup/ignore
   - File ownership tasks that search existing structure and add focused files
     when no suitable interface/data location exists
   - Validation tasks or validation notes
   - Test-case update tasks after successful validation
   - Re-run tasks after test-case updates
   - Local branch completion tasks: make affected repositories merge-ready,
     run completion preflight-only, request explicit user confirmation, merge
     the same Spec branch back to the configured base branch, and delete the
     local branch only after confirmation
4. For multi-repo work, include same-name local Spec branch checks for every
   affected repository listed in `.specify/workspace.yml`.
5. For UI interaction work, do not create UI tasks that hardcode business UI rules,
   infer operation availability from labels/strings, or persist business state
   as source of truth.
   For UI-interaction migration, every Qt behavior coverage item must map to an
   implementation task, validation/test task, or owner-approved gap. A fixed
   table is not required when another structured form is clearer.
6. Do not create tasks that add parallel cross-boundary identities, leak SDK
   native IDs/handles, use frontend `node.id`/`entityId`/`metadata.uuid`
   fallbacks for business operations, make events a truth source, or put
   debug/test APIs in production Biz exports.
7. Do not create tasks that grow one interface/data file with unrelated
   contract, DTO, cache adapter, permission/availability model, and UI adapter
   responsibilities.
8. Do not create tasks for remote push, remote tracking, or GitHub issue
   generation.
9. Use `[P]` only for tasks that can safely run in parallel.
10. If automated unit/regression coverage is not feasible, add an explicit N/A
   task with the substitute evidence to collect.
11. Write `tasks.md` in Chinese-first style because it is human-reviewed and
   team-executed. Preserve task IDs, `[P]`, `[CSx]`, file paths, APIs, fields,
   enum/status values, commands, and test names in their original language.
12. Output a Chinese stage overview and ask the developer to review whether
   task grouping, validation/test closure, or branch completion tasks need
   adjustment. If no adjustment is needed, state that the only next stage is
   analysis.
