# DeviceSdk

## Role

`DeviceSdk` is the device SDK. It exposes C APIs and internally
implements ProtocolA, ProtocolB, ProtocolC, virtual devices, transport, and
player behavior in C++.

## Load When

- Affected repositories include `DeviceSdk`.
- Task mentions SDK API, ProtocolC, ProtocolA/ProtocolB, virtual device, device discovery,
  device handle behavior, API tests, or unit tests.

## Key Paths

- `include/`: public SDK and internal SDK headers.
- `src/DeviceSdkApi.cpp`: public C API implementation.
- `src/DeviceSdkInternal.cpp`: internal APIs used by upper layers.
- `src/device/`: transports, players, factories, virtual devices.
- `src/device/virtual_models/`: virtual device model definitions.
- `test/ApiTest/`: public API black-box tests.
- `test/UnitTest/`: internal unit tests.

## Build

- Use CMake with Visual Studio on Windows.
- Important options include `DEVICE_SDK_BUILD_STATIC_ONLY`,
  `DEVICE_SDK_API_TEST_ENABLE`, `DEVICE_SDK_UNIT_TEST_ENABLE`, and
  `DEVICE_SDK_VIRTUAL_DEVICE_ENABLE`.

## Validation

- API tests validate public C API behavior.
- Unit tests validate internal SDK behavior.
- Virtual-device tests usually require both internal usage and virtual device
  support to be enabled.

## Boundaries

- Keep SDK native handles and protocol details inside SDK/lower service layers.
- Do not infer upper-layer UI or business permission rules from SDK labels.

## Verify Before Use

Check current CMake option names and test executable paths in the active tree.
