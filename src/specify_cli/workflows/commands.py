"""Typer command registration for workflow operations."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

import typer
import yaml

from specify_cli._console import console


_REQUIRE_PROJECT: Callable[[str | Path | None], Path] | None = None


def register_workflow_commands(
    app: typer.Typer,
    require_project: Callable[[str | Path | None], Path],
) -> None:
    """Register workflow commands on the root Typer app."""
    global _REQUIRE_PROJECT
    _REQUIRE_PROJECT = require_project
    app.add_typer(workflow_app, name="workflow")


def _require_specify_project(project_dir: str | Path | None = None) -> Path:
    if _REQUIRE_PROJECT is None:
        raise RuntimeError("Workflow commands registered without project resolver")
    return _REQUIRE_PROJECT(project_dir)


# ===== Workflow Commands =====

workflow_app = typer.Typer(
    name="workflow",
    help="Manage and run automation workflows",
    add_completion=False,
)
workflow_catalog_app = typer.Typer(
    name="catalog",
    help="Legacy workflow catalog management (not exposed)",
    add_completion=False,
)

def _parse_workflow_inputs(input_values: list[str] | None) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    if input_values:
        for kv in input_values:
            if "=" not in kv:
                console.print(f"[red]Error:[/red] Invalid input format: {kv!r} (expected key=value)")
                raise typer.Exit(1)
            key, _, value = kv.partition("=")
            inputs[key.strip()] = value.strip()
    return inputs


def _workflow_state_payload(state: Any, project_root: Path) -> dict[str, Any]:
    run_dir = project_root / ".specify" / "workflows" / "runs" / state.run_id
    payload = {
        "run_id": state.run_id,
        "workflow_id": state.workflow_id,
        "status": state.status.value,
        "current_step_index": state.current_step_index,
        "current_step_id": state.current_step_id,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "inputs": state.inputs,
        "step_results": state.step_results,
        "run_dir": str(run_dir),
    }
    hook_results = getattr(state, "hook_results", {})
    if hook_results:
        payload["hook_results"] = hook_results
    pending_hook = getattr(state, "pending_hook", None)
    if pending_hook:
        payload["pending_hook"] = pending_hook
    return payload


def _merge_feature_hook_state(feature_dir: str, state: Any, project_root: Path) -> Path | None:
    hook_results = getattr(state, "hook_results", {})
    pending_hook = getattr(state, "pending_hook", None)
    if not hook_results and not pending_hook:
        return None

    feature_path = Path(feature_dir)
    if not feature_path.is_absolute():
        feature_path = project_root / feature_path
    feature_path = feature_path.resolve()
    if not feature_path.is_dir():
        raise ValueError(f"Feature directory not found: {feature_path}")
    state_path = feature_path / "workflow-state.json"

    payload: dict[str, Any] = {}
    if state_path.is_file():
        try:
            loaded = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except json.JSONDecodeError:
            raise ValueError(f"workflow-state.json is not valid JSON: {state_path}")

    existing_hook_results = payload.get("hook_results")
    if not isinstance(existing_hook_results, dict):
        existing_hook_results = {}
    existing_hook_results.update(hook_results)
    payload["hook_results"] = existing_hook_results

    if pending_hook:
        payload["pending_hook"] = pending_hook
    else:
        payload.pop("pending_hook", None)

    state_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return state_path


@workflow_app.command("invoke-hooks")
def workflow_invoke_hooks(
    stage_id: str = typer.Argument(..., help="Workflow stage ID whose hooks should run"),
    workflow_id: str = typer.Option("speckit", "--workflow-id", help="Workflow ID for hook event names"),
    phase: str = typer.Option("after", "--phase", help="Hook phase: before or after"),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional workflow hook run id"),
    feature_dir: str = typer.Option("", "--feature-dir", help="Feature directory whose workflow-state.json should record hook results"),
    input_values: list[str] | None = typer.Option(
        None, "--input", "-i", help="Hook context input values as key=value pairs"
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable hook run state JSON"),
):
    """Invoke workflow hooks through the same dispatcher used by workflow run."""
    from .engine import WorkflowEngine

    project_root = _require_specify_project()
    engine = WorkflowEngine(project_root)
    inputs = _parse_workflow_inputs(input_values)
    if feature_dir:
        inputs.setdefault("feature_dir", feature_dir)

    try:
        state = engine.dispatch_hooks(
            workflow_id=workflow_id,
            stage_id=stage_id,
            phase=phase,
            run_id=run_id,
            inputs=inputs,
            default_integration="codex",
        )
        feature_state_path = (
            _merge_feature_hook_state(feature_dir, state, project_root)
            if feature_dir
            else None
        )
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Workflow hook dispatch failed:[/red] {exc}")
        raise typer.Exit(1)

    payload = _workflow_state_payload(state, project_root)
    if feature_state_path is not None:
        payload["feature_workflow_state"] = str(feature_state_path)

    if json_output:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        status_colors = {
            "completed": "green",
            "paused": "yellow",
            "failed": "red",
            "aborted": "red",
        }
        color = status_colors.get(state.status.value, "white")
        console.print(f"[{color}]Hook status: {state.status.value}[/{color}]")
        if getattr(state, "pending_hook", None):
            pending = state.pending_hook or {}
            console.print(f"[yellow]Pending hook:[/yellow] {pending.get('event')}")

    if state.status.value in {"paused", "failed", "aborted"}:
        raise typer.Exit(1)


@workflow_app.command("run")
def workflow_run(
    source: str = typer.Argument(..., help="Workflow ID or YAML file path"),
    input_values: list[str] | None = typer.Option(
        None, "--input", "-i", help="Input values as key=value pairs"
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable run state JSON"),
):
    """Run a workflow from an installed ID or local YAML path."""
    from .engine import WorkflowEngine

    project_root = _require_specify_project()
    engine = WorkflowEngine(project_root)
    if not json_output:
        engine.on_step_start = lambda sid, label: console.print(f"  -> [{sid}] {label} ...")

    try:
        definition = engine.load_workflow(source)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Workflow not found: {source}")
        raise typer.Exit(1)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] Invalid workflow: {exc}")
        raise typer.Exit(1)

    # Validate
    errors = engine.validate(definition)
    if errors:
        console.print("[red]Workflow validation failed:[/red]")
        for err in errors:
            console.print(f"  - {err}")
        raise typer.Exit(1)

    inputs = _parse_workflow_inputs(input_values)

    if not json_output:
        console.print(f"\n[bold cyan]Running workflow:[/bold cyan] {definition.name} ({definition.id})")
        console.print(f"[dim]Version: {definition.version}[/dim]\n")

    try:
        state = engine.execute(definition, inputs)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Workflow failed:[/red] {exc}")
        raise typer.Exit(1)

    if json_output:
        sys.stdout.write(json.dumps(_workflow_state_payload(state, project_root), ensure_ascii=False, indent=2) + "\n")
        if state.status.value in {"failed", "aborted"}:
            raise typer.Exit(1)
        return

    status_colors = {
        "completed": "green",
        "paused": "yellow",
        "failed": "red",
        "aborted": "red",
    }
    color = status_colors.get(state.status.value, "white")
    console.print(f"\n[{color}]Status: {state.status.value}[/{color}]")
    console.print(f"[dim]Run ID: {state.run_id}[/dim]")

    if getattr(state, "pending_hook", None):
        pending = state.pending_hook or {}
        pending_stage = pending.get("stage_id") or pending.get("step_id")
        console.print(f"[yellow]Pending hook:[/yellow] {pending.get('phase')} {pending_stage}")

    if state.status.value == "paused":
        console.print(f"\nResume with: [cyan]specify workflow resume {state.run_id}[/cyan]")
    elif state.status.value in {"failed", "aborted"}:
        raise typer.Exit(1)


@workflow_app.command("resume")
def workflow_resume(
    run_id: str = typer.Argument(..., help="Run ID to resume"),
    input_values: list[str] | None = typer.Option(
        None, "--input", "-i", help="Input values to merge before resume, as key=value pairs"
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable run state JSON"),
):
    """Resume a paused or failed workflow run."""
    from .engine import RunState, WorkflowEngine

    project_root = _require_specify_project()
    engine = WorkflowEngine(project_root)
    if not json_output:
        engine.on_step_start = lambda sid, label: console.print(f"  -> [{sid}] {label} ...")

    try:
        merged_inputs = _parse_workflow_inputs(input_values)
        if merged_inputs:
            state_for_update = RunState.load(run_id, project_root)
            state_for_update.inputs.update(merged_inputs)
            state_for_update.save()
        state = engine.resume(run_id)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Run not found: {run_id}")
        raise typer.Exit(1)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Resume failed:[/red] {exc}")
        raise typer.Exit(1)

    status_colors = {
        "completed": "green",
        "paused": "yellow",
        "failed": "red",
        "aborted": "red",
    }
    color = status_colors.get(state.status.value, "white")
    if json_output:
        sys.stdout.write(json.dumps(_workflow_state_payload(state, project_root), ensure_ascii=False, indent=2) + "\n")
        if state.status.value in {"failed", "aborted"}:
            raise typer.Exit(1)
        return
    console.print(f"\n[{color}]Status: {state.status.value}[/{color}]")
    if getattr(state, "pending_hook", None):
        pending = state.pending_hook or {}
        pending_stage = pending.get("stage_id") or pending.get("step_id")
        console.print(f"[yellow]Pending hook:[/yellow] {pending.get('phase')} {pending_stage}")
    if state.status.value in {"failed", "aborted"}:
        raise typer.Exit(1)


@workflow_app.command("status")
def workflow_status(
    run_id: str | None = typer.Argument(None, help="Run ID to inspect (shows all if omitted)"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable run state JSON"),
):
    """Show workflow run status."""
    from .engine import WorkflowEngine

    project_root = _require_specify_project()
    engine = WorkflowEngine(project_root)

    if run_id:
        try:
            from .engine import RunState
            state = RunState.load(run_id, project_root)
        except FileNotFoundError:
            console.print(f"[red]Error:[/red] Run not found: {run_id}")
            raise typer.Exit(1)

        if json_output:
            sys.stdout.write(json.dumps(_workflow_state_payload(state, project_root), ensure_ascii=False, indent=2) + "\n")
            return

        status_colors = {
            "completed": "green",
            "paused": "yellow",
            "failed": "red",
            "aborted": "red",
            "running": "blue",
            "created": "dim",
        }
        color = status_colors.get(state.status.value, "white")

        console.print(f"\n[bold cyan]Workflow Run: {state.run_id}[/bold cyan]")
        console.print(f"  Workflow: {state.workflow_id}")
        console.print(f"  Status:   [{color}]{state.status.value}[/{color}]")
        console.print(f"  Created:  {state.created_at}")
        console.print(f"  Updated:  {state.updated_at}")

        if state.current_step_id:
            console.print(f"  Current:  {state.current_step_id}")

        if getattr(state, "pending_hook", None):
            pending = state.pending_hook or {}
            pending_stage = pending.get("stage_id") or pending.get("step_id")
            console.print(f"  Hook:     [yellow]pending[/yellow] {pending.get('phase')} {pending_stage}")

        if state.step_results:
            console.print(f"\n  [bold]Steps ({len(state.step_results)}):[/bold]")
            for step_id, step_data in state.step_results.items():
                s = step_data.get("status", "unknown")
                sc = {"completed": "green", "failed": "red", "paused": "yellow"}.get(s, "white")
                console.print(f"    [{sc}]*[/{sc}] {step_id}: {s}")
    else:
        runs = engine.list_runs()
        if json_output:
            sys.stdout.write(json.dumps({"runs": runs}, ensure_ascii=False, indent=2) + "\n")
            return
        if not runs:
            console.print("[yellow]No workflow runs found.[/yellow]")
            return

        console.print("\n[bold cyan]Workflow Runs:[/bold cyan]\n")
        for run_data in runs:
            s = run_data.get("status", "unknown")
            sc = {"completed": "green", "failed": "red", "paused": "yellow", "running": "blue"}.get(s, "white")
            console.print(
                f"  [{sc}]*[/{sc}] {run_data['run_id']}  "
                f"{run_data.get('workflow_id', '?')}  "
                f"[{sc}]{s}[/{sc}]  "
                f"[dim]{run_data.get('updated_at', '?')}[/dim]"
            )


@workflow_app.command("list")
def workflow_list():
    """List installed workflows."""
    from .catalog import WorkflowRegistry

    project_root = _require_specify_project()
    registry = WorkflowRegistry(project_root)
    installed = registry.list()

    if not installed:
        console.print("[yellow]No workflows installed.[/yellow]")
        console.print("\nInstall a workflow with:")
        console.print("  [cyan]specify workflow add <workflow-id>[/cyan]")
        return

    console.print("\n[bold cyan]Installed Workflows:[/bold cyan]\n")
    for wf_id, wf_data in installed.items():
        console.print(f"  [bold]{wf_data.get('name', wf_id)}[/bold] ({wf_id}) v{wf_data.get('version', '?')}")
        desc = wf_data.get("description", "")
        if desc:
            console.print(f"    {desc}")
        console.print()


@workflow_app.command("add")
def workflow_add(
    source: str = typer.Argument(..., help="Local workflow.yml file or workflow directory"),
):
    """Install a workflow from a local file or directory."""
    from .catalog import WorkflowRegistry
    from .engine import WorkflowDefinition

    project_root = _require_specify_project()
    registry = WorkflowRegistry(project_root)
    workflows_dir = project_root / ".specify" / "workflows"

    def _validate_and_install_local(yaml_path: Path, source_label: str) -> None:
        """Validate and install a workflow from a local YAML file."""
        try:
            definition = WorkflowDefinition.from_yaml(yaml_path)
        except (ValueError, yaml.YAMLError) as exc:
            console.print(f"[red]Error:[/red] Invalid workflow YAML: {exc}")
            raise typer.Exit(1)
        if not definition.id or not definition.id.strip():
            console.print("[red]Error:[/red] Workflow definition has an empty or missing 'id'")
            raise typer.Exit(1)

        from .engine import validate_workflow
        errors = validate_workflow(definition)
        if errors:
            console.print("[red]Error:[/red] Workflow validation failed:")
            for err in errors:
                console.print(f"  - {err}")
            raise typer.Exit(1)

        dest_dir = workflows_dir / definition.id
        dest_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(yaml_path, dest_dir / "workflow.yml")
        registry.add(definition.id, {
            "name": definition.name,
            "version": definition.version,
            "description": definition.description,
            "source": source_label,
        })
        console.print(f"[green]OK[/green] Workflow '{definition.name}' ({definition.id}) installed")

    if source.startswith("http://") or source.startswith("https://"):
        console.print("[red]Error:[/red] Remote workflow installs are disabled in this Codex-only build.")
        raise typer.Exit(1)

    # Try as a local file/directory
    source_path = Path(source)
    if source_path.exists():
        if source_path.is_file() and source_path.suffix in (".yml", ".yaml"):
            _validate_and_install_local(source_path, str(source_path))
            return
        elif source_path.is_dir():
            wf_file = source_path / "workflow.yml"
            if not wf_file.exists():
                console.print(f"[red]Error:[/red] No workflow.yml found in {source}")
                raise typer.Exit(1)
            _validate_and_install_local(wf_file, str(source_path))
            return

    console.print(f"[red]Error:[/red] Workflow source '{source}' was not found as a local YAML file or directory")
    raise typer.Exit(1)


@workflow_app.command("remove")
def workflow_remove(
    workflow_id: str = typer.Argument(..., help="Workflow ID to uninstall"),
):
    """Uninstall a workflow."""
    from .catalog import WorkflowRegistry

    project_root = _require_specify_project()
    registry = WorkflowRegistry(project_root)

    if not registry.is_installed(workflow_id):
        console.print(f"[red]Error:[/red] Workflow '{workflow_id}' is not installed")
        raise typer.Exit(1)

    # Remove workflow files
    workflow_dir = project_root / ".specify" / "workflows" / workflow_id
    if workflow_dir.exists():
        import shutil
        shutil.rmtree(workflow_dir)

    registry.remove(workflow_id)
    console.print(f"[green]OK[/green] Workflow '{workflow_id}' removed")


@workflow_app.command("search")
def workflow_search(
    query: str | None = typer.Argument(None, help="Search query"),
    tag: str | None = typer.Option(None, "--tag", help="Filter by tag"),
):
    """Search installed local workflows."""
    from .catalog import WorkflowRegistry

    project_root = _require_specify_project()
    registry = WorkflowRegistry(project_root)
    installed = registry.list()
    results = []
    normalized_query = (query or "").casefold()
    normalized_tag = (tag or "").casefold()
    for wf_id, wf_data in installed.items():
        tags = [str(value) for value in wf_data.get("tags", [])]
        haystack = " ".join(
            [
                wf_id,
                str(wf_data.get("name", "")),
                str(wf_data.get("description", "")),
                " ".join(tags),
            ]
        ).casefold()
        if normalized_query and normalized_query not in haystack:
            continue
        if normalized_tag and normalized_tag not in {item.casefold() for item in tags}:
            continue
        item = {"id": wf_id, **wf_data}
        results.append(item)

    if not results:
        console.print("[yellow]No installed local workflows found.[/yellow]")
        return

    console.print(f"\n[bold cyan]Workflows ({len(results)}):[/bold cyan]\n")
    for wf in results:
        console.print(f"  [bold]{wf.get('name', wf.get('id', '?'))}[/bold] ({wf.get('id', '?')}) v{wf.get('version', '?')}")
        desc = wf.get("description", "")
        if desc:
            console.print(f"    {desc}")
        tags = wf.get("tags", [])
        if tags:
            console.print(f"    [dim]Tags: {', '.join(tags)}[/dim]")
        console.print()


@workflow_app.command("info")
def workflow_info(
    workflow_id: str = typer.Argument(..., help="Workflow ID"),
):
    """Show installed workflow details and step graph."""
    from .catalog import WorkflowRegistry
    from .engine import WorkflowEngine

    project_root = _require_specify_project()

    registry = WorkflowRegistry(project_root)
    installed = registry.get(workflow_id)
    if not installed:
        console.print(f"[red]Error:[/red] Workflow '{workflow_id}' is not installed")
        raise typer.Exit(1)

    engine = WorkflowEngine(project_root)
    try:
        definition = engine.load_workflow(workflow_id)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] Workflow '{workflow_id}' is registered but its local definition is missing")
        raise typer.Exit(1) from exc

    console.print(f"\n[bold cyan]{definition.name}[/bold cyan] ({definition.id})")
    console.print(f"  Version:     {definition.version}")
    if definition.author:
        console.print(f"  Author:      {definition.author}")
    if definition.description:
        console.print(f"  Description: {definition.description}")
    if definition.default_integration:
        console.print(f"  Integration: {definition.default_integration}")
    console.print("  [green]Installed[/green]")

    if definition.inputs:
        console.print("\n  [bold]Inputs:[/bold]")
        for name, inp in definition.inputs.items():
            if isinstance(inp, dict):
                req = "required" if inp.get("required") else "optional"
                console.print(f"    {name} ({inp.get('type', 'string')}) - {req}")

    if definition.steps:
        console.print(f"\n  [bold]Steps ({len(definition.steps)}):[/bold]")
        for step in definition.steps:
            stype = step.get("type", "command")
            console.print(f"    -> {step.get('id', '?')} [{stype}]")


@workflow_catalog_app.command("list")
def workflow_catalog_list():
    """List configured workflow catalog sources."""
    from .catalog import WorkflowCatalog, WorkflowCatalogError

    project_root = _require_specify_project()
    catalog = WorkflowCatalog(project_root)

    try:
        configs = catalog.get_catalog_configs()
    except WorkflowCatalogError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    console.print("\n[bold cyan]Workflow Catalog Sources:[/bold cyan]\n")
    for i, cfg in enumerate(configs):
        install_status = "[green]install allowed[/green]" if cfg["install_allowed"] else "[yellow]discovery only[/yellow]"
        console.print(f"  [{i}] [bold]{cfg['name']}[/bold] — {install_status}")
        console.print(f"      {cfg['url']}")
        if cfg.get("description"):
            console.print(f"      [dim]{cfg['description']}[/dim]")
        console.print()


@workflow_catalog_app.command("add")
def workflow_catalog_add(
    url: str = typer.Argument(..., help="Catalog URL to add"),
    name: str = typer.Option(None, "--name", help="Catalog name"),
):
    """Add a workflow catalog source."""
    from .catalog import WorkflowCatalog, WorkflowValidationError

    project_root = _require_specify_project()
    catalog = WorkflowCatalog(project_root)
    try:
        catalog.add_catalog(url, name)
    except WorkflowValidationError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Catalog source added: {url}")


@workflow_catalog_app.command("remove")
def workflow_catalog_remove(
    index: int = typer.Argument(..., help="Catalog index to remove (from 'catalog list')"),
):
    """Remove a workflow catalog source by index."""
    from .catalog import WorkflowCatalog, WorkflowValidationError

    project_root = _require_specify_project()
    catalog = WorkflowCatalog(project_root)
    try:
        removed_name = catalog.remove_catalog(index)
    except WorkflowValidationError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Catalog source '{removed_name}' removed")



