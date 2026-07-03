"""Workflow hook pack scaffold commands for Spec Kit."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import typer

from ._assets import _locate_core_pack, _repo_root
from ._console import console


hook_app = typer.Typer(
    name="hook",
    help="Scaffold portable workflow hook capability packs",
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
    project_root = _resolve_path(project_dir)
    if project_root is None:
        project_root = _resolve_path(os.environ.get("SPECIFY_INIT_DIR"))
    if project_root is None:
        current = Path.cwd().resolve()
        for path in [current, *current.parents]:
            if (path / ".specify").is_dir():
                project_root = path
                break
    if project_root is None:
        project_root = Path.cwd().resolve()
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


def _hook_script(script_name: str, *, project_root: Path | None = None) -> Path:
    for root in _script_roots(project_root):
        candidate = root / script_name
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(root / script_name) for root in _script_roots(project_root))
    console.print(f"[red]Error:[/red] Hook script not found: {script_name}")
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


def _invoke_script(
    script_name: str,
    *,
    project_root: Path | None,
    args: list[str],
) -> dict[str, Any]:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        console.print("[red]Error:[/red] PowerShell is required for hook commands.")
        raise typer.Exit(1)

    script = _hook_script(script_name, project_root=project_root)
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
        for key in ["pack_id", "pack_root", "event", "hook_id", "hooks_dir"]:
            value = facts.get(key)
            if value not in (None, "", []):
                console.print(f"{key}: [cyan]{value}[/cyan]")
        for blocker in result.get("blockers") or []:
            console.print(f"[red]Blocked:[/red] {blocker}")
        for hint in (result.get("hints") or [])[:8]:
            console.print(f"[dim]Hint:[/dim] {hint}")

    if result.get("status") == "blocked":
        raise typer.Exit(1)


@hook_app.command("scaffold")
def hook_scaffold(
    adapter: str = typer.Argument("generic", help="Hook adapter template: generic or open-code-review"),
    event: str = typer.Option(..., "--event", help="Hook event, e.g. workflow.speckit.commit.after"),
    project_dir: str | None = typer.Option(None, "--project-dir", "--dir", "-C", help="Spec Kit project root"),
    output_dir: str | None = typer.Option(None, "--output-dir", help="Output pack directory"),
    pack_id: str | None = typer.Option(None, "--pack-id", help="Capability pack id"),
    hook_id: str | None = typer.Option(None, "--hook-id", help="Hook id within the pack"),
    tool_id: str | None = typer.Option(None, "--tool-id", help="External tool id"),
    version: str = typer.Option(..., "--version", help="External tool version to pin"),
    install_method: str = typer.Option("manual", "--install-method", help="pack-local-script, npm, github-release, or manual"),
    package: str | None = typer.Option(None, "--package", help="NPM package name when --install-method npm is used"),
    url: str | None = typer.Option(None, "--url", help="Release asset URL when --install-method github-release is used"),
    sha256: str | None = typer.Option(None, "--sha256", help="Expected release asset SHA-256"),
    command: str | None = typer.Option(None, "--command", help="Command used by the hook wrapper"),
    verify_command: str | None = typer.Option(None, "--verify-command", help="Command used to verify tool availability"),
    verify_timeout_seconds: int = typer.Option(60, "--verify-timeout-seconds", help="Tool verify timeout"),
    timeout_seconds: int = typer.Option(1800, "--timeout-seconds", help="Hook execution timeout"),
    failure_policy: str = typer.Option("block", "--failure-policy", help="block, warn, warning, or advisory"),
    force: bool = typer.Option(False, "--force", help="Overwrite output directory"),
    apply: bool = typer.Option(False, "--apply", help="Apply the scaffolded pack after validation"),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON"),
) -> None:
    """Generate a portable workflow hook capability pack."""
    project_root = _require_project(project_dir)
    resolved_pack_id = pack_id or ("open-code-review" if adapter == "open-code-review" else "workflow-hook")
    resolved_output = _resolve_path(
        output_dir,
        base=project_root,
    ) or (
        project_root
        / ".specify"
        / "capabilities"
        / "overlays"
        / "local"
        / "packs"
        / resolved_pack_id
    )
    args = [
        "-PackId",
        resolved_pack_id,
        "-Adapter",
        adapter,
        "-Event",
        event,
        "-ToolVersion",
        version,
        "-InstallMethod",
        install_method,
        "-OutputDir",
        str(resolved_output),
    ]
    _append_arg(args, "-HookId", hook_id)
    _append_arg(args, "-ToolId", tool_id)
    _append_arg(args, "-Package", package)
    _append_arg(args, "-Url", url)
    _append_arg(args, "-Sha256", sha256)
    _append_arg(args, "-Command", command)
    _append_arg(args, "-VerifyCommand", verify_command)
    _append_arg(args, "-VerifyTimeoutSeconds", verify_timeout_seconds)
    _append_arg(args, "-TimeoutSeconds", timeout_seconds)
    _append_arg(args, "-FailurePolicy", failure_policy)
    _append_arg(args, "-Force", force)

    result = _invoke_script("new-workflow-hook-pack.ps1", project_root=project_root, args=args)
    if apply and result.get("status") != "blocked":
        pack_root = result.get("facts", {}).get("pack_root")
        if pack_root:
            apply_result = _invoke_script(
                "apply-knowledge-pack.ps1",
                project_root=project_root,
                args=["-RepoRoot", str(project_root), "-PackPath", str(pack_root), "-Force"],
            )
            result.setdefault("facts", {})["applied_pack"] = apply_result
            if apply_result.get("status") == "blocked":
                result["status"] = "blocked"
                result.setdefault("blockers", []).append(
                    "scaffolded pack apply failed: "
                    + "; ".join(map(str, apply_result.get("blockers") or []))
                )

    _emit_result(result, json_output=json_output, title="hook scaffold")
