# Virtual Device And SDK Tests

## Load When

- Task mentions virtual devices, SDK API tests, SDK unit tests, ProtocolC,
  discovery, or device simulation.

## Concepts

- Virtual devices are compiled when SDK virtual-device support is enabled.
- Virtual device models are registered through generated model registry code.
- API tests validate public SDK behavior.
- Unit tests validate internal SDK behavior and usually link static SDK output.

## Validation Hints

- Enable API tests for public C API behavior.
- Enable unit tests for internal transport/player/helper behavior.
- Enable virtual-device support for tests that rely on simulated devices.
- ProtocolC behavior may require CTI library availability and careful environment
  setup.

## Boundaries

- Do not use virtual-device behavior to justify unguarded real-device behavior
  changes.
- If real-device behavior is affected and unavailable locally, record the gap
  explicitly.

## Verify Before Use

Read current `DeviceSdk` CMake options and test configuration flags before running
or recommending commands.
