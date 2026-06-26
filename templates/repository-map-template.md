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
- **Primary repository**: `app`
- **Default base branch**: `main`
- **Branch policy**: local-only spec branches, same branch name across affected
  repositories, no push, no remote tracking, keep local spec branch after
  cherry-pick.

## Repository / Path / Role / Capability

Replace the example rows with the repositories that actually exist in this
workspace before running feature delivery. Keep names stable because scripts and
gate selection use them as structured keys.

| Repository | Path | Role | Capability / Ownership | AI Usage Notes |
|------------|------|------|-------------------------|----------------|
| `app` | `.` | `primary-application` | Main source tree for product or library changes. | Use as the default affected repository only when the task really targets this source tree. |
| `spec-kit` | `spec-kit` | `ai-delivery-tooling` | Optional Spec Kit source checkout, wrappers, templates, scripts, skills, workflow assets, and tests. | Use for shared workflow infrastructure, generated context, routing, validator, installer, and AI governance changes. It does not participate in ordinary product spec branch fan-out. |

## Project Path Categories

> These are relative path templates. Resolve `<workspace-root>` from
> `.specify/workspace.yml`, then resolve repository names from this map.
> Do not write machine-specific absolute paths here.

Add only categories that are true for this workspace. Keep generated, runtime,
and packaged artifacts separate from durable source locations.

| Category | Relative Path Template | Owner / Source | AI Usage Notes |
|----------|------------------------|----------------|----------------|
| Application source root | `<workspace-root>/<app-path>/` | `app` | Durable source location for ordinary implementation changes. |
| Test source root | `<workspace-root>/<app-path>/tests/` | `app` | Regression and smoke tests when this path exists. |
| Build output | `<workspace-root>/<app-path>/<build-output>/` | repository build | Generated artifact; do not treat as durable source unless the repository explicitly marks it as source. |
| Package artifact | `<workspace-root>/<app-path>/<package-output>/<artifact-name>` | repository package command | Release or install artifact. Validation evidence only unless explicitly documented otherwise. |
| Runtime data root | `<runtime-root>/` | runtime environment | Runtime state, logs, caches, and installed resources. Read for evidence; do not commit as source. |
| Optional plugin source root | `<workspace-root>/<plugin-source-repo>/<plugin-id>/` | plugin source repository | Use only when this workspace has plugin repositories and the task selects plugin gates. |
| Optional host runtime root | `<host-app-root>/` | host application runtime | Use only when a selected host/runtime gate requires real host validation. |

## Optional Host / CDP Defaults

Fill this section only for projects with a real host application, browser,
Electron, device, or other runtime target that can be inspected. Otherwise leave
the rows as `N/A` and rely on normal build/test evidence.

| Fact | Team Default | AI Usage Notes |
|------|--------------|----------------|
| Runtime launch | `N/A` | Command to start the real validation runtime, if one exists. |
| CDP or browser endpoint | `N/A` | Endpoint such as `http://127.0.0.1:<port>` when host/browser validation is available. |
| CDP target inventory | `N/A` | If CDP is used, record `/json/list` page targets with `id/title/url/webSocketDebuggerUrl` before DOM or screenshot validation. |
| Valid product target patterns | `N/A` | URL/title patterns that identify the real product surface. |
| Rejected validation targets | `devtools://`, blank pages, unrelated browser targets | Never use unrelated targets as product UI evidence. |
| Runtime validation priority | Real target first when supported; isolated preview only as fallback | Record the reason whenever a lower-fidelity fallback is used. |

For expanded host/plugin/runtime examples, select the relevant gate pack with
`select-gates` and then load only the returned `ai/workflows/gates/*` file or
optional knowledge guide. Do not rediscover fixed facts by broad source search
unless a concrete mismatch appears.

## Rules For AI

- This file is authoritative for repository purpose, path, and capability
  ownership.
- Use the Project Path Categories section before scanning source when a task
  needs build output, package artifacts, install artifacts, runtime directories,
  or plugin source.
- Keep long-term path knowledge relative to `<workspace-root>`, repository
  names, `<app-path>`, `<runtime-root>`, `<host-app-root>`, `<plugin-id>`,
  `<artifact-name>`, and similar placeholders. Do not write machine-specific
  absolute paths here.
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
