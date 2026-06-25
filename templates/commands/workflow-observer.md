---
description: Observe Spec Kit workflow compliance from a bounded packet before promotion or commit.
scripts:
  packet_ps: scripts/powershell/collect-workflow-observer-packet.ps1 -Json -FeatureDir <feature-dir>
  closure_ps: scripts/powershell/inspect-workflow-closure.ps1 -Json -FeatureDir <feature-dir> -Stage final-response
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`,
`.specify/memory/repository-map.md`, `.specify/feature.json` when present, and
`ai/workflows/task-routing.md`.

For this command, read only:

- `FEATURE_DIR/workflow-observer-packet.json`
- `workflows/speckit/workflow.yml` or `.specify/workflows/speckit/workflow.yml`
- `ai/workflows/task-routing.md`
- A feature artifact only when the packet names it as missing or contradictory

Do not read project source trees, old completed `specs/*`, full `ai/knowledge/*`,
or broad design-history docs by default. Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic
routing, root-cause judgment, validation sufficiency, and tradeoff decisions.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`;
if this stage cannot execute the next required stage, report `blockers` and
`next_required_human_action`.

## Purpose

Create `FEATURE_DIR/workflow-observation.md` after retrospective and before any
promotion or commit. This is a clean-context observer for Spec Kit workflow
quality. It does not replace retrospective; it checks whether the workflow itself
missed stages, had contradictory rules, lacked script enforcement, or relied too
much on agent self-discipline.

## Execution Steps

1. Run `collect-workflow-observer-packet` for the active `FEATURE_DIR`.
2. Read the generated packet plus workflow and task-routing contracts.
3. Compare expected stage sequence with actual artifact and closure state.
4. Identify missing stages and classify the likely cause:
   - rule conflict
   - missing script or weak script wiring
   - weak command/template wording
   - generated-context drift
   - agent execution miss
   - unavailable external tool or host
5. Write `FEATURE_DIR/workflow-observation.md` with:
   - expected path vs actual path
   - missing or late stages
   - closure gate result and `next_required_stage`
   - smallest repair location: script, skill, workflow.yml, task-routing.md, or test
   - whether this should become an `improvement-candidates.md` item
6. If `inspect-workflow-closure` reports `blocked`, continue to the reported
   `facts.next_required_stage`.
7. If no approved promotion candidates exist, continue to `speckit.commit`.

## Output Template

```md
# Workflow Observation

## Expected Path vs Actual Path
- Expected:
- Actual:

## Missing or Late Stages
- Stage:
- Evidence:

## Root Cause Classification
- Classification:
- Evidence:
- Inference:

## Minimal Repair Location
- Script:
- Skill:
- workflow.yml:
- task-routing.md:
- Test:

## Closure Gate
- Status:
- Next required stage:
- Missing artifacts:

## Long-term Improvement Candidate
- Needed: yes/no
- Candidate summary:
```

## Output

Report in Chinese:

- `workflow-observer-packet.json` path.
- `workflow-observation.md` path.
- Closure gate status and `next_required_stage`.
- Whether the issue should become a long-term Spec Kit improvement candidate.
- Required next stage: approved promotion stage when applicable; otherwise
  `speckit.commit`.
