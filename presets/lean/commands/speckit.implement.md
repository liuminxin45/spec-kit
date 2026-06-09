---
description: Execute focused CoreServicesLib tasks with scoped changes.
---

## User Input

```text
$ARGUMENTS
```

## Outline

1. Read `.specify/feature.json` to find the feature directory.
2. Load constitution, `spec.md`, `plan.md`, and `tasks.md`.
3. Execute tasks in order.
   - Preserve existing patterns.
   - Avoid unrelated refactors.
   - Preserve real runtime/device/status/permission behavior.
   - For UI interaction or operation availability migration, review the Qt source
     behavior coverage before editing; if device type/status/display/action
     coverage is missing, stop and return to spec/plan rather than guessing.
   - Keep `NativeBridge` forwarding-only. Non-UI runtime/permission/capability
     facts must come from `CoreServicesLib`; UI-display-specific element/action order/
     enabled/visible/action composition belongs in the frontend plugin.
   - Do not infer runtime/permission truth from labels/strings or fake device
     facts in frontend plugin code.
   - Enforce Identity / State / API Boundary: UUID decimal string is the only
     cross-boundary device identity; new UUIDs come only from
     `device::identity::generateUUID()`; SDK native IDs/handles stay internal;
     frontend business operations use `node.uuid`; `NativeBridge` does not
     cache runtime/device state; events only trigger refresh from
     `CoreServicesLib`; equivalent old APIs are removed or migrated, and
     debug/test APIs stay out of production Biz exports unless an owner-approved
     gap is recorded.
   - Search existing ownership locations before adding interface/data code; add
     focused files when no suitable module owns the responsibility.
   - Keep work on the local Spec branch.
   - Do not push, create remote tracking, or introduce GitHub issue dependency.
   - Mark completed tasks in `tasks.md`.
4. Run feasible validation or record the exact unverified gap.
5. When validation passes, add or update the corresponding unit test,
   regression test, fixture, contract test, smoke case, or explicit N/A reason.
6. Re-run affected tests or substitute validation after the test-case update and
   record the result.
7. Run completion preflight without side effects:
   - PowerShell: `.specify/scripts/powershell/complete-spec-branches.ps1 -Json -PreflightOnly`
   - Bash, only when sh scripts are installed: `.specify/scripts/bash/complete-spec-branches.sh --json --preflight-only`
8. Present a Chinese merge/delete confirmation request listing the Spec branch,
   target base branch, affected repositories, preflight result, whether local
   branches will be deleted, and that nothing will be pushed.
9. Stop until the user explicitly confirms.
10. After confirmation, complete the Spec by running the local branch completion
   script from the Spec Kit repository root:
   - PowerShell: `.specify/scripts/powershell/complete-spec-branches.ps1 -Json -ConfirmCompletion`
   - Bash, only when sh scripts are installed: `.specify/scripts/bash/complete-spec-branches.sh --json --confirm-completion`
11. Report merged repositories, base branch, deleted local branches, and
    confirm nothing was pushed.
