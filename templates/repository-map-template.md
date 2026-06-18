# Workspace Repository Map

> This file is the single source of truth for workspace repository paths,
> roles, and capability ownership during Spec Kit stages.
> Do not infer repository purpose by scanning source trees during `specify`.
> Read this table first; inspect source files only later when a concrete
> affected repository, API, or path must be verified.
> L0.5 knowledge files under `ai/knowledge/*` may summarize this map, but this
> file remains authoritative for repository role and capability ownership.

## Workspace

- **Workspace root**: `.`
- **Primary repository**: `CoreRuntime`
- **Default base branch**: `master`
- **Branch policy**: local-only spec branches, same branch name across affected
  repositories, no push, no remote tracking, keep local spec branch after
  cherry-pick.

## Repository / Path / Role / Capability

| Repository | Path | Role | Capability / Ownership | AI Usage Notes |
|------------|------|------|-------------------------|----------------|
| `CoreRuntime` | `CoreRuntime` | `sdk-biz-core` | Core core/application library surface, reusable device/runtime facts, public contracts, identity/state/API boundary decisions. | Treat as the primary source for non-UI runtime, permission, capability, identity, and reusable business facts. |
| `SdkConsumer` | `SdkConsumer` | `sdk-consumer` | SDK consumer and compatibility validation surface for SDK-facing behavior. | Use for downstream SDK impact, virtual/real-device smoke, and SDK consumer regression evidence. |
| `JsPlugin` | `JsPlugin` | `js-plugin` | JavaScript/plugin-side integration surface and frontend-facing operation calls. | Use when JS/plugin contracts, node fields, JSON/RPC/N-API boundary consumers, or frontend business calls are affected. |
| `NativePlugin` | `NativePlugin` | `native-plugin-and-bridge` | Native plugin and `ServiceBridge` bridge layer. | `ServiceBridge` is forwarding-only; do not place runtime truth, permission calculation, or business-state cache here. |
| `PluginCommon` | `PluginCommon` | `shared-plugin-common` | Shared plugin-side common code, contracts, helpers, and reusable plugin support. | Use for shared plugin contracts/helpers that are not UI-display-specific and not core Libs runtime truth. |
| `FrontendPlugin` | `FrontendPlugin` | `frontend-plugin-targets` | Frontend plugin targets and UI display composition. | Owns UI-specific structure, order, visible/enabled presentation, and action entry composition based on facts from Libs/Biz. |
| `PlatformLibs` | `PlatformLibs` | `windows-dependencies` | Windows dependency/package support. | Do not use generated dependency artifacts as evidence for source ownership or API design. |
| `HostApplication` | `HostApplication` | `host-and-frontend-plugins` | Host application and frontend plugin integration workspace. | Use for host/plugin integration impact, frontend packaging, and cross-plugin validation when affected. |
| `spec-kit` | `spec-kit` | `ai-delivery-tooling` | Workspace-level Spec Kit source, wrappers, templates, scripts, skills, workflow assets, and tests. | Use for shared workflow infrastructure, generated context, routing, validator, installer, and AI governance changes. It does not participate in ordinary product spec branch fan-out. |

## Project Path Categories

> These are relative path templates. Resolve `<workspace-root>` from
> `.specify/workspace.yml`, then resolve repository names from this map. Do not
> store machine-specific absolute paths in long-term knowledge.

| Category | Relative Path Template | Owner / Source | AI Usage Notes |
|----------|------------------------|----------------|----------------|
| Frontend plugin source root | `<workspace-root>/FrontendPlugin/<plugin-id>/` | `FrontendPlugin` | Edit frontend plugin source here. Use `<plugin-id>/src/` for Vue/JS/CSS, `<plugin-id>/frontend-plugin.conf` for plugin metadata, and `<plugin-id>/front-meta.json` for host frontend metadata when present. |
| Frontend plugin build output | `<workspace-root>/FrontendPlugin/<plugin-id>/dist/` | `FrontendPlugin` build | Built frontend resources. Validation/deployment artifact; do not treat as the durable fix location unless the repository explicitly marks it as source. |
| Frontend plugin dependency DLL output | `<workspace-root>/FrontendPlugin/<plugin-id>/public/dist/dll/` | `FrontendPlugin` build | Webpack DLL resources copied into `dist/` during build. Generated artifact. |
| Frontend plugin package staging | `<workspace-root>/FrontendPlugin/<plugin-id>/plugin-out/<version>/staging/` | `HostApplication` packaging scripts | Temporary package staging. Generated artifact. |
| Packaged plugin artifact | `<workspace-root>/HostApplication/HostApplication/dist/plugins/<plugin-id>-<version>.plugin` | `HostApplication` plugin host packer | Installable `.plugin` artifact collected by host tooling. Generated artifact; do not patch as source. |
| Native Biz plugin source root | `<workspace-root>/NativePlugin/<plugin-id>/` | `NativePlugin` | Edit native plugin source here, for example `<plugin-id>/src/` and `<plugin-id>/CMakeLists.txt`. |
| Native Biz CMake build cache | `<workspace-root>/NativePlugin/<plugin-id>/build/<generator>/<arch>/<config>/` | `NativePlugin` / CMake | Generated build cache and `_deps` tree. Do not use as source ownership evidence. |
| Native Biz export output | `<workspace-root>/NativePlugin/<plugin-id>/export/` | `NativePlugin` build | Native export/output directory. Generated deployment artifact. |
| Host project root during development | `<workspace-root>/HostApplication/HostApplication/` | `HostApplication` | Development host root. Runtime helpers may use `app.getAppPath()` for the equivalent packaged host root. |
| Host app-data root during development | `<workspace-root>/HostApplication/HostApplication/app-data/` | `HostApplication` runtime state | Development app-data root for plugin registry, installed plugin runtime state, and local host validation. Runtime state, not durable source. |
| Host app-data native plugin runtime | `<host-app-root>/app-data/plugins/<plugin-id>/<version>/` | `HostApplication` runtime install | Runtime directory for installed native plugins such as `service-bridge-plugin`. Use only for validation/runtime sync after source build/export. |
| Host app-data native plugin addon directory | `<host-app-root>/app-data/plugins/<plugin-id>/<version>/native/` | `HostApplication` runtime install | Runtime `.node` addon location. Keep `.proto` and `native-exports.json` in the plugin root, not under `native/`. |
| Host-served frontend plugin runtime | `<host-app-root>/frontend/<location>/<plugin-id>/` | `HostApplication` runtime install | Runtime copy served by host. Default `<location>` is `plugins`; read `frontend-plugin.conf` `extMetaData.location` before assuming it. Validation/deployment target only. |
| Host frontend descriptor mock | `<host-app-root>/mock_data/api/pluginManager/v1/getFrontDescriptorList.json` | `HostApplication` frontend plugin sync | Development descriptor response generated from installed frontend runtime resources. |
| Host app-data frontend plugin config | `<app-data-root>/<brand-name>/<project-name>/<front-plugins-config-file>` | `HostApplication` runtime state | User/runtime state. Read source constants for exact brand/project/config names when needed; do not hardcode local absolute paths. |
| Legacy host plugin runtime directories | `<host-app-root>/plugins/Surv.biz`, `<host-app-root>/plugins/Surv.ui`, `<host-app-root>/plugins/IotUtility.ui` | `HostApplication` project path helpers | Host runtime plugin directories. Runtime artifacts, not durable source targets. |

## HostApplication Electron / CDP Defaults

| Fact | Team Default | AI Usage Notes |
|------|--------------|----------------|
| Development host launch | Run from `<host-app-root>` with `npm run debug` | Starts HostApplication Electron with plugin DevTools enabled. Use when host-embedded UI validation needs the real container. |
| CDP endpoint | `http://127.0.0.1:9222` | `npm run debug` sets `UTILITY_CHROME_REMOTE_DEBUGGING_PORT=9222`; use `/json/version` and `/json/list` to confirm the endpoint before validation. |
| CDP target inventory | `/json/list` page targets with `id/title/url/webSocketDebuggerUrl` | Record the full page target list before DOM/screenshot validation. A note that `9222` is connected is insufficient evidence. Prefer `inspect-host-cdp-target` when available. |
| Host app CDP target patterns | `app-home`, `app-main-window`, `frontend/static/index.html` | Select a real HostApplication page target matching these URL patterns for host-embedded app or frontend-plugin validation. The expected ProductModule business target is usually `http://example.local/frontend/static/index.html#/app-home/appHome` or a child route such as `.../appMainWindow`; title `ExampleHost` alone is insufficient. |
| Plugin Workbench CDP target pattern | `Plugin Workbench\|plugin-workbench.html` | Use only when the changed surface is `plugin-host` DevTools / Plugin Workbench itself. `npm run debug` opens this target directly; select it from `/json/list` for workbench DOM/CSS/click smoke instead of using host app targets. Treat it as wrong-target evidence for product UI. |
| Rejected product-UI CDP targets | `devtools://...`, `src/plugin-host/devtools/plugin-workbench.html#build`, `base-win.html`, blank pages, unrelated Chrome targets | Never use these as product UI DOM/screenshot evidence. `base-win.html` may share the `ExampleHost` title but is not the business page. Mark evidence from these targets as `wrong-target / insufficient`. |
| Host UI validation priority | Real HostApplication Electron + CDP first; isolated plugin preview only as fallback | After source build and optional source-to-runtime sync, prefer CDP screenshots, DOM, computed style, box metrics, console, and simulated/forced interactions on the real host route. |
| CDP hover validation | Use `Input.dispatchMouseEvent` when reliable; use `CSS.forcePseudoState(['hover'])` for CSS-only hover states when Electron does not apply hover from synthetic mouse movement | Record which method was used in `validation.md` or `fact-pack.md`. |

For expanded host debugging steps, runtime sync cautions, and direct CDP usage,
load `ai/knowledge/build-and-package-notes.md`; do not rediscover these fixed
facts by scanning HostApplication source unless a concrete mismatch appears.

## Rules For AI

- This file is authoritative for repository purpose, path, and capability
  ownership.
- Use the Project Path Categories section before scanning source when a task
  needs plugin source, build output, install artifact, or runtime directory
  context.
- Keep long-term path knowledge relative to `<workspace-root>`, repository
  names, `<host-app-root>`, `<app-data-root>`, `<plugin-id>`, `<version>`, and
  `<location>` placeholders. Do not write machine-specific absolute paths here.
- Do not infer repository purpose by scanning source trees.
- Do not spend `specify` tokens rediscovering repository roles.
- In `specify`, use this map to decide likely affected repositories and record
  explicit uncertainty instead of guessing.
- Inspect repository files only after the affected repository is identified and
  only to confirm concrete identifiers such as existing API names, paths, or
  source behavior references.
- If this map is stale, stop and ask the user to update this map rather than
  silently inventing repository ownership.
- Proposed long-term repository-map changes require source evidence, reason,
  validation or owner confirmation, and explicit human approval before being
  promoted into `.specify/memory/repository-map.md` or `ai/knowledge/*`.
