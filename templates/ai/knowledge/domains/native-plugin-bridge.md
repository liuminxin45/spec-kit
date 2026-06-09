# Native Plugin Bridge

## Load When

- Task touches `NativeBridge`, NAPI exports, JSON payloads, event forwarding,
  JS facade calls, or native bridge tests.

## Bridge Shape

- JS calls a native addon method exported from `NativeBridge.cpp`.
- `NapiExports.cpp` parses arguments and dispatches to payload functions.
- `JsonNapi.cpp` converts between JS values and `nlohmann::json`.
- Service payload files call `CoreServicesLib` services and return normalized
  JSON or direct NAPI objects.
- `NapiEventForwarder.cpp` forwards EventBus events to JS callbacks through a
  thread-safe function.

## Rules

- Keep `NativeBridge` forwarding-only.
- Do not add production debug/test facades unless explicitly approved.
- Convert `uint64_t` UUID/handle-like fields to strings at JS/RPC boundaries.
- Facade tests should preserve bridge contracts when exports or payload shapes
  change.

## Verify Before Use

Inspect active export table, payload file ownership, and facade test runner
before editing.
