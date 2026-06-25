"""Project-level knowledge pack commands for Spec Kit."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import typer

from ._assets import _locate_core_pack, _repo_root
from ._console import console


knowledge_app = typer.Typer(
    name="knowledge",
    help="Generate, mount, export, and evaluate Spec Kit knowledge packs",
    add_completion=False,
)


def _resolve_path(value: str | None, *, base: Path | None = None) -> Path | None:
    if value is None or not str(value).strip():
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    return path.resolve()


def _require_project(project_dir: str | None = None) -> Path:
    project_root = _resolve_path(project_dir) or Path.cwd().resolve()
    if (project_root / ".specify").is_dir():
        return project_root
    console.print(f"[red]Error:[/red] Not a spec-kit project: {project_root}")
    console.print("Pass --project-dir <dir> or run this command from a spec-kit project root.")
    raise typer.Exit(1)


def _script_roots(project_root: Path | None = None) -> list[Path]:
    roots: list[Path] = []
    if project_root is not None:
        roots.append(project_root / ".specify" / "scripts" / "powershell")
    core_pack = _locate_core_pack()
    if core_pack is not None:
        roots.append(core_pack / "scripts" / "powershell")
    roots.append(_repo_root() / "scripts" / "powershell")
    return roots


def _knowledge_script(script_name: str, *, project_root: Path | None = None) -> Path:
    for root in _script_roots(project_root):
        candidate = root / script_name
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(root / script_name) for root in _script_roots(project_root))
    console.print(f"[red]Error:[/red] Knowledge script not found: {script_name}")
    console.print(f"Searched: {searched}")
    raise typer.Exit(1)


def _append_arg(args: list[str], name: str, value: str | int | bool | Path | None) -> None:
    if value is None:
        return
    if isinstance(value, str) and value == "":
        return
    if isinstance(value, bool):
        if value:
            args.append(name)
        return
    args.extend([name, str(value)])


def _append_many(args: list[str], name: str, values: list[str] | None) -> None:
    for value in values or []:
        _append_arg(args, name, value)


def _invoke_script(
    script_name: str,
    *,
    project_root: Path | None,
    args: list[str],
) -> dict[str, Any]:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        console.print("[red]Error:[/red] PowerShell is required for knowledge pack commands.")
        raise typer.Exit(1)

    script = _knowledge_script(script_name, project_root=project_root)
    command = [shell, "-NoProfile", "-File", str(script), *args, "-Json"]
    completed = subprocess.run(
        command,
        cwd=project_root or Path.cwd(),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    output = completed.stdout.strip()
    if completed.returncode != 0:
        detail = completed.stderr.strip() or output or f"exit {completed.returncode}"
        return {
            "tool": script_name.removesuffix(".ps1"),
            "status": "blocked",
            "facts": {"script": str(script), "exit_code": completed.returncode},
            "blockers": [detail],
            "unknowns": [],
            "hints": [],
        }

    json_start = output.find("{")
    if json_start > 0:
        output = output[json_start:]
    if json_start < 0:
        return {
            "tool": script_name.removesuffix(".ps1"),
            "status": "blocked",
            "facts": {"script": str(script), "raw_output": completed.stdout},
            "blockers": ["script did not return JSON"],
            "unknowns": [],
            "hints": [],
        }
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        return {
            "tool": script_name.removesuffix(".ps1"),
            "status": "blocked",
            "facts": {"script": str(script), "raw_output": output},
            "blockers": [f"script returned invalid JSON: {exc}"],
            "unknowns": [],
            "hints": [],
        }


def _emit_result(result: dict[str, Any], *, json_output: bool, title: str) -> None:
    if json_output:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        status = str(result.get("status", "unknown"))
        style = "green" if status == "ok" else "red" if status == "blocked" else "yellow"
        console.print(f"[{style}]{status.upper()}[/{style}] {title}")
        facts = result.get("facts") if isinstance(result.get("facts"), dict) else {}
        for key in [
            "repo_root",
            "output_dir",
            "draft_knowledge_dir",
            "synthesis_knowledge_dir",
            "generation_contract",
            "source_read_queue",
            "pack_id",
            "pack_root",
            "knowledge_dir",
        ]:
            value = facts.get(key)
            if value not in (None, "", []):
                console.print(f"{key}: [cyan]{value}[/cyan]")
        blockers = result.get("blockers") or []
        unknowns = result.get("unknowns") or []
        hints = result.get("hints") or []
        for blocker in blockers:
            console.print(f"[red]Blocked:[/red] {blocker}")
        for unknown in unknowns[:8]:
            console.print(f"[yellow]Unknown:[/yellow] {unknown}")
        for hint in hints[:8]:
            console.print(f"[dim]Hint:[/dim] {hint}")

    if result.get("status") == "blocked":
        raise typer.Exit(1)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "knowledge-pack"


def _pack_root_from_generation(
    result: dict[str, Any],
    *,
    project_root: Path,
    pack_id: str,
    pack_output_dir: str | None,
) -> Path:
    pack = result.get("facts", {}).get("pack")
    if isinstance(pack, dict):
        pack_facts = pack.get("facts")
        if isinstance(pack_facts, dict) and pack_facts.get("pack_root"):
            return Path(str(pack_facts["pack_root"])).resolve()
    explicit = _resolve_path(pack_output_dir, base=project_root)
    if explicit is not None:
        return explicit
    return (project_root / ".specify" / "knowledge-pack-generation" / "pack" / _slug(pack_id)).resolve()


@knowledge_app.command("bootstrap")
def knowledge_bootstrap(
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root"),
    output_dir: str | None = typer.Option(None, "--output-dir", help="Bootstrap output directory"),
    pack_id: str | None = typer.Option(None, "--pack-id", help="Pack id to export when --export-pack is used"),
    pack_path: str | None = typer.Option(None, "--pack-path", "--pack", help="Existing pack to mount instead of generating a review packet"),
    pack_output_dir: str | None = typer.Option(None, "--pack-output-dir", help="Output directory for exported pack"),
    compose_strategy: str = typer.Option("overlay-active-knowledge", "--compose-strategy", help="overlay-active-knowledge or replace-active-knowledge"),
    export_pack: bool = typer.Option(False, "--export-pack", help="Export the bootstrap draft as a pack"),
    include_profiles: bool = typer.Option(False, "--include-profiles", help="Include workspace.yml and repository-map.md when exporting"),
    apply: bool = typer.Option(False, "--apply", help="Apply the exported bootstrap pack"),
    apply_profiles: bool = typer.Option(False, "--apply-profiles", help="Apply profiles from a mounted pack"),
    force: bool = typer.Option(False, "--force", help="Overwrite outputs or profiles when the script permits it"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Create a draft knowledge layer or mount an existing pack."""
    project_root = _require_project(project_dir)
    args = ["-RepoRoot", str(project_root)]
    _append_arg(args, "-OutputDir", _resolve_path(output_dir, base=project_root))
    _append_arg(args, "-PackId", pack_id)
    _append_arg(args, "-PackPath", _resolve_path(pack_path, base=project_root))
    _append_arg(args, "-PackOutputDir", _resolve_path(pack_output_dir, base=project_root))
    _append_arg(args, "-ComposeStrategy", compose_strategy)
    _append_arg(args, "-ExportPack", export_pack)
    _append_arg(args, "-IncludeProfiles", include_profiles)
    _append_arg(args, "-Apply", apply)
    _append_arg(args, "-ApplyProfiles", apply_profiles)
    _append_arg(args, "-Force", force)
    result = _invoke_script("bootstrap-knowledge.ps1", project_root=project_root, args=args)
    _emit_result(result, json_output=json_output, title="knowledge bootstrap")


@knowledge_app.command("generate-pack")
def knowledge_generate_pack(
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root"),
    pack_id: str = typer.Option(..., "--pack-id", help="Pack id to generate"),
    output_dir: str | None = typer.Option(None, "--output-dir", help="Generation workspace directory"),
    pack_output_dir: str | None = typer.Option(None, "--pack-output-dir", help="Pack output directory"),
    compose_strategy: str = typer.Option("overlay-active-knowledge", "--compose-strategy", help="overlay-active-knowledge or replace-active-knowledge"),
    minimum_quality_score: int = typer.Option(70, "--minimum-quality-score", help="Minimum synthesis quality score"),
    include_profiles: bool = typer.Option(False, "--include-profiles", help="Include workspace.yml and repository-map.md in generated pack"),
    force: bool = typer.Option(False, "--force", help="Overwrite generated outputs when needed"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Prepare an AI synthesis workspace and a draft pack for a project."""
    project_root = _require_project(project_dir)
    args = ["-RepoRoot", str(project_root), "-PackId", pack_id]
    _append_arg(args, "-OutputDir", _resolve_path(output_dir, base=project_root))
    _append_arg(args, "-PackOutputDir", _resolve_path(pack_output_dir, base=project_root))
    _append_arg(args, "-ComposeStrategy", compose_strategy)
    _append_arg(args, "-MinimumQualityScore", minimum_quality_score)
    _append_arg(args, "-IncludeProfiles", include_profiles)
    _append_arg(args, "-Force", force)
    result = _invoke_script("generate-knowledge-pack.ps1", project_root=project_root, args=args)
    _emit_result(result, json_output=json_output, title="knowledge generate-pack")


@knowledge_app.command("finalize-pack")
def knowledge_finalize_pack(
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root"),
    pack_id: str = typer.Option(..., "--pack-id", help="Pack id to finalize"),
    reviewed_knowledge_dir: str | None = typer.Option(None, "--reviewed-knowledge-dir", help="Reviewed ai/knowledge directory"),
    output_dir: str | None = typer.Option(None, "--output-dir", help="Generation workspace directory"),
    pack_output_dir: str | None = typer.Option(None, "--pack-output-dir", help="Pack output directory"),
    compose_strategy: str = typer.Option("overlay-active-knowledge", "--compose-strategy", help="overlay-active-knowledge or replace-active-knowledge"),
    minimum_quality_score: int = typer.Option(70, "--minimum-quality-score", help="Minimum synthesis quality score"),
    include_profiles: bool = typer.Option(False, "--include-profiles", help="Include workspace.yml and repository-map.md in finalized pack"),
    apply: bool = typer.Option(False, "--apply", help="Apply the finalized pack to this project"),
    apply_profiles: bool = typer.Option(False, "--apply-profiles", help="Apply profiles from the finalized pack"),
    force: bool = typer.Option(False, "--force", help="Overwrite generated outputs or profiles when needed"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Export reviewed AI synthesis as a validated pack, optionally applying it."""
    project_root = _require_project(project_dir)
    reviewed_dir = _resolve_path(
        reviewed_knowledge_dir,
        base=project_root,
    ) or (
        project_root
        / ".specify"
        / "knowledge-pack-generation"
        / "ai-synthesis"
        / "ai"
        / "knowledge"
    )
    args = [
        "-RepoRoot",
        str(project_root),
        "-PackId",
        pack_id,
        "-ReviewedKnowledgeDir",
        str(reviewed_dir),
    ]
    _append_arg(args, "-OutputDir", _resolve_path(output_dir, base=project_root))
    _append_arg(args, "-PackOutputDir", _resolve_path(pack_output_dir, base=project_root))
    _append_arg(args, "-ComposeStrategy", compose_strategy)
    _append_arg(args, "-MinimumQualityScore", minimum_quality_score)
    _append_arg(args, "-IncludeProfiles", include_profiles)
    _append_arg(args, "-Force", force)
    result = _invoke_script("generate-knowledge-pack.ps1", project_root=project_root, args=args)

    if apply and result.get("status") != "blocked":
        pack_root = _pack_root_from_generation(
            result,
            project_root=project_root,
            pack_id=pack_id,
            pack_output_dir=pack_output_dir,
        )
        apply_args = ["-RepoRoot", str(project_root), "-PackPath", str(pack_root)]
        _append_arg(apply_args, "-ApplyProfiles", apply_profiles)
        _append_arg(apply_args, "-Force", force or apply_profiles)
        applied = _invoke_script("apply-knowledge-pack.ps1", project_root=project_root, args=apply_args)
        result.setdefault("facts", {})["applied_pack"] = applied
        if applied.get("status") == "blocked":
            result["status"] = "blocked"
            result.setdefault("blockers", []).append(
                "finalized pack apply failed: " + "; ".join(map(str, applied.get("blockers") or []))
            )

    _emit_result(result, json_output=json_output, title="knowledge finalize-pack")


@knowledge_app.command("apply-pack")
def knowledge_apply_pack(
    pack_path: str = typer.Argument(..., help="Pack directory to install and materialize"),
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root"),
    pack_id: str | None = typer.Option(None, "--pack-id", help="Expected pack id"),
    apply_profiles: bool = typer.Option(False, "--apply-profiles", help="Apply pack profiles to workspace.yml and repository-map.md"),
    force: bool = typer.Option(False, "--force", help="Overwrite installed pack or profiles when needed"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Install and materialize an existing knowledge pack."""
    project_root = _require_project(project_dir)
    args = ["-RepoRoot", str(project_root), "-PackPath", str(_resolve_path(pack_path, base=project_root))]
    _append_arg(args, "-PackId", pack_id)
    _append_arg(args, "-ApplyProfiles", apply_profiles)
    _append_arg(args, "-Force", force)
    result = _invoke_script("apply-knowledge-pack.ps1", project_root=project_root, args=args)
    _emit_result(result, json_output=json_output, title="knowledge apply-pack")


@knowledge_app.command("update-pack")
def knowledge_update_pack(
    pack_path: str = typer.Argument(..., help="Incoming replacement pack directory"),
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root"),
    pack_id: str | None = typer.Option(None, "--pack-id", help="Expected pack id"),
    force: bool = typer.Option(False, "--force", help="Install even when the pack was not installed before"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Update an installed pack and recompose active knowledge."""
    project_root = _require_project(project_dir)
    args = ["-RepoRoot", str(project_root), "-PackPath", str(_resolve_path(pack_path, base=project_root))]
    _append_arg(args, "-PackId", pack_id)
    _append_arg(args, "-Force", force)
    result = _invoke_script("update-knowledge-pack.ps1", project_root=project_root, args=args)
    _emit_result(result, json_output=json_output, title="knowledge update-pack")


@knowledge_app.command("uninstall-pack")
def knowledge_uninstall_pack(
    pack_id: str = typer.Argument(..., help="Installed pack id to remove"),
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root"),
    force: bool = typer.Option(False, "--force", help="Continue even when the installed pack directory is missing"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Remove an installed pack and restore the remaining composed knowledge."""
    project_root = _require_project(project_dir)
    args = ["-RepoRoot", str(project_root), "-PackId", pack_id]
    _append_arg(args, "-Force", force)
    result = _invoke_script("uninstall-knowledge-pack.ps1", project_root=project_root, args=args)
    _emit_result(result, json_output=json_output, title="knowledge uninstall-pack")


@knowledge_app.command("export-pack")
def knowledge_export_pack(
    source_knowledge_dir: str = typer.Option("ai/knowledge", "--source-knowledge-dir", help="Source ai/knowledge directory"),
    pack_id: str = typer.Option(..., "--pack-id", help="Pack id to export"),
    output_dir: str = typer.Option(..., "--output-dir", help="Pack output directory"),
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root for resolving relative paths"),
    title: str | None = typer.Option(None, "--title", help="Pack title"),
    version: str = typer.Option("0.1.0", "--version", help="Pack version"),
    workspace_file: str | None = typer.Option(None, "--workspace-file", help="Workspace profile file"),
    repository_map: str | None = typer.Option(None, "--repository-map", help="Repository map profile file"),
    compose_strategy: str = typer.Option("overlay-active-knowledge", "--compose-strategy", help="overlay-active-knowledge or replace-active-knowledge"),
    repack_mode: str = typer.Option("none", "--repack-mode", help="none, full-snapshot, delta-overlay, or promote-reviewed"),
    skills_dir: str | None = typer.Option(None, "--skills-dir", help="Optional skills layer source"),
    tools_dir: str | None = typer.Option(None, "--tools-dir", help="Optional tools layer source"),
    scripts_dir: str | None = typer.Option(None, "--scripts-dir", help="Optional scripts layer source"),
    commands_dir: str | None = typer.Option(None, "--commands-dir", help="Optional commands layer source"),
    prompts_dir: str | None = typer.Option(None, "--prompts-dir", help="Optional prompts layer source"),
    resources_dir: str | None = typer.Option(None, "--resources-dir", help="Optional resources layer source"),
    templates_dir: str | None = typer.Option(None, "--templates-dir", help="Optional templates layer source"),
    evaluation_scenarios_file: str | None = typer.Option(None, "--evaluation-scenarios-file", help="Optional evaluation scenarios JSON"),
    tool_alias: list[str] | None = typer.Option(None, "--tool-alias", help="Tool alias mapping as from=to; repeatable"),
    force: bool = typer.Option(False, "--force", help="Overwrite output directory"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Export a knowledge/capability directory as a portable pack."""
    project_root = _require_project(project_dir)
    args = [
        "-SourceKnowledgeDir",
        str(_resolve_path(source_knowledge_dir, base=project_root)),
        "-PackId",
        pack_id,
        "-OutputDir",
        str(_resolve_path(output_dir, base=project_root)),
        "-Version",
        version,
    ]
    _append_arg(args, "-Title", title)
    _append_arg(args, "-WorkspaceFile", _resolve_path(workspace_file, base=project_root))
    _append_arg(args, "-RepositoryMap", _resolve_path(repository_map, base=project_root))
    _append_arg(args, "-ComposeStrategy", compose_strategy)
    _append_arg(args, "-RepackMode", repack_mode)
    _append_arg(args, "-SkillsDir", _resolve_path(skills_dir, base=project_root))
    _append_arg(args, "-ToolsDir", _resolve_path(tools_dir, base=project_root))
    _append_arg(args, "-ScriptsDir", _resolve_path(scripts_dir, base=project_root))
    _append_arg(args, "-CommandsDir", _resolve_path(commands_dir, base=project_root))
    _append_arg(args, "-PromptsDir", _resolve_path(prompts_dir, base=project_root))
    _append_arg(args, "-ResourcesDir", _resolve_path(resources_dir, base=project_root))
    _append_arg(args, "-TemplatesDir", _resolve_path(templates_dir, base=project_root))
    _append_arg(args, "-EvaluationScenariosFile", _resolve_path(evaluation_scenarios_file, base=project_root))
    _append_many(args, "-ToolAlias", tool_alias)
    _append_arg(args, "-Force", force)
    result = _invoke_script("export-knowledge-pack.ps1", project_root=project_root, args=args)
    _emit_result(result, json_output=json_output, title="knowledge export-pack")


@knowledge_app.command("repack")
def knowledge_repack(
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root"),
    pack_id: str | None = typer.Option(None, "--pack-id", help="Pack id to export"),
    title: str | None = typer.Option(None, "--title", help="Pack title"),
    version: str = typer.Option("0.1.0", "--version", help="Pack version"),
    output_dir: str | None = typer.Option(None, "--output-dir", help="Pack output directory"),
    mode: str = typer.Option("full-snapshot", "--mode", help="full-snapshot, delta-overlay, or promote-reviewed"),
    compose_strategy: str = typer.Option("overlay-active-knowledge", "--compose-strategy", help="overlay-active-knowledge or replace-active-knowledge"),
    include_capabilities: bool = typer.Option(True, "--include-capabilities/--no-include-capabilities", help="Include mounted capability layers"),
    include_profiles: bool = typer.Option(False, "--include-profiles", help="Include workspace.yml and repository-map.md"),
    force: bool = typer.Option(False, "--force", help="Overwrite output directory"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Package the current enriched active knowledge layer for redistribution."""
    project_root = _require_project(project_dir)
    args = ["-RepoRoot", str(project_root)]
    _append_arg(args, "-PackId", pack_id)
    _append_arg(args, "-Title", title)
    _append_arg(args, "-Version", version)
    _append_arg(args, "-OutputDir", _resolve_path(output_dir, base=project_root))
    _append_arg(args, "-Mode", mode)
    _append_arg(args, "-ComposeStrategy", compose_strategy)
    args.append("-IncludeCapabilities:$true" if include_capabilities else "-IncludeCapabilities:$false")
    _append_arg(args, "-IncludeProfiles", include_profiles)
    _append_arg(args, "-Force", force)
    result = _invoke_script("repack-knowledge-pack.ps1", project_root=project_root, args=args)
    _emit_result(result, json_output=json_output, title="knowledge repack")


@knowledge_app.command("evaluate-synthesis")
def knowledge_evaluate_synthesis(
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root"),
    knowledge_dir: str | None = typer.Option(None, "--knowledge-dir", help="Reviewed synthesis ai/knowledge directory"),
    bootstrap_facts: str | None = typer.Option(None, "--bootstrap-facts", help="Bootstrap facts JSON"),
    claim_ledger: str | None = typer.Option(None, "--claim-ledger", help="Claim ledger JSON"),
    output_dir: str | None = typer.Option(None, "--output-dir", help="Quality output directory"),
    minimum_score: int = typer.Option(70, "--minimum-score", help="Minimum acceptable quality score"),
    fail_below_minimum: bool = typer.Option(False, "--fail-below-minimum", help="Block when score is below minimum"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Evaluate AI synthesis quality and source coverage."""
    project_root = _require_project(project_dir)
    args = ["-RepoRoot", str(project_root)]
    _append_arg(args, "-KnowledgeDir", _resolve_path(knowledge_dir, base=project_root))
    _append_arg(args, "-BootstrapFacts", _resolve_path(bootstrap_facts, base=project_root))
    _append_arg(args, "-ClaimLedger", _resolve_path(claim_ledger, base=project_root))
    _append_arg(args, "-OutputDir", _resolve_path(output_dir, base=project_root))
    _append_arg(args, "-MinimumScore", minimum_score)
    _append_arg(args, "-FailBelowMinimum", fail_below_minimum)
    result = _invoke_script("evaluate-knowledge-pack-synthesis.ps1", project_root=project_root, args=args)
    _emit_result(result, json_output=json_output, title="knowledge evaluate-synthesis")


@knowledge_app.command("validate-pack")
def knowledge_validate_pack(
    pack_root: str = typer.Argument(..., help="Pack directory to validate"),
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Optional project root used to find installed scripts"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Validate a portable knowledge pack."""
    project_root = _require_project(project_dir) if project_dir else None
    base = project_root or Path.cwd()
    args = ["-PackRoot", str(_resolve_path(pack_root, base=base))]
    result = _invoke_script("validate-knowledge-pack.ps1", project_root=project_root, args=args)
    _emit_result(result, json_output=json_output, title="knowledge validate-pack")
