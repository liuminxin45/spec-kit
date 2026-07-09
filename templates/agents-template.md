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

Then read only active feature files for the selected path: use
`workpack.md` `Outcome` first for lean final implementation facts;
`implementation-summary.md` first for non-lean, handoff, commit, branch
completion, or strict governance facts when present; lightweight and
standard-lite fixes use `workpack.md`; standard work uses `plan.md` with compact slices; heavy work adds `spec.md`, `tasks.md`,
`research.md`, `contracts/`, or `data-model.md` only when needed; runtime/debug work adds
`fact-pack.md`, latest logs, or DevTools evidence only for unclear/repeated/runtime symptoms.

## Do Not Load By Default

Do not read these unless the current stage explicitly needs them: `TEAM-README.md`,
`Layered SDD for AI Coding.md`, `LAYERED-SDD-*`, `ai/knowledge/*`,
`ai/templates/*`, `ai/tools/*`, `templates/*`, or old completed `specs/*`.

This avoids stale knowledge and keeps AI coding context bounded.

## Operating Rules

- Use `.specify/memory/repository-map.md` as repository role truth. Do not infer
  ownership by scanning source trees.
- Durable fixes belong in repository source files, not generated outputs,
  installed runtime directories, caches, or built artifacts.
- Bugfix work must complete a Root-Fix Decision Gate before implementation:
  compare root fix, mitigation, compatibility fallback, and containment when
  applicable. Do not describe cleanup, release, reset, retry, fallback, or
  limiting as root fix unless the failure mechanism is eliminated.
- When a task needs repository path, build output, package, generated output, or
  runtime/deployment context, use the `Project Path Categories` section in
  `.specify/memory/repository-map.md` first. When repository-map is not enough,
  use `select-knowledge` or read `ai/knowledge/index.yml` to select at most the
  small guide set required by affected repositories, risk flags, capability
  tags, or stage. Do not load all `ai/knowledge/*` by default, and do not use
  full-text/BM25 search for this layer. Keep long-term path notes relative; do
  not write machine-specific absolute paths into team memory. Use placeholders
  such as `<workspace-root>`, `<app-root>`, `<artifact-root>`, `<component-id>`,
  `<version>`, and `<location>`.
- For workflow-specific evidence rules, use `select-gates` or
  `ai/workflows/gates/index.yml` first and read only selected packs. Command
  templates are stage contracts, not full manuals.
- Optional specialized delivery chains live behind selected gate packs; they are
  not default context for generic repositories. Run `select-gates` before
  loading their detailed evidence rules.
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
  style/box metrics through available browser/runtime inspection tools before a
  second patch, unless the user provides copied DOM/CSS evidence.
- After UI/UX-affecting code changes, use available browser/runtime automation
  for best-effort self-validation such as screenshots, visual comparison, and
  simulated interactions. If unsupported, record the reason instead of treating
  it as a hard blocker.
- Runtime investigations should use log locations documented in
  `.specify/memory/repository-map.md`, selected gate packs, or selected
  knowledge guides. Do not assume project-specific log directories in generic
  workspaces.
- Branch completion cherry-picks back to the entry branch recorded at spec
  branch creation, keeps the local spec branch by default, and does not push.
- Commit is opt-in after validation and user acceptance. It does not require
  retrospective or workflow-observer artifacts. Post-commit self-check and
  Rubric scoring are strict/release-mode opt-in stages.
- Complete-branch is a local branch-state mutation: preflight may run
  automatically, but cherry-pick requires explicit human approval and
  `-ConfirmCompletion`.
- Push is outside the default workflow. Prefer PR-first; any exceptional push
  requires explicit human approval and `preflight-push`.
- Before final response after human acceptance, commit, strict self-check, or
  rubric work, run `inspect-workflow-closure`. If it reports a default-stage
  blocker, execute or report that blocker. Opt-in governance artifacts are not
  required unless the selected path requested them.
- Retrospective creates `knowledge-candidates.md` only as pending project
  knowledge candidates. Only human-approved candidates may be promoted into
  `ai/knowledge` with `promote-knowledge-candidates`, followed by
  `validate-knowledge-index` and optional delta-overlay repack.
- Long-term facts or rules are not edited silently. They require source
  evidence, validation evidence, and explicit human approval.

## Workflow Weight

- `micro-fix`: `workpack.md`, code change, `Outcome` validation evidence, acceptance.
- `standard-bugfix-lite`: compact low/medium-risk bugfix in `workpack.md`,
  with root cause, one implementation slice, validation, `Outcome`, and acceptance summary.
- `standard-bugfix`: `plan.md` may contain executable slices and replace a
  separate `tasks.md`.
- `full-sdd`: add `tasks.md` and extra design artifacts only for broad,
  cross-repo, public API, architecture, migration, or external-system semantics.
- `blocked-investigation`: collect facts first; do not patch by guessing.
- `validation-only`: write validation evidence without product-code changes.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan only
when the selected workflow path requires `plan.md`.
<!-- SPECKIT END -->
