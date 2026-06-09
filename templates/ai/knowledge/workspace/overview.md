# Workspace Overview

## Role

This workspace is the ExampleCorp ExamplePlatform / ProductSuite multi-repository
development area. ProductSuite is an device desktop application for
ProtocolA, ProtocolB, and ProtocolC devices.

## Load When

- Need a compact product/workspace summary after reading repository-map.md.
- Need to explain why a feature may cross SDK, business library, native plugin,
  frontend plugin, and Electron host layers.

## Main Repositories

- `DesktopShell`: Electron desktop host, plugin host, RPC gateway, runtime
  plugin install and debug/CDP validation surface.
- `DeviceSdk`: device SDK and C API for ProtocolA, ProtocolB,
  ProtocolC, and virtual devices.
- `CoreServicesLib`: sdk-biz-core static library with device tree, property,
  runtime orchestration, services, and reusable business facts.
- `ProductNativePlugin`: native NAPI bridge, especially `NativeBridge`.
- `ProductJSPlugin`: JavaScript plugin integration surface.
- `ProductUIPlugin`: frontend plugin source and UI display composition.
- `SharedPluginCommon`: shared CMake and NAPI helper infrastructure.
- `WindowsDeps`: Windows/Qt UI helper library used by desktop products.

## Boundaries

Repository ownership is defined by `.specify/memory/repository-map.md`. This
guide is only a compact orientation layer.

## Verify Before Use

Build commands, branch names, and product-specific repos.config details may
change. Use repository guide and current source files before executing commands.
