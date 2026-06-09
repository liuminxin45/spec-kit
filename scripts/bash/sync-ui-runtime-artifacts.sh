#!/usr/bin/env bash

set -euo pipefail

JSON_MODE=false
SOURCE_DIR=""
RUNTIME_DIR=""
PLUGIN_ID=""
REFRESH_COMMAND=""
DRY_RUN=false
KEEP_STALE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json) JSON_MODE=true; shift ;;
        --source-dir) SOURCE_DIR="${2:-}"; shift 2 ;;
        --runtime-dir) RUNTIME_DIR="${2:-}"; shift 2 ;;
        --plugin-id) PLUGIN_ID="${2:-}"; shift 2 ;;
        --refresh-command) REFRESH_COMMAND="${2:-}"; shift 2 ;;
        --keep-stale) KEEP_STALE=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h)
            echo "Usage: sync-ui-runtime-artifacts.sh --source-dir <dir> --runtime-dir <dir> --plugin-id <id> [--refresh-command <command>] [--keep-stale] [--dry-run] [--json]"
            echo "Mirrors built UI artifacts from repository source output into an explicit host-served runtime plugin directory, then optionally runs a refresh command."
            exit 0
            ;;
        *) echo "ERROR: Unknown option '$1'" >&2; exit 1 ;;
    esac
done

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required for sync-ui-runtime-artifacts.sh" >&2
    exit 1
fi

python3 - "$JSON_MODE" "$SOURCE_DIR" "$RUNTIME_DIR" "$PLUGIN_ID" "$REFRESH_COMMAND" "$DRY_RUN" "$KEEP_STALE" <<'PY'
import json
import pathlib
import shutil
import subprocess
import sys

json_mode = sys.argv[1].lower() == "true"
source_arg = sys.argv[2]
runtime_arg = sys.argv[3]
plugin_id = sys.argv[4]
refresh_command = sys.argv[5]
dry_run = sys.argv[6].lower() == "true"
keep_stale = sys.argv[7].lower() == "true"

blockers = []
unknowns = []
hints = [
    "Treat the runtime directory as validation/deployment output only; keep durable fixes in repository source.",
    "This script mirrors current source output into one explicit plugin runtime directory and removes stale files by default.",
]

facts = {
    "source_dir": source_arg,
    "runtime_dir": runtime_arg,
    "plugin_id": plugin_id,
    "dry_run": dry_run,
    "copied_entry_count": 0,
    "copied_file_count": 0,
    "removed_stale_count": 0,
    "keep_stale": keep_stale,
    "refresh_command": refresh_command,
    "refresh_exit_code": None,
}

def emit(status: str) -> None:
    payload = {
        "tool": "sync-ui-runtime-artifacts",
        "status": status,
        "facts": facts,
        "blockers": blockers,
        "unknowns": unknowns,
        "hints": hints,
    }
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    elif status == "ok":
        print("UI runtime artifacts synchronized.")
    else:
        print("UI runtime artifact synchronization failed:", file=sys.stderr)
        for blocker in blockers:
            print(f" - {blocker}", file=sys.stderr)

def is_subpath(child: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        child.relative_to(parent)
        return child != parent
    except ValueError:
        return False

if not source_arg.strip():
    blockers.append("SourceDir is required.")
if not runtime_arg.strip():
    blockers.append("RuntimeDir is required.")
if not plugin_id.strip():
    blockers.append("PluginId is required so stale runtime cleanup is scoped to one explicit plugin directory.")
if blockers:
    emit("blocked")
    sys.exit(1)

source = pathlib.Path(source_arg).expanduser().resolve()
runtime = pathlib.Path(runtime_arg).expanduser().resolve()
facts["source_dir"] = str(source)
facts["runtime_dir"] = str(runtime)

if not source.is_dir():
    blockers.append(f"SourceDir does not exist or is not a directory: {source_arg}")
if source == runtime:
    blockers.append("SourceDir and RuntimeDir must be different directories.")
if is_subpath(runtime, source):
    blockers.append("RuntimeDir must not be inside SourceDir; copying would recurse into its own output.")
if is_subpath(source, runtime):
    blockers.append("SourceDir must not be inside RuntimeDir; runtime artifacts cannot be treated as source.")
if not runtime.parent.is_dir():
    blockers.append(f"RuntimeDir parent does not exist: {runtime_arg}")
if plugin_id.strip() and runtime.name != plugin_id:
    blockers.append(f"RuntimeDir leaf '{runtime.name}' must match PluginId '{plugin_id}' before runtime replacement is allowed.")

if blockers:
    emit("blocked")
    sys.exit(1)

entries = list(source.iterdir())
files = [path for path in source.rglob("*") if path.is_file()]
facts["copied_entry_count"] = len(entries)
facts["copied_file_count"] = len(files)

if not dry_run:
    runtime.mkdir(parents=False, exist_ok=True)
    if not keep_stale:
        stale_entries = list(runtime.iterdir())
        facts["removed_stale_count"] = len(stale_entries)
        for stale in stale_entries:
            if stale.is_dir():
                shutil.rmtree(stale)
            else:
                stale.unlink()
    else:
        hints.append("KeepStale kept existing runtime files; stale split chunks may still be loaded.")

    for entry in entries:
        target = runtime / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)

    if refresh_command.strip():
        completed = subprocess.run(refresh_command, shell=True)
        facts["refresh_exit_code"] = completed.returncode
        if completed.returncode != 0:
            blockers.append(f"RefreshCommand failed with exit code {completed.returncode}.")
else:
    if runtime.is_dir():
        facts["removed_stale_count"] = len(list(runtime.iterdir()))
    if refresh_command.strip():
        hints.append("DryRun skipped RefreshCommand.")

emit("ok" if not blockers else "blocked")
sys.exit(0 if not blockers else 1)
PY
