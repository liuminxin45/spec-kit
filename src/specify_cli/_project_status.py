"""Project-level Spec Kit version and upgrade status facts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .integrations.manifest import IntegrationManifest

LOCK_REL_PATH = ".specify/spec-kit.lock.yml"
INIT_OPTIONS_REL_PATH = ".specify/init-options.json"
INTEGRATIONS_DIR_REL_PATH = ".specify/integrations"
SPECKIT_MANIFEST_REL_PATH = ".specify/integrations/speckit.manifest.json"
INTEGRATION_STATE_REL_PATH = ".specify/integration.json"


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


def _manifest_integrity(
    project_root: Path,
    *,
    key: str,
    manifest_path: Path,
) -> dict[str, Any]:
    """Return verified on-disk integrity for one managed-asset manifest."""
    if not manifest_path.is_file():
        return {
            "status": "missing-manifest",
            "tracked": 0,
            "matched": 0,
            "modified": [],
            "missing": [],
            "unsafe": [],
            "error": "manifest not found",
        }

    try:
        manifest = IntegrationManifest.load(key, project_root)
        facts = manifest.inspect_integrity()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid-manifest",
            "tracked": 0,
            "matched": 0,
            "modified": [],
            "missing": [],
            "unsafe": [],
            "error": str(exc),
        }

    if facts["unsafe"]:
        status = "invalid-manifest"
    elif facts["missing"]:
        status = "incomplete"
    elif facts["modified"]:
        status = "customized"
    else:
        status = "current"
    return {
        "status": status,
        "tracked": facts["tracked"],
        "matched": len(facts["matched"]),
        "modified": facts["modified"],
        "missing": facts["missing"],
        "unsafe": facts["unsafe"],
        "error": "",
    }


def _combined_status(version_status: str, integrity_status: str) -> str:
    if integrity_status not in {"current", "customized"}:
        return "incomplete"
    if version_status != "current":
        return version_status
    if integrity_status == "current":
        return "current"
    if integrity_status == "customized":
        return "customized"
    return "incomplete"


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
    asset_version_status = _status_for(asset_version, target_version)
    asset_manifest_path = project_root / SPECKIT_MANIFEST_REL_PATH
    asset_integrity = _manifest_integrity(
        project_root,
        key="speckit",
        manifest_path=asset_manifest_path,
    )
    asset_status = _combined_status(asset_version_status, asset_integrity["status"])
    assets = {
        "version": asset_version,
        "status": asset_status,
        "version_status": asset_version_status,
        "integrity": asset_integrity,
        "lock_file": LOCK_REL_PATH if (project_root / LOCK_REL_PATH).is_file() else "",
        "manifest": SPECKIT_MANIFEST_REL_PATH
        if asset_manifest_path.is_file()
        else "",
    }

    integrations: list[dict[str, Any]] = []
    integrations_dir = project_root / INTEGRATIONS_DIR_REL_PATH
    integration_keys: set[str] = set()
    if integrations_dir.is_dir():
        integration_keys.update(
            path.name.removesuffix(".manifest.json")
            for path in integrations_dir.glob("*.manifest.json")
            if path.name != "speckit.manifest.json"
        )
    integration_state = _read_json(project_root / INTEGRATION_STATE_REL_PATH)
    installed = integration_state.get("installed_integrations")
    if isinstance(installed, list):
        integration_keys.update(
            str(item).strip()
            for item in installed
            if isinstance(item, str) and item.strip()
        )
    legacy_key = integration_state.get("integration")
    if isinstance(legacy_key, str) and legacy_key.strip():
        integration_keys.add(legacy_key.strip())

    for key in sorted(integration_keys):
        manifest_path = integrations_dir / f"{key}.manifest.json"
        version = _read_manifest_version(manifest_path) or "unknown"
        version_status = _status_for(version, target_version)
        integrity = _manifest_integrity(
            project_root,
            key=key,
            manifest_path=manifest_path,
        )
        integrations.append(
            {
                "key": key,
                "version": version,
                "status": _combined_status(version_status, integrity["status"]),
                "version_status": version_status,
                "integrity": integrity,
                "manifest": manifest_path.relative_to(project_root).as_posix(),
            }
        )

    outdated = [
        f"assets:{asset_version}"
        for _ in [None]
        if asset_version_status not in {"current"}
    ]
    outdated.extend(
        f"integration:{item['key']}:{item['version']}"
        for item in integrations
        if item["version_status"] != "current"
    )

    drifted: list[str] = []
    if asset_integrity["status"] != "current":
        drifted.append(f"assets:{asset_integrity['status']}")
    drifted.extend(
        f"integration:{item['key']}:{item['integrity']['status']}"
        for item in integrations
        if item["integrity"]["status"] != "current"
    )

    next_actions: list[str] = []
    if asset_status != "current":
        next_actions.append(
            f"specify upgrade --project-dir {project_root} --version {target_version} --dry-run"
        )
    for item in integrations:
        if item["status"] != "current":
            next_actions.append(f"specify integration upgrade {item['key']} --dry-run --json")

    all_statuses = [asset_status, *(item["status"] for item in integrations)]
    if any(item in {"outdated", "unknown"} for item in all_statuses):
        status = "outdated"
    elif any(item == "incomplete" for item in all_statuses):
        status = "incomplete"
    elif any(item == "customized" for item in all_statuses):
        status = "customized"
    else:
        status = "current"
    return {
        "status": status,
        "detected": True,
        "project_root": str(project_root),
        "target_version": target_version,
        "assets": assets,
        "integrations": integrations,
        "outdated": outdated,
        "drifted": drifted,
        "next_actions": next_actions,
    }
