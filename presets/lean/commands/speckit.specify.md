---
description: Create a compact capability spec for a small CoreServicesLib change.
---

## User Input

```text
$ARGUMENTS
```

## Outline

1. Ask for or choose a short feature name, then create or switch to the local
   Spec branch before writing the spec:
   - PowerShell: `.specify/scripts/powershell/create-spec-branch.ps1 -FeatureName "<short-name>" -Json`
   - Bash: `.specify/scripts/bash/create-spec-branch.sh --feature-name "<short-name>" --json`
2. Keep the Spec branch local-only. Do not push it, create remote tracking, or
   depend on GitHub issue generation.
3. When `.specify/workspace.yml` lists additional repositories, ensure every
   existing affected repository uses the same local Spec branch.
4. Read existing `intake.md` and `.specify/feature.json` task type when
   present. If intake is missing, state that routing should be completed first.
5. Write `.specify/feature.json` with the chosen feature directory, local Spec
   branch, and preserved task type fields when they already exist.
6. Create `<feature_directory>/spec.md` with:
   - Intake summary and task type
   - Capability overview
   - Capability scenarios
   - Functional requirements
   - Compatibility/integration boundaries
   - Qt source behavior coverage when UI interaction or operation availability
     migration depends on device type or device state
   - UI/Biz/Libs layering and UI interaction display boundaries when UI state,
     UI interaction, operation availability, or device runtime UI is involved
   - Identity / State / API Boundary when device identity, runtime state,
     RPC/N-API, JS/UI, or public API boundaries are involved
   - UI design/source directories for UI-related migration or new-feature
   - Validation expectations
   - Out of scope and assumptions
7. Mark unresolved decisions as `NEEDS CLARIFICATION`.
8. Write `spec.md` in Chinese-first style because it is human-reviewed.
   Preserve file paths, module names, class names, function names, APIs,
   fields, enum/status values, commands, and test names in their original
   language.
   For UI interaction work, explicitly require `NativeBridge` to stay forwarding-only,
   `CoreServicesLib` to provide non-UI runtime/permission/capability facts, and
   frontend plugin to own UI-display-specific element/action order/visible/enabled/
   action composition based on those facts.
   For UI-interaction migration, do not accept a vague "refer to Qt" note; cover
   the Qt source path/function, object/device type, state/condition, UI element order
   or action order, visible/enabled rule, action handler, migration requirement,
   and target contract source. A table is recommended for simple cases, but
   grouped lists, decision tables, state-machine notes, fixture matrices, or
   per-Qt-function rule lists are acceptable when clearer.
   For identity/runtime/API work, require UUID decimal string as the only
   cross-boundary device identity, `device::identity::generateUUID()` as the
   only UUID generation owner, SDK native IDs/handles as bottom-layer internals,
   frontend operations to use `node.uuid`, events to trigger refresh from
   `CoreServicesLib`, and equivalent old APIs plus debug/test APIs in production
   exports to be removed, migrated, or recorded as owner-approved gaps.
9. Output a Chinese stage overview and ask the developer to review whether
   `spec.md` needs adjustment. If no adjustment is needed, state that the only
   next stage is clarification before planning.
