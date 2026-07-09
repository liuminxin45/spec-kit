---
description: Generate tasks.md only when a separate execution artifact is justified.
scripts:
  ps: scripts/powershell/setup-tasks.ps1 -Json
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load `spec.md`, `plan.md`, and optional design artifacts only for `full-sdd` or when `plan.md` cannot compactly hold executable slices.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, root-cause judgment, validation sufficiency, and tradeoff decisions.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this stage cannot continue, report `blockers` and `next_required_human_action`.

## Purpose

Create `tasks.md` for:

- `full-sdd`
- broad migrations
- public API or cross-repo work whose implementation slices need independent sequencing
- standard work where `plan.md` explicitly says a separate L3 artifact is needed

Do not create `tasks.md` for `micro-fix` or `standard-bugfix-lite`. Do not create tasks.md for micro-fix. Do not duplicate `plan.md` slices.

## Layered Artifact Contract

- Required L3 output is `tasks.md` only when the selected profile needs a separate L3 artifact.
- `tasks.md` must include `## Implementation Slices`.
- Every slice must include target, allowed write scope, forbidden scope, validation, search scope, and stop condition.
- `workflow-state.json` carries structured status; `progress.md` is not required by default. progress.md is not required by default.

## Language Rules

- `tasks.md` is a human-reviewed execution artifact. Write slice summaries,
  validation expectations, risks, and N/A reasoning in Chinese-first style.
- When `tasks.md` is created, it must include a top `## 人类审核摘要` section
  for fast human review. This section is additive only: it must summarize task
  scope, root cause correctness, test sufficiency, validation entry, highest
  risks, and next step, and 不得替代或删减 later AI/流程读取区 such as
  Implementation Slices, dependencies, per-task evidence, validation commands,
  assumptions, blockers, and unknowns.
- Do not ask humans to restate root cause correctness or test sufficiency when
  the plan and task slices already provide enough evidence; surface only
  concrete blocking decisions.
- Preserve technical identifiers in their original form: file paths, module
  names, APIs, fields, enum/status values, commands, test names, task IDs, and
  scenario IDs.

## Execution Steps

1. Run setup and parse `FEATURE_DIR`, `AVAILABLE_DOCS`, and `TASKS_TEMPLATE`.
2. Load:
   - `spec.md`
   - `plan.md`
   - `.specify/feature.json`
   - optional `research.md`, `data-model.md`, `contracts/`, and `quickstart.md` only when named by the plan.
3. If the selected profile is not `full-sdd` and `plan.md` already contains complete Implementation Slices, stop and report that `tasks.md` is unnecessary.
4. Generate `tasks.md` from the template.
5. Organize work by executable implementation slice and validation closure, not by process ceremonies.
6. For bugfixes, include repro/regression tasks only when they are part of the selected plan.
7. For UI/API/runtime/device work, include tasks that preserve ownership boundaries and selected gate evidence.
8. Include validation and test-case update tasks when feasible; record explicit N/A reasons when not feasible.

## Task Rules

- Do not create tasks for unrelated cleanup.
- Do not add default tasks for acceptance checklist, retrospective, workflow-observer, promotion, post-commit self-check, rubric, or complete-branch.
- Optional commit or branch completion may be mentioned as a one-line handoff only when the user requested it.
- Do not split workflow gates into many checklist chores.
- Public interface changes must include downstream impact tasks.
- UI/UX/copy tasks must cite source references or block for clarification.
- Multi-repo work must name affected repositories from `.specify/workspace.yml`.
- Use bounded search scopes; do not search the whole `workspace_root`.

## Output

Report in Chinese:

- Whether `tasks.md` was created or skipped.
- Tasks path when created.
- Total task count and slice summary.
- Validation and test-case gaps.
- Required next stage: `speckit.analyze` for full-sdd/high-risk, otherwise `speckit.implement`.
