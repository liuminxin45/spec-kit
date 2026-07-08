"""Project asset upgrade helpers for Spec Kit."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .integrations.base import IntegrationBase
from .integrations.manifest import IntegrationManifest, _sha256
from ._assets import UPSTREAM_BASELINE
from ._project_status import build_project_status, current_project_version
from .shared_infra import (
    RUNTIME_TEMPLATE_FILES,
    load_speckit_manifest,
    shared_ai_templates_source,
    shared_checklist_rules_source,
    shared_scripts_source,
    shared_templates_source,
    should_skip_shared_script_file,
)


LOCK_REL_PATH = ".specify/spec-kit.lock.yml"
MANIFEST_REL_PATH = ".specify/integrations/speckit.manifest.json"
MANAGED_WORKFLOW_REL = ".specify/workflows/speckit/workflow.yml"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read_pyproject_version(source_root: Path) -> str:
    path = source_root / "pyproject.toml"
    if not path.is_file():
        return ""
    try:
        import tomllib

        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return str(data.get("project", {}).get("version", "")).strip()
    except Exception:
        return ""


def _git_commit(source_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def read_spec_kit_lock(project_root: Path) -> dict[str, Any]:
    path = project_root / LOCK_REL_PATH
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def get_current_project_version(project_root: Path) -> str:
    """Return the current Spec Kit managed asset version for a project."""
    return current_project_version(project_root)


def write_spec_kit_lock(
    project_root: Path,
    *,
    version: str,
    source: str,
    source_commit: str = "",
) -> Path:
    path = project_root / LOCK_REL_PATH
    existing = read_spec_kit_lock(project_root)
    spec_kit = existing.get("spec_kit") if isinstance(existing.get("spec_kit"), dict) else {}
    installed_at = spec_kit.get("installed_at") or _now()
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "spec_kit": {
            "package": "specify-cli",
            "version": version,
            "upstream_baseline": UPSTREAM_BASELINE,
            "source": source,
            "installed_at": installed_at,
            "updated_at": _now(),
        },
        "managed_assets": {
            "manifest": MANIFEST_REL_PATH,
            "upgrade_command": "specify upgrade",
        },
    }
    if source_commit:
        payload["spec_kit"]["source_commit"] = source_commit

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def resolve_upgrade_source(
    *,
    source: str | None,
    core_pack: Path | None,
    repo_root: Path,
    installed_version: str,
) -> dict[str, Any]:
    if source:
        source_root = Path(source).expanduser().resolve()
        if not source_root.is_dir():
            raise ValueError(f"Upgrade source does not exist: {source}")
        if not (source_root / "scripts").is_dir() or not (source_root / "templates").is_dir():
            raise ValueError(f"Upgrade source is not a Spec Kit source checkout: {source_root}")
        source_version = _read_pyproject_version(source_root) or installed_version
        return {
            "kind": "source-checkout",
            "root": source_root,
            "core_pack": None,
            "repo_root": source_root,
            "version": source_version,
            "commit": _git_commit(source_root),
        }

    if core_pack is not None:
        return {
            "kind": "installed-package",
            "root": core_pack,
            "core_pack": core_pack,
            "repo_root": repo_root,
            "version": installed_version,
            "commit": "",
        }

    return {
        "kind": "editable-source",
        "root": repo_root,
        "core_pack": None,
        "repo_root": repo_root,
        "version": _read_pyproject_version(repo_root) or installed_version,
        "commit": _git_commit(repo_root),
    }


def _collect_shared_assets(
    *,
    project_root: Path,
    core_pack: Path | None,
    repo_root: Path,
    invoke_separator: str,
) -> dict[str, bytes]:
    assets: dict[str, bytes] = {}

    scripts_src = shared_scripts_source(core_pack=core_pack, repo_root=repo_root)
    for variant in ("powershell", "python"):
        variant_src = scripts_src / variant
        if variant_src.is_dir():
            for src in variant_src.rglob("*"):
                if (
                    src.is_file()
                    and not src.name.startswith(".")
                    and not should_skip_shared_script_file(src)
                ):
                    rel = (Path(".specify/scripts") / variant / src.relative_to(variant_src)).as_posix()
                    assets[rel] = src.read_bytes()

    templates_src = shared_templates_source(core_pack=core_pack, repo_root=repo_root)
    if templates_src.is_dir():
        for src in templates_src.iterdir():
            if src.is_file() and src.name in RUNTIME_TEMPLATE_FILES:
                rel = (Path(".specify/templates") / src.name).as_posix()
                content = IntegrationBase.resolve_command_refs(src.read_text(encoding="utf-8"), invoke_separator)
                assets[rel] = content.encode("utf-8")

    ai_src = shared_ai_templates_source(core_pack=core_pack, repo_root=repo_root)
    if ai_src.is_dir():
        for src in ai_src.rglob("*"):
            if src.is_file() and not src.name.startswith("."):
                rel = (Path("ai") / src.relative_to(ai_src)).as_posix()
                content = IntegrationBase.resolve_command_refs(src.read_text(encoding="utf-8"), invoke_separator)
                assets[rel] = content.encode("utf-8")

    checklist_src = shared_checklist_rules_source(core_pack=core_pack, repo_root=repo_root)
    if checklist_src.is_dir():
        for src in checklist_src.rglob("*"):
            if src.is_file() and not src.name.startswith("."):
                rel = (Path(".specify/checklist-rules") / src.relative_to(checklist_src)).as_posix()
                assets[rel] = src.read_bytes()

    return assets


def _workflow_source(*, core_pack: Path | None, repo_root: Path) -> Path | None:
    source_candidate = repo_root / "workflows" / "speckit" / "workflow.yml"
    if source_candidate.is_file():
        return source_candidate
    if core_pack is not None:
        bundled = core_pack / "workflows" / "speckit" / "workflow.yml"
        if bundled.is_file():
            return bundled
    return None


def build_upgrade_plan(
    project_root: Path,
    *,
    source_info: dict[str, Any],
    current_version: str,
    invoke_separator: str = ".",
    force: bool = False,
) -> dict[str, Any]:
    manifest = load_speckit_manifest(project_root, version=source_info["version"])
    prior_hashes = manifest.files
    modified = set(manifest.check_modified())
    source_assets = _collect_shared_assets(
        project_root=project_root,
        core_pack=source_info["core_pack"],
        repo_root=source_info["repo_root"],
        invoke_separator=invoke_separator,
    )

    plan: dict[str, Any] = {
        "current_version": current_version,
        "target_version": source_info["version"],
        "source": source_info["kind"],
        "source_root": str(source_info["root"]),
        "source_commit": source_info.get("commit", ""),
        "managed_manifest": MANIFEST_REL_PATH,
        "lock_file": LOCK_REL_PATH,
        "added": [],
        "updated": [],
        "unchanged": [],
        "preserved_customized": [],
        "skipped_untracked": [],
        "removed_stale": [],
        "preserved_stale": [],
        "forced_overwrite": [],
        "workflow": {},
    }

    for rel, content in sorted(source_assets.items()):
        dest = project_root / rel
        target_hash = _hash_bytes(content)
        if not dest.exists() and not dest.is_symlink():
            plan["added"].append(rel)
            continue
        if not dest.is_file() or dest.is_symlink():
            plan["preserved_customized"].append(rel)
            continue
        current_hash = _sha256(dest)
        if current_hash == target_hash:
            plan["unchanged"].append(rel)
        elif force:
            plan["forced_overwrite"].append(rel)
        elif rel in prior_hashes and rel not in modified:
            plan["updated"].append(rel)
        elif rel in prior_hashes:
            plan["preserved_customized"].append(rel)
        else:
            plan["skipped_untracked"].append(rel)

    valid_rels = set(source_assets)
    managed_prefixes = (
        ".specify/scripts/",
        ".specify/templates/",
        ".specify/checklist-rules/",
        "ai/",
    )
    for rel in sorted(prior_hashes):
        if not rel.startswith(managed_prefixes) or rel in valid_rels:
            continue
        dest = project_root / rel
        if not dest.exists() and not dest.is_symlink():
            plan["removed_stale"].append(rel)
        elif force or rel not in modified:
            plan["removed_stale"].append(rel)
        else:
            plan["preserved_stale"].append(rel)

    workflow = _workflow_source(core_pack=source_info["core_pack"], repo_root=source_info["repo_root"])
    if workflow is None:
        plan["workflow"] = {"status": "missing-source", "path": MANAGED_WORKFLOW_REL}
    else:
        dest = project_root / MANAGED_WORKFLOW_REL
        source_hash = _sha256(workflow)
        if not dest.exists():
            status = "added"
        elif not dest.is_file() or dest.is_symlink():
            status = "preserved-customized"
        elif _sha256(dest) == source_hash:
            status = "unchanged"
        elif force:
            status = "forced-overwrite"
        elif MANAGED_WORKFLOW_REL in prior_hashes and MANAGED_WORKFLOW_REL not in modified:
            status = "updated"
        else:
            status = "skipped-untracked"
        plan["workflow"] = {"status": status, "path": MANAGED_WORKFLOW_REL}

    plan["project_status"] = build_project_status(
        project_root,
        target_version=source_info["version"],
    )
    return plan


def install_bundled_workflow(
    project_root: Path,
    *,
    source_info: dict[str, Any],
    version: str,
    force: bool = False,
) -> str:
    workflow = _workflow_source(core_pack=source_info["core_pack"], repo_root=source_info["repo_root"])
    if workflow is None:
        return "missing-source"

    dest = project_root / MANAGED_WORKFLOW_REL
    manifest = load_speckit_manifest(project_root, version=version)
    modified = set(manifest.check_modified())
    status = "added"

    if dest.exists():
        if dest.is_file() and _sha256(dest) == _sha256(workflow):
            manifest.record_existing(MANAGED_WORKFLOW_REL)
            manifest.save()
            return "unchanged"
        if not force and (
            MANAGED_WORKFLOW_REL not in manifest.files
            or MANAGED_WORKFLOW_REL in modified
            or not dest.is_file()
            or dest.is_symlink()
        ):
            return "preserved-customized"
        status = "forced-overwrite" if force else "updated"

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(workflow, dest)

    from .workflows.catalog import WorkflowRegistry
    from .workflows.engine import WorkflowDefinition

    definition = WorkflowDefinition.from_yaml(dest)
    registry = WorkflowRegistry(project_root)
    registry.add(
        "speckit",
        {
            "name": definition.name,
            "version": definition.version,
            "description": definition.description,
            "source": "bundled",
        },
    )
    manifest.record_existing(MANAGED_WORKFLOW_REL)
    manifest.save()
    return status


def apply_project_upgrade(
    project_root: Path,
    *,
    source_info: dict[str, Any],
    current_version: str,
    invoke_separator: str = ".",
    force: bool = False,
    console: Any,
) -> dict[str, Any]:
    from .shared_infra import install_shared_infra

    install_shared_infra(
        project_root,
        "ps",
        version=source_info["version"],
        core_pack=source_info["core_pack"],
        repo_root=source_info["repo_root"],
        console=console,
        force=force,
        invoke_separator=invoke_separator,
        refresh_managed=True,
        refresh_hint="Use [cyan]specify upgrade --force[/cyan] to overwrite customized managed assets.",
    )
    workflow_status = install_bundled_workflow(
        project_root,
        source_info=source_info,
        version=source_info["version"],
        force=force,
    )
    lock_path = write_spec_kit_lock(
        project_root,
        version=source_info["version"],
        source=source_info["kind"],
        source_commit=source_info.get("commit", ""),
    )
    return {
        "previous_version": current_version,
        "version": source_info["version"],
        "workflow_status": workflow_status,
        "lock_file": lock_path.relative_to(project_root).as_posix(),
        "manifest": MANIFEST_REL_PATH,
    }


def run_post_upgrade_validations(project_root: Path) -> list[dict[str, Any]]:
    scripts = project_root / ".specify" / "scripts" / "powershell" / "automation-common.ps1"
    if not scripts.is_file():
        return [
            {
                "tool": "post-upgrade-validation",
                "status": "skipped",
                "reason": ".specify/scripts/powershell/automation-common.ps1 not found",
            }
        ]

    commands = [
        "validate-generated-context",
        "validate-knowledge-index",
        "validate-context-budget",
    ]
    results: list[dict[str, Any]] = []
    for command in commands:
        try:
            completed = subprocess.run(
                [
                    "pwsh",
                    "-NoProfile",
                    "-File",
                    str(scripts),
                    "-Tool",
                    command,
                    "-RepoRoot",
                    str(project_root),
                    "-Json",
                ],
                cwd=project_root,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=120,
            )
        except FileNotFoundError:
            return [
                {
                    "tool": "post-upgrade-validation",
                    "status": "skipped",
                    "reason": "pwsh not found",
                }
            ]
        except subprocess.TimeoutExpired:
            results.append({"tool": command, "status": "blocked", "reason": "validation timed out"})
            continue

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {
                "tool": command,
                "status": "blocked" if completed.returncode else "warning",
                "stdout": completed.stdout[-1000:],
                "stderr": completed.stderr[-1000:],
            }
        results.append(payload)
    return results
