#!/usr/bin/env bash

set -euo pipefail

JSON_MODE=false
KEEP_BRANCH=true
ALLOW_DIRTY=false
CONFIRM_COMPLETION=false
PREFLIGHT_ONLY=false
BRANCH_NAME=""
BASE_BRANCH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json) JSON_MODE=true; shift ;;
        --keep-branch) KEEP_BRANCH=true; shift ;;
        --delete-branch) KEEP_BRANCH=false; shift ;;
        --allow-dirty) ALLOW_DIRTY=true; shift ;;
        --confirm-completion) CONFIRM_COMPLETION=true; shift ;;
        --preflight-only|--dry-run) PREFLIGHT_ONLY=true; shift ;;
        --branch) BRANCH_NAME="${2:-}"; shift 2 ;;
        --base-branch) BASE_BRANCH="${2:-}"; shift 2 ;;
        --help|-h)
            echo "Usage: complete-spec-branches.sh [--branch <name>] [--base-branch master|main] [--keep-branch] [--delete-branch] [--allow-dirty] [--preflight-only] [--confirm-completion] [--json]"
            echo "Cherry-picks local spec branch commits into the base branch and keeps the local spec branch by default."
            echo "Use --preflight-only to inspect every repository without cherry-picking commits."
            echo "Requires feature retrospective artifacts before completion: workflow-record.md and improvement-candidates.md."
            echo "Requires --confirm-completion because cherry-pick changes repository state."
            exit 0
            ;;
        *) echo "ERROR: Unknown option '$1'" >&2; exit 1 ;;
    esac
done

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

read_workspace() {
    local repo_root="$1"
    local cfg="$repo_root/.specify/workspace.yml"
    local workspace_root
    workspace_root="$(cd "$repo_root/.." && pwd)"
    local base_branch="master"
    local repos=()

    if [[ -f "$cfg" ]]; then
        local root_value
        root_value=$(sed -nE 's/^[[:space:]]*root:[[:space:]]*"?([^"]+)"?[[:space:]]*$/\1/p' "$cfg" | head -n 1)
        if [[ -n "$root_value" ]]; then
            case "$root_value" in
                /*) workspace_root="$root_value" ;;
                *) workspace_root="$(cd "$repo_root/$root_value" && pwd)" ;;
            esac
        fi
        local configured_base
        configured_base=$(sed -nE 's/^[[:space:]]*default_base_branch:[[:space:]]*"?([^"]+)"?[[:space:]]*$/\1/p' "$cfg" | head -n 1)
        [[ -n "$configured_base" ]] && base_branch="$configured_base"

        local current_name="" current_path="" current_required="false"
        while IFS= read -r line; do
            if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*name:[[:space:]]*\"?([^\"]+)\"?[[:space:]]*$ ]]; then
                if [[ -n "$current_name" ]]; then
                    repos+=("$current_name|$current_path|$current_required")
                fi
                current_name="${BASH_REMATCH[1]}"
                current_path=""
                current_required="false"
            elif [[ -n "$current_name" && "$line" =~ ^[[:space:]]*path:[[:space:]]*\"?([^\"]+)\"?[[:space:]]*$ ]]; then
                current_path="${BASH_REMATCH[1]}"
            elif [[ -n "$current_name" && "$line" =~ ^[[:space:]]*required:[[:space:]]*(true|false)[[:space:]]*$ ]]; then
                current_required="${BASH_REMATCH[1]}"
            fi
        done < "$cfg"
        if [[ -n "$current_name" ]]; then
            repos+=("$current_name|$current_path|$current_required")
        fi
    fi
    [[ ${#repos[@]} -gt 0 ]] || repos+=("$(basename "$repo_root")|$(basename "$repo_root")|true")
    [[ -n "$BASE_BRANCH" ]] || BASE_BRANCH="$base_branch"

    printf 'BASE_BRANCH=%q\n' "$BASE_BRANCH"
    printf 'WORKSPACE_ROOT=%q\n' "$workspace_root"
    local i=0
    for repo in "${repos[@]}"; do
        IFS='|' read -r name path required <<< "$repo"
        [[ "$path" = /* ]] || path="$workspace_root/$path"
        printf 'REPO_%d_NAME=%q\n' "$i" "$name"
        printf 'REPO_%d_PATH=%q\n' "$i" "$path"
        printf 'REPO_%d_REQUIRED=%q\n' "$i" "$required"
        i=$((i + 1))
    done
    printf 'REPO_COUNT=%q\n' "$i"
}

is_git_repo() { [[ -d "$1" ]] && git -C "$1" rev-parse --is-inside-work-tree >/dev/null 2>&1; }
is_generated_or_temp_path() {
    local path
    path=$(printf '%s' "$1" | tr '\\' '/' | tr '[:upper:]' '[:lower:]')
    case "$path" in
        .agents/*|.specify/*|ai/*|specs/*|sdkarchive/*|*/.agents/*|*/.specify/*|*/ai/*|*/specs/*|*/sdkarchive/*|\
        mock_data/api/pluginmanager/*|*/mock_data/api/pluginmanager/*|\
        __pycache__/*|*/__pycache__/*|.pytest_cache/*|*/.pytest_cache/*|\
        .mypy_cache/*|*/.mypy_cache/*|.ruff_cache/*|*/.ruff_cache/*|\
        .cache/*|*/.cache/*|node_modules/*|*/node_modules/*|\
        dist/*|*/dist/*|build/*|*/build/*|export/*|*/export/*|\
        plugin-out/*|*/plugin-out/*|coverage/*|*/coverage/*|\
        log/*|logs/*|*/log/*|*/logs/*|tmp/*|temp/*|*/tmp/*|*/temp/*|\
        *.log|*.tmp|*.temp|*.bak|*.swp|*.pid|*.dmp|*.cache|*.pyc|*.pyo|*.obj|*.ilk|*.pdb|\
        thumbs.db|*/thumbs.db|.ds_store|*/.ds_store)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}
is_dirty() {
    local line candidate
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        if [[ "$line" == "?? "* ]]; then
            candidate="${line:3}"
            if is_generated_or_temp_path "$candidate"; then
                continue
            fi
        fi
        return 0
    done < <(git -C "$1" status --porcelain)
    return 1
}
dirty_summary() {
    local line candidate
    local tracked=0 ignored_untracked=0 unclassified_untracked=0
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        if [[ "$line" == "?? "* ]]; then
            candidate="${line:3}"
            if is_generated_or_temp_path "$candidate"; then
                ignored_untracked=$((ignored_untracked + 1))
            else
                unclassified_untracked=$((unclassified_untracked + 1))
            fi
        else
            tracked=$((tracked + 1))
        fi
    done < <(git -C "$1" status --porcelain)
    printf 'tracked=%s,ignored_untracked=%s,unclassified_untracked=%s' "$tracked" "$ignored_untracked" "$unclassified_untracked"
}
dirty_blocks_completion() {
    local path="$1"
    local commit_count="$2"
    local line candidate
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        if [[ "$line" == "?? "* ]]; then
            candidate="${line:3}"
            if is_generated_or_temp_path "$candidate"; then
                continue
            fi
            [[ "$commit_count" -eq 0 ]] || return 0
            continue
        fi
        return 0
    done < <(git -C "$path" status --porcelain)
    return 1
}
branch_exists() { git -C "$1" show-ref --verify --quiet "refs/heads/$2"; }
branch_has_upstream() { git -C "$1" rev-parse --abbrev-ref "$2@{upstream}" >/dev/null 2>&1; }
remote_divergence() {
    local upstream counts ahead behind
    upstream=$(git -C "$1" rev-parse --abbrev-ref "$2@{upstream}" 2>/dev/null) || {
        echo "no-upstream"
        return
    }
    counts=$(git -C "$1" rev-list --left-right --count "$2...$upstream" 2>/dev/null) || {
        echo "$upstream:unknown"
        return
    }
    read -r ahead behind <<< "$counts"
    echo "$upstream:ahead=$ahead,behind=$behind"
}
cherry_pick_commits() { git -C "$1" rev-list --reverse "$2..$3"; }
conflict_files() { git -C "$1" diff --name-only --diff-filter=U; }
run_cherry_pick() {
    local path="$1"
    local commit="$2"
    (cd "$path" && git cherry-pick "$commit" >/dev/null)
}
resolve_generated_artifact_conflicts() {
    local path="$1"
    shift
    local file
    [[ "$#" -gt 0 ]] || return 1
    for file in "$@"; do
        [[ -n "$file" ]] || continue
        if ! is_generated_or_temp_path "$file"; then
            return 1
        fi
    done
    for file in "$@"; do
        [[ -n "$file" ]] || continue
        git -C "$path" checkout --ours -- "$file" >/dev/null || return 1
        git -C "$path" add -- "$file" >/dev/null || return 1
    done
    if git -C "$path" -c core.editor=true cherry-pick --continue >/dev/null; then
        return 0
    fi
    git -C "$path" cherry-pick --skip >/dev/null
}

resolve_base_branch() {
    local path="$1"
    for candidate in "$BASE_BRANCH" master main; do
        [[ -n "$candidate" ]] || continue
        if branch_exists "$path" "$candidate"; then
            echo "$candidate"
            return
        fi
    done
    echo "ERROR: No base branch found in $path. Tried '$BASE_BRANCH', master, main." >&2
    return 1
}

resolve_feature_dir() {
    local repo_root="$1"
    local branch="$2"
    local feature_json="$repo_root/.specify/feature.json"

    if [[ -f "$feature_json" ]] && command -v python3 >/dev/null 2>&1; then
        python3 - "$feature_json" "$repo_root" "$branch" <<'PY'
import json
import os
import sys

feature_json, repo_root, branch = sys.argv[1:4]
try:
    with open(feature_json, encoding="utf-8") as handle:
        data = json.load(handle)
except Exception:
    data = {}

configured_branch = data.get("spec_branch") or ""
feature_dir = data.get("feature_directory") or ""
if feature_dir and (not configured_branch or configured_branch == branch):
    if os.path.isabs(feature_dir):
        print(feature_dir)
    else:
        print(os.path.join(repo_root, feature_dir))
else:
    print(os.path.join(repo_root, "specs", branch))
PY
        return
    fi

    printf '%s\n' "$repo_root/specs/$branch"
}

run_retrospective_gate() {
    local repo_root="$1"
    local branch="$2"
    RETRO_FEATURE_DIR="$(resolve_feature_dir "$repo_root" "$branch")"
    RETRO_REQUIRED=("workflow-record.md" "improvement-candidates.md")
    RETRO_MISSING=()

    local file_name
    for file_name in "${RETRO_REQUIRED[@]}"; do
        if [[ ! -f "$RETRO_FEATURE_DIR/$file_name" ]]; then
            RETRO_MISSING+=("$file_name")
        fi
    done

    if [[ ${#RETRO_MISSING[@]} -eq 0 ]]; then
        RETRO_STATUS="ok"
    else
        RETRO_STATUS="blocked"
    fi
}

json_escape_simple() { json_escape "$1"; }

preflight=()
errors=()
results=()
RETRO_FEATURE_DIR=""
RETRO_REQUIRED=()
RETRO_MISSING=()
RETRO_STATUS="blocked"

print_json_payload() {
    local action="$1"
    local confirmed="$2"
    local merge_ready="$3"
    local message="${4:-}"

    printf '{"branch":"%s","base_branch":"%s","confirmed":%s,"action":"%s","merge_ready":%s,"cherry_pick_ready":%s,"keep_branch":%s,"pushed":false' \
        "$(json_escape_simple "$BRANCH_NAME")" \
        "$(json_escape_simple "$BASE_BRANCH")" \
        "$confirmed" \
        "$(json_escape_simple "$action")" \
        "$merge_ready" \
        "$merge_ready" \
        "$KEEP_BRANCH"
    if [[ -n "$message" ]]; then
        printf ',"message":"%s"' "$(json_escape_simple "$message")"
    fi
    printf ',"retrospective_gate":{"feature_dir":"%s","required":[' "$(json_escape_simple "$RETRO_FEATURE_DIR")"
    local first_required=true
    local required_item
    for required_item in "${RETRO_REQUIRED[@]}"; do
        $first_required || printf ','
        first_required=false
        printf '"%s"' "$(json_escape_simple "$required_item")"
    done
    printf '],"missing":['
    local first_missing=true
    local missing_item
    for missing_item in "${RETRO_MISSING[@]}"; do
        $first_missing || printf ','
        first_missing=false
        printf '"%s"' "$(json_escape_simple "$missing_item")"
    done
    printf '],"status":"%s"}' "$(json_escape_simple "$RETRO_STATUS")"
    printf ',"preflight":['
    local first=true
    for item in "${preflight[@]}"; do
        IFS='|' read -r name path status branch base action_item remote_info dirty_info <<< "$item"
        $first || printf ','
        first=false
        printf '{"repository":"%s","path":"%s","status":"%s","branch":"%s","base":"%s","planned_action":"%s","remote_divergence":"%s","dirty_state":"%s"}' \
            "$(json_escape_simple "$name")" \
            "$(json_escape_simple "$path")" \
            "$(json_escape_simple "$status")" \
            "$(json_escape_simple "$branch")" \
            "$(json_escape_simple "$base")" \
            "$(json_escape_simple "$action_item")" \
            "$(json_escape_simple "${remote_info:-}")" \
            "$(json_escape_simple "${dirty_info:-}")"
    done
    printf '],"errors":['
    first=true
    for error in "${errors[@]}"; do
        $first || printf ','
        first=false
        printf '"%s"' "$(json_escape_simple "$error")"
    done
    printf '],"repositories":['
    first=true
    for result in "${results[@]}"; do
        IFS='|' read -r name path status branch base <<< "$result"
        $first || printf ','
        first=false
        printf '{"repository":"%s","path":"%s","status":"%s","branch":"%s","base":"%s"}' \
            "$(json_escape_simple "$name")" \
            "$(json_escape_simple "$path")" \
            "$(json_escape_simple "$status")" \
            "$(json_escape_simple "$branch")" \
            "$(json_escape_simple "$base")"
    done
    printf ']}\n'
}

repo_root=$(get_repo_root)
eval "$(read_workspace "$repo_root")"

if [[ -z "$BRANCH_NAME" && -f "$repo_root/.specify/feature.json" ]]; then
    if command -v python3 >/dev/null 2>&1; then
        BRANCH_NAME=$(python3 - "$repo_root/.specify/feature.json" <<'PY'
import json, os, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
print(data.get("spec_branch") or os.path.basename(data.get("feature_directory", "")))
PY
)
    fi
fi
if [[ -z "$BRANCH_NAME" ]]; then
    BRANCH_NAME=$(git -C "$repo_root" rev-parse --abbrev-ref HEAD)
fi
[[ -n "$BRANCH_NAME" && "$BRANCH_NAME" != "HEAD" ]] || { echo "ERROR: Could not resolve spec branch. Pass --branch." >&2; exit 1; }

run_retrospective_gate "$repo_root" "$BRANCH_NAME"
if [[ "$RETRO_STATUS" != "ok" ]]; then
    missing_text=""
    for missing_item in "${RETRO_MISSING[@]}"; do
        if [[ -n "$missing_text" ]]; then
            missing_text="$missing_text, "
        fi
        missing_text="$missing_text$missing_item"
    done
    errors+=("Retrospective gate failed for '$BRANCH_NAME': missing $missing_text in $RETRO_FEATURE_DIR. Run speckit.retrospective before complete-branch.")
fi

for (( i=0; i<REPO_COUNT; i++ )); do
    name_var="REPO_${i}_NAME"; path_var="REPO_${i}_PATH"; required_var="REPO_${i}_REQUIRED"
    name="${!name_var}"; path="${!path_var}"; required="${!required_var}"
    if [[ ! -d "$path" ]]; then
        preflight+=("$name|$path|missing|$BRANCH_NAME|$BASE_BRANCH|skip||")
        [[ "$required" != "true" ]] || errors+=("Required repository not found: $name")
        continue
    fi
    if ! is_git_repo "$path"; then
        preflight+=("$name|$path|not-git|$BRANCH_NAME|$BASE_BRANCH|error||")
        errors+=("Repository is not a git work tree: $name")
        continue
    fi
    dirty_info=$(dirty_summary "$path")
    if ! base=$(resolve_base_branch "$path"); then
        preflight+=("$name|$path|base-missing|$BRANCH_NAME|$BASE_BRANCH|error||$dirty_info")
        errors+=("No base branch found in $name. Tried '$BASE_BRANCH', master, main.")
        continue
    fi
    remote=$(remote_divergence "$path" "$base")
    if ! branch_exists "$path" "$BRANCH_NAME"; then
        if [[ "$ALLOW_DIRTY" != "true" ]] && dirty_blocks_completion "$path" 0; then
            preflight+=("$name|$path|dirty|$BRANCH_NAME|$base|error|$remote|$dirty_info")
            errors+=("Repository has tracked or blocking dirty changes: $name. Commit/stash them before completing the spec.")
            continue
        fi
        preflight+=("$name|$path|branch-missing|$BRANCH_NAME|$base|switch-to-base|$remote|$dirty_info")
        [[ "$required" != "true" ]] || errors+=("Required spec branch '$BRANCH_NAME' missing in $name")
        continue
    fi
    if branch_has_upstream "$path" "$BRANCH_NAME"; then
        preflight+=("$name|$path|branch-has-upstream|$BRANCH_NAME|$base|error|$remote|$dirty_info")
        errors+=("Spec branch '$BRANCH_NAME' in $name has an upstream; Spec Kit branches must stay local-only.")
        continue
    fi
    if [[ "$BRANCH_NAME" == "$base" ]]; then
        preflight+=("$name|$path|branch-is-base|$BRANCH_NAME|$base|error|$remote|$dirty_info")
        errors+=("Spec branch '$BRANCH_NAME' is the base branch in $name; refusing to complete.")
        continue
    fi
    commits=$(cherry_pick_commits "$path" "$base" "$BRANCH_NAME") || {
        preflight+=("$name|$path|cherry-pick-list-error|$BRANCH_NAME|$base|error|$remote|$dirty_info")
        errors+=("Could not resolve cherry-pick commit list for '$BRANCH_NAME' into '$base' in $name.")
        continue
    }
    commit_count=0
    if [[ -n "$commits" ]]; then
        commit_count=$(printf '%s\n' "$commits" | sed '/^[[:space:]]*$/d' | wc -l | tr -d '[:space:]')
    fi
    if [[ "$ALLOW_DIRTY" != "true" ]] && dirty_blocks_completion "$path" "$commit_count"; then
        preflight+=("$name|$path|dirty|$BRANCH_NAME|$base|error|$remote|$dirty_info")
        errors+=("Repository has tracked or blocking dirty changes: $name. Commit/stash them before completing the spec.")
        continue
    fi
    if [[ -z "$commits" ]]; then
        preflight+=("$name|$path|already-up-to-date|$BRANCH_NAME|$base|switch-to-base|$remote|$dirty_info")
        continue
    fi
    if [[ "$KEEP_BRANCH" == "true" ]]; then
        action="cherry-pick"
    else
        action="cherry-pick-and-delete"
    fi
    preflight+=("$name|$path|ready|$BRANCH_NAME|$base|$action|$remote|$dirty_info")
done

if [[ ${#errors[@]} -gt 0 ]]; then
    if $JSON_MODE; then
        print_json_payload "preflight-failed" "false" "false"
    else
        echo "ERROR: Preflight failed before cherry-picking spec branches:" >&2
        for error in "${errors[@]}"; do
            echo " - $error" >&2
        done
    fi
    exit 1
fi

if [[ "$PREFLIGHT_ONLY" == "true" || "$CONFIRM_COMPLETION" != "true" ]]; then
    if [[ "$PREFLIGHT_ONLY" == "true" ]]; then
        action_name="preflight-only"
        message=""
        exit_code=0
    else
        action_name="confirmation-required"
        if [[ "$KEEP_BRANCH" == "true" ]]; then
            branch_action="keeping local spec branches"
        else
            branch_action="deleting local spec branches"
        fi
        message="Confirmation required before cherry-picking spec branch '$BRANCH_NAME' into '$BASE_BRANCH' and $branch_action. Re-run with --confirm-completion only after explicit user approval."
        exit_code=2
    fi
    if $JSON_MODE; then
        print_json_payload "$action_name" "$CONFIRM_COMPLETION" "true" "$message"
    else
        echo "SPEC_BRANCH: $BRANCH_NAME"
        echo "PUSHED: false"
        echo "PREFLIGHT: passed"
        for item in "${preflight[@]}"; do
            IFS='|' read -r name path status branch base action_item remote_info dirty_info <<< "$item"
            echo "$name: $status -> $action_item on $base"
        done
        if [[ "$exit_code" -eq 2 ]]; then
            echo "ERROR: $message" >&2
        fi
    fi
    exit "$exit_code"
fi

for item in "${preflight[@]}"; do
    IFS='|' read -r name path status branch base action remote_info dirty_info <<< "$item"
    if [[ "$status" == "missing" ]]; then
        results+=("$name|$path|$status|$BRANCH_NAME|$base")
        continue
    fi
    if [[ "$status" == "branch-missing" || "$status" == "already-up-to-date" ]]; then
        git -C "$path" switch "$base" >/dev/null
        results+=("$name|$path|$status; switched-to-$base|$BRANCH_NAME|$base")
        continue
    fi
    git -C "$path" switch "$base" >/dev/null
    auto_resolved_conflicts=()
    while IFS= read -r commit; do
        [[ -n "$commit" ]] || continue
        if ! run_cherry_pick "$path" "$commit"; then
            mapfile -t conflict_array < <(conflict_files "$path")
            if resolve_generated_artifact_conflicts "$path" "${conflict_array[@]}"; then
                auto_resolved_conflicts+=("${conflict_array[@]}")
                continue
            fi
            conflicts=$(printf '%s\n' "${conflict_array[@]}" | paste -sd "," -)
            [[ -n "$conflicts" ]] || conflicts="unknown"
            echo "ERROR: Cherry-pick failed in $name at $commit. Conflicts: $conflicts" >&2
            exit 1
        fi
    done < <(cherry_pick_commits "$path" "$base" "$BRANCH_NAME")
    status="cherry-picked-to-$base"
    if [[ "$KEEP_BRANCH" != "true" ]]; then
        git -C "$path" branch -d "$BRANCH_NAME" >/dev/null
        status="$status; deleted-local-branch"
    else
        status="$status; kept-local-branch"
    fi
    if [[ "${#auto_resolved_conflicts[@]}" -gt 0 ]]; then
        resolved=$(printf '%s\n' "${auto_resolved_conflicts[@]}" | sort -u | paste -sd "," -)
        status="$status; auto-resolved-artifact-conflicts=$resolved"
    fi
    results+=("$name|$path|$status|$BRANCH_NAME|$base")
done

if $JSON_MODE; then
    print_json_payload "completed" "true" "true"
else
    echo "SPEC_BRANCH: $BRANCH_NAME"
    echo "PUSHED: false"
    echo "PREFLIGHT: passed"
    for result in "${results[@]}"; do
        IFS='|' read -r name path status branch base <<< "$result"
        echo "$name: $status"
    done
fi
