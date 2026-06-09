#!/usr/bin/env bash

set -euo pipefail

ENDPOINT="http://127.0.0.1:9222"
TARGET_KIND="host-app"
TARGETS_JSON=""
JSON_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --endpoint) ENDPOINT="${2:-}"; shift 2 ;;
        --target-kind) TARGET_KIND="${2:-}"; shift 2 ;;
        --targets-json) TARGETS_JSON="${2:-}"; shift 2 ;;
        --json) JSON_MODE=true; shift ;;
        --help|-h)
            echo "Usage: ensure-desktop-shell-cdp-host.sh [--endpoint http://127.0.0.1:9222] [--target-kind host-app|workbench] [--targets-json <json>] [--json]"
            echo "Probes DesktopShell CDP readiness and reports recoverable host/port facts before UI validation."
            exit 0
            ;;
        *) echo "ERROR: Unknown option '$1'" >&2; exit 1 ;;
    esac
done

if [[ "$TARGET_KIND" != "host-app" && "$TARGET_KIND" != "workbench" ]]; then
    echo "ERROR: --target-kind must be host-app or workbench" >&2
    exit 1
fi

ENDPOINT="$ENDPOINT" TARGET_KIND="$TARGET_KIND" TARGETS_JSON="$TARGETS_JSON" JSON_MODE="$JSON_MODE" python3 - <<'PY'
import json
import os
import re
import sys
import urllib.request

endpoint = os.environ["ENDPOINT"]
target_kind = os.environ["TARGET_KIND"]
targets_json = os.environ.get("TARGETS_JSON", "")
json_mode = os.environ.get("JSON_MODE", "false").lower() == "true"

hints = [
    "If a usable DesktopShell target is already running, reuse it instead of starting a second host.",
    "If CDP is unreachable and no process owns the port, start DesktopShell from <host-app-root> with npm run debug, then rerun this probe.",
    "If another process owns the CDP port, identify it before stopping; destructive process termination requires explicit human approval.",
    "Do not switch to human acceptance until this probe and the target inventory prove host/CDP is unavailable.",
]
facts = {
    "endpoint": endpoint,
    "target_kind": target_kind,
    "endpoint_reachable": False,
    "page_targets": [],
    "rejected_targets": [],
    "selected_target": None,
    "port_owners": [],
}
blockers = []
unknowns = []

def reason(title: str, url: str) -> str:
    if "DevTools" in title or url.startswith("devtools://"):
        return "devtools"
    if "Plugin Workbench" in title or re.search(r"plugin-workbench\.html", url):
        return "workbench"
    if "base-win.html" in url:
        return "base-window"
    if url == "" or "about:blank" in url:
        return "blank"
    if re.search(r"product-homepage|product-main-window|frontend/static/index\.html", url):
        return "host-app"
    return "unknown"

try:
    if targets_json:
        targets = json.loads(targets_json)
    else:
        with urllib.request.urlopen(endpoint.rstrip("/") + "/json/list", timeout=3) as response:
            targets = json.loads(response.read().decode("utf-8"))
    facts["endpoint_reachable"] = True
except Exception as exc:
    blockers.append(
        "CDP endpoint is unreachable; start or recover DesktopShell with npm run debug, inspect any port owner, then rerun this probe before manual acceptance."
    )
    payload = {
        "tool": "ensure-desktop-shell-cdp-host",
        "status": "blocked",
        "facts": facts,
        "blockers": blockers,
        "unknowns": unknowns,
        "hints": hints + [str(exc)],
    }
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) if json_mode else payload["status"])
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
    record["reason"] = reason(record["title"], record["url"])
    facts["page_targets"].append(record)

for target in facts["page_targets"]:
    if target_kind == "host-app" and target["reason"] == "host-app":
        facts["selected_target"] = target
        break
    if target_kind == "workbench" and target["reason"] == "workbench":
        facts["selected_target"] = target
        break

for target in facts["page_targets"]:
    if facts["selected_target"] and target["id"] == facts["selected_target"]["id"]:
        continue
    if target["reason"] in {"devtools", "workbench", "base-window", "blank"}:
        facts["rejected_targets"].append(target)

if not facts["selected_target"]:
    blockers.append(
        f"CDP is reachable, but no matching DesktopShell target was found for TargetKind '{target_kind}'; navigate/reuse the host before manual acceptance."
    )
if not facts["page_targets"]:
    unknowns.append("No page targets were returned by CDP.")

payload = {
    "tool": "ensure-desktop-shell-cdp-host",
    "status": "blocked" if blockers else "ok",
    "facts": facts,
    "blockers": blockers,
    "unknowns": unknowns,
    "hints": hints,
}
if json_mode:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
else:
    print("status: " + payload["status"])
    if facts["selected_target"]:
        print("selected_target: " + facts["selected_target"]["url"])
    for blocker in blockers:
        print(" - " + blocker, file=sys.stderr)
sys.exit(1 if blockers else 0)
PY
