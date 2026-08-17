#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer",
#     "rich",
#     "platformdirs",
#     "readchar",
#     "json5",
#     "pyyaml",
#     "packaging",
# ]
# ///
"""
Specify CLI - Setup tool for Specify projects

Usage:
    uvx specify-cli.py init <project-name>
    uvx specify-cli.py init .
    uvx specify-cli.py init --here

Or install globally:
    uv tool install --from specify-cli.py specify-cli
    specify init <project-name>
    specify init .
    specify init --here
"""

import os
import sys
import subprocess
import zipfile
import shutil
import json
import tempfile
import yaml
from pathlib import Path

from typing import Any, Optional

import typer
from rich.panel import Panel
from rich.live import Live
from rich.align import Align
from rich.table import Table
from .integration_runtime import (
    invoke_separator_for_integration as _invoke_separator_for_integration,
    resolve_integration_options as _resolve_integration_options_impl,
    with_integration_setting as _with_integration_setting,
)
from .integration_state import (
    INTEGRATION_JSON,
    INTEGRATION_STATE_SCHEMA,
    dedupe_integration_keys as _dedupe_integration_keys,
    default_integration_key as _default_integration_key,
    installed_integration_keys as _installed_integration_keys,
    integration_setting as _integration_setting,
    integration_settings as _integration_settings,
    normalize_integration_state as _normalize_integration_state,
    write_integration_json as _write_integration_json_file,
)
from .shared_infra import (
    install_shared_infra as _install_shared_infra_impl,
    refresh_shared_templates as _refresh_shared_templates_impl,
    shared_templates_source as _shared_templates_source,
)

from ._console import (
    BANNER as BANNER,
    TAGLINE as TAGLINE,
    BannerGroup,
    StepTracker,
    console,
    get_key as get_key,
    show_banner,
)
from ._assets import (
    UPSTREAM_BASELINE,
    _locate_core_pack,
    _repo_root,
    get_speckit_version as get_speckit_version,
)
from ._utils import (
    _display_project_path,
    check_tool as check_tool,
    handle_vscode_settings as handle_vscode_settings,
    init_git_repo as init_git_repo,
    is_git_repo as is_git_repo,
    merge_json_files as merge_json_files,
    run_command as run_command,
)
from ._version import (
    self_app as _self_app,
    self_check as self_check,
    self_upgrade as self_upgrade,
)
from ._knowledge import knowledge_app as _knowledge_app
from ._hooks import hook_app as _hook_app

def _locate_bundled_preset(_: str) -> Path | None:
    """Preset bundles are disabled in the Codex-only build."""
    return None


def _locate_bundled_extension(_: str) -> Path | None:
    """Extension bundles are disabled in the Codex-only build."""
    return None


def _build_agent_config() -> dict[str, dict[str, Any]]:
    """Derive AGENT_CONFIG from INTEGRATION_REGISTRY."""
    from .integrations import INTEGRATION_REGISTRY
    config: dict[str, dict[str, Any]] = {}
    for key, integration in INTEGRATION_REGISTRY.items():
        if integration.config:
            config[key] = dict(integration.config)
    return config

AGENT_CONFIG = _build_agent_config()
INIT_INTEGRATION = "codex"
INIT_AI_MESSAGE = (
    "Spec Kit init exposes one Codex entry skill and installs internal stage skills."
)

def _stdin_is_interactive() -> bool:
    return sys.stdin.isatty()

SCRIPT_TYPE_CHOICES = {"ps": "PowerShell", "py": "Python"}

app = typer.Typer(
    name="specify",
    help="Setup tool for Specify spec-driven development projects",
    add_completion=False,
    invoke_without_command=True,
    cls=BannerGroup,
)

def _version_callback(value: bool):
    if value:
        console.print(f"specify {get_speckit_version()}")
        raise typer.Exit()

@app.callback()
def callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit."),
):
    """Show banner when no subcommand is provided."""
    if ctx.invoked_subcommand is None and "--help" not in sys.argv and "-h" not in sys.argv:
        show_banner()
        console.print(Align.center("[dim]Run 'specify --help' for usage information[/dim]"))
        console.print()

def _refresh_shared_templates(
    project_path: Path,
    *,
    invoke_separator: str,
    force: bool = False,
) -> None:
    """Refresh default-sensitive shared templates without touching scripts."""
    _refresh_shared_templates_impl(
        project_path,
        version=get_speckit_version(),
        core_pack=_locate_core_pack(),
        repo_root=_repo_root(),
        console=console,
        invoke_separator=invoke_separator,
        force=force,
    )


def _install_shared_infra(
    project_path: Path,
    script_type: str,
    tracker: StepTracker | None = None,
    force: bool = False,
    invoke_separator: str = ".",
    refresh_managed: bool = False,
    refresh_hint: str | None = None,
) -> bool:
    """Install shared infrastructure files into *project_path*.

    Copies ``.specify/scripts/powershell/``, ``.specify/templates/``,
    ``.specify/checklist-rules/``, and layered ``ai/**`` templates from the
    bundled core_pack or source checkout.
    Tracks all installed files in ``speckit.manifest.json``.

    Page templates are processed to resolve ``__SPECKIT_COMMAND_<NAME>__``
    placeholders using *invoke_separator* (``"."`` for markdown agents,
    ``"-"`` for skills agents).

    Overwrite policy:

    * ``force=True``  — overwrite every existing file (still skips symlinks
      to avoid following links outside the project root).
    * ``refresh_managed=True`` — overwrite only files whose on-disk hash
      still matches the previously recorded manifest hash (i.e. unmodified
      files installed by spec-kit). Files with diverging hashes are
      treated as user customizations and preserved with a warning.
    * Default — only add missing files; existing ones are skipped.

    *refresh_hint* — caller-supplied rich-text fragment shown after the
    "Preserved customized files" warning to tell the user which flag/command
    they should re-run with to overwrite their customizations. Each caller
    passes the flag that's actually valid in its CLI surface (e.g.
    ``--refresh-shared-infra`` for ``integration switch``,
    ``--force`` for ``init``/``integration upgrade``). When ``None``, no
    remediation hint is printed for customizations.

    Returns ``True`` on success.
    """
    return _install_shared_infra_impl(
        project_path,
        script_type,
        version=get_speckit_version(),
        core_pack=_locate_core_pack(),
        repo_root=_repo_root(),
        console=console,
        force=force,
        invoke_separator=invoke_separator,
        refresh_managed=refresh_managed,
        refresh_hint=refresh_hint,
    )


def _install_shared_infra_or_exit(
    project_path: Path,
    script_type: str,
    tracker: StepTracker | None = None,
    force: bool = False,
    invoke_separator: str = ".",
    refresh_managed: bool = False,
    refresh_hint: str | None = None,
) -> bool:
    try:
        return _install_shared_infra(
            project_path,
            script_type,
            tracker=tracker,
            force=force,
            invoke_separator=invoke_separator,
            refresh_managed=refresh_managed,
            refresh_hint=refresh_hint,
        )
    except (ValueError, OSError) as exc:
        console.print(f"[red]Error:[/red] Failed to install shared infrastructure: {exc}")
        raise typer.Exit(1)


def _source_template_path(template_name: str) -> Path:
    """Resolve a bundled/source template that is not installed at runtime."""
    return _shared_templates_source(
        core_pack=_locate_core_pack(),
        repo_root=_repo_root(),
    ) / template_name


def _mount_knowledge_pack(
    project_path: Path,
    knowledge_pack: str,
    *,
    apply_profiles: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Mount a Spec Kit knowledge pack through the installed bootstrap script."""
    pack_path = Path(knowledge_pack).expanduser()
    if not pack_path.is_absolute():
        pack_path = (Path.cwd() / pack_path).resolve()
    else:
        pack_path = pack_path.resolve()
    if not pack_path.exists():
        raise ValueError(f"Knowledge pack path not found: {pack_path}")

    bootstrap_script = (
        project_path
        / ".specify"
        / "scripts"
        / "powershell"
        / "bootstrap-knowledge.ps1"
    )
    if not bootstrap_script.is_file():
        raise ValueError(f"Knowledge bootstrap script not found: {bootstrap_script}")

    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise ValueError("PowerShell is required to mount a knowledge pack")

    command = [
        shell,
        "-NoProfile",
        "-File",
        str(bootstrap_script),
        "-RepoRoot",
        str(project_path),
        "-PackPath",
        str(pack_path),
        "-Json",
    ]
    if apply_profiles:
        command.append("-ApplyProfiles")
    if force or apply_profiles:
        command.append("-Force")

    completed = subprocess.run(
        command,
        cwd=project_path,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    output = completed.stdout.strip()
    if completed.returncode != 0:
        detail = completed.stderr.strip() or output or f"exit {completed.returncode}"
        raise ValueError(f"Knowledge pack mount failed: {detail}")

    json_start = output.find("{")
    if json_start < 0:
        raise ValueError(f"Knowledge pack mount did not return JSON: {output}")
    try:
        result = json.loads(output[json_start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Knowledge pack mount returned invalid JSON: {exc}") from exc

    if result.get("status") == "blocked":
        blockers = result.get("blockers") or ["unknown blocker"]
        raise ValueError("Knowledge pack mount blocked: " + "; ".join(map(str, blockers)))
    return result


def ensure_constitution_from_template(project_path: Path, tracker: StepTracker | None = None) -> None:
    """Copy constitution template to memory if it doesn't exist (preserves existing constitution on reinitialization)."""
    memory_constitution = project_path / ".specify" / "memory" / "constitution.md"
    template_constitution = _source_template_path("constitution-template.md")

    # If constitution already exists in memory, preserve it
    if memory_constitution.exists():
        if tracker:
            tracker.add("constitution", "Constitution setup")
            tracker.skip("constitution", "existing file preserved")
        return

    # If template doesn't exist, something went wrong with extraction
    if not template_constitution.exists():
        if tracker:
            tracker.add("constitution", "Constitution setup")
            tracker.error("constitution", "template not found")
        return

    # Copy template to memory directory
    try:
        memory_constitution.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_constitution, memory_constitution)
        if tracker:
            tracker.add("constitution", "Constitution setup")
            tracker.complete("constitution", "copied from template")
        else:
            console.print("[cyan]Initialized constitution from template[/cyan]")
    except Exception as e:
        if tracker:
            tracker.add("constitution", "Constitution setup")
            tracker.error("constitution", str(e))
        else:
            console.print(f"[yellow]Warning: Could not initialize constitution: {e}[/yellow]")


def ensure_pitfalls_from_template(project_path: Path, tracker: StepTracker | None = None) -> None:
    """Copy pitfalls template to memory if it doesn't exist."""
    memory_pitfalls = project_path / ".specify" / "memory" / "pitfalls.md"
    template_pitfalls = _source_template_path("pitfalls-template.md")

    if memory_pitfalls.exists():
        if tracker:
            tracker.add("pitfalls", "Pitfalls memory setup")
            tracker.skip("pitfalls", "existing file preserved")
        return

    if not template_pitfalls.exists():
        if tracker:
            tracker.add("pitfalls", "Pitfalls memory setup")
            tracker.error("pitfalls", "template not found")
        return

    try:
        memory_pitfalls.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_pitfalls, memory_pitfalls)
        if tracker:
            tracker.add("pitfalls", "Pitfalls memory setup")
            tracker.complete("pitfalls", "copied from template")
        else:
            console.print("[cyan]Initialized pitfalls memory from template[/cyan]")
    except Exception as e:
        if tracker:
            tracker.add("pitfalls", "Pitfalls memory setup")
            tracker.error("pitfalls", str(e))
        else:
            console.print(f"[yellow]Warning: Could not initialize pitfalls memory: {e}[/yellow]")


def ensure_repository_map_from_template(project_path: Path, tracker: StepTracker | None = None) -> None:
    """Copy repository map template to memory if it doesn't exist."""
    memory_map = project_path / ".specify" / "memory" / "repository-map.md"
    template_map = _source_template_path("repository-map-template.md")

    if memory_map.exists():
        if tracker:
            tracker.add("repository-map", "Repository map setup")
            tracker.skip("repository-map", "existing file preserved")
        return

    if not template_map.exists():
        if tracker:
            tracker.add("repository-map", "Repository map setup")
            tracker.error("repository-map", "template not found")
        return

    try:
        memory_map.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_map, memory_map)
        if tracker:
            tracker.add("repository-map", "Repository map setup")
            tracker.complete("repository-map", "copied from template")
        else:
            console.print("[cyan]Initialized repository map from template[/cyan]")
    except Exception as e:
        if tracker:
            tracker.add("repository-map", "Repository map setup")
            tracker.error("repository-map", str(e))
        else:
            console.print(f"[yellow]Warning: Could not initialize repository map: {e}[/yellow]")


def ensure_workspace_from_template(project_path: Path, tracker: StepTracker | None = None) -> None:
    """Copy workspace template to .specify/workspace.yml if it doesn't exist."""
    workspace_file = project_path / ".specify" / "workspace.yml"
    template_file = _source_template_path("workspace-template.yml")

    if workspace_file.exists():
        if tracker:
            tracker.add("workspace", "Workspace setup")
            tracker.skip("workspace", "existing file preserved")
        return

    if not template_file.exists():
        if tracker:
            tracker.add("workspace", "Workspace setup")
            tracker.error("workspace", "template not found")
        return

    try:
        workspace_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_file, workspace_file)
        if tracker:
            tracker.add("workspace", "Workspace setup")
            tracker.complete("workspace", "copied from template")
    except Exception as e:
        if tracker:
            tracker.add("workspace", "Workspace setup")
            tracker.error("workspace", str(e))
        else:
            console.print(f"[yellow]Warning: Could not initialize workspace: {e}[/yellow]")


INIT_OPTIONS_FILE = ".specify/init-options.json"


def save_init_options(project_path: Path, options: dict[str, Any]) -> None:
    """Persist the CLI options used during ``specify init``.

    Writes a small JSON file to ``.specify/init-options.json`` so later
    operations can adapt their behaviour without scanning the filesystem.
    """
    dest = project_path / INIT_OPTIONS_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(options, indent=2, sort_keys=True))


def load_init_options(project_path: Path) -> dict[str, Any]:
    """Load the init options previously saved by ``specify init``.

    Returns an empty dict if the file does not exist or cannot be parsed.
    """
    path = project_path / INIT_OPTIONS_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _get_skills_dir(project_path: Path, selected_ai: str = INIT_INTEGRATION) -> Path:
    """Resolve the Codex skills directory."""
    return project_path / ".agents" / "skills"


# Constants for Codex skill generation.
DEFAULT_SKILLS_DIR = ".agents/skills"
SKILL_DESCRIPTIONS = {
    "intake": "Classify a request as migration, bugfix, validation, or new-feature before specification.",
    "specify": "Create or update feature specifications from natural language descriptions.",
    "plan": "Generate technical implementation plans from feature specifications.",
    "tasks": "Break down implementation plans into actionable task lists.",
    "implement": "Execute all tasks from the task breakdown to build the feature.",
    "analyze": "Perform cross-artifact consistency analysis across spec.md, plan.md, and tasks.md.",
    "clarify": "Structured clarification workflow for underspecified requirements.",
    "constitution": "Create or update project governing principles and development guidelines.",
    "checklist": "Generate custom quality checklists for validating requirements completeness and clarity.",
}


@app.command()
def init(
    project_name: str = typer.Argument(None, help="Name for your new project directory (optional if using --here, or use '.' for current directory)"),
    ignore_agent_tools: bool = typer.Option(False, "--ignore-agent-tools", help="Skip checks for the selected AI coding agent CLI"),
    no_git: bool = typer.Option(False, "--no-git", help="Skip git repository initialization"),
    here: bool = typer.Option(False, "--here", help="Initialize project in the current directory instead of creating a new one"),
    force: bool = typer.Option(False, "--force", help="Force refresh/overwrite bundled files when using --here (skip confirmation)"),
    knowledge_pack: str = typer.Option(None, "--knowledge-pack", help="Mount an existing Spec Kit knowledge pack during initialization"),
    knowledge_pack_apply_profiles: bool = typer.Option(False, "--knowledge-pack-apply-profiles", help="Also apply workspace.yml and repository-map profiles from --knowledge-pack"),
    debug: bool = typer.Option(False, "--debug", help="Show detailed diagnostics when initialization fails."),
    branch_numbering: str = typer.Option(None, "--branch-numbering", help="Branch numbering strategy: 'sequential' (001, 002, …, 1000, … — expands past 999 automatically) or 'timestamp' (YYYYMMDD-HHMMSS)"),
):
    """
    Initialize a new Specify project.

    Project files are scaffolded from assets bundled inside this local
    specify-cli package. This Codex-only distribution works without downloading
    templates from GitHub during initialization.

    This command will:
    1. Check that required tools are installed (git is optional)
    2. Initialize the Codex entry skill and internal stage skills
    3. Scaffold bundled project templates and workflows
    4. Optionally mount an existing knowledge pack
    5. Initialize a fresh git repository (if not --no-git and no existing repo)
    6. Install the Spec Kit skills

    Examples:
        specify init my-project
        specify init my-project --no-git
        specify init --ignore-agent-tools my-project
        specify init .                     # Initialize in current directory
        specify init --here
        specify init --here --force  # Skip confirmation when current directory not empty
        specify init --here --knowledge-pack <pack-dir>
    """

    show_banner()

    from .integrations import get_integration
    selected_ai = INIT_INTEGRATION

    resolved_integration = get_integration(selected_ai)
    if not resolved_integration:
        console.print(f"[red]Error:[/red] Integration '{selected_ai}' is not registered.")
        raise typer.Exit(1)
    console.print(f"[dim]{INIT_AI_MESSAGE}[/dim]")

    if project_name == ".":
        here = True
        project_name = None  # Clear project_name to use existing validation logic

    if here and project_name:
        console.print("[red]Error:[/red] Cannot specify both project name and --here flag")
        raise typer.Exit(1)

    if not here and not project_name:
        console.print("[red]Error:[/red] Must specify either a project name, use '.' for current directory, or use --here flag")
        raise typer.Exit(1)

    BRANCH_NUMBERING_CHOICES = {"sequential", "timestamp"}
    if branch_numbering and branch_numbering not in BRANCH_NUMBERING_CHOICES:
        console.print(f"[red]Error:[/red] Invalid --branch-numbering value '{branch_numbering}'. Choose from: {', '.join(sorted(BRANCH_NUMBERING_CHOICES))}")
        raise typer.Exit(1)

    dir_existed_before = False
    if here:
        project_name = Path.cwd().name
        project_path = Path.cwd()
        dir_existed_before = True

        existing_items = list(project_path.iterdir())
        if existing_items:
            console.print(f"[yellow]Warning:[/yellow] Current directory is not empty ({len(existing_items)} items)")
            console.print("[yellow]Bundled template files will be written into the existing directory and may overwrite existing files[/yellow]")
            if force:
                console.print("[cyan]--force supplied: skipping confirmation and refreshing bundled files[/cyan]")
            else:
                response = typer.confirm("Do you want to continue?")
                if not response:
                    console.print("[yellow]Operation cancelled[/yellow]")
                    raise typer.Exit(0)
    else:
        project_path = Path(project_name).resolve()
        dir_existed_before = project_path.exists()
        if project_path.exists():
            if not project_path.is_dir():
                console.print(f"[red]Error:[/red] '{project_name}' exists but is not a directory.")
                raise typer.Exit(1)
            existing_items = list(project_path.iterdir())
            if force:
                if existing_items:
                    console.print(f"[yellow]Warning:[/yellow] Directory '{project_name}' is not empty ({len(existing_items)} items)")
                    console.print("[yellow]Bundled template files will be written into the existing directory and may overwrite existing files[/yellow]")
                console.print(f"[cyan]--force supplied: initializing existing directory '[cyan]{project_name}[/cyan]'[/cyan]")
            else:
                error_panel = Panel(
                    f"Directory already exists: '[cyan]{project_name}[/cyan]'\n"
                    "Please choose a different project name or remove the existing directory.\n"
                    "Use [bold]--force[/bold] to initialize the existing directory.",
                    title="[red]Directory Conflict[/red]",
                    border_style="red",
                    padding=(1, 2)
                )
                console.print()
                console.print(error_panel)
                raise typer.Exit(1)

    current_dir = Path.cwd()

    setup_lines = [
        "[cyan]Specify Project Setup[/cyan]",
        "",
        f"{'Project':<15} [green]{project_path.name}[/green]",
        f"{'Working Path':<15} [dim]{current_dir}[/dim]",
    ]

    if not here:
        setup_lines.append(f"{'Target Path':<15} [dim]{project_path}[/dim]")

    console.print(Panel("\n".join(setup_lines), border_style="cyan", padding=(1, 2)))

    should_init_git = False
    if not no_git:
        should_init_git = check_tool("git")
        if not should_init_git:
            console.print("[yellow]Git not found - will skip repository initialization[/yellow]")

    if not ignore_agent_tools:
        agent_config = AGENT_CONFIG.get(selected_ai)
        if agent_config and agent_config["requires_cli"]:
            install_url = agent_config["install_url"]
            if not check_tool(selected_ai):
                error_panel = Panel(
                    f"[cyan]{selected_ai}[/cyan] not found\n"
                    f"Install from: [cyan]{install_url}[/cyan]\n"
                    f"{agent_config['name']} is required to continue with this project type.\n\n"
                    "Tip: Use [cyan]--ignore-agent-tools[/cyan] to skip this check",
                    title="[red]Agent Detection Error[/red]",
                    border_style="red",
                    padding=(1, 2)
                )
                console.print()
                console.print(error_panel)
                raise typer.Exit(1)

    selected_script = "ps"

    console.print(f"[cyan]Selected coding agent integration:[/cyan] {selected_ai}")
    console.print(f"[cyan]Selected script type:[/cyan] {selected_script}")

    tracker = StepTracker("Initialize Specify Project")

    sys._specify_tracker_active = True

    tracker.add("precheck", "Check required tools")
    tracker.complete("precheck", "ok")
    tracker.add("ai-select", "Select AI integration")
    tracker.complete("ai-select", f"{selected_ai}")
    tracker.add("script-select", "Select script runtime")
    tracker.complete("script-select", selected_script)

    tracker.add("integration", "Install integration")
    tracker.add("shared-infra", "Install shared infrastructure")

    for key, label in [
        ("constitution", "Constitution setup"),
        ("workspace", "Workspace setup"),
        ("knowledge-pack", "Knowledge pack setup"),
        ("git", "Git repository setup"),
        ("workflow", "Install bundled workflow"),
        ("final", "Finalize"),
    ]:
        tracker.add(key, label)

    git_default_notice = False
    knowledge_pack_result: dict[str, Any] | None = None

    with Live(tracker.render(), console=console, refresh_per_second=8, transient=True) as live:
        tracker.attach_refresh(lambda: live.update(tracker.render()))
        try:
            # Integration-based scaffolding
            from .integrations.manifest import IntegrationManifest
            tracker.start("integration")
            manifest = IntegrationManifest(
                resolved_integration.key, project_path, version=get_speckit_version()
            )

            resolved_integration.setup(
                project_path, manifest,
                script_type=selected_script,
            )
            manifest.save()

            integration_settings = _with_integration_setting(
                {},
                resolved_integration.key,
                resolved_integration,
                script_type=selected_script,
            )
            _write_integration_json(
                project_path,
                resolved_integration.key,
                [resolved_integration.key],
                integration_settings,
            )

            tracker.complete("integration", resolved_integration.config.get("name", resolved_integration.key))

            # Install shared infrastructure (scripts, templates)
            tracker.start("shared-infra")
            _install_shared_infra_or_exit(
                project_path,
                selected_script,
                tracker=tracker,
                force=force,
                invoke_separator=resolved_integration.effective_invoke_separator(),
            )
            tracker.complete("shared-infra", "PowerShell scripts + templates")

            ensure_constitution_from_template(project_path, tracker=tracker)
            ensure_pitfalls_from_template(project_path, tracker=tracker)
            ensure_repository_map_from_template(project_path, tracker=tracker)
            ensure_workspace_from_template(project_path, tracker=tracker)

            tracker.start("knowledge-pack")
            if knowledge_pack:
                try:
                    knowledge_pack_result = _mount_knowledge_pack(
                        project_path,
                        knowledge_pack,
                        apply_profiles=knowledge_pack_apply_profiles,
                        force=force,
                    )
                    applied_pack = (
                        knowledge_pack_result
                        .get("facts", {})
                        .get("applied_pack", {})
                    )
                    pack_id = applied_pack.get("facts", {}).get("pack_id") or "knowledge-pack"
                    tracker.complete("knowledge-pack", f"mounted {pack_id}")
                except ValueError as pack_err:
                    sanitized_pack_err = str(pack_err).replace("\n", " ").strip()
                    tracker.error("knowledge-pack", sanitized_pack_err[:120])
                    raise
            else:
                tracker.skip("knowledge-pack", "not requested")

            # Initialize git only when requested and the target is not already
            # inside a git work tree. Spec branches remain local; init does not
            # configure or push to a remote.
            tracker.start("git")
            if no_git:
                tracker.skip("git", "disabled by --no-git")
            elif not should_init_git:
                tracker.skip("git", "git not available")
            elif is_git_repo(project_path):
                tracker.skip("git", "existing repository")
            else:
                git_ok, git_error = init_git_repo(project_path, quiet=True)
                if git_ok:
                    tracker.complete("git", "initialized local repository")
                else:
                    tracker.error("git", (git_error or "failed")[:120])

            # Install bundled speckit workflow
            try:
                from ._upgrade import install_bundled_workflow, resolve_upgrade_source
                from .workflows.catalog import WorkflowRegistry

                wf_registry = WorkflowRegistry(project_path)
                workflow_should_install = not wf_registry.is_installed("speckit") or force
                source_info = resolve_upgrade_source(
                    source=None,
                    core_pack=_locate_core_pack(),
                    repo_root=_repo_root(),
                    installed_version=get_speckit_version(),
                )
                workflow_status = install_bundled_workflow(
                    project_path,
                    source_info=source_info,
                    version=get_speckit_version(),
                    force=force,
                )
                if workflow_status == "missing-source":
                    tracker.skip("workflow", "bundled workflow not found")
                elif workflow_status == "unchanged":
                    tracker.complete("workflow", "already installed")
                elif workflow_should_install and workflow_status in {"added", "forced-overwrite"}:
                    tracker.complete(
                        "workflow",
                        "speckit refreshed" if force else "speckit installed",
                    )
                elif workflow_status == "preserved-customized":
                    tracker.complete("workflow", "customized workflow preserved")
                else:
                    tracker.complete("workflow", f"speckit {workflow_status}")
            except Exception as wf_err:
                sanitized_wf = str(wf_err).replace('\n', ' ').strip()
                tracker.error("workflow", f"install failed: {sanitized_wf[:120]}")

            # Persist the CLI options so later operations can adapt their
            # behaviour without re-scanning the filesystem.
            init_opts = {
                "ai": selected_ai,
                "integration": resolved_integration.key,
                "ai_skills": True,
                "branch_numbering": branch_numbering or "sequential",
                "context_file": resolved_integration.context_file,
                "canonical_context_file": getattr(
                    resolved_integration,
                    "canonical_context_file",
                    resolved_integration.context_file,
                ),
                "here": here,
                "script": selected_script,
                "speckit_version": get_speckit_version(),
                "upstream_baseline": UPSTREAM_BASELINE,
            }
            if knowledge_pack:
                applied_pack = (
                    (knowledge_pack_result or {})
                    .get("facts", {})
                    .get("applied_pack", {})
                )
                init_opts["knowledge_pack"] = {
                    "path": str(Path(knowledge_pack).expanduser().resolve()),
                    "apply_profiles": bool(knowledge_pack_apply_profiles),
                    "status": (knowledge_pack_result or {}).get("status", "unknown"),
                    "id": applied_pack.get("facts", {}).get("pack_id", ""),
                }
            save_init_options(project_path, init_opts)
            try:
                from ._upgrade import write_spec_kit_lock

                write_spec_kit_lock(
                    project_path,
                    version=get_speckit_version(),
                    source="init",
                )
            except Exception as lock_err:
                console.print(f"[yellow]Warning:[/yellow] Could not write spec-kit lockfile: {lock_err}")

            tracker.complete("final", "project ready")
        except (typer.Exit, SystemExit):
            raise
        except Exception as e:
            tracker.error("final", str(e))
            console.print(Panel(f"Initialization failed: {e}", title="Failure", border_style="red"))
            if debug:
                _env_pairs = [
                    ("Python", sys.version.split()[0]),
                    ("Platform", sys.platform),
                    ("CWD", str(Path.cwd())),
                ]
                _label_width = max(len(k) for k, _ in _env_pairs)
                env_lines = [f"{k.ljust(_label_width)} → [bright_black]{v}[/bright_black]" for k, v in _env_pairs]
                console.print(Panel("\n".join(env_lines), title="Debug Environment", border_style="magenta"))
            if not here and project_path.exists() and not dir_existed_before:
                shutil.rmtree(project_path)
            raise typer.Exit(1)
        finally:
            pass

    console.print(tracker.render())
    console.print("\n[bold green]Project ready.[/bold green]")

    # Agent folder security notice
    agent_config = AGENT_CONFIG.get(selected_ai)
    if agent_config:
        agent_folder = agent_config["folder"]
        if agent_folder:
            security_notice = Panel(
                f"Some agents may store credentials, auth tokens, or other identifying and private artifacts in the agent folder within your project.\n"
                f"Consider adding [cyan]{agent_folder}[/cyan] (or parts of it) to [cyan].gitignore[/cyan] to prevent accidental credential leakage.",
                title="[yellow]Agent Folder Security[/yellow]",
                border_style="yellow",
                padding=(1, 2)
            )
            console.print()
            console.print(security_notice)

    steps_lines = []
    if not here:
        steps_lines.append(f"1. Go to the project folder: [cyan]cd {project_name}[/cyan]")
        step_num = 2
    else:
        steps_lines.append("1. You're already in the project directory!")
        step_num = 2

    integration_name = (
        resolved_integration.config.get("name", selected_ai)
        if resolved_integration.config
        else selected_ai
    )
    skills_path = _get_skills_dir(project_path, selected_ai)
    try:
        skills_display = skills_path.relative_to(project_path).as_posix()
    except ValueError:
        skills_display = str(skills_path)
    steps_lines.append(
        f"{step_num}. Start {integration_name} in this project directory; "
        f"spec-kit skills were installed to [cyan]{skills_display}[/cyan]"
    )
    step_num += 1

    if knowledge_pack_result:
        applied_pack = (
            knowledge_pack_result
            .get("facts", {})
            .get("applied_pack", {})
        )
        pack_id = applied_pack.get("facts", {}).get("pack_id") or "knowledge-pack"
        steps_lines.append(
            f"{step_num}. Knowledge pack [cyan]{pack_id}[/cyan] is active in [cyan]ai/knowledge[/cyan]."
        )
        step_num += 1

    steps_lines.append(f"{step_num}. Start the workflow with the exposed Codex skill:")
    steps_lines.append("   [cyan]$speckit-specify[/] - capture the request and route the smallest needed workflow.")
    steps_lines.append(
        "   Internal stage skills live under [cyan].agents/spec-kit/skills[/] and are loaded "
        "on demand through [cyan]ai/workflows/skill-routing.yml[/]."
    )
    steps_lines.append(
        "   The agent should continue stages automatically until human acceptance, "
        "clarification, high-risk confirmation, validation failure, or a real blocker is reached."
    )

    steps_panel = Panel("\n".join(steps_lines), title="Next Steps", border_style="cyan", padding=(1,2))
    console.print()
    console.print(steps_panel)

@app.command()
def check():
    """Check that all required tools are installed."""
    show_banner()
    console.print("[bold]Checking for installed tools...[/bold]\n")

    tracker = StepTracker("Check Available Tools")

    tracker.add("git", "Git version control")
    git_ok = check_tool("git", tracker=tracker)

    agent_results = {}
    for agent_key, agent_config in AGENT_CONFIG.items():
        agent_name = agent_config["name"]
        requires_cli = agent_config["requires_cli"]

        tracker.add(agent_key, agent_name)

        if requires_cli:
            agent_results[agent_key] = check_tool(agent_key, tracker=tracker)
        else:
            # IDE-based agent - skip CLI check and mark as optional
            tracker.skip(agent_key, "IDE-based, no CLI check")
            agent_results[agent_key] = False  # Don't count IDE agents as "found"

    # Check VS Code variants (not in agent config)
    tracker.add("code", "Visual Studio Code")
    check_tool("code", tracker=tracker)

    tracker.add("code-insiders", "Visual Studio Code Insiders")
    check_tool("code-insiders", tracker=tracker)

    console.print(tracker.render())

    console.print("\n[bold green]Specify CLI is ready to use![/bold green]")

    if not git_ok:
        console.print("[dim]Tip: Install git for repository management[/dim]")

    if not any(agent_results.values()):
        console.print("[dim]Tip: Install a coding agent for the best experience[/dim]")


def _current_project_speckit_version(project_root: Path) -> str:
    """Return the version recorded in project state, falling back conservatively."""
    from ._upgrade import get_current_project_version

    return get_current_project_version(project_root)


def _upgrade_invoke_separator(project_root: Path) -> str:
    """Resolve the current integration command separator for template refresh."""
    from .integrations import get_integration

    current = _read_integration_json(project_root)
    key = _default_integration_key(current) or INIT_INTEGRATION
    integration = get_integration(key)
    if integration is None:
        return "."
    try:
        _, parsed_options = _resolve_integration_options(integration, current, key, None)
        return _invoke_separator_for_integration(integration, current, key, parsed_options)
    except Exception:
        return integration.effective_invoke_separator()


def _print_upgrade_plan(plan: dict[str, Any]) -> None:
    table = Table(title="Spec Kit Upgrade Plan")
    table.add_column("Item")
    table.add_column("Count", justify="right")
    for key, label in [
        ("added", "Add managed assets"),
        ("updated", "Update unchanged managed assets"),
        ("forced_overwrite", "Force overwrite"),
        ("preserved_customized", "Preserve customized assets"),
        ("skipped_untracked", "Skip untracked existing assets"),
        ("removed_stale", "Remove stale tracked assets"),
        ("preserved_stale", "Preserve stale customized assets"),
        ("unchanged", "Already current"),
    ]:
        table.add_row(label, str(len(plan.get(key, []))))
    workflow = plan.get("workflow", {})
    table.add_row("Bundled workflow", workflow.get("status", "unknown"))
    console.print(table)
    console.print(
        f"Current: [cyan]{plan['current_version']}[/cyan]  "
        f"Target: [cyan]{plan['target_version']}[/cyan]  "
        f"Source: [cyan]{plan['source']}[/cyan]"
    )
    for key in ["preserved_customized", "skipped_untracked", "preserved_stale"]:
        values = plan.get(key, [])
        if values:
            console.print(f"[yellow]{key}[/yellow]:")
            for rel in values[:20]:
                console.print(f"  {rel}")
            if len(values) > 20:
                console.print(f"  ... {len(values) - 20} more")


@app.command("upgrade")
def upgrade(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the upgrade plan without writing files"),
    force: bool = typer.Option(False, "--force", help="Overwrite customized managed assets"),
    source: str | None = typer.Option(None, "--source", help="Use a local spec-kit source checkout instead of the installed package"),
    version: str | None = typer.Option(None, "--version", help="Require the upgrade source to match this version"),
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root to upgrade"),
    skip_validation: bool = typer.Option(False, "--skip-validation", help="Do not run post-upgrade validation gates"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Upgrade Spec Kit-managed assets in the current project.

    This command upgrades project assets from a confirmed Spec Kit source:
    the installed package/core pack by default, or a local source checkout
    passed with ``--source``. It does not pull a remote branch implicitly.
    """
    from ._upgrade import (
        apply_project_upgrade,
        build_upgrade_plan,
        capture_upgrade_snapshot,
        resolve_upgrade_source,
        restore_upgrade_snapshot,
        run_post_upgrade_validations,
    )
    from ._project_status import build_project_status

    project_root = _require_specify_project(project_dir)
    current_version = _current_project_speckit_version(project_root)
    try:
        source_info = resolve_upgrade_source(
            source=source,
            core_pack=_locate_core_pack(),
            repo_root=_repo_root(),
            installed_version=get_speckit_version(),
        )
    except ValueError as exc:
        if json_output:
            console.print(json.dumps({"status": "blocked", "blockers": [str(exc)]}, ensure_ascii=False))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if version and source_info["version"] != version:
        blocker = (
            f"Requested version {version} does not match upgrade source version "
            f"{source_info['version']}."
        )
        if json_output:
            console.print(json.dumps({"status": "blocked", "blockers": [blocker]}, ensure_ascii=False))
        else:
            console.print(f"[red]Error:[/red] {blocker}")
            console.print("Install or select the desired Spec Kit release first, then rerun upgrade.")
        raise typer.Exit(1)

    invoke_separator = _upgrade_invoke_separator(project_root)
    plan = build_upgrade_plan(
        project_root,
        source_info=source_info,
        current_version=current_version,
        invoke_separator=invoke_separator,
        force=force,
    )

    result: dict[str, Any] = {
        "status": "planned" if dry_run else "ok",
        "dry_run": dry_run,
        "plan": plan,
        "applied": None,
        "validations": [],
        "blockers": [],
        "transaction": {"captured": False, "rolled_back": False, "rollback_errors": []},
    }

    if dry_run:
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            _print_upgrade_plan(plan)
        return

    try:
        snapshot = capture_upgrade_snapshot(project_root, plan)
        result["transaction"]["captured"] = True
    except (OSError, ValueError) as exc:
        result["status"] = "blocked"
        result["blockers"].append(f"Could not create upgrade rollback snapshot: {exc}")
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            console.print(f"[red]Blocked:[/red] {result['blockers'][0]}")
        raise typer.Exit(1)

    try:
        applied = apply_project_upgrade(
            project_root,
            source_info=source_info,
            current_version=current_version,
            invoke_separator=invoke_separator,
            force=force,
            console=console,
        )
        result["applied"] = applied

        init_options = load_init_options(project_root)
        init_options["speckit_version"] = source_info["version"]
        init_options["speckit_upgrade_lock"] = applied.get("lock_file", "")
        save_init_options(project_root, init_options)

        if not skip_validation:
            validations = run_post_upgrade_validations(project_root)
            result["validations"] = validations
            failed = [
                item.get("tool", "validation")
                for item in validations
                if item.get("status") != "ok"
            ]
            if failed:
                result["status"] = "blocked"
                result["blockers"].append(
                    "Post-upgrade validation did not pass: " + ", ".join(failed)
                )
    except Exception as exc:
        result["status"] = "blocked"
        result["blockers"].append(f"Project asset upgrade failed: {exc}")

    if result["status"] == "blocked":
        rollback_errors = restore_upgrade_snapshot(project_root, snapshot)
        result["transaction"]["rolled_back"] = not rollback_errors
        result["transaction"]["rollback_errors"] = rollback_errors
        if rollback_errors:
            result["blockers"].append(
                "Upgrade rollback was incomplete: " + "; ".join(rollback_errors)
            )

    unresolved_upgrade_items = [
        {"kind": key, "paths": plan.get(key, [])}
        for key in ["preserved_customized", "skipped_untracked", "preserved_stale"]
        if plan.get(key)
    ]
    workflow_status = (plan.get("workflow") or {}).get("status", "")
    if workflow_status in {"preserved-customized", "skipped-untracked", "missing-source"}:
        unresolved_upgrade_items.append(
            {"kind": "workflow", "paths": [plan["workflow"].get("path", "")]}
        )
    result["unresolved_upgrade_items"] = unresolved_upgrade_items

    project_status = build_project_status(
        project_root,
        target_version=source_info["version"],
    )
    result["project_status"] = project_status
    if result["status"] == "ok" and (
        project_status["status"] != "current" or unresolved_upgrade_items
    ):
        result["status"] = "warning"

    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["status"] == "blocked":
            for blocker in result["blockers"]:
                console.print(f"[red]Blocked:[/red] {blocker}")
            if result["transaction"]["rolled_back"]:
                console.print("[green]Rollback complete:[/green] project files were restored.")
        else:
            applied = result["applied"] or {}
            console.print(
                f"[green]OK[/green] Spec Kit project assets upgraded "
                f"{current_version} -> {source_info['version']}"
            )
            console.print(f"Lockfile: [cyan]{applied.get('lock_file', '')}[/cyan]")
            console.print(f"Manifest: [cyan]{applied.get('manifest', '')}[/cyan]")
            if unresolved_upgrade_items:
                console.print("[yellow]Warning:[/yellow] Some managed assets were preserved or skipped.")
                console.print("Review the dry-run plan, then rerun with [cyan]--force[/cyan] only when the overwrite is intended.")
            if project_status["status"] != "current":
                console.print("[yellow]Warning:[/yellow] Some project assets are not fully verified against the target version.")
                for action in project_status.get("next_actions", []):
                    console.print(f"  {action}")

    if result["status"] == "blocked":
        raise typer.Exit(1)


def _feature_capabilities() -> dict[str, bool]:
    """Return stable local CLI capability flags for humans and agents."""
    return {
        "controlled_multi_install_integrations": False,
        "integration_use_command": True,
        "multi_install_safe_registry_metadata": True,
        "integration_upgrade_command": True,
        "self_check_command": True,
        "workflow_catalog": False,
        "bundled_templates": True,
    }


@app.command()
def version(
    features: bool = typer.Option(
        False,
        "--features",
        help="Show local CLI feature capabilities.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit feature capabilities as JSON. Requires --features.",
    ),
):
    """Display version and system information."""
    import platform

    cli_version = get_speckit_version()

    if json_output and not features:
        console.print("[red]Error:[/red] --json requires --features.")
        raise typer.Exit(1)

    if features:
        capabilities = _feature_capabilities()
        if json_output:
            payload = {"version": cli_version, "features": capabilities}
            console.print(json.dumps(payload, indent=2))
            return

        console.print(f"Spec Kit CLI: {cli_version}")
        console.print()
        console.print("Features:")
        for key, enabled in capabilities.items():
            label = key.replace("_", " ")
            console.print(f"- {label}: {'yes' if enabled else 'no'}")
        return

    show_banner()

    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Key", style="cyan", justify="right")
    info_table.add_column("Value", style="white")

    info_table.add_row("CLI Version", cli_version)
    info_table.add_row("", "")
    info_table.add_row("Python", platform.python_version())
    info_table.add_row("Platform", platform.system())
    info_table.add_row("Architecture", platform.machine())
    info_table.add_row("OS Version", platform.version())

    panel = Panel(
        info_table,
        title="[bold cyan]Specify CLI Information[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    )

    console.print(panel)
    console.print()

app.add_typer(_knowledge_app, name="knowledge")
app.add_typer(_hook_app, name="hook")
app.add_typer(_self_app, name="self")


# ===== Integration Commands =====

integration_app = typer.Typer(
    name="integration",
    help="Manage coding agent integrations",
    add_completion=False,
)
app.add_typer(integration_app, name="integration")

def _read_integration_json(project_root: Path) -> dict[str, Any]:
    """Load ``.specify/integration.json``. Returns normalized state when present."""
    path = project_root / INTEGRATION_JSON
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        console.print(f"[red]Error:[/red] {path} contains invalid JSON.")
        console.print(f"Please fix or delete {INTEGRATION_JSON} and retry.")
        console.print(f"[dim]Details:[/dim] {exc}")
        raise typer.Exit(1)
    except OSError as exc:
        console.print(f"[red]Error:[/red] Could not read {path}.")
        console.print(f"Please fix file permissions or delete {INTEGRATION_JSON} and retry.")
        console.print(f"[dim]Details:[/dim] {exc}")
        raise typer.Exit(1)
    if not isinstance(data, dict):
        console.print(f"[red]Error:[/red] {path} must contain a JSON object, got {type(data).__name__}.")
        console.print(f"Please fix or delete {INTEGRATION_JSON} and retry.")
        raise typer.Exit(1)
    schema = data.get("integration_state_schema")
    if isinstance(schema, int) and not isinstance(schema, bool) and schema > INTEGRATION_STATE_SCHEMA:
        console.print(
            f"[red]Error:[/red] {path} uses integration state schema {schema}, "
            f"but this CLI only supports schema {INTEGRATION_STATE_SCHEMA}."
        )
        console.print("Please upgrade Spec Kit before modifying integrations.")
        raise typer.Exit(1)
    return _normalize_integration_state(data)


def _write_integration_json(
    project_root: Path,
    integration_key: str | None,
    installed_integrations: list[str] | None = None,
    integration_settings: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Write ``.specify/integration.json`` with legacy-compatible state."""
    _write_integration_json_file(
        project_root,
        version=get_speckit_version(),
        integration_key=integration_key,
        installed_integrations=installed_integrations,
        settings=integration_settings,
    )


def _clear_init_options_for_integration(project_root: Path, integration_key: str) -> None:
    """Clear active integration keys from init-options.json when they match."""
    opts = load_init_options(project_root)
    if opts.get("integration") == integration_key or opts.get("ai") == integration_key:
        opts.pop("integration", None)
        opts.pop("ai", None)
        opts.pop("ai_skills", None)
        opts.pop("context_file", None)
        opts.pop("canonical_context_file", None)
        save_init_options(project_root, opts)


def _remove_integration_json(project_root: Path) -> None:
    """Remove ``.specify/integration.json`` if it exists."""
    path = project_root / INTEGRATION_JSON
    if path.exists():
        path.unlink()


_MANIFEST_READ_ERRORS = (ValueError, FileNotFoundError, OSError, UnicodeDecodeError)


class _SharedTemplateRefreshError(RuntimeError):
    """Raised when default integration metadata should not be persisted."""


def _normalize_script_type(script_type: str, source: str) -> str:
    """Normalize and validate a script type from CLI/config sources."""
    normalized = script_type.strip().lower()
    if normalized in SCRIPT_TYPE_CHOICES:
        return normalized
    console.print(
        f"[red]Error:[/red] Invalid script type {script_type!r} from {source}. "
        f"Expected one of: {', '.join(sorted(SCRIPT_TYPE_CHOICES.keys()))}."
    )
    raise typer.Exit(1)


def _resolve_script_type(project_root: Path, script_type: str | None) -> str:
    """Resolve the script type from the CLI flag or init-options.json."""
    if script_type:
        return _normalize_script_type(script_type, "--script")
    opts = load_init_options(project_root)
    saved = opts.get("script")
    if isinstance(saved, str) and saved.strip():
        return _normalize_script_type(saved, ".specify/init-options.json")
    return "ps"


def _resolve_integration_script_type(
    project_root: Path,
    state: dict[str, Any],
    key: str,
    script_type: str | None = None,
) -> str:
    """Resolve script type for an integration, preferring stored settings."""
    if script_type:
        return _normalize_script_type(script_type, "--script")

    stored = _integration_setting(state, key).get("script")
    if isinstance(stored, str) and stored.strip():
        return _normalize_script_type(stored, f"{INTEGRATION_JSON} integration_settings.{key}.script")

    return _resolve_script_type(project_root, None)


def _resolve_integration_options(
    integration: Any,
    state: dict[str, Any],
    key: str,
    raw_options: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Resolve raw and parsed options for an integration operation."""
    return _resolve_integration_options_impl(
        integration,
        state,
        key,
        raw_options,
        parse_options=_parse_integration_options,
    )


def _set_default_integration(
    project_root: Path,
    state: dict[str, Any],
    key: str,
    integration: Any,
    installed_keys: list[str],
    *,
    script_type: str | None = None,
    raw_options: str | None = None,
    parsed_options: dict[str, Any] | None = None,
    refresh_templates: bool = True,
    refresh_templates_force: bool = False,
) -> None:
    """Persist *key* as default and align active runtime metadata."""
    resolved_script = _resolve_integration_script_type(project_root, state, key, script_type)
    settings = _with_integration_setting(
        state,
        key,
        integration,
        script_type=resolved_script,
        raw_options=raw_options,
        parsed_options=parsed_options,
    )

    if refresh_templates:
        try:
            _refresh_shared_templates(
                project_root,
                invoke_separator=_invoke_separator_for_integration(
                    integration, {"integration_settings": settings}, key, parsed_options
                ),
                force=refresh_templates_force,
            )
        except (ValueError, OSError) as exc:
            raise _SharedTemplateRefreshError(
                f"Failed to refresh shared templates for '{key}': {exc}"
            ) from exc

    _write_integration_json(project_root, key, installed_keys, settings)
    _update_init_options_for_integration(project_root, integration, script_type=resolved_script)


def _set_default_integration_or_exit(*args: Any, **kwargs: Any) -> None:
    try:
        _set_default_integration(*args, **kwargs)
    except _SharedTemplateRefreshError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


def _resolve_project_root_arg(project_dir: str | Path | None = None) -> Path:
    candidate = project_dir
    if candidate is None or str(candidate).strip() == "":
        candidate = os.environ.get("SPECIFY_INIT_DIR", "")
    if candidate is None or str(candidate).strip() == "":
        current = Path.cwd().resolve()
        for path in [current, *current.parents]:
            if (path / ".specify").is_dir():
                return path
        return current
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _require_specify_project(project_dir: str | Path | None = None) -> Path:
    """Return the current project root if it is a spec-kit project, else exit."""
    project_root = _resolve_project_root_arg(project_dir)
    if (project_root / ".specify").is_dir():
        return project_root
    console.print(f"[red]Error:[/red] Not a spec-kit project: {project_root}")
    console.print("Pass --project-dir <dir> or run this command from a spec-kit project root.")
    raise typer.Exit(1)


@integration_app.command("list")
def integration_list(
    catalog: bool = typer.Option(False, "--catalog", help="Deprecated no-op; remote catalogs are disabled in the Codex-only build"),
):
    """List available integrations and installed status."""
    from .integrations import INTEGRATION_REGISTRY

    project_root = _require_specify_project()
    current = _read_integration_json(project_root)
    default_key = _default_integration_key(current)
    installed_keys = set(_installed_integration_keys(current))

    if catalog:
        console.print("[yellow]Remote integration catalogs are disabled in this Codex-only build.[/yellow]")

    table = Table(title="Coding Agent Integrations")
    table.add_column("Key", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("CLI Required")
    table.add_column("Multi-install Safe")

    for key in sorted(INTEGRATION_REGISTRY.keys()):
        integration = INTEGRATION_REGISTRY[key]
        cfg = integration.config or {}
        name = cfg.get("name", key)
        requires_cli = cfg.get("requires_cli", False)

        if key == default_key:
            status = "[green]installed (default)[/green]"
        elif key in installed_keys:
            status = "[green]installed[/green]"
        else:
            status = ""

        cli_req = "yes" if requires_cli else "no (IDE)"
        safe = "yes" if getattr(integration, "multi_install_safe", False) else "no"
        table.add_row(key, name, status, cli_req, safe)

    console.print(table)

    if installed_keys:
        console.print(f"\n[dim]Default integration:[/dim] [cyan]{default_key or 'none'}[/cyan]")
        console.print(f"[dim]Installed integrations:[/dim] [cyan]{', '.join(sorted(installed_keys))}[/cyan]")
    else:
        console.print("\n[yellow]No integration currently installed.[/yellow]")
        console.print("Install one with: [cyan]specify integration install <key>[/cyan]")


@integration_app.command("status")
def integration_status(
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable integration diagnostics"),
):
    """Show project-local integration diagnostics."""
    from .integrations import INTEGRATION_REGISTRY

    project_root = _require_specify_project()
    current = _read_integration_json(project_root)
    default_key = _default_integration_key(current) or ""
    installed_keys = _installed_integration_keys(current)
    integrations: list[dict[str, Any]] = []

    for key in sorted(INTEGRATION_REGISTRY.keys()):
        integration = INTEGRATION_REGISTRY[key]
        cfg = integration.config or {}
        folder = str(cfg.get("folder", ""))
        commands_subdir = str(cfg.get("commands_subdir", ""))
        internal_subdir = str(cfg.get("internal_skills_subdir", ""))
        context_file = getattr(integration, "context_file", "")
        paths = {
            "folder": str(project_root / folder) if folder else "",
            "commands_dir": str(project_root / folder / commands_subdir) if folder and commands_subdir else "",
            "internal_skills_dir": str(project_root / folder / internal_subdir) if folder and internal_subdir else "",
            "context_file": str(project_root / context_file) if context_file else "",
        }
        path_status = {
            name: (Path(value).exists() if value else False)
            for name, value in paths.items()
        }
        integrations.append(
            {
                "key": key,
                "name": cfg.get("name", key),
                "installed": key in installed_keys,
                "default": key == default_key,
                "requires_cli": bool(cfg.get("requires_cli", False)),
                "multi_install_safe": bool(getattr(integration, "multi_install_safe", False)),
                "paths": paths,
                "path_status": path_status,
                "exposed_skill_names": list(cfg.get("exposed_skill_names", [])),
            }
        )

    payload = {
        "project_root": str(project_root),
        "integration_state_path": str(project_root / INTEGRATION_JSON),
        "integration_state_exists": (project_root / INTEGRATION_JSON).is_file(),
        "codex_only": True,
        "default_integration": default_key,
        "installed_integrations": installed_keys,
        "integrations": integrations,
    }

    if json_output:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return

    console.print("\n[bold cyan]Integration Status[/bold cyan]")
    console.print(f"Project: [cyan]{payload['project_root']}[/cyan]")
    console.print(f"Default: [cyan]{default_key or 'none'}[/cyan]")
    console.print(f"Installed: [cyan]{', '.join(installed_keys) if installed_keys else 'none'}[/cyan]")
    for item in integrations:
        state = "default" if item["default"] else "installed" if item["installed"] else "available"
        console.print(f"\n[bold]{item['key']}[/bold] ({state})")
        for path_name, exists in item["path_status"].items():
            style = "green" if exists else "yellow"
            console.print(f"  {path_name}: [{style}]{'ok' if exists else 'missing'}[/{style}] {item['paths'][path_name]}")


@integration_app.command("install")
def integration_install(
    key: str = typer.Argument(help="Integration key to install (codex)"),
    script: str | None = typer.Option(None, "--script", help="Script type: ps (default: from init-options.json or PowerShell)"),
    force: bool = typer.Option(False, "--force", help="Allow multi-install when integrations are not declared safe"),
    integration_options: str | None = typer.Option(None, "--integration-options", help='Options for the integration (e.g. --integration-options="--commands-dir .myagent/cmds")'),
):
    """Install an integration into an existing project."""
    from .integrations import INTEGRATION_REGISTRY, get_integration
    from .integrations.manifest import IntegrationManifest

    project_root = _require_specify_project()
    integration = get_integration(key)
    if integration is None:
        console.print(f"[red]Error:[/red] Unknown integration '{key}'")
        available = ", ".join(sorted(INTEGRATION_REGISTRY.keys()))
        console.print(f"Available integrations: {available}")
        raise typer.Exit(1)

    current = _read_integration_json(project_root)
    default_key = _default_integration_key(current)
    installed_keys = _installed_integration_keys(current)

    if key in installed_keys:
        console.print(f"[yellow]Integration '{key}' is already installed.[/yellow]")
        if default_key == key:
            console.print("It is already the default integration.")
        else:
            console.print(
                f"To make it the default integration, run "
                f"[cyan]specify integration use {key}[/cyan]."
            )
        console.print(
            f"To refresh its managed files or options, run "
            f"[cyan]specify integration upgrade {key}[/cyan]."
        )
        console.print("No files were changed.")
        raise typer.Exit(0)

    if installed_keys and not force:
        unsafe_keys = []
        for installed_key in installed_keys:
            installed_integration = get_integration(installed_key)
            if not installed_integration or not getattr(installed_integration, "multi_install_safe", False):
                unsafe_keys.append(installed_key)
        if unsafe_keys or not getattr(integration, "multi_install_safe", False):
            console.print(
                f"[red]Error:[/red] Installed integrations: {', '.join(installed_keys)}."
            )
            if default_key:
                console.print(f"Default integration: [cyan]{default_key}[/cyan].")
            console.print(
                "Installing multiple integrations is only automatic when all involved "
                "integrations are declared multi-install safe."
            )
            console.print(
                f"To replace the default integration, run "
                f"[cyan]specify integration switch {key}[/cyan]."
            )
            console.print(
                f"To install '{key}' alongside the existing integrations anyway, "
                "retry the same install command with [cyan]--force[/cyan]."
            )
            raise typer.Exit(1)

    selected_script = _resolve_script_type(project_root, script)

    # Build parsed options from --integration-options so the integration
    # can determine its effective invoke separator before shared infra
    # is installed.
    raw_options, parsed_options = _resolve_integration_options(
        integration, current, key, integration_options
    )

    # Ensure shared infrastructure is present (safe to run unconditionally;
    # _install_shared_infra merges missing files without overwriting).
    infra_integration = integration
    infra_key = key
    infra_parsed = parsed_options
    if default_key:
        default_integration = get_integration(default_key)
        if default_integration is not None:
            infra_integration = default_integration
            infra_key = default_key
            _, infra_parsed = _resolve_integration_options(
                default_integration, current, default_key, None
            )
    _install_shared_infra_or_exit(
        project_root,
        selected_script,
        invoke_separator=_invoke_separator_for_integration(
            infra_integration, current, infra_key, infra_parsed
        ),
    )
    manifest = IntegrationManifest(
        integration.key, project_root, version=get_speckit_version()
    )

    try:
        integration.setup(
            project_root, manifest,
            parsed_options=parsed_options,
            script_type=selected_script,
            raw_options=raw_options,
        )
        manifest.save()
        new_installed = _dedupe_integration_keys([*installed_keys, integration.key])
        new_default = default_key or integration.key
        settings = _with_integration_setting(
            current,
            integration.key,
            integration,
            script_type=selected_script,
            raw_options=raw_options,
            parsed_options=parsed_options,
        )
        _write_integration_json(project_root, new_default, new_installed, settings)
        if new_default == integration.key:
            _update_init_options_for_integration(project_root, integration, script_type=selected_script)

    except Exception as e:
        # Attempt rollback of any files written by setup
        try:
            integration.teardown(project_root, manifest, force=True)
        except Exception as rollback_err:
            # Suppress so the original setup error remains the primary failure
            console.print(f"[yellow]Warning:[/yellow] Failed to roll back integration changes: {rollback_err}")
        if installed_keys:
            _write_integration_json(
                project_root, default_key, installed_keys, _integration_settings(current)
            )
        else:
            _remove_integration_json(project_root)
        console.print(f"[red]Error:[/red] Failed to install integration: {e}")
        raise typer.Exit(1)

    name = (integration.config or {}).get("name", key)
    console.print(f"\n[green]OK[/green] Integration '{name}' installed successfully")
    if default_key:
        console.print(f"[dim]Default integration remains:[/dim] [cyan]{default_key}[/cyan]")


def _parse_integration_options(integration: Any, raw_options: str) -> dict[str, Any] | None:
    """Parse --integration-options string into a dict matching the integration's declared options.

    Returns ``None`` when no options are provided.
    """
    import shlex
    parsed: dict[str, Any] = {}
    tokens = shlex.split(raw_options)
    declared_options = list(integration.options())
    declared = {opt.name.lstrip("-"): opt for opt in declared_options}
    allowed = ", ".join(sorted(opt.name for opt in declared_options))
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token.startswith("-"):
            console.print(f"[red]Error:[/red] Unexpected integration option value '{token}'.")
            if allowed:
                console.print(f"Allowed options: {allowed}")
            raise typer.Exit(1)
        name = token.lstrip("-")
        value: str | None = None
        # Handle --name=value syntax
        if "=" in name:
            name, value = name.split("=", 1)
        opt = declared.get(name)
        if not opt:
            console.print(f"[red]Error:[/red] Unknown integration option '{token}'.")
            if allowed:
                console.print(f"Allowed options: {allowed}")
            raise typer.Exit(1)
        key = name.replace("-", "_")
        if opt.is_flag:
            if value is not None:
                console.print(f"[red]Error:[/red] Option '{opt.name}' is a flag and does not accept a value.")
                raise typer.Exit(1)
            parsed[key] = True
            i += 1
        elif value is not None:
            parsed[key] = value
            i += 1
        elif i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
            parsed[key] = tokens[i + 1]
            i += 2
        else:
            console.print(f"[red]Error:[/red] Option '{opt.name}' requires a value.")
            raise typer.Exit(1)
    return parsed or None


def _update_init_options_for_integration(
    project_root: Path,
    integration: Any,
    script_type: str | None = None,
) -> None:
    """Update ``init-options.json`` to reflect *integration* as the active one."""
    from .integrations.base import SkillsIntegration
    opts = load_init_options(project_root)
    opts["integration"] = integration.key
    opts["ai"] = integration.key
    opts["context_file"] = integration.context_file
    opts["canonical_context_file"] = getattr(
        integration,
        "canonical_context_file",
        integration.context_file,
    )
    if script_type:
        opts["script"] = script_type
    if isinstance(integration, SkillsIntegration) or getattr(integration, "_skills_mode", False):
        opts["ai_skills"] = True
    else:
        opts.pop("ai_skills", None)
    save_init_options(project_root, opts)


@integration_app.command("use")
def integration_use(
    key: str = typer.Argument(help="Installed integration key to make the default"),
    force: bool = typer.Option(False, "--force", help="Overwrite managed shared templates while changing the default"),
):
    """Set the default integration without uninstalling other integrations."""
    from .integrations import get_integration

    project_root = _require_specify_project()
    current = _read_integration_json(project_root)
    installed_keys = _installed_integration_keys(current)
    if key not in installed_keys:
        console.print(f"[red]Error:[/red] Integration '{key}' is not installed.")
        if installed_keys:
            console.print(f"[yellow]Installed integrations:[/yellow] {', '.join(installed_keys)}")
        else:
            console.print("Install one with: [cyan]specify integration install <key>[/cyan]")
        raise typer.Exit(1)

    integration = get_integration(key)
    if integration is None:
        console.print(f"[red]Error:[/red] Unknown integration '{key}'")
        raise typer.Exit(1)

    raw_options, parsed_options = _resolve_integration_options(integration, current, key, None)
    _set_default_integration_or_exit(
        project_root,
        current,
        key,
        integration,
        installed_keys,
        raw_options=raw_options,
        parsed_options=parsed_options,
        refresh_templates_force=force,
    )
    console.print(f"[green]✓[/green] Default integration set to [bold]{key}[/bold].")


@integration_app.command("uninstall")
def integration_uninstall(
    key: str = typer.Argument(None, help="Integration key to uninstall (default: current integration)"),
    force: bool = typer.Option(False, "--force", help="Remove files even if modified"),
):
    """Uninstall an integration, safely preserving modified files."""
    from .integrations import get_integration
    from .integrations.manifest import IntegrationManifest

    project_root = _require_specify_project()
    current = _read_integration_json(project_root)
    default_key = _default_integration_key(current)
    installed_keys = _installed_integration_keys(current)

    if key is None:
        if not default_key:
            console.print("[yellow]No integration is currently installed.[/yellow]")
            raise typer.Exit(0)
        key = default_key

    if key not in installed_keys:
        console.print(f"[red]Error:[/red] Integration '{key}' is not installed.")
        raise typer.Exit(1)

    integration = get_integration(key)

    manifest_path = project_root / ".specify" / "integrations" / f"{key}.manifest.json"
    if not manifest_path.exists():
        console.print(f"[yellow]No manifest found for integration '{key}'. Nothing to uninstall.[/yellow]")
        remaining = [installed for installed in installed_keys if installed != key]
        new_default = default_key if default_key != key else (remaining[0] if remaining else None)
        if remaining:
            if default_key == key and new_default and (new_integration := get_integration(new_default)):
                raw_options, parsed_options = _resolve_integration_options(
                    new_integration, current, new_default, None
                )
                _set_default_integration_or_exit(
                    project_root,
                    current,
                    new_default,
                    new_integration,
                    remaining,
                    raw_options=raw_options,
                    parsed_options=parsed_options,
                )
            else:
                _write_integration_json(
                    project_root, new_default, remaining, _integration_settings(current)
                )
        else:
            _remove_integration_json(project_root)
        if default_key == key:
            _clear_init_options_for_integration(project_root, key)
        raise typer.Exit(0)

    try:
        manifest = IntegrationManifest.load(key, project_root)
    except _MANIFEST_READ_ERRORS as exc:
        console.print(f"[red]Error:[/red] Integration manifest for '{key}' is unreadable.")
        console.print(f"Manifest: {manifest_path}")
        console.print(
            f"To recover, delete the unreadable manifest, run "
            f"[cyan]specify integration uninstall {key}[/cyan] to clear stale metadata, "
            f"then run [cyan]specify integration install {key}[/cyan] to regenerate."
        )
        console.print(f"[dim]Details:[/dim] {exc}")
        raise typer.Exit(1)

    removed, skipped = manifest.uninstall(project_root, force=force)

    # Remove managed context section from the agent context file
    if integration:
        integration.remove_context_section(project_root)

    remaining = [installed for installed in installed_keys if installed != key]
    new_default = default_key if default_key != key else (remaining[0] if remaining else None)
    if remaining:
        if default_key == key and new_default and (new_integration := get_integration(new_default)):
            raw_options, parsed_options = _resolve_integration_options(
                new_integration, current, new_default, None
            )
            _set_default_integration_or_exit(
                project_root,
                current,
                new_default,
                new_integration,
                remaining,
                raw_options=raw_options,
                parsed_options=parsed_options,
            )
        else:
            _write_integration_json(
                project_root, new_default, remaining, _integration_settings(current)
            )
    else:
        _remove_integration_json(project_root)

    if default_key == key:
        _clear_init_options_for_integration(project_root, key)

    name = (integration.config or {}).get("name", key) if integration else key
    console.print(f"\n[green]✓[/green] Integration '{name}' uninstalled")
    if removed:
        console.print(f"  Removed {len(removed)} file(s)")
    if skipped:
        console.print(f"\n[yellow]⚠[/yellow]  {len(skipped)} modified file(s) were preserved:")
        for path in skipped:
            rel = _display_project_path(project_root, path)
            console.print(f"    {rel}")


@integration_app.command("switch")
def integration_switch(
    target: str = typer.Argument(help="Integration key to switch to"),
    script: str | None = typer.Option(None, "--script", help="Script type: ps (default: from init-options.json or PowerShell)"),
    force: bool = typer.Option(False, "--force", help="Force removal of modified files during uninstall of the previous integration"),
    refresh_shared_infra: bool = typer.Option(False, "--refresh-shared-infra", help="Also overwrite shared infrastructure files even if you customized them (otherwise customizations are preserved)"),
    integration_options: str | None = typer.Option(None, "--integration-options", help='Options for the target integration'),
):
    """Switch from the current integration to a different one."""
    from .integrations import INTEGRATION_REGISTRY, get_integration
    from .integrations.manifest import IntegrationManifest

    project_root = _require_specify_project()
    target_integration = get_integration(target)
    if target_integration is None:
        console.print(f"[red]Error:[/red] Unknown integration '{target}'")
        available = ", ".join(sorted(INTEGRATION_REGISTRY.keys()))
        console.print(f"Available integrations: {available}")
        raise typer.Exit(1)

    current = _read_integration_json(project_root)
    installed_keys = _installed_integration_keys(current)
    installed_key = _default_integration_key(current)

    if installed_key == target:
        if integration_options is not None:
            console.print(
                "[red]Error:[/red] --integration-options cannot be used when switching "
                "to an already installed integration."
            )
            console.print(
                f"Run [cyan]specify integration upgrade {target} --integration-options ...[/cyan] "
                "to update managed files/options."
            )
            raise typer.Exit(1)
        if force:
            raw_options, parsed_options = _resolve_integration_options(
                target_integration, current, target, None
            )
            _set_default_integration_or_exit(
                project_root,
                current,
                target,
                target_integration,
                installed_keys,
                raw_options=raw_options,
                parsed_options=parsed_options,
                refresh_templates_force=True,
            )
            console.print(
                f"\n[green]✓[/green] Default integration remains [bold]{target}[/bold]; "
                "managed shared templates refreshed."
            )
            raise typer.Exit(0)
        console.print(f"[yellow]Integration '{target}' is already the default integration. Nothing to switch.[/yellow]")
        raise typer.Exit(0)

    if target in installed_keys:
        if integration_options is not None:
            console.print(
                "[red]Error:[/red] --integration-options cannot be used when switching "
                "to an already installed integration."
            )
            console.print(
                f"Run [cyan]specify integration upgrade {target} --integration-options ...[/cyan] "
                f"to update managed files/options, then [cyan]specify integration use {target}[/cyan]."
            )
            raise typer.Exit(1)
        raw_options, parsed_options = _resolve_integration_options(
            target_integration, current, target, None
        )
        _set_default_integration_or_exit(
            project_root,
            current,
            target,
            target_integration,
            installed_keys,
            raw_options=raw_options,
            parsed_options=parsed_options,
            refresh_templates_force=force,
        )
        console.print(f"\n[green]✓[/green] Default integration set to [bold]{target}[/bold].")
        raise typer.Exit(0)

    selected_script = _resolve_script_type(project_root, script)

    # Phase 1: Uninstall current integration (if any)
    if installed_key:
        current_integration = get_integration(installed_key)
        manifest_path = project_root / ".specify" / "integrations" / f"{installed_key}.manifest.json"

        if current_integration and manifest_path.exists():
            console.print(f"Uninstalling current integration: [cyan]{installed_key}[/cyan]")
            try:
                old_manifest = IntegrationManifest.load(installed_key, project_root)
            except _MANIFEST_READ_ERRORS as exc:
                console.print(f"[red]Error:[/red] Could not read integration manifest for '{installed_key}': {manifest_path}")
                console.print(f"[dim]{exc}[/dim]")
                console.print(
                    f"To recover, delete the unreadable manifest at {manifest_path}, "
                    f"run [cyan]specify integration uninstall {installed_key}[/cyan], then retry."
                )
                raise typer.Exit(1)
            removed, skipped = old_manifest.uninstall(project_root, force=force)
            current_integration.remove_context_section(project_root)
            if removed:
                console.print(f"  Removed {len(removed)} file(s)")
            if skipped:
                console.print(f"  [yellow]⚠[/yellow]  {len(skipped)} modified file(s) preserved")
        elif not current_integration and manifest_path.exists():
            # Integration removed from registry but manifest exists — use manifest-only uninstall
            console.print(f"Uninstalling unknown integration '{installed_key}' via manifest")
            try:
                old_manifest = IntegrationManifest.load(installed_key, project_root)
                removed, skipped = old_manifest.uninstall(project_root, force=force)
                if removed:
                    console.print(f"  Removed {len(removed)} file(s)")
                if skipped:
                    console.print(f"  [yellow]⚠[/yellow]  {len(skipped)} modified file(s) preserved")
            except _MANIFEST_READ_ERRORS as exc:
                console.print(f"[yellow]Warning:[/yellow] Could not read manifest for '{installed_key}': {exc}")
        else:
            console.print(f"[red]Error:[/red] Integration '{installed_key}' is installed but has no manifest.")
            console.print(
                f"Run [cyan]specify integration uninstall {installed_key}[/cyan] to clear metadata, "
                f"then retry [cyan]specify integration switch {target}[/cyan]."
            )
            raise typer.Exit(1)

        # Unregister extension commands for the old agent so they don't
        # remain as orphans in the old agent's directory.
        try:
            from .extensions import ExtensionManager

            ext_mgr = ExtensionManager(project_root)
            ext_mgr.unregister_agent_artifacts(installed_key)
        except Exception as ext_err:
            console.print(
                f"[yellow]Warning:[/yellow] Could not clean up extension artifacts "
                f"(commands, skills, registry entries) for '{installed_key}': {ext_err}"
            )

        # Clear metadata so a failed Phase 2 doesn't leave stale references
        installed_keys = [installed for installed in installed_keys if installed != installed_key]
        _clear_init_options_for_integration(project_root, installed_key)
        if installed_keys:
            fallback_key = installed_keys[0]
            fallback_integration = get_integration(fallback_key)
            if fallback_integration is not None:
                raw_options, parsed_options = _resolve_integration_options(
                    fallback_integration, current, fallback_key, None
                )
                _set_default_integration_or_exit(
                    project_root,
                    current,
                    fallback_key,
                    fallback_integration,
                    installed_keys,
                    raw_options=raw_options,
                    parsed_options=parsed_options,
                )
            else:
                _write_integration_json(
                    project_root, fallback_key, installed_keys, _integration_settings(current)
                )
        else:
            _remove_integration_json(project_root)
        current = _read_integration_json(project_root)

    # Build parsed options from --integration-options so the integration
    # can determine its effective invoke separator before shared infra
    # is installed.
    raw_options, parsed_options = _resolve_integration_options(
        target_integration, current, target, integration_options
    )

    # Refresh shared infrastructure to the current CLI version. Switching
    # integrations is exactly when stale vendored shared scripts would
    # silently break the new integration.
    #
    # Use refresh_managed=True so only files that match their previously
    # recorded hash are overwritten — user customizations are detected via
    # hash divergence and preserved with a warning. Pass
    # --refresh-shared-infra to overwrite customizations as well. See #2293.
    _install_shared_infra_or_exit(
        project_root,
        selected_script,
        force=refresh_shared_infra,
        refresh_managed=True,
        invoke_separator=_invoke_separator_for_integration(
            target_integration, current, target, parsed_options
        ),
        refresh_hint=(
            "To overwrite customizations, re-run with "
            "[cyan]specify integration switch ... --refresh-shared-infra[/cyan]."
        ),
    )
    # Phase 2: Install target integration
    console.print(f"Installing integration: [cyan]{target}[/cyan]")
    manifest = IntegrationManifest(
        target_integration.key, project_root, version=get_speckit_version()
    )

    try:
        target_integration.setup(
            project_root, manifest,
            parsed_options=parsed_options,
            script_type=selected_script,
            raw_options=raw_options,
        )
        manifest.save()
        _set_default_integration(
            project_root,
            current,
            target_integration.key,
            target_integration,
            _dedupe_integration_keys([*installed_keys, target_integration.key]),
            script_type=selected_script,
            raw_options=raw_options,
            parsed_options=parsed_options,
        )

        # Re-register extension commands for the new agent so that
        # previously-installed extensions are available in the new integration.
        try:
            from .extensions import ExtensionManager

            ext_mgr = ExtensionManager(project_root)
            ext_mgr.register_enabled_extensions_for_agent(target)
        except Exception as ext_err:
            console.print(
                f"[yellow]Warning:[/yellow] Could not register extension commands, skills, "
                f"or related artifacts for '{target}': {ext_err}"
            )

    except Exception as e:
        # Attempt rollback of any files written by setup
        try:
            target_integration.teardown(project_root, manifest, force=True)
        except Exception as rollback_err:
            # Suppress so the original setup error remains the primary failure
            console.print(f"[yellow]Warning:[/yellow] Failed to roll back integration '{target}': {rollback_err}")
        if installed_keys:
            fallback_key = installed_keys[0]
            fallback_integration = get_integration(fallback_key)
            if fallback_integration is not None:
                raw_options, parsed_options = _resolve_integration_options(
                    fallback_integration, current, fallback_key, None
                )
                try:
                    _set_default_integration(
                        project_root,
                        current,
                        fallback_key,
                        fallback_integration,
                        installed_keys,
                        raw_options=raw_options,
                        parsed_options=parsed_options,
                    )
                except _SharedTemplateRefreshError as restore_err:
                    console.print(
                        f"[yellow]Warning:[/yellow] Failed to restore default "
                        f"integration '{fallback_key}': {restore_err}"
                    )
            else:
                _write_integration_json(
                    project_root, fallback_key, installed_keys, _integration_settings(current)
                )
        else:
            _remove_integration_json(project_root)
        console.print(f"[red]Error:[/red] Failed to install integration '{target}': {e}")
        raise typer.Exit(1)

    name = (target_integration.config or {}).get("name", target)
    console.print(f"\n[green]✓[/green] Switched to integration '{name}'")


@integration_app.command("upgrade")
def integration_upgrade(
    key: str | None = typer.Argument(None, help="Integration key to upgrade (default: current integration)"),
    force: bool = typer.Option(False, "--force", help="Force upgrade even if files are modified"),
    script: str | None = typer.Option(None, "--script", help="Script type: ps (default: from init-options.json or PowerShell)"),
    integration_options: str | None = typer.Option(None, "--integration-options", help="Options for the integration"),
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root to upgrade"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate the upgrade without writing files"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable upgrade facts"),
):
    """Upgrade an integration by reinstalling with diff-aware file handling.

    Compares manifest hashes to detect locally modified files and
    blocks the upgrade unless --force is used.
    """
    from .integrations import get_integration
    from .integrations.manifest import IntegrationManifest
    from ._upgrade import (
        _collect_shared_assets,
        capture_file_snapshot,
        restore_upgrade_snapshot,
    )
    from .shared_infra import load_speckit_manifest

    project_root = _require_specify_project(project_dir)
    current = _read_integration_json(project_root)
    installed_key = _default_integration_key(current)
    installed_keys = _installed_integration_keys(current)

    if key is None:
        if not installed_key:
            blocker = "No integration is currently installed."
            if json_output:
                print(json.dumps({"status": "blocked", "blockers": [blocker]}, ensure_ascii=False))
            else:
                console.print(f"[yellow]{blocker}[/yellow]")
            raise typer.Exit(1)
        key = installed_key

    if key not in installed_keys:
        blocker = f"Integration '{key}' is not installed."
        if json_output:
            print(json.dumps({"status": "blocked", "blockers": [blocker]}, ensure_ascii=False))
        else:
            console.print(f"[red]Error:[/red] {blocker}")
        raise typer.Exit(1)

    integration = get_integration(key)
    if integration is None:
        blocker = f"Unknown integration '{key}'"
        if json_output:
            print(json.dumps({"status": "blocked", "blockers": [blocker]}, ensure_ascii=False))
        else:
            console.print(f"[red]Error:[/red] {blocker}")
        raise typer.Exit(1)

    manifest_path = project_root / ".specify" / "integrations" / f"{key}.manifest.json"
    if not manifest_path.exists():
        blocker = f"No manifest found for integration '{key}'."
        if json_output:
            print(json.dumps({"status": "blocked", "blockers": [blocker]}, ensure_ascii=False))
        else:
            console.print(f"[yellow]{blocker}[/yellow]")
            console.print(f"Run [cyan]specify integration install {key}[/cyan] to perform a fresh install.")
        raise typer.Exit(1)

    try:
        old_manifest = IntegrationManifest.load(key, project_root)
    except _MANIFEST_READ_ERRORS as exc:
        blocker = f"Integration manifest for '{key}' is unreadable: {exc}"
        if json_output:
            print(json.dumps({"status": "blocked", "blockers": [blocker]}, ensure_ascii=False))
        else:
            console.print(f"[red]Error:[/red] {blocker}")
        raise typer.Exit(1)

    integrity = old_manifest.inspect_integrity()
    modified = integrity["modified"]
    plan = {
        "integration": key,
        "project_root": str(project_root),
        "current_version": old_manifest.version or "unknown",
        "target_version": get_speckit_version(),
        "force": force,
        "tracked": integrity["tracked"],
        "matched": len(integrity["matched"]),
        "modified": modified,
        "missing": integrity["missing"],
        "unsafe": integrity["unsafe"],
    }
    if modified and not force:
        blocker = (
            f"{len(modified)} integration file(s) have been modified since installation. "
            "Review the dry-run result and use --force only when overwriting them is intended."
        )
        if json_output:
            print(json.dumps({"status": "blocked", "dry_run": dry_run, "plan": plan, "blockers": [blocker]}, ensure_ascii=False, indent=2))
        else:
            console.print(f"[yellow]Warning:[/yellow] {blocker}")
            for rel in modified:
                console.print(f"    {rel}")
        raise typer.Exit(1)
    if integrity["unsafe"]:
        blocker = f"Integration manifest contains {len(integrity['unsafe'])} unsafe path(s)."
        if json_output:
            print(json.dumps({"status": "blocked", "dry_run": dry_run, "plan": plan, "blockers": [blocker]}, ensure_ascii=False, indent=2))
        else:
            console.print(f"[red]Error:[/red] {blocker}")
        raise typer.Exit(1)
    selected_script = _resolve_integration_script_type(project_root, current, key, script)

    # Build parsed options from --integration-options so the integration
    # can determine its effective invoke separator before shared infra
    # is installed.
    raw_options, parsed_options = _resolve_integration_options(
        integration, current, key, integration_options
    )

    # Ensure shared infrastructure is up to date; --force overwrites existing files.
    infra_integration = integration
    infra_key = key
    infra_parsed = parsed_options
    if installed_key and installed_key != key:
        default_integration = get_integration(installed_key)
        if default_integration is not None:
            infra_integration = default_integration
            infra_key = installed_key
            _, infra_parsed = _resolve_integration_options(
                default_integration, current, installed_key, None
            )
    infra_separator = _invoke_separator_for_integration(
        infra_integration, current, infra_key, infra_parsed
    )

    affected_files = set(old_manifest.files)
    with tempfile.TemporaryDirectory(prefix=f"specify-{key}-upgrade-plan-") as temp_dir:
        temp_root = Path(temp_dir)
        predicted_manifest = IntegrationManifest(key, temp_root, version=get_speckit_version())
        integration.setup(
            temp_root,
            predicted_manifest,
            parsed_options=parsed_options,
            script_type=selected_script,
            raw_options=raw_options,
        )
        affected_files.update(predicted_manifest.files)

    speckit_manifest = load_speckit_manifest(project_root, version=get_speckit_version())
    affected_files.update(speckit_manifest.files)
    affected_files.update(
        _collect_shared_assets(
            project_root=project_root,
            core_pack=_locate_core_pack(),
            repo_root=_repo_root(),
            invoke_separator=infra_separator,
        )
    )
    affected_files.update(
        {
            f".specify/integrations/{key}.manifest.json",
            ".specify/integrations/speckit.manifest.json",
            INTEGRATION_JSON,
            INIT_OPTIONS_FILE,
        }
    )
    plan["planned_files"] = len(predicted_manifest.files)
    plan["affected_files"] = len(affected_files)
    if dry_run:
        payload = {"status": "planned", "dry_run": True, "plan": plan, "blockers": []}
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            console.print(
                f"Integration '{key}' upgrade is ready: "
                f"{plan['current_version']} -> {plan['target_version']}"
            )
            console.print(
                f"Tracked: {plan['tracked']}, matched: {plan['matched']}, "
                f"missing to restore: {len(plan['missing'])}, "
                f"planned files: {plan['planned_files']}"
            )
        return

    try:
        snapshot = capture_file_snapshot(project_root, affected_files)
    except (OSError, ValueError) as exc:
        blocker = f"Could not create integration rollback snapshot: {exc}"
        if json_output:
            print(json.dumps({"status": "blocked", "dry_run": False, "plan": plan, "blockers": [blocker]}, ensure_ascii=False, indent=2))
        else:
            console.print(f"[red]Blocked:[/red] {blocker}")
        raise typer.Exit(1)

    transaction = {"captured": True, "rolled_back": False, "rollback_errors": []}
    new_manifest = IntegrationManifest(key, project_root, version=get_speckit_version())
    console_was_quiet = console.quiet
    if json_output:
        console.quiet = True

    try:
        _install_shared_infra_or_exit(
            project_root,
            selected_script,
            force=force,
            invoke_separator=infra_separator,
        )
        console.print(f"Upgrading integration: [cyan]{key}[/cyan]")
        integration.setup(
            project_root,
            new_manifest,
            parsed_options=parsed_options,
            script_type=selected_script,
            raw_options=raw_options,
        )
        settings = _with_integration_setting(
            current,
            key,
            integration,
            script_type=selected_script,
            raw_options=raw_options,
            parsed_options=parsed_options,
        )
        if installed_key == key:
            try:
                _refresh_shared_templates(
                    project_root,
                    invoke_separator=_invoke_separator_for_integration(
                        integration, {"integration_settings": settings}, key, parsed_options
                    ),
                    force=force,
                )
            except (ValueError, OSError) as exc:
                raise _SharedTemplateRefreshError(
                    f"Failed to refresh shared templates for '{key}': {exc}"
                ) from exc
        new_manifest.save()
        _write_integration_json(project_root, installed_key, installed_keys, settings)
        if installed_key == key:
            _update_init_options_for_integration(project_root, integration, script_type=selected_script)

        old_files = old_manifest.files
        new_files = new_manifest.files
        stale_keys = set(old_files) - set(new_files)
        if stale_keys:
            stale_manifest = IntegrationManifest(key, project_root, version="stale-cleanup")
            stale_manifest._files = {item: old_files[item] for item in stale_keys}
            stale_removed, _ = stale_manifest.uninstall(
                project_root,
                force=True,
                remove_manifest=False,
            )
            if stale_removed:
                console.print(f"  Removed {len(stale_removed)} stale file(s) from previous install")

        verified_manifest = IntegrationManifest.load(key, project_root)
        verified = verified_manifest.inspect_integrity()
        if verified["modified"] or verified["missing"] or verified["unsafe"]:
            raise RuntimeError(
                "post-upgrade integration integrity verification failed "
                f"(modified={len(verified['modified'])}, "
                f"missing={len(verified['missing'])}, unsafe={len(verified['unsafe'])})"
            )
    except Exception as exc:
        console.quiet = console_was_quiet
        rollback_errors = restore_upgrade_snapshot(project_root, snapshot)
        transaction["rolled_back"] = not rollback_errors
        transaction["rollback_errors"] = rollback_errors
        blockers = [f"Failed to upgrade integration: {exc}"]
        if rollback_errors:
            blockers.append("Integration rollback was incomplete: " + "; ".join(rollback_errors))
        if json_output:
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "dry_run": False,
                        "plan": plan,
                        "blockers": blockers,
                        "transaction": transaction,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            for blocker in blockers:
                console.print(f"[red]Error:[/red] {blocker}")
            if transaction["rolled_back"]:
                console.print("[green]Rollback complete:[/green] integration files were restored.")
        raise typer.Exit(1)

    console.quiet = console_was_quiet

    name = (integration.config or {}).get("name", key)
    if json_output:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "dry_run": False,
                    "plan": plan,
                    "version": get_speckit_version(),
                    "stale_removed": sorted(stale_keys),
                    "blockers": [],
                    "transaction": transaction,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        console.print(f"\n[green]OK[/green] Integration '{name}' upgraded successfully")


# ===== Integration catalog discovery commands =====
#
# These commands mirror the workflow catalog CLI shape:
#   - `search` / `info` for discovery over the active catalog stack
#   - `catalog list/add/remove` for managing catalog sources
#
# They deliberately do NOT add `integration add/remove/enable/disable/
# set-priority`: integrations are single-active (install / uninstall / switch),
# not additive like extensions and presets.


@integration_app.command("search")
def integration_search(
    query: Optional[str] = typer.Argument(None, help="Search query (optional)"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag"),
    author: Optional[str] = typer.Option(None, "--author", help="Filter by author"),
):
    """Search built-in integrations."""
    from .integrations import INTEGRATION_REGISTRY

    project_root = _require_specify_project()
    integration_config = _read_integration_json(project_root)
    installed_key = integration_config.get("integration")
    results = []
    for iid, integration in INTEGRATION_REGISTRY.items():
        cfg = integration.config or {}
        name = cfg.get("name", iid)
        tags = ["codex", "builtin", "skills"]
        haystack = " ".join([iid, name, *tags]).lower()
        if query and query.lower() not in haystack:
            continue
        if tag and tag.lower() not in {item.lower() for item in tags}:
            continue
        if author and author.lower() not in "spec kit team":
            continue
        results.append({
            "id": iid,
            "name": name,
            "version": get_speckit_version(),
            "description": cfg.get("description", "Built-in Codex skills integration."),
            "author": "Spec Kit Team",
            "tags": tags,
        })

    if not results:
        console.print("\n[yellow]No integrations found matching criteria[/yellow]")
        if query or tag or author:
            console.print("\nTry:")
            console.print("  • Broader search terms")
            console.print("  • Remove filters")
            console.print("  • specify integration search (show all)")
        return

    console.print(f"\n[green]Found {len(results)} integration(s):[/green]\n")
    for integ in sorted(results, key=lambda e: e.get("id", "")):
        iid = integ.get("id", "?")
        name = integ.get("name", iid)
        version = integ.get("version", "?")
        console.print(f"[bold]{name}[/bold] ({iid}) v{version}")
        desc = integ.get("description", "")
        if desc:
            console.print(f"  {desc}")

        console.print(f"\n  [dim]Author:[/dim] {integ.get('author', 'Unknown')}")
        tags = integ.get("tags", [])
        if isinstance(tags, list) and tags:
            console.print(f"  [dim]Tags:[/dim] {', '.join(str(t) for t in tags)}")

        if iid == installed_key:
            console.print("\n  [green]✓ Installed[/green] (currently active)")
        elif iid in INTEGRATION_REGISTRY:
            console.print(f"\n  [cyan]Install:[/cyan] specify integration install {iid}")
        console.print()


@integration_app.command("info")
def integration_info(
    integration_id: str = typer.Argument(..., help="Integration ID"),
):
    """Show details for a built-in integration."""
    from .integrations import INTEGRATION_REGISTRY

    project_root = _require_specify_project()
    installed_key = _read_integration_json(project_root).get("integration")

    if integration_id in INTEGRATION_REGISTRY:
        integration = INTEGRATION_REGISTRY[integration_id]
        cfg = integration.config or {}
        name = cfg.get("name", integration_id)
        console.print(f"\n[bold cyan]{name}[/bold cyan] ({integration_id})")
        console.print("  [dim]Built-in Codex-only integration[/dim]")
        console.print(f"  [dim]Version:[/dim] {get_speckit_version()}")
        console.print("  [dim]Tags:[/dim] codex, builtin, skills")
        if integration_id == installed_key:
            console.print("\n  [green]✓ Installed[/green] (currently active)")
        return

    console.print(f"[red]Error:[/red] Integration '{integration_id}' not found")
    console.print("\nTry: specify integration search")
    raise typer.Exit(1)


# ===== Workflow Commands =====

from .workflows.commands import register_workflow_commands as _register_workflow_commands

_register_workflow_commands(app, _require_specify_project)

def main():
    app()

if __name__ == "__main__":
    main()
