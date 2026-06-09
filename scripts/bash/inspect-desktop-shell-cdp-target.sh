#!/usr/bin/env bash

set -euo pipefail

JSON_MODE=false
ENDPOINT="http://127.0.0.1:9222"
TARGET_KIND="host-app"
TARGETS_JSON=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json) JSON_MODE=true; shift ;;
        --endpoint) ENDPOINT="${2:-}"; shift 2 ;;
        --target-kind) TARGET_KIND="${2:-}"; shift 2 ;;
        --targets-json) TARGETS_JSON="${2:-}"; shift 2 ;;
        --help|-h)
            echo "Usage: inspect-desktop-shell-cdp-target.sh [--endpoint http://127.0.0.1:9222] [--target-kind host-app|workbench] [--targets-json <json>] [--json]"
            echo "Selects the correct DesktopShell CDP page target and rejects DevTools, base-win, blank, and wrong-process targets."
            exit 0
            ;;
        *) echo "ERROR: Unknown option '$1'" >&2; exit 1 ;;
    esac
done

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required for inspect-desktop-shell-cdp-target.sh" >&2
    exit 1
fi

python3 - "$JSON_MODE" "$ENDPOINT" "$TARGET_KIND" "$TARGETS_JSON" <<'PY'
import json
import sys
import urllib.request

json_mode = sys.argv[1].lower() == "true"
endpoint = sys.argv[2].rstrip("/")
target_kind = sys.argv[3]
targets_json = sys.argv[4]

blockers = []
unknowns = []
hints = [
    "Record selected target id, title, url, and webSocketDebuggerUrl before collecting DOM or screenshot evidence.",
    "Use Plugin Workbench only for plugin-host/workbench validation; it is wrong-target evidence for product UI.",
]
facts = {
    "endpoint": endpoint,
    "target_kind": target_kind,
    "page_targets": [],
    "rejected_targets": [],
    "selected_target": None,
}

def emit(status):
    payload = {
        "tool": "inspect-desktop-shell-cdp-target",
        "status": status,
        "facts": facts,
        "blockers": blockers,
        "unknowns": unknowns,
        "hints": hints,
    }
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    elif status == "ok":
        print("DesktopShell CDP target selected.")
    else:
        print("DesktopShell CDP target selection failed:", file=sys.stderr)
        for blocker in blockers:
            print(f" - {blocker}", file=sys.stderr)

def reason_for(title, url):
    if "DevTools" in title or url.startswith("devtools://"):
        return "devtools"
    if "Plugin Workbench" in title or "plugin-workbench.html" in url:
        return "workbench"
    if "base-win.html" in url:
        return "base-window"
    if not url or "about:blank" in url:
        return "blank"
    if any(pattern in url for pattern in ["product-homepage", "product-main-window", "frontend/static/index.html"]):
        return "host-app"
    return "unknown"

try:
    if targets_json.strip():
        targets = json.loads(targets_json)
    else:
        with urllib.request.urlopen(endpoint + "/json/list", timeout=3) as response:
            targets = json.loads(response.read().decode("utf-8"))
except Exception as exc:
    blockers.append(f"Unable to read CDP targets from {endpoint}/json/list: {exc}")
    emit("blocked")
    sys.exit(1)

for target in targets:
    if str(target.get("type", "")) != "page":
        continue
    record = {
        "id": str(target.get("id", "")),
        "type": str(target.get("type", "")),
        "title": str(target.get("title", "")),
        "url": str(target.get("url", "")),
        "webSocketDebuggerUrl": str(target.get("webSocketDebuggerUrl", "")),
    }
    record["reason"] = reason_for(record["title"], record["url"])
    facts["page_targets"].append(record)

for target in facts["page_targets"]:
    if target_kind == "host-app" and target["reason"] == "host-app":
        facts["selected_target"] = target
        break
    if target_kind == "workbench" and target["reason"] == "workbench":
        facts["selected_target"] = target
        break

selected_id = facts["selected_target"]["id"] if facts["selected_target"] else None
for target in facts["page_targets"]:
    if selected_id and target["id"] == selected_id:
        continue
    if target["reason"] in {"devtools", "workbench", "base-window", "blank"}:
        facts["rejected_targets"].append(target)

if target_kind not in {"host-app", "workbench"}:
    blockers.append("TargetKind must be host-app or workbench.")
if not facts["selected_target"]:
    blockers.append(f"No matching DesktopShell CDP target found for TargetKind '{target_kind}'.")
if not facts["page_targets"]:
    unknowns.append("No page targets were returned by CDP.")

status = "blocked" if blockers else "ok"
emit(status)
sys.exit(1 if blockers else 0)
PY
