# Electron Host CDP

## Load When

- Task requires DesktopShell host validation, DOM inspection, console
  evidence, screenshots, hover state, box metrics, or target selection.

## Target Selection

- Inspect `/json/list` before validation.
- Record every page target's id, title, URL, and WebSocket debugger URL.
- For product UI, select host app targets matching ProductSuite business routes
  or `frontend/static/index.html`.
- Reject devtools, blank pages, base window, Plugin Workbench, and unrelated
  targets for product UI validation.
- Use Plugin Workbench only when the changed surface is plugin-host DevTools or
  workbench itself.

## Evidence

- Selected target id and URL.
- Console errors or absence.
- Screenshots when visual behavior matters.
- DOM/computed style/box metrics for layout or clipping fixes.
- Interaction method, such as mouse event or forced pseudo-state.

## Verify Before Use

Confirm DesktopShell is running with the expected remote debugging port.
Run `ensure-desktop-shell-cdp-host` before giving up on validation: reuse a
valid running target, start the host when no process owns the CDP port, or
identify the port owner and report a blocker before manual acceptance.
