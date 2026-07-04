# AGENTS.md

This repository uses Spec Kit for AI coding. Keep default context small: read stable facts first, then load only artifacts and policies the task needs.

## Default Context

Read these at the start of every task:

1. `.specify/workspace.yml`
2. `.specify/memory/repository-map.md`
3. `.specify/feature.json` when present, as current-feature state only
4. `ai/workflows/task-routing.md`

If the user asks about `spec-kit`, shared workflow infrastructure,
repository governance, or another task that is clearly not the active feature,
treat `.specify/feature.json` as a stale/current-feature hint. Do not load the
active feature's `specs/<feature>/*` artifacts or apply its risk flags unless
the user explicitly resumes that feature.

Then read only active feature files for the selected path: lightweight fix
uses `progress.md` or `micro-fix.md`; standard-lite work uses `workpack.md` and
`progress.md`; standard work uses `spec.md`, `plan.md`, and `progress.md`;
heavy work adds `tasks.md`, `research.md`, `contracts/`, or `data-model.md`
only when needed; runtime/debug work adds `fact-pack.md`, latest logs, or
DevTools evidence only for unclear/repeated/runtime symptoms.

## Do Not Load By Default

Do not read these unless the current stage explicitly needs them: `TEAM-README.md`,
`Layered SDD for AI Coding.md`, `LAYERED-SDD-*`, `ai/knowledge/*`,
`ai/templates/*`, `ai/tools/*`, `templates/*`, or old completed `specs/*`.

This avoids stale knowledge and keeps AI coding context bounded.

## Operating Rules

- Use `.specify/memory/repository-map.md` as repository role truth. Do not infer
  ownership by scanning source trees.
- Product or plugin fixes belong in repository source files, not only installed
  runtime plugin directories or built artifacts.
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
- For workflow-specific evidence rules, use `select-gates` or
  `ai/workflows/gates/index.yml` first and read only selected packs. Command
  templates are stage contracts, not full manuals.
- Optional desktop host/plugin/native delivery chains live behind selected gate
  packs such as `host-cdp`, `frontend-runtime-sync`, `native-bridge`, and
  `plugin-package`; they are not default context for generic repositories.
- For host-embedded UI fixes, a source-to-runtime copy and refresh may validate
  built source output; runtime artifacts are still not source or commit targets.
- Host-embedded frontend plugin source edits must follow the AI delivery chain:
  source edit -> frontend build -> direct runtime replacement -> real host CDP
  verification, then final `.plugin` build/package evidence. Native, JS, and
  integrated plugin source edits also require the shared `.plugin`
  build/package evidence; local build/export/runtime replacement is validation
  evidence only.
- host CDP validation must inspect `/json/list` first and record
  all page target `id/title/url/webSocketDebuggerUrl` values plus the selected
  target id/URL. Product UI validation rejects Plugin Workbench, `base-win.html`,
  `devtools://`, blank, and unrelated targets as wrong-target evidence.
  Before giving up on AI-owned host validation, run
  `ensure-host-cdp` or equivalent probes to reuse a valid
  running target, start the host when no process owns the CDP port, or identify
  a port owner as a real blocker; a running process or occupied port is not by
  itself a reason to skip to manual acceptance. Save key-path screenshots from
  CDP into `FEATURE_DIR/cdp-screenshots/` and report the screenshot directory to
  the human when CDP validation ends.
- Qt-to-frontend UI parity should read `.specify/memory/qt-source-behavior-map.md`
  or `ai/knowledge/qt-source-behavior-map.md` before broad workspace search.
- After changing or upgrading `spec-kit` templates, run
  `validate-generated-context`, `validate-knowledge-index`, and
  `validate-context-budget` before relying on generated default context. If a
  validator reports missing gate phrases in `AGENTS.md`, `.specify/memory/*`,
  `.specify/templates/*`, `ai/*`, missing guides, machine-specific paths, or
  context-budget drift, refresh or report it explicitly instead of silently
  skipping the rule.
- Scripts output `facts`, `blockers`, `unknowns`, and `hints`. The LLM owns
  semantic routing, root-cause judgment, validation sufficiency, and tradeoffs.
- During test planning, use `inspect-validation-capabilities` before searching
  test commands. E2E may be `N/A` when unsupported, but API test plan remains required.
- Required repositories from `.specify/workspace.yml` must be present. If a
  required repo is missing, run `inspect-workspace-repositories` and block
  instead of scanning other repositories to guess an implementation owner.
- Before starting a new Spec Kit workflow, run `preflight-new-workflow`; dirty
  worktrees, non-base branches, unfinished `.specify/feature.json`, or
  unresolved workflow runs block intake until the user manually resolves them
  or explicitly authorizes a named AI action.
- If a UI/CSS/layout patch fails once, collect runtime DOM/CSS/computed
  style/box metrics through DevTools/CDP before a second patch, unless the user
  provides copied DOM/CSS evidence.
- After UI/UX-affecting code changes, use available MCP/CDP/browser automation
  for best-effort self-validation such as screenshots, visual comparison, and
  simulated interactions. If unsupported, record the reason instead of treating
  it as a hard blocker.
- Runtime investigations should use log locations documented in
  `.specify/memory/repository-map.md`, selected gate packs, or selected
  knowledge guides. Do not assume project-specific log directories in generic
  workspaces.
- Branch completion cherry-picks back to the entry branch recorded at spec
  branch creation, keeps the local spec branch by default, and does not push.
- Commit is automated after hard gates and deterministic preflight pass. After
  commit, run exactly one post-commit self-check, then output final Rubric
  scoring. Complete-branch is a local branch-state mutation: preflight may run
  automatically, but cherry-pick requires explicit human approval and
  `-ConfirmCompletion`; never run it unless `validate-rubric-score` passes.
- Push is outside the default workflow. Prefer PR-first; any exceptional push
  requires explicit human approval and `preflight-push`.
- Before any final response after human acceptance, commit, post-commit
  self-check, or rubric work, run `inspect-workflow-closure`. If it reports a
  `next_required_stage`, execute that stage instead of reporting completion.
  Branch policy such as `local_only`, `push_remote: false`, or
  `complete_by_cherry_picking_to_base: false` does not skip retrospective,
  workflow-observer, post-commit self-check, or rubric-score.
- Retrospective creates `knowledge-candidates.md` only as pending project
  knowledge candidates. Only human-approved candidates may be promoted into
  `ai/knowledge` with `promote-knowledge-candidates`, followed by
  `validate-knowledge-index` and optional delta-overlay repack.
- Long-term facts or rules are not edited silently. They require source
  evidence, validation evidence, and explicit human approval.

## Workflow Weight

- `micro-fix`: minimal note/progress, code change, validation, acceptance.
- `standard-bugfix-lite`: compact low/medium-risk bugfix in `workpack.md`,
  with root cause, one implementation slice, validation, and acceptance summary.
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
