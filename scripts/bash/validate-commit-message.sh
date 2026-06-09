#!/usr/bin/env bash

set -euo pipefail

JSON_MODE=false
MESSAGE=""
MESSAGE_FILE=""
READ_STDIN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json) JSON_MODE=true; shift ;;
        --message) MESSAGE="${2:-}"; shift 2 ;;
        --message-file) MESSAGE_FILE="${2:-}"; shift 2 ;;
        --stdin) READ_STDIN=true; shift ;;
        --help|-h)
            echo "Usage: validate-commit-message.sh [--message <text> | --message-file <path> | --stdin] [--json]"
            echo "Validates the DesktopShell / project Chinese commit-message template."
            exit 0
            ;;
        *) echo "ERROR: Unknown option '$1'" >&2; exit 1 ;;
    esac
done

if [[ "$READ_STDIN" == "true" ]]; then
    MESSAGE="$(cat)"
elif [[ -n "$MESSAGE_FILE" ]]; then
    MESSAGE="$(cat "$MESSAGE_FILE")"
fi

if command -v python3 >/dev/null 2>&1; then
    MESSAGE_PAYLOAD="$MESSAGE" python3 - "$JSON_MODE" <<'PY'
import json
import os
import re
import sys

json_mode = sys.argv[1].lower() == "true"
message = os.environ.get("MESSAGE_PAYLOAD", "").replace("\r\n", "\n")
lines = message.split("\n")
non_empty = [line for line in lines if line.strip()]
required = [
    "【提交类型】",
    "【问题描述】",
    "【修改方案】",
    "【影响评估】",
    "【兼容性分析】",
    "【需要同时入库的提交】",
    "【自测结果】",
]
blockers = []

if not non_empty:
    blockers.append("Commit message is empty.")

for section in required:
    if section not in lines:
        blockers.append(f"Missing required section: {section}")
        continue
    index = lines.index(section)
    has_content = False
    for line in lines[index + 1:]:
        if line in required or line.startswith("Change-Id:"):
            break
        if line.strip():
            has_content = True
            break
    if not has_content:
        blockers.append(f"Required section has no content: {section}")

if non_empty and non_empty[0].startswith("【"):
    blockers.append("Missing subject line before template sections.")
if len(non_empty) < 2:
    blockers.append("Missing Chinese summary line after subject.")
elif non_empty[1].startswith("【"):
    blockers.append("Missing Chinese summary line before template sections.")

def display_width(text: str) -> int:
    return sum(1 if ord(ch) <= 0x7f else 2 for ch in text)

def contains_cjk(text: str) -> bool:
    return any(0x4E00 <= ord(ch) <= 0x9FFF for ch in text)

def section_content(section: str) -> list[str]:
    if section not in lines:
        return []
    index = lines.index(section)
    content = []
    for line in lines[index + 1:]:
        if line in required or line.startswith("Change-Id:"):
            break
        if line.strip():
            content.append(line)
    return content

if non_empty:
    subject = non_empty[0]
    if re.match(r"^(fix|feat|chore|docs|refactor|test|tests|build|ci|perf|style|revert)(\(|:)", subject):
        blockers.append(f"Subject must use '<Module>: <concise English summary>', not Conventional Commit format: {subject}")
    if not re.match(r"^[A-Za-z][A-Za-z0-9._/-]*:\s+\S", subject):
        blockers.append(f"Subject must use '<Module>: <concise English summary>': {subject}")

if len(non_empty) >= 2 and not non_empty[1].startswith("【") and not contains_cjk(non_empty[1]):
    blockers.append(f"Second non-empty line must be the Chinese summary, not a wrapped subject line: {non_empty[1]}")

type_lines = section_content("【提交类型】")
if type_lines and " - " not in type_lines[0]:
    blockers.append(f"【提交类型】 must use '<类型> - <范围或问题域>': {type_lines[0]}")
generic_type_blocklist = [
    "修复 - UI 交互",
    "修复 - 代码",
    "修复 - 逻辑",
    "缺陷修复 - UI",
    "缺陷修复 - 前端",
]
if type_lines and type_lines[0].strip() in generic_type_blocklist:
    blockers.append(f"【提交类型】 scope is too generic; name the concrete module or problem domain: {type_lines[0]}")

self_test_lines = section_content("【自测结果】")
if self_test_lines and "相关测试通过，自测通过" not in self_test_lines[-1]:
    blockers.append(f"【自测结果】 must end with '相关测试通过，自测通过' when validation passes: {self_test_lines[-1]}")

for line in non_empty:
    width = display_width(line)
    if width > 68:
        blockers.append(f"Line exceeds 68 display columns ({width}): {line}")
    if re.search(r"[A-Za-z_][A-Za-z0-9_]*::$", line):
        blockers.append(f"Technical token appears split across lines: {line}")

if "【提交类型】\n\nChange-Id:" in message:
    blockers.append("Commit message appears truncated after 【提交类型】.")

payload = {
    "tool": "validate-commit-message",
    "status": "ok" if not blockers else "blocked",
    "facts": {
        "required_sections": required,
        "non_empty_line_count": len(non_empty),
        "generic_type_blocklist": generic_type_blocklist,
    },
    "blockers": blockers,
    "unknowns": [],
    "hints": [],
}

if json_mode:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
elif blockers:
    print("Commit message template validation failed:", file=sys.stderr)
    for blocker in blockers:
        print(f" - {blocker}", file=sys.stderr)
else:
    print("Commit message template validation passed.")

sys.exit(1 if blockers else 0)
PY
    exit $?
fi

echo "ERROR: python3 is required for validate-commit-message.sh" >&2
exit 1
