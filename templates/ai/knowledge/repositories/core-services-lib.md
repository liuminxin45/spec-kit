# CoreServicesLib

## Role

`CoreServicesLib` is the sdk-biz-core repository. It owns reusable industrial
device business/runtime facts, device tree orchestration, property services,
and public facade decisions.

## Load When

- Affected repositories include `CoreServicesLib`.
- Task touches `DeviceManager`, device tree, property tree, services, UUID,
  connection/acquisition state, operation availability, or public facade.

## Key Paths

- `include/`: public API surface.
- `deviceTree/`: device hierarchy, manager, store, read-only facade.
- `deviceProperty/`: property parsing, translation, polling, event
  coordination.
- `services/`: business service wrappers and typed result structs.
- `infra/`: EventBus and runtime helpers.
- `tests/`: Google Test and E2E validation assets.

## Build

- Configure with Visual Studio generator and build Debug or Release.
- Offline builds may require disabling online third-party dependencies.

## Validation

- Prefer focused Google Test filters for touched modules.
- Use CTest or the `run_tests` target for broader regression.
- For UI-facing behavior, validate the downstream bridge/frontend route when
  feasible.

## Boundaries

- Do not move UI-display-specific structure or visual state into Libs.
- Do not expose SDK handles, native ids, or ambiguous device ids above the
  SDK/service layer.
- Generated artifacts under build/output directories are not source evidence.

## Verify Before Use

Inspect current `CMakeLists.txt`, test target names, and exact facade paths
before running commands.
