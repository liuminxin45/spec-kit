---
description: Judge AI-owned validation after code changes before convergence and human acceptance.
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, root-cause judgment, validation sufficiency, and tradeoff decisions.
Keep this command stage-specific. Do not duplicate long-term governance prose here.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this stage cannot execute the next required stage, report `blockers` and `next_required_human_action`.

## Purpose

Run the AI self-acceptance loop after code changes when `acceptance-rubric.md`
exists or a selected high-risk gate requires it. This is a judgeable gate:
collect evidence, score `acceptance-rubric.md`, write lean `workpack.md`
`Outcome` or strict `validation.md`, and return `PASS`, `FAIL`, or `BLOCKED`.
Human acceptance starts after lean Outcome or strict implementation-summary
closure is complete.

## Required Inputs

- `plan.md` `AI Context Contract`
- `acceptance-rubric.md`
- `quality-vision.md` for UI/UX work
- selected gate packs from `select-gates`
- `workpack.md` `Outcome`, `validation.md`, `implementation-summary.md`,
  `evidence.md`, and `fact-pack.md` when present

## Evidence Menu

Use only evidence required by the plan, selected gates, rubric, and changed
surface:

- build/test results and regression tests
- API/network payload and response checks
- selected gate-pack runtime target inventory when applicable
- key-path screenshots, screenshots-index.md, visual comparison, DOM, console, network, computed
  style, box metrics, scrollbar/clipping/overflow geometry
- source edit -> build -> runtime/deployment verification evidence
- build/export, runtime sync, protocol/export validation when selected gates require it
- latest service/runtime logs for runtime/external-system issues
- target-environment smoke when local resources and permissions are available

## Judge Steps

1. Confirm the original symptom or target scenario was reproduced or otherwise
   has a valid baseline.
2. Run or inspect the planned validations and selected gate evidence.
3. For every rubric row, assign `PASS`, `FAIL`, `BLOCKED`, or `N/A` and cite
   concrete evidence.
4. Fail immediately when any `Essential` row fails or any `Pitfall` triggers.
5. Treat missing UI baseline, wrong runtime target, missing key-path screenshot for
   UI-visible validation, stale runtime artifact, uninspected console/log
   errors, or unrun feasible smoke as `FAIL`, not a human-acceptance item.
6. For bugfix work, fail when Root-Fix Decision Gate is missing, final fix type
   is absent, a scale-growth failure path is still present but labeled root
   fix, or cleanup/release/reset/retry/fallback/limiting is treated as root fix
   without evidence that the failure mechanism is eliminated.
7. Use `BLOCKED` only for external facts the agent cannot fix or obtain:
   unavailable external resource, missing permission, unknown unsafe process owner, missing
   owner decision, or unavailable tool after recovery attempts.
8. Write lean `workpack.md` `Outcome` or strict `validation.md`
   `AI Self-Acceptance` / `AI Acceptance Result` with the rubric row results,
   blockers, evidence links, and next action.
9. Do not output final strict/release Rubric scores here. Record criteria
   coverage and triggered pitfalls only; `speckit.rubric-score` is an opt-in
   strict/release stage.

## Loop Contract

- `PASS`: continue to `speckit.acceptance` after lean `workpack.md` `Outcome`
  or strict `implementation-summary.md` and `validation.md` are current.
- `FAIL`: return to `speckit-implement` or `speckit-fact-layer`; patch source,
  rebuild/sync when relevant, and rerun this skill.
- `BLOCKED`: stop with concrete blocker evidence and `next_required_human_action`.

## Output

Report in Chinese:

- AI Self-Acceptance status: `PASS | FAIL | BLOCKED`.
- Rubric failures or triggered pitfalls.
- Evidence collected, including runtime target, screenshot directory, and logs when
  used.
- Rubric criteria coverage and explicit note that final strict/release scoring
  is opt-in.
- Next workflow stage.
- `next_required_human_action` only for true blockers or human acceptance after convergence.
