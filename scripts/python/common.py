"""Shared helpers for Spec Kit Python scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _trim_trailing_separators(value: Path) -> str:
    text = str(value)
    while len(text) > 1 and text.endswith((os.sep, "/")):
        text = text[:-1]
    return text


def find_specify_root(start_dir: Path | None = None) -> Path | None:
    current = (start_dir or Path.cwd()).resolve()
    while True:
        if (current / ".specify").is_dir():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _resolve_env_dir(name: str, *, require_specify: bool) -> Path | None:
    raw = os.environ.get(name, "")
    if not raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        print(f"ERROR: {name} does not point to an existing directory: {raw}", file=sys.stderr)
        raise SystemExit(1)
    if not resolved.is_dir():
        print(f"ERROR: {name} does not point to an existing directory: {raw}", file=sys.stderr)
        raise SystemExit(1)
    if require_specify and not (resolved / ".specify").is_dir():
        print(
            f"ERROR: {name} is not a Spec Kit project (no .specify/ directory): {resolved}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return resolved


def get_current_repo_root() -> Path | None:
    env_root = _resolve_env_dir("SPECIFY_REPO_ROOT", require_specify=False)
    if env_root is not None:
        return env_root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    return None


def get_spec_kit_root(script_file: Path | None = None) -> Path:
    env_init = _resolve_env_dir("SPECIFY_INIT_DIR", require_specify=True)
    if env_init is not None:
        return env_init

    env_root = _resolve_env_dir("SPECIFY_ROOT", require_specify=False)
    if env_root is not None:
        return env_root

    specify_root = find_specify_root()
    if specify_root is not None:
        return specify_root

    if script_file is not None:
        script_root = find_specify_root(script_file.resolve().parent)
        if script_root is not None:
            return script_root
        try:
            return script_file.resolve().parents[3]
        except IndexError:
            pass

    repo_root = get_current_repo_root()
    if repo_root is not None:
        return repo_root

    return Path.cwd().resolve()


def has_git() -> bool:
    repo_root = get_current_repo_root()
    if repo_root is None:
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def latest_feature_dir_name(repo_root: Path) -> str:
    specs_dir = repo_root / "specs"
    if not specs_dir.is_dir():
        return ""

    latest_feature = ""
    highest = 0
    latest_timestamp = ""
    for child in specs_dir.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if len(name) >= 16 and name[:8].isdigit() and name[8] == "-" and name[9:15].isdigit() and name[15] == "-":
            timestamp = name[:15]
            if timestamp > latest_timestamp:
                latest_timestamp = timestamp
                latest_feature = name
            continue
        prefix, sep, _slug = name.partition("-")
        if sep and len(prefix) >= 3 and prefix.isdigit():
            number = int(prefix)
            if number > highest:
                highest = number
                if not latest_timestamp:
                    latest_feature = name
    return latest_feature


def get_current_branch(repo_root: Path) -> str:
    feature = os.environ.get("SPECIFY_FEATURE", "")
    if feature:
        return feature

    repo = get_current_repo_root()
    if repo is not None and has_git():
        try:
            result = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError:
            result = None
        if result is not None and result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

    latest = latest_feature_dir_name(repo_root)
    return latest or "main"


def effective_branch_name(branch: str) -> str:
    parts = branch.split("/")
    if len(parts) == 2 and all(parts):
        return parts[1]
    return branch


def test_feature_branch(branch: str, has_git_repo: bool) -> bool:
    if not has_git_repo:
        print("[specify] Warning: Git repository not detected; skipped branch validation", file=sys.stderr)
        return True

    raw = branch
    effective = effective_branch_name(raw)
    malformed_timestamp = (
        (len(effective) >= 16 and effective[:7].isdigit() and effective[7] == "-" and effective[8:14].isdigit() and effective[14] == "-")
        or (
            len(effective) in {14, 15}
            and effective.split("-")[0].isdigit()
            and len(effective.split("-")[0]) in {7, 8}
            and len(effective.split("-")) == 2
            and effective.split("-")[1].isdigit()
        )
    )
    prefix, sep, _slug = effective.partition("-")
    is_sequential = bool(sep and len(prefix) >= 3 and prefix.isdigit() and not malformed_timestamp)
    is_timestamp = (
        len(effective) >= 16
        and effective[:8].isdigit()
        and effective[8] == "-"
        and effective[9:15].isdigit()
        and effective[15] == "-"
    )
    if not is_sequential and not is_timestamp:
        print(f"ERROR: Not on a feature branch. Current branch: {raw}", file=sys.stderr)
        print(
            "Feature branches should be named like: 001-feature-name, "
            "1234-feature-name, or 20260319-143022-feature-name",
            file=sys.stderr,
        )
        return False
    return True


def read_feature_json(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / ".specify" / "feature.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Failed to parse .specify/feature.json: {exc}", file=sys.stderr)
        raise SystemExit(1)
    if not isinstance(data, dict):
        print("ERROR: Failed to parse .specify/feature.json: expected object", file=sys.stderr)
        raise SystemExit(1)
    return data


def _resolve_spec_kit_path(value: str, repo_root: Path) -> Path | None:
    if not value.strip():
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve(strict=False)


def _same_spec_kit_path(left: str | Path, right: str | Path, repo_root: Path) -> bool:
    left_path = _resolve_spec_kit_path(str(left), repo_root)
    right_path = _resolve_spec_kit_path(str(right), repo_root)
    if left_path is None or right_path is None:
        return False
    if os.name == "nt":
        return os.path.normcase(str(left_path)) == os.path.normcase(str(right_path))
    return str(left_path) == str(right_path)


def _read_feature_json_for_profile(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / ".specify" / "feature.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def get_feature_delivery_profile(repo_root: Path, feature_dir: Path, explicit_profile: str = "") -> str:
    if explicit_profile.strip():
        explicit = explicit_profile.strip().lower()
        return "" if explicit == "auto" else explicit

    feature_config = _read_feature_json_for_profile(repo_root)
    if feature_config is not None:
        configured_dir = str(feature_config.get("feature_directory") or "")
        matches_feature_dir = not configured_dir or _same_spec_kit_path(configured_dir, feature_dir, repo_root)
        if matches_feature_dir:
            profile = str(feature_config.get("delivery_profile") or "")
            if profile.strip() and profile.strip().lower() != "auto":
                return profile.strip().lower()

    state_path = feature_dir / "workflow-state.json"
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        workflow_model = state.get("workflow_model") if isinstance(state, dict) else {}
        if isinstance(workflow_model, dict):
            profile = str(workflow_model.get("delivery_profile") or "")
            if profile.strip() and profile.strip().lower() != "auto":
                return profile.strip().lower()

    return ""


def is_lean_delivery_profile(profile: str) -> bool:
    return profile in {"micro-fix", "standard-bugfix-lite"}


def _feature_dir_by_prefix(repo_root: Path, branch: str) -> Path:
    specs_dir = repo_root / "specs"
    branch_name = effective_branch_name(branch)
    prefix = ""
    if len(branch_name) >= 16 and branch_name[:8].isdigit() and branch_name[8] == "-" and branch_name[9:15].isdigit() and branch_name[15] == "-":
        prefix = branch_name[:15]
    else:
        first, sep, _rest = branch_name.partition("-")
        if sep and len(first) >= 3 and first.isdigit():
            prefix = first
    if not prefix:
        return specs_dir / branch_name

    matches = [p for p in specs_dir.glob(f"{prefix}-*") if p.is_dir()] if specs_dir.is_dir() else []
    if not matches:
        return specs_dir / branch_name
    if len(matches) == 1:
        return matches[0]
    names = " ".join(p.name for p in matches)
    print(f"ERROR: Multiple spec directories found with prefix '{prefix}': {names}", file=sys.stderr)
    print("Please ensure only one spec directory exists per prefix.", file=sys.stderr)
    raise SystemExit(1)


@dataclass(frozen=True)
class FeaturePaths:
    repo_root: Path
    current_branch: str
    has_git: bool
    feature_dir: Path
    feature_spec: Path
    impl_plan: Path
    workpack: Path
    tasks: Path
    research: Path
    data_model: Path
    quickstart: Path
    contracts_dir: Path


def get_feature_paths(*, no_persist: bool = False, script_file: Path | None = None) -> FeaturePaths:
    del no_persist
    repo_root = get_spec_kit_root(script_file)
    current_branch = get_current_branch(repo_root)
    git_available = has_git()

    feature_dir_raw = os.environ.get("SPECIFY_FEATURE_DIRECTORY", "")
    if feature_dir_raw:
        feature_dir = Path(feature_dir_raw)
        if not feature_dir.is_absolute():
            feature_dir = repo_root / feature_dir
    else:
        feature_config = read_feature_json(repo_root)
        if feature_config is not None:
            effective_current = effective_branch_name(current_branch)
            pinned_branch = str(feature_config.get("spec_branch") or "")
            if pinned_branch and effective_branch_name(pinned_branch) != effective_current:
                print(
                    ".specify/feature.json points to spec branch "
                    f"'{pinned_branch}' but current branch is '{current_branch}'.",
                    file=sys.stderr,
                )
                print(
                    "Run /speckit.specify or create-spec-branch for the active spec before continuing.",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            stored = str(feature_config.get("feature_directory") or "")
            if stored and pinned_branch:
                feature_dir = Path(stored)
                if not feature_dir.is_absolute():
                    feature_dir = repo_root / feature_dir
            else:
                feature_dir = _feature_dir_by_prefix(repo_root, current_branch)
        else:
            feature_dir = _feature_dir_by_prefix(repo_root, current_branch)

    return FeaturePaths(
        repo_root=repo_root,
        current_branch=current_branch,
        has_git=git_available,
        feature_dir=feature_dir,
        feature_spec=feature_dir / "spec.md",
        impl_plan=feature_dir / "plan.md",
        workpack=feature_dir / "workpack.md",
        tasks=feature_dir / "tasks.md",
        research=feature_dir / "research.md",
        data_model=feature_dir / "data-model.md",
        quickstart=feature_dir / "quickstart.md",
        contracts_dir=feature_dir / "contracts",
    )


def get_invoke_separator(repo_root: Path) -> str:
    integration_json = repo_root / ".specify" / "integration.json"
    if not integration_json.is_file():
        return "."
    try:
        state = json.loads(integration_json.read_text(encoding="utf-8"))
        key = state.get("default_integration") or state.get("integration") or ""
        settings = state.get("integration_settings")
        if isinstance(key, str) and isinstance(settings, dict):
            entry = settings.get(key)
            if isinstance(entry, dict) and entry.get("invoke_separator") in {".", "-"}:
                return entry["invoke_separator"]
    except (OSError, json.JSONDecodeError):
        pass
    return "."


def format_speckit_command(command_name: str, repo_root: Path) -> str:
    separator = get_invoke_separator(repo_root)
    name = command_name.lstrip("/")
    if name.startswith("speckit."):
        name = name[len("speckit.") :]
    elif name.startswith("speckit-"):
        name = name[len("speckit-") :]
    name = name.replace(".", separator)
    return f"/speckit{separator}{name}"
