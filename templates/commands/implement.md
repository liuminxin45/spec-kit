---
description: Execute approved implementation slices while preserving source scope and validation evidence.
scripts:
  ps: scripts/powershell/check-prerequisites.ps1 -Json -IncludeTasks
  preflight_ps: scripts/powershell/validate-feature-artifacts.ps1 -Json -Stage implement -FeatureDir <feature-dir>
  select_knowledge_ps: scripts/powershell/select-knowledge.ps1 -Json -Stage implement -FeatureDir <feature-dir>
  select_gates_ps: scripts/powershell/select-gates.ps1 -Json -Stage implement -FeatureDir <feature-dir>
  sync_ui_runtime_ps: scripts/powershell/sync-ui-runtime-artifacts.ps1 -Json -SourceDir <source-dist> -RuntimeDir <host-runtime-dir> -PluginId <plugin-id> [-RefreshCommand <command>]
  sync_native_runtime_ps: scripts/powershell/sync-native-runtime-artifacts.ps1 -Json -SourceNativeDir <source-native-dir> -RuntimePluginDir <runtime-plugin-dir> -PluginId <plugin-id> [-ProtoFile <proto>] [-NativeExportsFile <native-exports.json>]
  validate_rpc_proto_bundle_ps: scripts/powershell/validate-rpc-proto-bundle.ps1 -Json -BundleJs <service-proto-bundle-json.js> -ServiceName <service> -RequiredFields Message:field1,field2
  ensure_cdp_host_ps: scripts/powershell/ensure-host-cdp.ps1 -Json -TargetKind host-app -HostRoot <host-app-root> -AllowProcessRecovery
  inspect_cdp_target_ps: scripts/powershell/inspect-host-cdp-target.ps1 -Json -TargetKind host-app
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load only the active `workpack.md`, `plan.md`, or `tasks.md` needed for this implementation. Load knowledge, tools, gate packs, old specs, and design-history docs only when selected by script facts.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, root-cause judgment, validation sufficiency, and tradeoff decisions.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this stage cannot continue, report `blockers` and `next_required_human_action`.

## Purpose

Implement the active change with the smallest durable artifact set:

1. Read the selected execution artifact: `workpack.md`, `plan.md` slices, or `tasks.md`.
2. Patch only the allowed repository source scope.
3. Run required validation and selected gate evidence.
4. Update `validation.md` with concrete command/result/evidence.
5. Update `implementation-summary.md` as the final actual implementation index.

This stage does not create `progress.md` by default and does not perform user acceptance, retrospective, commit, branch completion, push, or remote tracking setup.

## Required Inputs

- `FEATURE_DIR/workpack.md` for `micro-fix` and `standard-bugfix-lite`, or
- `FEATURE_DIR/plan.md` for `standard-bugfix`, or
- `FEATURE_DIR/tasks.md` plus `plan.md` for `full-sdd`.
- `.specify/feature.json` routing fields when present.
- `.specify/memory/constitution.md` when present.

Optional artifacts such as `acceptance-rubric.md`, `quality-vision.md`, `fact-pack.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, and `checklists/` are loaded only when the active slice or selected gate needs them.

## Execution Steps

1. Run the prerequisite script and `validate-feature-artifacts -Stage implement`.
   - `full-sdd` and high-risk gates may require `analysis.md` and `checklists/implementation-readiness.md`.
   - Lean bugfix profiles should be satisfied by `workpack.md` plus `workflow-state.json`.
2. Run `select-gates` for stage `implement`; read only selected gate packs.
3. Run `select-knowledge` only when repository-map, active artifacts, and selected gates still lack required repository/domain/build/validation context.
4. Resolve executable slices:
   - `workpack.md` `Change Slice` for lean bugfixes.
   - `plan.md` `Implementation Slices` for standard-bugfix.
   - `tasks.md` for full-sdd.
   Each slice must name target, allowed write scope, forbidden scope, validation, and stop condition.
5. Execute one slice at a time.
   - Read nearby code before editing.
   - Preserve user or teammate changes.
   - Modify repository source, never runtime/build/export output as the durable fix.
   - Use bounded `rg`/`rg --files` searches from affected repositories and known paths.
   - Run documented validation and selected gate evidence.
6. Update `validation.md`.
   - Record command/tool, result, evidence path, and interpretation.
   - Use `evidence.md` or `fact-pack.md` only when raw output would bloat `validation.md`.
7. Update `implementation-summary.md`.
   - Final solution.
   - Final fix type and whether the failure mechanism was eliminated.
   - Changed code/config/scripts/docs/tests.
   - Mechanism changes and plan/spec/workpack deltas.
   - Not implemented, residual risks, compatibility impact, follow-ups, and evidence links.
8. If `acceptance-rubric.md` exists, load `speckit-ai-self-acceptance` through `skill-routing.yml` and record `PASS`, `FAIL`, or `BLOCKED` in `validation.md`.
   - `FAIL` loops back to implement or fact-layer.
   - `BLOCKED` needs a true external blocker.
9. Stop and route back when validation fails, the original symptom persists, scope expands, source behavior is missing, root cause evidence fails, or a user/owner decision is required.

## Selected Gate Discipline

- `host-cdp`: use `ensure-host-cdp`, inspect the real product target, reject wrong targets, and save key screenshots when visual evidence matters.
- `frontend-runtime-sync`: source edit -> frontend build -> direct runtime replacement -> real host CDP verification; final package evidence is required before release/branch completion, not before every lean delivery.
- `plugin-package`: use shared `.plugin` package validation for frontend/native/JS/integrated plugin release paths.
- `native-bridge`: build/export native source, sync explicit runtime artifacts when validating locally, restart host, and validate RPC proto bundle fields when bridge/proto changes.
- `qt-parity` and `real-device`: collect source behavior or device/runtime facts before patching behavior across boundaries.

## Implementation Discipline

- Do not invent SDK, device, permission, or status data.
- Do not make global fallback/status/permission changes from a virtual/simulated bug unless the guard is explicit and proven.
- Respect repository ownership from `.specify/memory/repository-map.md`.
- Cross-boundary device identity is UUID decimal string only; do not expose SDK handles, native ids, virtual ids, or parallel frontend ids above their owner layer.
- Do not commit or rely on installed runtime plugin directories, `dist/`, `build/`, `export/`, `plugin-out/`, app-data, or host-served runtime artifacts as the durable fix.
- If a required repository from `.specify/workspace.yml` is missing, run `inspect-workspace-repositories` and block instead of guessing.
- Confirm Root-Fix Decision Gate before bugfix edits.
- For a second same-class failure or UI/CSS/layout guessing, collect fact-layer evidence before another patch.

## Completion Gate

- Completion requires `validation.md` evidence and `implementation-summary.md`.
- `workflow-state.json` should record `implementation_summary.status = completed` and link `implementation-summary.md`.
- Human acceptance is after AI-owned validation; it is not a substitute for fixable build/browser/CDP/device/runtime validation.

## Output

Report in Chinese:

- Files changed.
- Validation run and result.
- Selected gate packs and evidence.
- `validation.md` path.
- `implementation-summary.md` path and final actual change summary.
- Remaining gaps or blocked tasks.
- Confirmation that no commit, branch cherry-pick/delete, push, or remote tracking action was performed.
- Required next stage: human acceptance or explicit opt-in governance/commit stage.
