# AGENTS.md

This repository uses Spec Kit for AI coding. Keep the default context small:
read stable facts first, then load only the feature artifacts and tool policies
that the current task actually needs.

## Default Context

Read these at the start of every task:

1. `.specify/workspace.yml`
2. `.specify/memory/repository-map.md`
3. `.specify/feature.json` when present, as current-feature state only
4. `ai/workflows/task-routing.md`

If the user asks about `tools/spec-kit`, shared workflow infrastructure,
repository governance, or another task that is clearly not the active feature,
treat `.specify/feature.json` as a stale/current-feature hint. Do not load the
active feature's `specs/<feature>/*` artifacts or apply its risk flags unless
the user explicitly resumes that feature.

Then read only the active feature files that match the selected path:

- Lightweight fix: `specs/<feature>/progress.md` or `micro-fix.md` when present.
- Standard work: `specs/<feature>/spec.md`, `plan.md`, and `progress.md`.
- Heavy work: add `tasks.md`, `research.md`, `contracts/`, or `data-model.md`
  only when the plan or user request requires them.
- Runtime/debug work: add `fact-pack.md`, latest logs, or DevTools evidence only
  when symptoms are unclear, repeated, or UI/runtime behavior is being debugged.

## Do Not Load By Default

Do not read these unless the current stage explicitly needs them:

- `TEAM-README.md`
- `Layered SDD for AI Coding.md`
- `LAYERED-SDD-*`
- `ai/knowledge/*`
- `ai/templates/*`
- `ai/tools/*`
- `templates/*`
- old completed `specs/*`

This avoids stale knowledge and keeps AI coding context bounded.

## Operating Rules

- Use `.specify/memory/repository-map.md` as the repository role source of
  truth. Do not infer repository ownership by scanning source trees.
- Product or plugin fixes must be made in repository source files, not only in
  installed runtime plugin directories or built artifacts.
- When a task needs plugin source, build output, package artifact, or runtime
  directory context, use the `Project Path Categories` section in
  `.specify/memory/repository-map.md` first. When repository-map is not enough,
  use `select-knowledge` or read `ai/knowledge/index.yml` to select at most the
  small guide set required by affected repositories, risk flags, capability
  tags, or stage. Do not load all `ai/knowledge/*` by default, and do not use
  full-text/BM25 search for this layer. Keep long-term path notes relative; do
  not write machine-specific absolute paths into team memory. Use placeholders
  such as `<workspace-root>`, `<host-app-root>`, `<app-data-root>`,
  `<plugin-id>`, `<version>`, and `<location>`.
- For host-embedded UI fixes, a source-to-runtime copy and refresh may be used
  as validation/deployment evidence after source output is built; runtime
  artifacts are still not source or commit targets.
- Host-embedded frontend plugin source edits must follow the AI delivery chain:
  source edit -> frontend build -> direct runtime replacement -> real host CDP
  verification. Native plugin source edits use source edit -> `.plugin` build
  evidence because native output cannot be hot-updated safely.
- DesktopShell CDP validation must inspect `/json/list` first and record
  all page target `id/title/url/webSocketDebuggerUrl` values plus the selected
  target id/URL. Product UI validation rejects Plugin Workbench, `base-win.html`,
  `devtools://`, blank, and unrelated targets as wrong-target evidence.
  Before giving up on AI-owned host validation, run
  `ensure-desktop-shell-cdp-host` or equivalent probes to reuse a valid
  running target, start the host when no process owns the CDP port, or identify
  a port owner as a real blocker; a running process or occupied port is not by
  itself a reason to skip to manual acceptance.
- Qt-to-frontend UI parity work should read
  `.specify/memory/qt-source-behavior-map.md` or
  `ai/knowledge/qt-source-behavior-map.md` before broad workspace search.
- After changing or upgrading `tools/spec-kit` templates, run
  `validate-generated-context` and `validate-knowledge-index` before relying on
  generated default context. If either reports missing gate phrases in
  `AGENTS.md`, `.specify/memory/*`, `.specify/templates/*`, `ai/*`, missing
  knowledge guides, or machine-specific knowledge paths, treat that as context
  drift and refresh or report it explicitly instead of silently skipping the
  rule.
- Scripts output `facts`, `blockers`, `unknowns`, and `hints`. The LLM owns
  semantic routing, root-cause judgment, validation sufficiency, and tradeoffs.
- If a UI/CSS/layout patch fails once, do not make a second patch until runtime
  DOM/CSS/computed style/box metrics are collected through DevTools/CDP or the
  user provides copied DOM/CSS evidence.
- After UI/UX-affecting code changes, use available MCP/CDP/browser automation
  for best-effort self-validation such as screenshots, visual comparison, and
  simulated interactions. If unsupported, record the reason instead of treating
  it as a hard blocker.
- SDK/Biz runtime investigations should use the latest logs from:
  `C:\Windows\Temp\ExampleSdkLog\SDK_*.log` and
  `C:\Windows\Temp\NativeBridgeLog\NativeBridge_*.log`.
- Branch completion cherry-picks back to the configured base branch, keeps the
  local spec branch by default, and does not push.
- Long-term facts or rules are not edited silently. They require source
  evidence, validation evidence, and explicit human approval.

## Workflow Weight

- `micro-fix`: minimal note/progress, code change, validation, acceptance.
- `standard-bugfix`: `spec.md` + `plan.md`; `plan.md` may contain executable
  slices and replace a separate `tasks.md`.
- `full-sdd`: add `tasks.md` and extra design artifacts only for broad,
  cross-repo, public API, architecture, migration, or real-device semantics.
- `blocked-investigation`: collect facts first; do not patch by guessing.
- `validation-only`: write validation evidence without product-code changes.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan only
when the selected workflow path requires `plan.md`.
<!-- SPECKIT END -->
