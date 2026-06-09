#!/usr/bin/env bash
set -euo pipefail

checklist_path=""
feature_dir=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --checklist)
      checklist_path="${2:-}"
      shift 2
      ;;
    --feature-dir)
      feature_dir="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$feature_dir" && -f ".specify/feature.json" ]]; then
  feature_dir="$(python - <<'PY'
import json
from pathlib import Path
print(json.loads(Path(".specify/feature.json").read_text(encoding="utf-8")).get("feature_directory", ""))
PY
)"
fi

if [[ -z "$feature_dir" ]]; then
  echo "Feature directory is required when .specify/feature.json is unavailable." >&2
  exit 1
fi

if [[ -z "$checklist_path" ]]; then
  checklist_path="$feature_dir/checklists/requirements.md"
fi

if [[ ! -f "$checklist_path" ]]; then
  echo "Checklist not found: $checklist_path" >&2
  exit 1
fi

if [[ ! -f "$feature_dir/spec.md" ]]; then
  echo "Spec not found: $feature_dir/spec.md" >&2
  exit 1
fi

python - "$checklist_path" <<'PY'
import re
import sys
from collections import Counter
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
patterns = [
    r"\[CHECKLIST TYPE\]",
    r"\[CAPABILITY NAME\]",
    r"\[DATE\]",
    r"\[Link to spec\.md\]",
    r"\bTBD\b",
    r"\bTODO\b",
]
for pattern in patterns:
    if re.search(pattern, text):
        raise SystemExit(f"Checklist contains unresolved placeholder or TODO matching: {pattern}")

ids = [
    match.group(1)
    for line in text.splitlines()
    if (match := re.match(r"^- \[[ xX]\]\s*(CHK[0-9A-Z]+)\b", line))
]
duplicates = sorted(item for item, count in Counter(ids).items() if count > 1)
if duplicates:
    raise SystemExit("Checklist contains duplicate CHK identifiers: " + ", ".join(duplicates))

for line in text.splitlines():
    if re.match(r"^- \[[ xX]\].*N/A\s*$", line):
        raise SystemExit("N/A checklist line must include a reason: " + line)
    if re.match(r"^- \[ \].*$", line) and not re.search(r"(缺失|待|需要|原因|gap|N/A|NEEDS CLARIFICATION)", line):
        raise SystemExit("Unchecked checklist line must include a reason or follow-up: " + line)

if "spec.md" not in text:
    raise SystemExit("Checklist must link or refer to spec.md.")
PY

echo "Checklist validation passed: $checklist_path"
