# Architecture Constraints

This file is L0 long-term governance for compatibility boundaries and
cross-layer ownership. It is intentionally stable and human-reviewed.

## Compatibility Boundaries

Treat these as first-class compatibility boundaries:

- Public APIs, SDK headers, CLIs, and script interfaces.
- Bridge, adapter, or integration contracts.
- Extension, runtime, or embedded-surface APIs.
- Frontend state/events and serialized fields.
- Status values, permission semantics, and externally visible behavior.

Any breaking change must be explicit in `spec.md` and `plan.md`, with impact,
migration notes, and validation evidence.

## Runtime Truth Boundary

- Preserve real external-system, cache, transport, handle, permission, and
  runtime state.
- Fake status, placeholder handles, or optimistic UI state are allowed only in a
  documented simulation boundary.
- Events are refresh triggers, not durable truth stores.

## Service / Runtime / Frontend Ownership

- A forwarding or adapter layer must not implement business rules, state
  inference, permission decisions, UI behavior calculation, or durable runtime
  truth.
- `runtime/domain owner` owns reusable non-UI runtime facts, permission/capability
  facts, identity rules, and reusable business logic.
- Frontend or presentation layers own UI-specific structure, order,
  visible/enabled presentation, and action-entry composition based on facts from
  the owning domain/runtime layer.

## Identity Ownership

- Cross-boundary entity identity must have one canonical owner and format.
- Public contracts must not introduce parallel identifiers for the same entity.
- Identifier generation belongs to the owning domain layer.
- UI node IDs, list indices, cache keys, and display labels are not business
  entity identifiers unless the project explicitly defines them as such.

## File Ownership

- Before adding interface, DTO, permission model, UI display model, adapter, or
  serialization code, search existing ownership locations and adjacent modules.
- If no suitable owner exists, create focused files with clear responsibility
  instead of growing unrelated files.
