# ProductUIPlugin

## Role

`ProductUIPlugin` is the frontend plugin source repository. It owns Vue plugin
source, visible UI composition, `front-meta.json`, mock data, and frontend build
outputs used by the Electron host.

## Load When

- Affected repositories include `ProductUIPlugin`.
- Task touches frontend plugin source, UI layout, visible copy, route/menu
  metadata, mock data, or frontend build/runtime sync.

## Plugin Types

- Library plugins build UMD component libraries.
- Application plugins build complete Vue applications with webpack and usually
  include `front-meta.json`, mock assets, route/store/page folders, and
  frontend plugin metadata.

## Key Paths

- `<plugin-id>/src/`: Vue source.
- `<plugin-id>/frontend-plugin.conf`: plugin metadata.
- `<plugin-id>/front-meta.json`: runtime route/menu/hook metadata when present.
- `<plugin-id>/mock_data/`: local mock responses.
- `<plugin-id>/dist/`: build output, not durable source.

## Build

- Run commands inside the specific plugin directory.
- Common commands include `npm run build`, `npm run buildNCopy`,
  `npm run serve`, `npm run dll`, and `npm run lint`.

## Boundaries

- UI display composition belongs here, but runtime truth comes from Libs/Biz.
- Do not patch host-served runtime files as the durable fix.

## Verify Before Use

Inspect the plugin's own `package.json`, webpack config, and metadata files.
