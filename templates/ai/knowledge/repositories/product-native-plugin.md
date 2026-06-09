# ProductNativePlugin

## Role

`ProductNativePlugin` owns ProductSuite native NAPI plugins. The primary
ProductSuite bridge is `NativeBridge`, a native addon connecting JavaScript/RPC
callers to `CoreServicesLib`.

## Load When

- Affected repositories include `ProductNativePlugin`.
- Task touches `NativeBridge`, NAPI exports, JSON payloads, event forwarding,
  native bridge contracts, or facade tests.

## Key Paths

- `NativeBridge/src/NativeBridge.cpp`: NAPI module entry and exports.
- `NativeBridge/src/NapiExports.cpp`: export implementations.
- `NativeBridge/src/NapiEventForwarder.cpp`: EventBus to JS forwarding.
- `NativeBridge/src/JsonNapi.cpp`: JSON/NAPI conversion.
- `NativeBridge/src/*Payloads.cpp`: service payload mapping.
- `NativeBridge/scripts/`: Node facade tests.

## Build

- Configure and build from `NativeBridge` using CMake.
- Native plugin output is a `.node` addon and plugin metadata.

## Validation

- Use facade tests under `NativeBridge/scripts` for bridge contract checks.
- CTest can run configured tests when `BUILD_TESTING` is enabled.

## Boundaries

- `NativeBridge` should remain forwarding-only.
- Do not cache device lists, connection/acquisition state, runtime state, or
  operation availability as truth.
- Convert `uint64_t` identifiers to decimal strings at JS/RPC boundaries.

## Verify Before Use

Check exact build output directory and facade test suite names in the active
tree before running commands.
