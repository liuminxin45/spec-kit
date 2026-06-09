#!/usr/bin/env bash
set -euo pipefail

SDK_LOG_DIR="C:\\Windows\\Temp\\ExampleSdkLog"
BIZ_LOG_DIR="C:\\Windows\\Temp\\NativeBridgeLog"
BROWSER_URL="http://127.0.0.1:9222"
TARGET_URL_PATTERN="product-homepage|product-main-window|frontend/static/index.html"
JSON=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sdk-log-dir)
      SDK_LOG_DIR="${2:-}"
      shift 2
      ;;
    --biz-log-dir)
      BIZ_LOG_DIR="${2:-}"
      shift 2
      ;;
    --browser-url)
      BROWSER_URL="${2:-}"
      shift 2
      ;;
    --target-url-pattern)
      TARGET_URL_PATTERN="${2:-}"
      shift 2
      ;;
    --json)
      JSON=true
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 64
      ;;
  esac
done

json_escape() {
  python -c 'import json,sys; print(json.dumps(sys.stdin.read().rstrip("\n")))' 2>/dev/null || printf '"%s"' "$1"
}

latest_log_json() {
  local dir="$1"
  local pattern="$2"
  local file=""

  if [[ ! -d "$dir" ]]; then
    printf '{"found":false,"directory":%s,"pattern":%s,"path":null,"lastWriteTime":null,"length":null,"reason":"directory-not-found"}' \
      "$(printf '%s' "$dir" | json_escape)" \
      "$(printf '%s' "$pattern" | json_escape)"
    return
  fi

  file="$(find "$dir" -maxdepth 1 -type f -name "$pattern" -printf '%f\t%T@\t%p\n' 2>/dev/null |
    python -c 'import re,sys
rows=[]
for line in sys.stdin:
    name, mtime, path = line.rstrip("\n").split("\t", 2)
    m = re.search(r"(\d{14})(?=\.log$)", name)
    rows.append((m.group(1) if m else "", float(mtime), path))
rows.sort(reverse=True)
print(rows[0][2] if rows else "")' || true)"
  if [[ -z "$file" ]]; then
    printf '{"found":false,"directory":%s,"pattern":%s,"path":null,"lastWriteTime":null,"length":null,"reason":"log-not-found"}' \
      "$(printf '%s' "$dir" | json_escape)" \
      "$(printf '%s' "$pattern" | json_escape)"
    return
  fi

  local mtime=""
  local length=""
  mtime="$(python -c 'import datetime,os,sys; print(datetime.datetime.fromtimestamp(os.path.getmtime(sys.argv[1])).astimezone().isoformat())' "$file")"
  length="$(python -c 'import os,sys; print(os.path.getsize(sys.argv[1]))' "$file")"
  printf '{"found":true,"directory":%s,"pattern":%s,"path":%s,"lastWriteTime":%s,"length":%s,"reason":null}' \
    "$(printf '%s' "$dir" | json_escape)" \
    "$(printf '%s' "$pattern" | json_escape)" \
    "$(printf '%s' "$file" | json_escape)" \
    "$(printf '%s' "$mtime" | json_escape)" \
    "$length"
}

devtools_json() {
  local url="${BROWSER_URL%/}"
  local version_url="$url/json/version"
  local targets_url="$url/json/list"

  if ! command -v curl >/dev/null 2>&1; then
    printf '{"available":false,"browserUrl":%s,"versionUrl":%s,"targetsUrl":%s,"browser":null,"protocolVersion":null,"targets":[],"error":"curl-not-found"}' \
      "$(printf '%s' "$url" | json_escape)" \
      "$(printf '%s' "$version_url" | json_escape)" \
      "$(printf '%s' "$targets_url" | json_escape)"
    return
  fi

  local version targets
  if ! version="$(curl -fsS --max-time 2 "$version_url" 2>/dev/null)"; then
    printf '{"available":false,"browserUrl":%s,"versionUrl":%s,"targetsUrl":%s,"browser":null,"protocolVersion":null,"targets":[],"error":"devtools-unavailable"}' \
      "$(printf '%s' "$url" | json_escape)" \
      "$(printf '%s' "$version_url" | json_escape)" \
      "$(printf '%s' "$targets_url" | json_escape)"
    return
  fi

  targets="$(curl -fsS --max-time 2 "$targets_url" 2>/dev/null || printf '[]')"
  python - "$url" "$version_url" "$targets_url" "$TARGET_URL_PATTERN" "$version" "$targets" <<'PY'
import json, re, sys
url, version_url, targets_url, target_pattern, version_raw, targets_raw = sys.argv[1:]
try:
    version = json.loads(version_raw)
except Exception:
    version = {}
try:
    targets = json.loads(targets_raw)
except Exception:
    targets = []
summary = []
for target in targets:
    summary.append({
        "id": target.get("id"),
        "type": target.get("type"),
        "title": target.get("title"),
        "url": target.get("url"),
        "webSocketDebuggerUrl": target.get("webSocketDebuggerUrl"),
    })
page_targets = [item for item in summary if item.get("type") == "page" and not str(item.get("url") or "").startswith("devtools://")]
selected = None
if target_pattern:
    pattern = re.compile(target_pattern)
    for item in page_targets:
        if pattern.search(str(item.get("url") or "")) or pattern.search(str(item.get("title") or "")):
            selected = item
            break
if selected is None:
    selected = next((item for item in page_targets if str(item.get("url") or "").startswith(("http://", "https://"))), None)
if selected is None and page_targets:
    selected = page_targets[0]
print(json.dumps({
    "available": True,
    "browserUrl": url,
    "versionUrl": version_url,
    "targetsUrl": targets_url,
    "browser": version.get("Browser"),
    "protocolVersion": version.get("Protocol-Version"),
    "targets": summary,
    "targetUrlPattern": target_pattern,
    "selectedTarget": selected,
    "directCdp": {
        "available": False,
        "error": "direct-cdp-fallback-is-powershell-only",
    },
    "error": None,
}, separators=(",", ":")))
PY
}

generated_at="$(python -c 'import datetime; print(datetime.datetime.now().astimezone().isoformat())')"
printf '{"generatedAt":%s,"defaults":{"sdkLogDir":"C:\\\\Windows\\\\Temp\\\\ExampleSdkLog","bizLogDir":"C:\\\\Windows\\\\Temp\\\\NativeBridgeLog","browserUrl":"http://127.0.0.1:9222","targetUrlPattern":"product-homepage|product-main-window|frontend/static/index.html"},"sdkLog":%s,"bizLog":%s,"devtools":%s}\n' \
  "$(printf '%s' "$generated_at" | json_escape)" \
  "$(latest_log_json "$SDK_LOG_DIR" "SDK_*.log")" \
  "$(latest_log_json "$BIZ_LOG_DIR" "NativeBridge_*.log")" \
  "$(devtools_json)"
