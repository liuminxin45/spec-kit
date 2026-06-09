# Architecture Map

## Role

Compact cross-layer architecture guide for ProductSuite / ExamplePlatform work.

## Load When

- Planning a cross-layer change.
- Explaining where runtime truth, bridge forwarding, UI display, and host
  validation belong.

## Layers

```text
DesktopShell Electron host
  main process -> renderer -> plugin host process
  RPC gateway / WebSocket / Protobuf

Plugin layer
  ProductNativePlugin native addon
  ProductJSPlugin JavaScript plugin
  ProductUIPlugin frontend plugins

Business layer
  CoreServicesLib sdk-biz-core static library

SDK layer
  DeviceSdk device SDK

Infrastructure
  tmedia, tnet, tutil, WindowsDeps, SharedPluginCommon
```

## Ownership Rules

- Runtime truth and reusable business facts belong in `CoreServicesLib`.
- SDK protocol and device handle behavior belongs in `DeviceSdk`.
- `NativeBridge` is forwarding-only; it should not own business truth.
- Frontend plugin source owns visible UI composition and user-facing state
  presentation, based on bridge facts.
- DesktopShell owns host runtime, plugin lifecycle, RPC routing, and CDP
  validation context.

## Verify Before Use

If this guide conflicts with repository-map.md, repository-map.md wins.
