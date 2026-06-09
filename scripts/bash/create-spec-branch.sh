#!/usr/bin/env bash

set -euo pipefail

JSON_MODE=false
ALLOW_DIRTY=false
FEATURE_NAME="${SPECIFY_FEATURE:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json) JSON_MODE=true; shift ;;
        --allow-dirty) ALLOW_DIRTY=true; shift ;;
        --feature-name)
            FEATURE_NAME="${2:-}"
            shift 2
            ;;
        --help|-h)
            echo "Usage: create-spec-branch.sh [--feature-name <name>] [--json] [--allow-dirty]"
            exit 0
            ;;
        *) echo "ERROR: Unknown option '$1'" >&2; exit 1 ;;
    esac
done

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

slugify() {
    local raw="$1"
    local slug
    slug=$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')
    [[ -n "$slug" ]] || slug="spec-work"
    printf '%s' "${slug:0:48}" | sed -E 's/-+$//'
}

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

        local current_name="" current_path="" current_role="" current_required="false"
        while IFS= read -r line; do
            if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*name:[[:space:]]*\"?([^\"]+)\"?[[:space:]]*$ ]]; then
                if [[ -n "$current_name" ]]; then
                    repos+=("$current_name|$current_path|$current_role|$current_required")
                fi
                current_name="${BASH_REMATCH[1]}"
                current_path=""
                current_role=""
                current_required="false"
            elif [[ -n "$current_name" && "$line" =~ ^[[:space:]]*path:[[:space:]]*\"?([^\"]+)\"?[[:space:]]*$ ]]; then
                current_path="${BASH_REMATCH[1]}"
            elif [[ -n "$current_name" && "$line" =~ ^[[:space:]]*role:[[:space:]]*\"?([^\"]+)\"?[[:space:]]*$ ]]; then
                current_role="${BASH_REMATCH[1]}"
            elif [[ -n "$current_name" && "$line" =~ ^[[:space:]]*required:[[:space:]]*(true|false)[[:space:]]*$ ]]; then
                current_required="${BASH_REMATCH[1]}"
            fi
        done < "$cfg"
        if [[ -n "$current_name" ]]; then
            repos+=("$current_name|$current_path|$current_role|$current_required")
        fi
    fi

    if [[ ${#repos[@]} -eq 0 ]]; then
        repos+=("$(basename "$repo_root")|$(basename "$repo_root")|primary|true")
    fi

    printf 'WORKSPACE_ROOT=%q\n' "$workspace_root"
    printf 'BASE_BRANCH=%q\n' "$base_branch"
    local i=0
    for repo in "${repos[@]}"; do
        IFS='|' read -r name path role required <<< "$repo"
        [[ -n "$role" ]] || role="unspecified"
        [[ "$path" = /* ]] || path="$workspace_root/$path"
        printf 'REPO_%d_NAME=%q\n' "$i" "$name"
        printf 'REPO_%d_PATH=%q\n' "$i" "$path"
        printf 'REPO_%d_ROLE=%q\n' "$i" "$role"
        printf 'REPO_%d_REQUIRED=%q\n' "$i" "$required"
        i=$((i + 1))
    done
    printf 'REPO_COUNT=%q\n' "$i"
}

is_git_repo() {
    [[ -d "$1" ]] && git -C "$1" rev-parse --is-inside-work-tree >/dev/null 2>&1
}

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

branch_has_upstream() {
    git -C "$1" rev-parse --abbrev-ref "$2@{upstream}" >/dev/null 2>&1
}

next_spec_number() {
    local repo_root="$1"
    local max=0
    if [[ -d "$repo_root/specs" ]]; then
        for dir in "$repo_root/specs"/*; do
            [[ -d "$dir" ]] || continue
            local name
            name=$(basename "$dir")
            if [[ "$name" =~ ^([0-9]{3,})- ]]; then
                local n=$((10#${BASH_REMATCH[1]}))
                (( n > max )) && max=$n
            fi
        done
    fi
    local i
    for (( i=0; i<REPO_COUNT; i++ )); do
        local path_var="REPO_${i}_PATH"
        local path="${!path_var}"
        if is_git_repo "$path"; then
            while IFS= read -r branch; do
                if [[ "$branch" =~ ^([0-9]{3,})- ]]; then
                    local n=$((10#${BASH_REMATCH[1]}))
                    (( n > max )) && max=$n
                fi
            done < <(git -C "$path" branch --format "%(refname:short)")
        fi
    done
    printf '%03d' $((max + 1))
}

json_escape_simple() {
    json_escape "$1"
}

repo_root=$(get_repo_root)
eval "$(read_workspace "$repo_root")"
REPOSITORY_MAP=".specify/memory/repository-map.md"

[[ -n "$FEATURE_NAME" ]] || { echo "ERROR: --feature-name is required when SPECIFY_FEATURE is not set" >&2; exit 1; }
slug=$(slugify "$FEATURE_NAME")
if [[ "$slug" =~ ^[0-9]{3,}- ]]; then
    branch_name="$slug"
else
    branch_name="$(next_spec_number "$repo_root")-$slug"
fi

preflight=()
errors=()
for (( i=0; i<REPO_COUNT; i++ )); do
    name_var="REPO_${i}_NAME"; path_var="REPO_${i}_PATH"; role_var="REPO_${i}_ROLE"; required_var="REPO_${i}_REQUIRED"
    name="${!name_var}"; path="${!path_var}"; role="${!role_var}"; required="${!required_var}"
    if [[ ! -d "$path" ]]; then
        preflight+=("$name|$path|$role|$required|missing|$branch_name|skip")
        [[ "$required" != "true" ]] || errors+=("Required repository not found: $name at $path")
        continue
    fi
    if ! is_git_repo "$path"; then
        preflight+=("$name|$path|$role|$required|not-git|$branch_name|error")
        errors+=("Repository is not a git work tree: $name at $path")
        continue
    fi
    if [[ "$ALLOW_DIRTY" != "true" ]] && is_dirty "$path"; then
        preflight+=("$name|$path|$role|$required|dirty|$branch_name|error")
        errors+=("Repository has uncommitted changes: $name. Commit/stash them, or rerun with --allow-dirty.")
        continue
    fi
    if git -C "$path" show-ref --verify --quiet "refs/heads/$branch_name"; then
        if branch_has_upstream "$path" "$branch_name"; then
            preflight+=("$name|$path|$role|$required|branch-has-upstream|$branch_name|error")
            errors+=("Spec branch '$branch_name' in $name has an upstream; Spec Kit branches must stay local-only.")
            continue
        fi
        preflight+=("$name|$path|$role|$required|ready|$branch_name|switch")
    else
        preflight+=("$name|$path|$role|$required|ready|$branch_name|create")
    fi
done

if [[ ${#errors[@]} -gt 0 ]]; then
    echo "ERROR: Preflight failed before creating or switching spec branches:" >&2
    for error in "${errors[@]}"; do
        echo " - $error" >&2
    done
    exit 1
fi

results=()
for item in "${preflight[@]}"; do
    IFS='|' read -r name path role required status branch action <<< "$item"
    if [[ "$status" == "missing" ]]; then
        results+=("$name|$path|$role|$required|missing|$branch_name")
        continue
    fi
    if [[ "$action" == "switch" ]]; then
        git -C "$path" switch "$branch_name" >/dev/null
        status="switched"
    elif [[ "$action" == "create" ]]; then
        git -C "$path" switch -c "$branch_name" >/dev/null
        status="created"
    else
        echo "ERROR: Unexpected preflight action '$action' for $name" >&2
        exit 1
    fi
    results+=("$name|$path|$role|$required|$status|$branch_name")
done

feature_dir="$repo_root/specs/$branch_name"
mkdir -p "$feature_dir" "$repo_root/.specify"
feature_json="$repo_root/.specify/feature.json"
if command -v python3 >/dev/null 2>&1; then
    repo_json="["
    first_repo=true
    for (( i=0; i<REPO_COUNT; i++ )); do
        name_var="REPO_${i}_NAME"; path_var="REPO_${i}_PATH"; role_var="REPO_${i}_ROLE"; required_var="REPO_${i}_REQUIRED"
        $first_repo || repo_json+=","
        first_repo=false
        repo_json+="{\"name\":\"$(json_escape_simple "${!name_var}")\",\"path\":\"$(json_escape_simple "${!path_var}")\",\"role\":\"$(json_escape_simple "${!role_var}")\",\"required\":${!required_var}}"
    done
    repo_json+="]"
    FEATURE_JSON="$feature_json" BRANCH_NAME="$branch_name" WORKSPACE_ROOT="$WORKSPACE_ROOT" DEFAULT_BASE_BRANCH="$BASE_BRANCH" REPOSITORY_MAP="$REPOSITORY_MAP" WORKSPACE_REPOSITORIES_JSON="$repo_json" python3 - <<'PY'
import json, os
path = os.environ["FEATURE_JSON"]
data = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
data["feature_directory"] = f"specs/{os.environ['BRANCH_NAME']}"
data["spec_branch"] = os.environ["BRANCH_NAME"]
data["branch_local_only"] = True
data["workspace_root"] = os.environ["WORKSPACE_ROOT"]
data["default_base_branch"] = os.environ["DEFAULT_BASE_BRANCH"]
data["repository_map"] = os.environ["REPOSITORY_MAP"]
data["workspace_repositories"] = json.loads(os.environ["WORKSPACE_REPOSITORIES_JSON"])
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
PY
else
    printf '{\n  "feature_directory": "specs/%s",\n  "spec_branch": "%s",\n  "branch_local_only": true,\n  "workspace_root": "%s",\n  "default_base_branch": "%s",\n  "repository_map": "%s"\n}\n' "$branch_name" "$branch_name" "$WORKSPACE_ROOT" "$BASE_BRANCH" "$REPOSITORY_MAP" > "$feature_json"
fi

if $JSON_MODE; then
    printf '{"branch":"%s","feature_dir":"%s","local_only":true,"workspace_root":"%s","default_base_branch":"%s","repository_map":"%s","preflight":[' "$(json_escape_simple "$branch_name")" "$(json_escape_simple "$feature_dir")" "$(json_escape_simple "$WORKSPACE_ROOT")" "$(json_escape_simple "$BASE_BRANCH")" "$(json_escape_simple "$REPOSITORY_MAP")"
    first=true
    for item in "${preflight[@]}"; do
        IFS='|' read -r name path role required status branch action <<< "$item"
        $first || printf ','
        first=false
        printf '{"repository":"%s","path":"%s","role":"%s","required":%s,"status":"%s","branch":"%s","planned_action":"%s"}' "$(json_escape_simple "$name")" "$(json_escape_simple "$path")" "$(json_escape_simple "$role")" "$required" "$(json_escape_simple "$status")" "$(json_escape_simple "$branch")" "$(json_escape_simple "$action")"
    done
    printf '],"repositories":['
    first=true
    for result in "${results[@]}"; do
        IFS='|' read -r name path role required status branch <<< "$result"
        $first || printf ','
        first=false
        printf '{"repository":"%s","path":"%s","role":"%s","required":%s,"status":"%s","branch":"%s"}' "$(json_escape_simple "$name")" "$(json_escape_simple "$path")" "$(json_escape_simple "$role")" "$required" "$(json_escape_simple "$status")" "$(json_escape_simple "$branch")"
    done
    printf ']}\n'
else
    echo "SPEC_BRANCH: $branch_name"
    echo "FEATURE_DIR: $feature_dir"
    echo "LOCAL_ONLY: true"
    echo "WORKSPACE_ROOT: $WORKSPACE_ROOT"
    echo "DEFAULT_BASE_BRANCH: $BASE_BRANCH"
    echo "REPOSITORY_MAP: $REPOSITORY_MAP"
    echo "PREFLIGHT: passed"
    for result in "${results[@]}"; do
        IFS='|' read -r name path role required status branch <<< "$result"
        echo "$name [$role]: $status -> $branch"
    done
fi
