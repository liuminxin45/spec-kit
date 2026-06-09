# Build And Package Notes

This file is L0.5 long-term project knowledge for durable build, package, and
deployment facts.

## Entry Format

- **ID**: BUILD-YYYYMMDD-NNN
- **Area**: [repo / package / plugin / SDK / installer]
- **Fact**: [stable build or packaging behavior]
- **Evidence**: [script, config, commit, validation output]
- **Future Check**: [what future agents should verify]

## Current Baseline

- Runtime plugin directories, host-served frontend plugin outputs, `dist/`,
  `build/`, `export/`, and `plugin-out/` are validation/deployment artifacts
  unless a repository explicitly treats them as source.
- Product or plugin fixes must be made in source files before acceptance or
  commit.
- Long-term path knowledge must use relative templates and placeholders. Use
  `<workspace-root>`, repository names from `.specify/memory/repository-map.md`,
  `<host-app-root>`, `<app-data-root>`, `<plugin-id>`, `<version>`, and
  `<location>` instead of machine-specific absolute paths.

## Plugin Path Knowledge

Use this section when a task needs source/build/runtime path context but does
not need to scan code yet. `.specify/memory/repository-map.md` remains the
authoritative repository map.

| Category | Relative Path Template | Notes |
|----------|------------------------|-------|
| Frontend plugin source root | `<workspace-root>/ProductUIPlugin/<plugin-id>/` | Source owner for frontend plugin UI, metadata, tests, and assets. |
| Frontend plugin source files | `<workspace-root>/ProductUIPlugin/<plugin-id>/src/` | Durable Vue/JS/CSS source. |
| Frontend plugin metadata | `<workspace-root>/ProductUIPlugin/<plugin-id>/frontend-plugin.conf`, `<workspace-root>/ProductUIPlugin/<plugin-id>/front-meta.json` | Read metadata before deriving plugin id, version, or frontend runtime location. |
| Frontend plugin build output | `<workspace-root>/ProductUIPlugin/<plugin-id>/dist/` | Build output. Validation/deployment artifact, not durable source. |
| Frontend plugin DLL output | `<workspace-root>/ProductUIPlugin/<plugin-id>/public/dist/dll/` | Generated webpack DLL assets. |
| Frontend plugin package staging | `<workspace-root>/ProductUIPlugin/<plugin-id>/plugin-out/<version>/staging/` | Temporary package staging. |
| Packaged plugin artifact | `<workspace-root>/DesktopShell/DesktopShell/dist/plugins/<plugin-id>-<version>.plugin` | Installable `.plugin` artifact collected by host tooling. |
| Host-served frontend runtime | `<host-app-root>/frontend/<location>/<plugin-id>/` | Runtime copy served by host; default `<location>` is `plugins`, but `frontend-plugin.conf` may override it through `extMetaData.location`. |
| Host descriptor mock | `<host-app-root>/mock_data/api/pluginManager/v1/getFrontDescriptorList.json` | Development descriptor response generated from frontend runtime resources. |
| Host app-data frontend config | `<app-data-root>/<brand-name>/<project-name>/<front-plugins-config-file>` | Runtime state/config. Resolve exact names from host constants when needed. |
| Native Biz plugin source root | `<workspace-root>/ProductNativePlugin/<plugin-id>/` | Source owner for native Biz plugins such as `NativeBridge`. |
| Native Biz CMake build cache | `<workspace-root>/ProductNativePlugin/<plugin-id>/build/<generator>/<arch>/<config>/` | Generated CMake cache and dependency tree. |
| Native Biz export output | `<workspace-root>/ProductNativePlugin/<plugin-id>/export/` | Native build/export output. |
| Legacy host plugin runtime directories | `<host-app-root>/plugins/Example.biz`, `<host-app-root>/plugins/Example.ui`, `<host-app-root>/plugins/ExampleTool.ui` | Runtime directories exposed by host path helpers. Do not patch as source. |

## DesktopShell Host Debugging

Use this section before reading DesktopShell source when a task needs the
real Electron host, CDP screenshots, host route validation, or frontend plugin
runtime sync.

### Stable Facts

- Host app root: `<workspace-root>/DesktopShell/DesktopShell/`.
- Start the development Electron host from `<host-app-root>` with:

  ```text
  npm run debug
  ```

- The debug script enables plugin DevTools and sets:

  ```text
  UTILITY_ENABLE_PLUGIN_DEVTOOLS=1
  UTILITY_CHROME_REMOTE_DEBUGGING_PORT=9222
  LANG=zh_CN.UTF-8
  LC_ALL=zh_CN.UTF-8
  ```

- The Electron main process Node inspector also starts on `5858`; use `5858`
  only for main-process Node debugging. UI/DOM/CSS screenshots use Chromium CDP
  on `9222`.
- Confirm CDP with:

  ```text
  http://127.0.0.1:9222/json/version
  http://127.0.0.1:9222/json/list
  ```

- Preferred real DesktopShell page target patterns for host app or
  frontend-plugin validation:

  ```text
  product-homepage|product-main-window|frontend/static/index.html
  ```

- Plugin Workbench target pattern for `plugin-host` DevTools / workbench
  changes:

  ```text
  Plugin Workbench|plugin-workbench.html
  ```

- Before collecting DOM, screenshot, console, or resource evidence, run
  `inspect-desktop-shell-cdp-target` or manually inspect
  `http://127.0.0.1:9222/json/list`. Record every page target's
  `id`, `title`, `url`, and `webSocketDebuggerUrl`, then record the selected
  target id and URL in `validation.md` or `fact-pack.md`.
- Real business target evidence for ProductSuite host UI should come from a page
  whose URL is `http://host.example.invalid/frontend/static/index.html`
  with route `#/product-homepage/productHome` or a child route such as
  `.../mainWindow`. Title alone is insufficient because `base-win.html` may
  also show `ExampleCorp`.
- Reject `devtools://...`, `src/plugin-host/devtools/plugin-workbench.html#build`,
  `base-win.html`, blank pages, and unrelated Chrome targets for product UI
  validation. Mark such evidence as `wrong-target / insufficient`.
- Reject DevTools pages, blank Chrome pages, unrelated browser targets, and
  `base-win.html` without the relevant embedded page. Also reject Plugin
  Workbench for host app or frontend-plugin validation; use it only when the
  changed surface is the plugin-host workbench itself.
- The usual entry flow for ProductSuite host UI validation is: attach to
  `#/product-homepage/productHome`, click the target app card such as
  `工业相机`, then validate the embedded `product-main-window` route.

### Frontend Plugin Runtime Sync For Validation

- Product fixes still belong in `<workspace-root>/ProductUIPlugin/<plugin-id>/`
  source files.
- After the plugin's npm build script, usually `npm run build` or
  `npm run build:main`, in the frontend plugin source, runtime validation may
  mirror built output into `<host-app-root>/frontend/<location>/<plugin-id>/`.
  The required AI chain for host-embedded frontend source edits is:
  source edit -> frontend build -> direct runtime replacement -> real host CDP
  verification. This copy is validation/deployment evidence only, not a source
  target. Use `sync-ui-runtime-artifacts` for the runtime replacement when the
  source/runtime mapping is explicit; it removes stale files in the target
  plugin runtime directory by default so old split chunks cannot remain loaded.
- CDP validation should also record loaded artifact evidence from
  `performance.getEntriesByType('resource')`, including the plugin entry files
  and current split chunk names. Do not treat a source build as host-loaded
  evidence unless the resource list or equivalent host fact proves the new
  runtime files were loaded.
- DesktopShell frontend runtime install helpers can generate or update
  development descriptor state under
  `<host-app-root>/mock_data/api/pluginManager/v1/getFrontDescriptorList.json`.
  Treat that descriptor as generated runtime state; do not commit it unless the
  repository explicitly tracks that file for the current task.
- For an installable frontend plugin package, use the host packaging path:
  `scripts/frontend-plugin-sync.js` stages `<plugin-id>/dist/` plus
  `front-meta.json` when required, writes `plugin.json`, calls
  `src/plugin-host/scripts/builders/pack-plugin.js`, and installs the generated
  `.plugin` through `npm run install-plugin -- <plugin-file>`.
- If using direct CDP rather than Chrome DevTools MCP, select the target from
  `/json/list`, connect to `webSocketDebuggerUrl`, use `Runtime.evaluate` for
  DOM/computed-style facts, `Page.captureScreenshot` for screenshots, and
  `Input.dispatchMouseEvent` for clicks when reliable.
- For CSS-only hover states in Electron, synthetic mouse movement may not apply
  `:hover`. Use CDP `CSS.forcePseudoState(['hover'])` on the target node and
  record that method in validation evidence.

## DesktopShell Plugin Build And Install Workflows

Use this section before inventing ad-hoc build commands for plugins. The host
DevTools build page and CLI share the same builders under
`<host-app-root>/src/plugin-host/`.

### Plugin Type Detection

- Frontend plugins are detected by `frontend-plugin.conf`.
- JavaScript plugins are detected by `js-plugin.conf`.
- Native addon plugins are detected by `CMakeLists.txt`.
- Search roots used by the host workbench include `ProductJSPlugin`,
  `ProductNativePlugin`, `ProductUIPlugin`, and related product plugin
  repositories.

### Frontend UI Plugins

- Source owner: `<workspace-root>/ProductUIPlugin/<plugin-id>/`.
- Build from the plugin source directory with the plugin's npm build script
  (`npm run build`, `npm run build:main`, or the script declared by that plugin).
- Package/install through DesktopShell when an installable artifact is
  needed: the frontend sync helper stages `dist/`, generates `plugin.json`,
  packs with `src/plugin-host/scripts/builders/pack-plugin.js`, then runs:

  ```text
  npm run install-plugin -- <plugin-file>
  ```

- Direct source-to-runtime copy into
  `<host-app-root>/frontend/<location>/<plugin-id>/` is allowed only as
  validation/development evidence after source build.

### JavaScript Plugins

- Source roots are usually under `<workspace-root>/ProductJSPlugin/` or the
  product JS plugin repositories.
- Build with the host JS plugin builder:

  ```text
  node src/plugin-host/scripts/builders/build-js-plugins.js --plugins-dir <plugin-source-or-root>
  ```

- The JS builder reads `js-plugin.conf`, generates exports/wrappers as needed,
  stages declared assets/native runtime deps, and produces a `.plugin` package.

### Native Addon Plugins

- Source owner for ProductSuite Biz native plugins:
  `<workspace-root>/ProductNativePlugin/<plugin-id>/`.
- Preferred host flow for native plugin packages is the DesktopShell
  builder, from `<host-app-root>`:

  ```text
  npm run build-builtin-plugins -- --config Release --arch x64
  ```

  or the lower-level CLI when adding extra plugin roots:

  ```text
  node src/plugin-host/scripts/builders/plugin-build-and-pack-cli.js build --plugins-dir <plugin-root> --config Release --arch x64
  ```

- The shared host build path is:
  CMake configure/build -> `generate-plugin-structure.js` -> `pack-plugin-core`.
  The DevTools `buildPlugin` API follows the same stages.
- The host `cmake-builder.js` expects Visual Studio plus a runnable VS-bundled
  `ninja.exe`, calls `vcvarsall.bat`, forces `CMAKE_MAKE_PROGRAM`, configures
  `build/Ninja/<arch>/<config>`, and outputs native files under
  `<plugin-source>/export/<config>/<arch>/native/`.
- If a stale CMake cache points to a non-runnable Ninja such as a PATH shim,
  treat that as build-environment/cache drift. Clean the affected
  `build/Ninja/<arch>/<config>` cache or configure a fresh generator directory
  for validation; do not change product source to work around a bad Ninja path.
- Focused native validation may build directly with CMake when the host unified
  Ninja path is unavailable, but record it as a validation fallback. Example:

  ```text
  cmake -G "Visual Studio 17 2022" -A x64 -S <plugin-source> -B <plugin-source>/build/VS2022/x64/Release -DCMAKE_BUILD_TYPE=Release
  cmake --build <plugin-source>/build/VS2022/x64/Release --config Release
  ```

- Native facade tests that load the addon should pass
  `--mvc-biz-native-dir <plugin-source>/export/Release/x64/native` or the
  matching `$<TARGET_FILE_DIR>` path from CTest.

### Install, Uninstall, And Hot Upgrade

- Install `.plugin` packages from `<host-app-root>` with:

  ```text
  npm run install-plugin -- <plugin-file> [plugin-file...]
  ```

- The install CLI requires `.plugin` files, starts the plugin host in install
  mode, sorts packages by dependency, and calls `pluginHost.installPlugin`.
- DevTools and the overlay preload expose `installPlugin(src)` and
  `uninstallPlugin(pluginId)` for interactive install/uninstall.
- Pure JavaScript plugins use hot swap when possible. Plugins with native
  dependencies use dual-directory restart semantics because loaded native
  modules cannot be fully unloaded from the current process.
- If install/upgrade reports `restartRequired`, restart the DesktopShell
  host before using CDP validation as acceptance evidence.

## Governance

Promote build/package lessons only after validation evidence or owner
confirmation. Feature-local build notes should first be recorded in
`workflow-record.md` or `promotion-report.md`.
