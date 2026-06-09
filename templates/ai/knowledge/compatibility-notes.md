# Compatibility Notes

This file is L0.5 long-term project knowledge for durable compatibility facts.

## Compatibility Surfaces

- Public SDK headers.
- Libs facade contracts.
- `NativeBridge` bridge API.
- RPC/N-API/JSON fields.
- Frontend plugin operation contracts.
- Serialized status, permission, and device identity fields.

## Entry Format

- **ID**: COMP-YYYYMMDD-NNN
- **Surface**: [API / field / status / behavior]
- **Constraint**: [stable compatibility requirement]
- **Evidence**: [source, spec, commit, owner confirmation, validation]
- **Validation**: [how future changes should verify compatibility]

## Confirmed Notes

N/A

## Governance

Add or change entries only after explicit human approval or approved
promote-lessons output. Normal feature work may cite this file but should not
silently rewrite it.
