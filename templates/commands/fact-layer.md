---
description: Collect runtime, log, source, and artifact facts before repeated or evidence-poor fixes.
scripts:
  ps: scripts/powershell/collect-fact-layer.ps1 -Json
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

Create or update `FEATURE_DIR/fact-pack.md` from concrete project facts before
AI continues a repeated or evidence-poor fix. This command is mandatory before a
second same-class fix when the first patch did not change the observed symptom,
when UI runtime structure contradicts source assumptions, or when external-system
state, permission, connection, service/runtime, or embedded behavior cannot be
localized from source alone.

## Fact Sources

- Local logs are read from disk. Do not use MCP for log files.
- Project log directories and filename patterns must come from
  `.specify/memory/repository-map.md`, a selected gate pack, or a selected
  knowledge guide.
- If no log location is configured, record that fact and use build/test/runtime
  evidence instead of inventing a project-specific log path.
- Browser/runtime facts use available inspection tooling when applicable. Use it
  for DOM, console, computed style, and box metrics, not for local log files.
- If a selected gate pack provides a runtime target selection or fallback
  procedure, follow that gate instead of guessing project-specific URLs, ports,
  process names, or target titles.

## Execution Steps

1. Run the prerequisite script when available and identify `FEATURE_DIR`.
2. Run the fact collector:
   - PowerShell: `scripts/powershell/collect-fact-layer.ps1 -Json`
   - Optional target override:
     `scripts/powershell/collect-fact-layer.ps1 -TargetUrlPattern "<runtime-target-pattern>" -Json`
3. Record the collector output in `fact-pack.md` using
   `.specify/templates/fact-pack-template.md`.
4. If browser/runtime inspection is available, inspect the real target selected
   by repository-map, selected gates, or explicit user input; do not accept an
   unrelated blank or wrong target as evidence.
5. For UI work, capture:
   - DOM subtree for the relevant container chain.
   - computed style for size, display, position, overflow, flex/grid,
     min/max-height, min/max-width, box-sizing, and padding/margin.
   - box metrics for embedded root, scroll owner, tree container,
     info panel, headers, footers, and sibling panels.
   - Console errors/warnings.
   - Screenshots and interaction method. For CSS-only hover states, use
     `CSS.forcePseudoState(['hover'])` when `Input.dispatchMouseEvent` does not
     reliably apply Electron hover.
6. For external-system state/permission/connection work, summarize the
   latest configured log lines that correspond to the user's operation
   timeline.
7. Verify source/runtime consistency:
   - Repository source files changed.
   - Built artifact generated from those source files.
   - Installed runtime path checked only as evidence, not as edit target.
8. Separate confirmed facts from inferences. Do not write another patch until
   the next fix target is supported by the collected facts.

## Trigger Rules

Run `speckit.fact-layer` when any of these applies:

- A UI parity/layout patch fails or symptoms persist after the first attempt.
- AI is about to make a second same-class fix without new runtime facts.
- DOM/CSS/layout ownership is unclear.
- Scrollbar appearance, clipping, blank area, parent compression, toolbar
  displacement, or sibling resize is involved.
- Entity/resource state differs from service/runtime expectation.
- Permission, connected/disconnected state, simulation, or operation behavior
  differs across UI, service, and runtime.
- User says the rebuilt/reinstalled result is unchanged.
- The issue may be caused by editing installed runtime artifacts instead of
  repository source.
- Logs are needed after adding diagnostic logging.

## Output

Report in Chinese:

- `fact-pack.md` path.
- Latest configured project log paths or missing reasons.
- Browser/runtime inspection target status.
- Whether browser/runtime inspection was available for DOM / computed style / box
  metrics.
- Confirmed facts.
- Inferences.
- Next implementation target or blocker.
