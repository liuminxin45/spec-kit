---
description: Execute approved implementation slices while preserving scope and evidence.
scripts:
  sh: scripts/bash/check-prerequisites.sh --json --include-tasks
  ps: scripts/powershell/check-prerequisites.ps1 -Json -IncludeTasks
  preflight_sh: scripts/bash/validate-feature-artifacts.sh --json --stage implement --feature-dir <feature-dir>
  preflight_ps: scripts/powershell/validate-feature-artifacts.ps1 -Json -Stage implement -FeatureDir <feature-dir>
  select_knowledge_sh: scripts/bash/select-knowledge.sh --json --stage implement --feature-dir <feature-dir>
  select_knowledge_ps: scripts/powershell/select-knowledge.ps1 -Json -Stage implement -FeatureDir <feature-dir>
  sync_ui_runtime_sh: scripts/bash/sync-ui-runtime-artifacts.sh --json --source-dir <source-dist> --runtime-dir <host-runtime-dir> --plugin-id <plugin-id> [--refresh-command <command>]
  sync_ui_runtime_ps: scripts/powershell/sync-ui-runtime-artifacts.ps1 -Json -SourceDir <source-dist> -RuntimeDir <host-runtime-dir> -PluginId <plugin-id> [-RefreshCommand <command>]
  ensure_cdp_host_sh: scripts/bash/ensure-desktop-shell-cdp-host.sh --json --target-kind host-app
  ensure_cdp_host_ps: scripts/powershell/ensure-desktop-shell-cdp-host.ps1 -Json -TargetKind host-app
  inspect_cdp_target_sh: scripts/bash/inspect-desktop-shell-cdp-target.sh --json --target-kind host-app
  inspect_cdp_target_ps: scripts/powershell/inspect-desktop-shell-cdp-target.ps1 -Json -TargetKind host-app
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

Implement the active capability by following `tasks.md` for `full-sdd`, or the
complete `Implementation Slices` embedded in `plan.md` for `standard-bugfix`.
Keep changes scoped, work with existing code patterns, and record progress in
the task list or `progress.md`.
Execute work as a slice loop: implement one `Implementation Slices` entry,
validate it, record evidence in `progress.md`, then continue only when the
slice stop conditions are not met.

This stage completes code implementation, required validation, and required
test-case closure. It does not perform user acceptance, simplification,
optional test-hardening, commit, branch cherry-pick completion, branch deletion, push, or remote
tracking setup.

For `micro-fix`, implementation may use the lightweight micro-fix evidence
artifact instead of a full `tasks.md`, but it still must preserve the same
evidence discipline: root cause, blast radius, validation, and acceptance-lite.

## Language Rules

- Keep code, identifiers, APIs, fields, enum/status values, commands, and test
  names in their original language.
- Human-facing updates, task completion notes in `tasks.md`, validation
  summaries, branch completion proposals, and final handoff text should be
  Chinese-first.
- Do not translate AI-oriented reference artifacts (`research.md`,
  `data-model.md`, `contracts/`) unless the user explicitly asks.

## Execution Steps

1. Run the prerequisite script and parse `FEATURE_DIR` and `AVAILABLE_DOCS`.
2. Load required context:
   - `FEATURE_DIR/spec.md`
   - `FEATURE_DIR/plan.md`
   - `FEATURE_DIR/tasks.md` when present; for `standard-bugfix`, `plan.md`
     slices may replace a separate tasks file.
   - `FEATURE_DIR/progress.md` when present; create it before the first slice
     update when missing.
   - `.specify/memory/constitution.md` if present
   - `.specify/feature.json` delivery_profile/risk when present
3. Load optional context when present:
   - `research.md`
   - `data-model.md`
   - `contracts/`
   - `quickstart.md`
   - `checklists/`
   - `review.md`
   - `lessons.md`

4. Check checklist status.
   - If checklists exist and contain incomplete blocking items, ask before
     continuing.
   - Non-blocking checklist gaps may be carried as known risk.

5. Run the implementation preflight.
   - Run `validate-feature-artifacts` with `--stage implement` /
     `-Stage implement`. Let the tool infer `delivery_profile`, `risk_level`,
     and `risk_flags` from `.specify/feature.json` when the command argument is
     empty or `auto`.
   - If the preflight reports missing `analysis.md`,
     `checklists/implementation-readiness.md`, `tasks.md`, or required
     sections, stop and return to the named prior stage instead of accepting a
     user's generic "next stage" instruction.
   - `full-sdd` and high-risk UI/runtime/cross-repo work must have analyze and
     checklist evidence before implementation.

6. Select knowledge only when the active slice needs it.
   - If repository-map and the active artifacts do not provide enough
     repository, domain, build, runtime, or validation context, run
     `select-knowledge` for stage `implement`.
   - Read only the returned `ai/knowledge/*` guide paths, normally one to three
     small guides. Do not load all guides and do not use full-text/BM25 search.
   - If no guide is selected, continue with default context instead of scanning
     the knowledge tree.

7. Check `## Implementation Slices` before editing.
   - Read slices from `tasks.md` when present.
   - For `standard-bugfix`, read slices from `plan.md` when `tasks.md` is not
     present.
   - Each slice must include target, 允许写入范围, 禁止范围, validation command
     or manual check, progress.md update expectation, and 停止条件.
   - If slices are missing or too broad to validate safely, stop and return to
     `speckit.plan` for `standard-bugfix` or `speckit.tasks` for `full-sdd`.
   - If the active slice conflicts with a checklist blocker, stop and report the
     blocker.
   - For `micro-fix`, an equivalent lightweight slice in `micro-fix.md` or
     `progress.md` is acceptable only when it names changed files, validation,
     stop conditions, and evidence.

8. Execute the slice loop.
   - Pick the first incomplete slice whose dependencies are satisfied.
   - Read nearby code before editing.
   - Modify only the slice's 允许写入范围.
   - Do not touch 禁止范围.
   - Run the slice validation command or perform the documented manual check.
   - Update `progress.md` with current slice, changed files, validation result,
     remaining risk, and next slice.
   - For UI parity/layout slices, if the first implementation attempt fails or
     the symptom persists, stop guessing CSS. Before the next patch, collect or
     request runtime DOM / computed style / box metrics for the affected
     element chain, including parent host containers, scroll owner, overflow,
     flex/grid grow-shrink, clipping/compression, and actual rendered size.
     Record that evidence in `progress.md` or route to
     `blocked-investigation` if it cannot be obtained.
     For host-embedded frontend plugins, always include box metrics for the
     plugin root, immediate shell/container, main panel, detail/footer panel,
     scroll owner, and last visible row/control when touching height, flex,
     overflow, bottom spacing, or detail panels. A root or shell using bare
     `100vh` is a known risk when the plugin starts below DesktopShell
     chrome; use measured host offset or a host-owned flex height instead.
   - For UI parity, 0px-level visual repair, or screenshot alignment slices,
     first follow the `UI Element Traversal Inventory / 0px Alignment Matrix`
     from `plan.md`. If it is missing or does not cover all visible affected
     elements and dynamic states, stop and return to `speckit.plan` or
     `blocked-investigation`. Apply fixes in the inventory order: outer
     container, baseline anchors, header/toolbar, scroll owner, repeated rows,
     nested icons/text, footer/detail panel, then state variants. Prefer one
     batch patch that updates shared row height, indentation, icon size,
     padding, typography, and layout tokens before local overrides, so related
     UI elements converge together instead of one symptom at a time.
   - For host-embedded frontend plugin source edits, use the fixed AI delivery
     chain: source edit -> frontend build -> direct runtime replacement -> real
     host CDP verification. In concrete terms, edit repository source, run the
     plugin frontend build, replace the explicit host runtime plugin directory
     from the built source output, then validate the real DesktopShell
     business target through CDP. This direct replacement targets the
     host-served runtime plugin directory only after source output exists. This is a
     required implementation loop for AI-owned frontend changes, not a late
     acceptance preference. Use `sync-ui-runtime-artifacts` for the direct
     runtime replacement when the source-to-runtime mapping is explicit; it
     mirrors the source output into `<host-app-root>/frontend/<location>/<plugin-id>/`
     and removes stale runtime files by default. Record source dir, runtime dir,
     plugin id, removed stale count, build command/result, refresh action,
     loaded resource evidence, and validation evidence in `progress.md`. If the
     source/runtime mapping or build command is unknown, investigate boundedly
     using repository-map and `ai/knowledge/build-and-package-notes.md` rather
     than asking for manual acceptance on stale runtime output.
   - For native plugin source edits, do not use frontend runtime hot replacement.
     Build the corresponding `.plugin` artifact, record the command and artifact
     path, and record the install/restart validation route or the reason native
     hot update is unavailable.
   - For UI/UX-affecting slices, perform best-effort AI self-validation after
     implementation when the local host, MCP/CDP/browser automation, or
     equivalent UI test tool is available. For host-embedded frontend plugins,
     prefer the real DesktopShell Electron host: first run
     `ensure-desktop-shell-cdp-host` or perform the equivalent probe. Reuse
     an already-running valid DesktopShell target instead of treating it
     as a blocker. If CDP is unreachable and no process owns the port, start
     `<host-app-root>` `npm run debug` and rerun the probe. If another process
     owns the port, identify the owner and try a safe recovery path; destructive
     process termination requires explicit human approval. Only after this
     CDP host recovery ladder proves host/CDP unavailable may the stage stop with
     `blockers` and `next_required_human_action`. Then confirm CDP at
     `http://127.0.0.1:9222`, run `inspect-desktop-shell-cdp-target` or
     inspect `/json/list`, and record all page target `id/title/url/webSocketDebuggerUrl`
     plus the selected target id and URL before DOM/screenshot collection.
     Select a host app target matching `product-homepage`,
     `product-main-window`, or `frontend/static/index.html`, then take
     screenshots and keep simulating core clicks, hover, expand/collapse,
     scroll, or keyboard flows that the change affects. Reject `Plugin
     Workbench`, `base-win.html`, `devtools://`, blank, and unrelated targets as
     product UI evidence. If the changed surface is `plugin-host` DevTools / Plugin
     Workbench itself, select the workbench target matching
     `Plugin Workbench|plugin-workbench.html` instead; `npm run debug` opens it
     directly and it is the primary target for workbench DOM/CSS/click smoke.
     Use CDP `CSS.forcePseudoState(['hover'])` for CSS-only hover
     states when synthetic mouse movement does not apply `:hover`. Record the
     selected target URL, screenshot paths, DOM/computed-style facts, and
     interaction method. Isolated plugin preview is fallback evidence, not the
     primary acceptance target. This is an AI-owned validation gate when the
     changed behavior depends on the real host container, event routing, or
     runtime state. If the environment cannot support automated UI/UX
     validation, record the unsupported reason and treat the gap as blocking
     unless the changed behavior is already fully covered by lower-level tests.
     Best-effort UI self-validation is advisory rather than a hard gate only
     for changes whose behavior is fully covered by lower-level automated tests
     and does not depend on host rendering, event routing, runtime state, or
     visual layout.
     For clipping fixes, the CDP evidence should explicitly state whether the
     root/shell/detail-panel bottom edge and the last visible row/control are
     within `window.innerHeight`; if no selectable data is available, still
     record root/shell layout evidence and mark data-dependent panel checks as
     a runtime-data gap.
   - For real-device, connection, acquisition, permission, status, SDK/Biz, or
     host-embedded runtime fixes, do not delegate the primary smoke to human
     acceptance when local tools can run it. Run or reuse DesktopShell from
     `<host-app-root>` with `npm run debug` after first probing/reusing any
     existing CDP host with `ensure-desktop-shell-cdp-host`, confirm CDP at
     `http://127.0.0.1:9222`, select a DesktopShell target, perform the
     operation through CDP/browser automation or an equivalent host/API path,
     then verify process liveness, latest SDK/Biz logs, console errors, and the
     refreshed runtime/UI state. A real-device smoke may be skipped only when
     the required device, host launch, permissions, or automation target is
     unavailable after evidence-backed probing; record that as a blocker or
     explicit validation gap, not as a passed acceptance item.
     If the AI-owned smoke fails or the symptom persists, keep the loop inside
     the agent: collect fresh runtime evidence, adjust source, rebuild/deploy the
     source output as needed, and rerun the real host/CDP/device smoke until the
     required behavior passes or the work is explicitly blocked by an unavailable
     device, host, permission, automation target, or missing owner decision.
     Human review comes after AI validation evidence is complete; it is for user
     acceptance and owner decisions, not for primary technical debugging.
   - Continue to the next slice only when validation passes and no 停止条件 is
     met.
   - Stop and report if validation fails, scope expands, required source
     behavior is missing, a user decision is needed, or the next change would
     cross the forbidden scope.
   - Stop and return to investigation if Root Cause Evidence fails, a
     counterexample is observed, or blast radius expands into real device,
     status, permission, API, identity, cross-layer, or cross-repo behavior.

8. Execute tasks in order within each active slice when `tasks.md` exists.
   - Complete one task before marking it done.
   - Mark completed items in `tasks.md` by changing `- [ ]` to `- [x]`.
   - Respect `[P]` only when changes do not overlap.
   - Stop and report if a task is impossible or contradicts the spec/plan.
   - When `standard-bugfix` uses plan-embedded slices without `tasks.md`, record
     completion, changed files, and validation in `progress.md` instead.

9. Implementation discipline.
   - Preserve user or teammate changes.
   - Avoid unrelated refactors.
   - Do not invent fake SDK, device, permission, or status data.
   - For bugfixes, confirm `Root Cause Evidence` before editing product code.
     Do not implement a plan that only says a different module has a similar
     pattern. A similar module is prior art, not proof.
   - Do not make global fallback/status/permission changes when the bug is
     virtual/simulated unless the code is guarded to virtual/simulated scope or
     the real-device behavior is explicitly proven safe.
   - Use bounded search only:
     - Start with affected repositories from `.specify/memory/repository-map.md`
       and `.specify/feature.json`.
     - Search known dirs and named symbols/files with `rg` or `rg --files`.
     - Do not run broad `find`/recursive searches over `<workspace-root>`
       (the repository-map `workspace_root`) unless the user explicitly asks or
       no bounded alternative exists and the risk is recorded.
     - Do not start an explorer/subagent for a simple local lookup.
   - For UI-interaction or operation-availability migration, check the Qt source
     behavior coverage before editing. First read `.specify/memory/qt-source-behavior-map.md`
     or `ai/knowledge/qt-source-behavior-map.md` when present so Qt source
     locations are not rediscovered by broad workspace search. If device
     type/status/UI element order/visible/enabled/action coverage is missing or
     contradictory, stop and report that the workflow must return to
     `specify`/`plan` rather than guessing. Do not require a single fixed table;
     grouped rules, decision tables, state-machine notes, fixture matrices, or
     per-Qt-function lists are acceptable when complete.
   - For any UI/UX/visible-copy change, check the spec/plan evidence gate before
     editing. Every new or modified icon, tooltip, label, menu item, button,
     layout/style rule, and visible interaction state must cite a reliable
     source: Qt UI/source/delegate/QSS/resource, product design/mockup/export,
     screenshot, existing target-app convention, or explicit owner/user
     decision. If the exact text/icon/style/behavior is not evidenced, stop and
     return to `speckit.clarify`, `speckit.plan`, or bounded investigation.
     Do not substitute a text button for an icon+tooltip, invent tooltip copy,
     or alter style/wording from taste.
   - For UI parity or host-embedded frontend layout work, validate against the
     real host page when the component is embedded. Single-plugin preview is not
     sufficient for height, scroll, clipping, blank-area, toolbar/sidebar, or
     parent-flex behavior. Include dynamic states such as hover, selected,
     disabled, expanded/collapsed, many-item, and scrollbar appear/disappear
     states so scrollbars do not resize unrelated UI.
   - For UI state/UI interaction/operation availability, keep `NativeBridge`
     forwarding-only. Implement non-UI runtime facts, permission/capability
     data, and reusable business rules in `CoreServicesLib`. Implement
     UI-display-specific structure, order, visible/enabled presentation,
     and action entry composition in the frontend plugin based on facts
     obtained through the bridge.
   - Do not infer runtime/permission truth from labels or strings. Do not fake
     action permissions or device/runtime status in frontend plugin code.
   - Enforce Identity / State / API Boundary for device identity, runtime
     state, RPC/N-API, JS/UI, and public API work:
     - Across `CoreServicesLib` facade, `NativeBridge`, N-API/JSON/RPC, JS, and
       UI, the only device identity is UUID decimal string.
     - C++ internals may use `uint64_t uuid`, but `deviceIndex`, `deviceId`,
       `handleId`, `virtualDeviceId`, SDK native IDs, and SDK handles must not
       cross facade/Biz/UI boundaries.
     - New UUIDs are generated only through `device::identity::generateUUID()`;
       `DeviceManager`, `SdkService`, UI code, and bridge code only consume the
       identity.
     - Frontend business operations read `node.uuid` only. Do not add
       `node.id`, `entityId`, `metadata.uuid`, or similar fallbacks.
     - `NativeBridge` must not cache device lists, connection/acquisition
       state, runtime state, or operation availability; events only trigger
       refresh, and refreshed facts come from `CoreServicesLib`.
     - Do not keep functionally equivalent old production APIs beside the new
       API unless there is an explicit owner-approved migration gap.
     - Keep debug/test facades, temporary SDK passthroughs, and validation-only
       helpers out of production Biz exports.
     - Use semantic names such as `uuid`, `deviceUuids`, `nodeId`, and
       `listIndex`; avoid ambiguous `deviceId`.
     - Do not let `build/`, `export/`, `plugin-out/`, or other generated
       artifacts influence interface ownership, package-source selection, or
       diff judgment.
     - Frontend/native plugin changes must be made in repository source files,
       not installed runtime plugin directories or built artifacts. Treat
       `dist/`, `build/`, `export/`, `plugin-out/`, `app-data/plugins/**`, and
       host-served `frontend/plugins/**` outputs as validation/deployment
       artifacts only unless the repository explicitly treats them as source.
       A source-to-runtime copy performed by `sync-ui-runtime-artifacts` is
       allowed for validation and fast UI refresh only after the repository
       source change and build output exist; it does not make runtime artifacts
       a durable fix location or commit target.
       If a runtime artifact is patched for emergency diagnosis, port the same
       change to source before acceptance/commit and do not commit the artifact
       patch.
   - Before adding interface/data-layer code, search existing ownership
     locations. Reuse the right module when one exists; otherwise add focused
     files for bridge API, DTO, runtime/permission model, UI display model,
     adapter, or serialization responsibilities rather than expanding one
     unrelated file.
   - Keep encoding and localization conversions at documented boundaries.
   - Do not add GitHub issue, remote push, or remote tracking assumptions.
   - Keep all work on the local spec branch until completion.
   - Maintain `review.md` when human-facing navigation changes.
   - Maintain `lessons.md` for feature-local project pitfall candidates.
     Do not promote anything into `.specify/memory/pitfalls.md` without
     explicit user confirmation.

10. Validation and test-case closure.
   - Run validation described in `tasks.md`, `plan.md`, or `quickstart.md`
     when feasible.
   - If validation passes, add or update the corresponding unit test,
     regression test, fixture, contract test, smoke case, or reviewable test
     artifact that preserves the behavior.
   - Re-run the affected tests after adding or updating the test case.
   - If an automated unit/regression test is not feasible, record why and use
     the narrowest substitute evidence: contract fixture, integration smoke,
     virtual-device check, real-device check, UI smoke, or manual review.
   - For UI/UX changes, include AI-collected UI evidence when feasible:
     screenshot paths, visual comparison notes, simulated interaction steps,
     DOM/computed/box metrics, console errors, and the target route/window. If
     automated UI/UX validation is unsupported, record the reason as a known
     validation gap instead of silently skipping it.
   - For 0px-level UI work, record the final traversal inventory result:
     baseline anchor deltas, per-element geometry/style deltas, dynamic state
     coverage, and any remaining non-zero difference with owner-approved N/A or
     follow-up scope.
   - If targeted validation for the changed scope passes but a broader/full
     suite fails outside the intended feature scope, do not silently declare
     success and do not expand the feature by guessing. Route through
     bounded-investigation: record the failing command, affected test/file,
     whether it is a pre-existing or infrastructure blocker, and the smallest
     repair if the root cause is clear. Keep unrelated broad cleanup out of the
     feature.
   - If validation cannot run, record exactly what remains unverified.

11. Implementation completion gate.
   - Do not report `/speckit-implement 完成` and do not continue to
     `speckit.acceptance` while AI-owned validation is still pending.
   - For host-embedded frontend plugin changes, completion requires source
     edit, frontend build, direct runtime replacement, real host CDP target
     inventory, selected target id/URL, and behavior evidence from the real
     DesktopShell product UI target. A report that lists "宿主运行时验证待执行",
     "CDP 验证待执行", "需启动 DesktopShell Electron", or an equivalent
     pending runtime check as a normal residual risk is non-compliant.
   - If the host, CDP endpoint, runtime target, device, permission, or
     automation path is unavailable after evidence-backed probing and the CDP
     host recovery ladder, stop with
     `blockers` and `next_required_human_action`; do not present the stage as
     complete and do not ask the user to perform primary technical validation
     as acceptance.
   - If validation fails or the original symptom persists, keep the loop inside
     this stage: collect fresh facts, patch repository source, rebuild, replace
     runtime output when relevant, and rerun validation until it passes or a
     real blocker is recorded.

12. Prepare acceptance handoff.
   - Ensure `tasks.md` reflects completed work and remaining risks when it
     exists; otherwise ensure `progress.md` records the completed plan slices.
   - Ensure `progress.md` has the latest slice, validation evidence, required
     test-case closure, remaining gaps, and next recommended stage.
   - Ensure `review.md` points human reviewers to the validation and acceptance
     entry when present.
   - Do not commit, merge, delete branches, push, or create remote tracking.

## Fact Layer Gate

- Before a second same-class fix, run `speckit.fact-layer` and create or update
  `fact-pack.md`. Do not keep guessing from source alone when the first patch
  did not change the observed symptom.
- For UI parity or host-embedded frontend layout, use fact-layer evidence for
  DOM, console, computed style, box metrics, scroll owner, overflow, flex/grid
  grow/shrink, clipping, compression, blank area, sibling resize, and toolbar
  displacement. Use chrome-devtools for runtime DOM/CSS/console/box metrics
  when available.
- For device state, permission, virtual device, connection, acquisition, SDK,
  Biz, or plugin behavior, use the fact collector to find the latest local
  logs: `C:\Windows\Temp\ExampleSdkLog\SDK_*.log` and
  `C:\Windows\Temp\NativeBridgeLog\NativeBridge_*.log`. Do not use MCP for
  log files. If logs lack required facts, add minimal source-level diagnostic
  logs, rerun, close DesktopShell so logs flush, then update
  `fact-pack.md`.

## Output

Report in Chinese:

- Tasks completed.
- Files changed.
- Validation run and result.
- Test cases added or updated, plus the re-run result.
- `progress.md` slice status and remaining risk.
- `review.md` / `lessons.md` updates, when relevant.
- Confirmation that no commit, branch cherry-pick/delete, push, or remote tracking
  action was performed.
- Any validation or test-case closure that is not feasible, with reason.
- Remaining gaps or blocked tasks.
- Required next stage: `speckit.acceptance` / `$speckit-acceptance`.
- Human review prompt:
  - Ask the developer only for user acceptance or required owner decisions.
  - Do not ask the developer to confirm root cause correctness, test sufficiency,
    fallback quality, or code correctness; if uncertain, report a blocker and
    return to analysis/investigation.
