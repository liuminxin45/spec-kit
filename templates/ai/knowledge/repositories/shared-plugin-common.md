# SharedPluginCommon

## Role

`SharedPluginCommon` provides shared plugin development infrastructure: CMake
modules, NAPI helper headers/implementation, stream callback helpers, and JS
tools that generate native export metadata and proto files.

## Load When

- Affected repositories include `SharedPluginCommon`.
- Task touches native addon CMake modules, Node SDK injection, NAPI value
  helpers, stream callback macros, native export generation, or proto output.

## Key Paths

- `cmake/`: Common, Node SDK, native dependency, and plugin config modules.
- `include/native/`: public native plugin helpers.
- `include/napiUtilis/` and `src/napiUtilis/`: NAPI value conversion helpers.
- `include/native/RpcStreamCallbackHelper.h`: stream callback macros.
- `js-lib/src/core/`: NAPI comment parser and proto generator.

## Build

- CMake consumers usually link `utility-plugin-common`.
- `NODE_RUNTIME` and `NODE_RUNTIME_VERSION` influence Node/Electron SDK setup.

## Validation

- Run focused JS parser/proto generator tests when comment parsing changes.
- Validate a downstream native addon build when CMake modules change.

## Boundaries

- Keep shared helper behavior generic. Product business logic belongs in
  product plugin or Libs repositories.

## Verify Before Use

Inspect current CMake module names and js-lib tests before editing.
