# Device Identity Boundary

## Load When

- Task mentions UUID, device id, node id, SDK handle, Biz bridge, RPC payloads,
  frontend operations, connection state, or operation availability.

## Rules

- Cross-boundary device identity is UUID decimal string.
- C++ internals may use `uint64_t uuid`.
- SDK native ids, handles, virtual ids, and transport handles stay inside SDK
  or lower service layers.
- `NativeBridge` forwards facts and converts payloads; it does not own runtime
  truth or cache business state.
- Frontend operations should use the business node UUID supplied by the bridge,
  not fallback ids invented from UI structure.

## Planning Notes

- Put reusable runtime facts and permission/capability decisions in
  `CoreServicesLib`.
- Put UI display order, visible/enabled state presentation, and interaction
  composition in frontend plugin source.
- Use semantic names such as `uuid`, `deviceUuids`, `nodeId`, and `listIndex`.

## Verify Before Use

Check current public facade, NAPI exports, JSON/RPC payload names, and frontend
node model before editing.
