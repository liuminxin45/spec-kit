"""Project-level Spec Kit version and upgrade status facts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

LOCK_REL_PATH = ".specify/spec-kit.lock.yml"
INIT_OPTIONS_REL_PATH = ".specify/init-options.json"
INTEGRATIONS_DIR_REL_PATH = ".specify/integrations"
SPECKIT_MANIFEST_REL_PATH = ".specify/integrations/speckit.manifest.json"


def resolve_project_root(project_dir: str | Path | None = None) -> Path | None:
    """Resolve a Spec Kit project root, returning None when no project is found."""
    candidate = project_dir
    if candidate is None or str(candidate).strip() == "":
        candidate = os.environ.get("SPECIFY_INIT_DIR", "")
    if candidate is None or str(candidate).strip() == "":
        current = Path.cwd().resolve()
        for path in [current, *current.parents]:
            if (path / ".specify").is_dir():
                return path
        return None

    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    return path if (path / ".specify").is_dir() else None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_lock_version(project_root: Path) -> str:
    path = project_root / LOCK_REL_PATH
    if not path.is_file():
        return ""
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    spec_kit = data.get("spec_kit")
    if not isinstance(spec_kit, dict):
        return ""
    return str(spec_kit.get("version", "")).strip()


def _read_init_options_version(project_root: Path) -> str:
    data = _read_json(project_root / INIT_OPTIONS_REL_PATH)
    return str(data.get("speckit_version", "")).strip()


def _read_manifest_version(path: Path) -> str:
    data = _read_json(path)
    return str(data.get("version", "")).strip()


def current_project_version(project_root: Path) -> str:
    """Return the project asset version using lock, init options, then manifest."""
    for version in [
        _read_lock_version(project_root),
        _read_init_options_version(project_root),
        _read_manifest_version(project_root / SPECKIT_MANIFEST_REL_PATH),
    ]:
        if version:
            return version
    return "unknown"


def _status_for(version: str, target_version: str) -> str:
    if not version or version == "unknown":
        return "unknown"
    return "current" if version == target_version else "outdated"


def build_project_status(
    project_root: Path | None,
    *,
    target_version: str,
) -> dict[str, Any]:
    """Build machine-readable project asset and integration upgrade status."""
    if project_root is None:
        return {
            "status": "not-detected",
            "detected": False,
            "project_root": "",
            "target_version": target_version,
            "assets": {},
            "integrations": [],
            "next_actions": [],
        }

    project_root = project_root.resolve()
    asset_version = current_project_version(project_root)
    asset_status = _status_for(asset_version, target_version)
    assets = {
        "version": asset_version,
        "status": asset_status,
        "lock_file": LOCK_REL_PATH if (project_root / LOCK_REL_PATH).is_file() else "",
        "manifest": SPECKIT_MANIFEST_REL_PATH
        if (project_root / SPECKIT_MANIFEST_REL_PATH).is_file()
        else "",
    }

    integrations: list[dict[str, Any]] = []
    integrations_dir = project_root / INTEGRATIONS_DIR_REL_PATH
    if integrations_dir.is_dir():
        for manifest_path in sorted(integrations_dir.glob("*.manifest.json")):
            key = manifest_path.name.removesuffix(".manifest.json")
            if key == "speckit":
                continue
            version = _read_manifest_version(manifest_path) or "unknown"
            integrations.append(
                {
                    "key": key,
                    "version": version,
                    "status": _status_for(version, target_version),
                    "manifest": manifest_path.relative_to(project_root).as_posix(),
                }
            )

    outdated = [
        f"assets:{asset_version}"
        for _ in [None]
        if asset_status not in {"current"}
    ]
    outdated.extend(
        f"integration:{item['key']}:{item['version']}"
        for item in integrations
        if item["status"] != "current"
    )

    next_actions: list[str] = []
    if asset_status != "current":
        next_actions.append(
            f"specify upgrade --project-dir {project_root} --version {target_version} --dry-run"
        )
    for item in integrations:
        if item["status"] != "current":
            next_actions.append(f"specify integration upgrade {item['key']} --force")

    status = "current" if not outdated else "outdated"
    return {
        "status": status,
        "detected": True,
        "project_root": str(project_root),
        "target_version": target_version,
        "assets": assets,
        "integrations": integrations,
        "outdated": outdated,
        "next_actions": next_actions,
    }
