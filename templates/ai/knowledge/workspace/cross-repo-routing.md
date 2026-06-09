# Cross-Repo Routing

## Role

Use this guide to decide which focused repository guide to read after the
repository-map has identified likely affected repositories.

## Load When

- A feature crosses SDK, Libs, Biz, frontend plugin, or host runtime.
- A task mentions repos.config, branch coordination, plugin packaging, or
  downstream validation.

## Routing Hints

- SDK API, ProtocolC, ProtocolB/ProtocolA control, virtual device registration, or frame
  acquisition: start with `repositories/device-sdk.md`.
- Device tree, property tree, connection state, operation availability,
  reusable service behavior, or public facade: start with
  `repositories/core-services-lib.md`.
- NAPI exports, native bridge payloads, event forwarding, or facade tests:
  start with `repositories/product-native-plugin.md`.
- Vue plugin UI, frontend runtime resources, `front-meta.json`, mock data, or
  visible UI: start with `repositories/product-ui-plugin.md`.
- Electron host, plugin-host lifecycle, app-data, installed plugin runtime, RPC
  gateway, or CDP validation: start with `repositories/desktop-shell.md`.
- Shared NAPI helpers or native addon CMake modules: start with
  `repositories/shared-plugin-common.md`.
- Qt source parity, QSE, or native UI controls: start with `repositories/windows-deps.md`.

## Boundaries

This guide should narrow reading. It should not add repositories to the feature
scope by itself.
