# Validation

This is the default L5 validation summary for a feature. It records what was
checked and what the result means. It pairs with `acceptance.md`; validation-only
work also writes into this file instead of creating a separate report.

## 1. Scope

- Feature:
- Repositories:
- Delivery profile:
- Risk level:
- Validation owner:

## 2. Validation Matrix

| Target | Command / Manual Check | Expected Result | Actual Result | Evidence |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## 3. Result Interpretation

- Passed checks:
- Failed checks:
- Not run:
- Known gaps:
- LLM judgment:

## 4. Routing Impact

- Continue current workflow:
- Return to implement:
- Return to plan/tasks:
- Escalate to fact-layer:
- Human/user acceptance required:

## 5. Evidence Links

- `acceptance.md`:
- `evidence.md` (optional for complex/runtime/tool-heavy evidence):
- `fact-pack.md` (optional fact-layer evidence):
- Logs:
- Screenshots:
- Test output:

## 6. Host Frontend Delivery Chain

- Applies:
- Source edit evidence:
- Frontend build command/result:
- Direct runtime replacement evidence (`sync-ui-runtime-artifacts`):
- Runtime plugin directory:
- Removed stale runtime files:
- Real host CDP target id/title/url:
- Loaded resource evidence:
- Native `.plugin` build evidence (if native instead of frontend):

## Rules

- No validation claim is complete without a concrete evidence reference in this
  file, `acceptance.md`, `evidence.md`, `fact-pack.md`, logs, screenshots,
  command output, or another cited artifact.
- This file may summarize sufficiency, but only the LLM can judge sufficiency.
- Keep raw command output and tool facts in `evidence.md` when they are lengthy.
- For host-embedded frontend plugin edits, record source edit -> frontend build
  -> direct runtime replacement -> real host CDP verification before asking for
  human acceptance.
- For DesktopShell CDP validation, record `/json/list` page targets and
  the selected target id/title/url. Mark Plugin Workbench, `base-win.html`,
  `devtools://`, blank, or unrelated product UI evidence as
  `wrong-target / insufficient`.
