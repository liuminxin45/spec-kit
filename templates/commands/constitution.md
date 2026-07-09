---
description: Create or update the team constitution and keep downstream templates aligned.
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

Create or update `.specify/memory/constitution.md` as the stable engineering
contract for domain/runtime ownership, integration boundaries, UI/service
layering, compatibility, validation, and migration work.

The constitution should describe principles and decision rules. Do not turn it
into a full project directory map. Project structure belongs in `plan.md` under
affected modules and project structure; the constitution only defines how the
team treats boundaries, compatibility, verification, and change control.

## Entry Context

- `AGENTS.md` is the AI entry file installed by Spec Kit.
- `ai/workflows/task-routing.md` defines workflow routing categories and the
  script-facts / LLM-judgment boundary.
- This command maintains durable principles only. The canonical rule templates
  are `ai/rules/engineering-principles.md`,
  `ai/rules/architecture-constraints.md`, and
  `ai/rules/ai-coding-rules.md`.
- Do not move repository maps,
  workflow routing, tool policies, or per-feature artifacts into the
  constitution.
- Do not silently edit durable rule files. Knowledge updates under `ai/knowledge/*`
  require source evidence, reason, validation evidence, and human approval.

## Language Rules

- `.specify/memory/constitution.md` is human-reviewed governance material.
  Write it in Chinese-first style.
- Preserve technical identifiers in their original form: repository names,
  file paths, module names, APIs, fields, enum/status values, commands, and
  workflow constants.

## Required Principles

Use these defaults unless the user explicitly overrides them:

1. Minimal scoped change
   - Prefer the smallest change that satisfies the capability.
   - Avoid unrelated refactors, formatting churn, or metadata churn.

2. Existing patterns first
   - Read nearby code, scripts, build files, and existing integration conventions
     before inventing a new abstraction.
   - Match existing naming, ownership boundaries, and error handling style.

3. Interface compatibility first
   - Treat public APIs, SDK headers, CLI/script interfaces, integration
     contracts, frontend extension contracts, and serialized status fields as
     compatibility boundaries.
   - Any breaking change must be explicit, justified, and accompanied by an
     impact and migration note.

4. Real validation loop
   - Prefer concrete build, unit, smoke, runtime, or device validation evidence.
   - If verification cannot be run, record the gap and the exact follow-up.

5. Runtime truth
   - Do not fake external-system, cache, transport, status, permission, or
     handle state.
   - Preserve real runtime facts and operation permissions unless the spec
     explicitly defines a simulation boundary.

6. UI display, service bridge, and runtime truth boundary
   - A forwarding or adapter layer is a transport/integration boundary only. It
     must not implement business logic, state inference,
     permission/availability decisions, UI behavior calculation, or durable
     business models.
   - Non-UI-specific runtime facts, cache/handle/transport/permission data, and
     reusable business rules belong in the owning domain/runtime layer.
   - Business-side code used only to display the current UI, such as UI
     interaction surface structure, ordering, visible/enabled presentation, and
     action entry composition, belongs in the frontend/presentation layer and
     must be based on owning domain/runtime facts.
   - Frontend code must not infer runtime/permission truth from labels/strings,
     fake state, or persist runtime/permission business state as truth.

7. Identity, state, and API single ownership
   - Across domain/runtime facade, adapter, RPC/JSON, JS, and UI, each business
     entity has one canonical identity owner and format.
   - Public contracts must not introduce parallel identifiers for the same
     entity.
   - Identifier generation belongs to the owning domain layer; service, adapter,
     and UI layers consume that identity instead of defining separate generation
     rules.
   - Native IDs, external handles, cache keys, list indices, and UI node IDs stay
     inside their local layer unless the spec explicitly defines them as public
     contract fields.
   - Events are refresh triggers only. After connect/disconnect/acquisition/
     runtime events, UI refreshes must return to the owning domain/runtime layer;
     event payloads do not become a parallel truth store.
   - Functionally equivalent old APIs should be removed or migrated instead of
   coexisting with the new production API. Debug/test facades and temporary
   SDK passthroughs must stay in tests or scripts, not production service exports.
   - Names must express real semantics; avoid ambiguous identifiers that hide
     whether a value is a business identity, UI node id, list index, cache key,
     or external handle.
   - Generated artifacts such as `dist/`, `build/`, and `export/` must not
     affect interface ownership, package-source selection, or diff judgment.
   - Product behavior changes must be made in repository source files, not
     installed runtime directories, served runtime artifacts, or generated
     outputs. Emergency artifact patches must be ported back to source before
     acceptance/commit and excluded from commits.

8. Interface and data file ownership
   - Before adding interface/data-layer code, search existing ownership
     locations and nearby modules.
   - If no suitable home exists, create focused files for contract, DTO,
     bridge API, runtime/permission model, UI display model, adapter, or serialization responsibilities instead
     of growing a single unrelated file.

9. Encoding and localization boundaries
   - Treat native string encoding, UTF-8 conversion, and localized display text
     as explicit boundary decisions.
   - Convert at the documented output boundary, not opportunistically inside
     unrelated layers.

10. Local-only Spec branch workflow
   - Each Spec starts on a local `NNN-short-name` spec branch.
   - Multi-repo Specs must create or switch every affected repository to the
     same local spec branch.
   - A Spec is complete only after user acceptance, required commit work, and
     all affected repositories cherry-pick the spec branch commits back to the
     entry branch recorded at spec branch creation.
   - Branch completion keeps the local spec branch by default; deletion is not
     part of the default workflow.
   - The agent must request and receive explicit user confirmation before
     running any command that commits or cherry-picks branch completion.
   - Spec Kit must not push branches, create remote tracking branches, or
     generate GitHub issues as part of the workflow.

11. Evidence before implementation
   - A capability should move from spec to plan to tasks with enough context for
     another engineer or agent to understand scope, affected files, risks, and
     validation expectations.

## Update Steps

1. Read the current `.specify/memory/constitution.md` if it exists.
2. If the constitution is missing, use Spec Kit's bundled init-source
   constitution template. This one-time template is not installed under
   `.specify/templates`.
3. Merge user input with the default principles above.
4. Write the completed constitution back to `.specify/memory/constitution.md`.
5. If a principle changes existing feature work, add an "Amendment Impact"
   section listing which specs, plans, tasks, or templates should be revisited.

## Output

Report in Chinese:

- Constitution path.
- Version or amendment summary.
- Principles added, changed, or removed.
- Any downstream artifacts that should be updated.
- Required next stage for a new feature workflow: `speckit.intake` /
  `$speckit-intake`, unless the user is only maintaining constitution text.
- Human review prompt:
  - Ask the developer to review the constitution changes and confirm whether
    downstream templates or active specs need adjustment.
  - If adjustment is needed, update the constitution and ask for review again.
  - If no adjustment is needed and a feature workflow is starting, tell the
    developer the only next step is `speckit.intake` / `$speckit-intake`.
