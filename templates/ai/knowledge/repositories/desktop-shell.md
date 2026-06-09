# DesktopShell

## Role

`DesktopShell` is the Electron desktop host. It owns app lifecycle,
windows, plugin host processes, RPC gateway, frontend runtime install, app-data,
and real host validation context.

## Load When

- Affected repositories include `DesktopShell`.
- Task mentions Electron host, plugin-host, RPC gateway, app-data, installed
  plugins, frontend runtime, CDP, screenshots, DOM, or console validation.

## Key Paths

- `src/main.js`: Electron main process entry.
- `src/plugin-host/`: plugin lifecycle, registry, executor, host manager.
- `src/rpc/`: RPC gateway and framework config.
- `src/front/`: frontend plugin management.
- `frontend/`: renderer/front resources.
- `app-data/`: runtime plugin registry, plugin status, proto files, built-in
  plugins, and development mock/runtime data.

## Build And Run

- `npm run bootstrap` initializes dependencies.
- `npm run debug` starts the app with plugin DevTools and CDP port.
- `npm test` runs plugin-host tests.

## Validation

- For host-embedded UI, inspect CDP `/json/list` first and select a real host
  target, not devtools, blank pages, base window, or unrelated workbench target.
- Record target id, title, URL, and WebSocket debugger URL before DOM or
  screenshot evidence.

## Boundaries

- Runtime plugin directories are validation/deployment artifacts, not durable
  source fixes.
- Product UI evidence must come from the real host target when host layout,
  event routing, or runtime state matters.

## Verify Before Use

Confirm current npm scripts and target URLs before validation.
