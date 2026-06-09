# Qt Source Behavior Map

This file is a durable AI-facing index for Qt-to-frontend parity work. It is
not a complete behavior specification by itself; each row must cite source
evidence and last verification before it is used as authority.

## Usage Rule

Use this map before broad workspace search when a task asks to match, migrate,
or compare Qt UI behavior. If the relevant module row is missing or stale,
record the gap in the active feature and do bounded source investigation in the
affected repositories; do not treat an absent row as proof that behavior does
not exist.

## Required Row Fields

| Field | Meaning |
|-------|---------|
| Source module | Qt module or feature area, such as `device-tree`. |
| Qt source paths | `.cpp`, `.h`, `.ui`, delegate, QSS/resource, and string constant files. |
| Key classes/functions | Classes, slots, delegates, handlers, model functions, or style constants that own behavior. |
| Behavior dimensions | Object type, device state, UI element/action order, visible/enabled rules, handler, dialog route, and dynamic state. |
| Target plugin paths | Frontend plugin source files, tests, and validation entry points. |
| Known gaps | Missing migration, route-only placeholder, unknown runtime fact, or owner decision. |
| Validation entry | Test, fixture, host route, CDP smoke, or manual acceptance path. |
| Last verified | Date, feature, and evidence used for the latest verification. |

## Module Rows

| Source module | Qt source paths | Key classes/functions | Behavior dimensions | Target plugin paths | Known gaps | Validation entry | Last verified |
|---------------|-----------------|-----------------------|---------------------|---------------------|------------|------------------|---------------|
| `product device list / device tree` | `unknown; fill from bounded Qt source investigation before next parity change` | `unknown` | device row right-click, first-level type row behavior, menu action width/order, device double-click by connection/status, menu focus loss | `<workspace-root>/ProductUIPlugin/product-device-tree/` | Current map row is a placeholder; use the active feature's spec/plan/progress evidence until the row is source-verified. | `specs/012-product-device-tree-ui-fixes/validation.md` when present | `2026-06-04; candidate created from workflow retrospective, not yet source-complete` |

## Maintenance Rules

- Add or update rows only with source paths plus validation or owner evidence.
- Keep paths relative with `<workspace-root>` placeholders.
- Mark unknowns explicitly instead of inventing file names.
- For UI interaction or operation availability migration, plan/checklist stages
  should require coverage of object type, state, action order, visible/enabled,
  handler/dialog route, and dynamic states.
