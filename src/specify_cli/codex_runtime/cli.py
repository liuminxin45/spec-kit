"""Machine-readable native command surface for the opt-in Codex Skill runtime."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from . import knowledge, packs, tasks
from .common import RuntimeBlocked, read_object, tree_digest, recover_transaction


Project = Annotated[Path, typer.Option("--project-dir", "-C", help="Project root (default: current directory)")]
Json = Annotated[bool, typer.Option("--json", help="Structured JSON output (always used by this runtime)")]


def emit(operation):
    try:
        result = operation()
    except (RuntimeBlocked, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "blockers": [str(exc)]}, ensure_ascii=False))
        raise typer.Exit(1) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") in {"blocked", "failed", "error"}:
        raise typer.Exit(1)
    return result


def register(app: typer.Typer) -> None:
    pack = typer.Typer(help="Install and maintain versioned knowledge/capability packs.")
    task = typer.Typer(help="Record requests, execute checks and inspect source-bound acceptance.")
    app.add_typer(pack, name="pack")
    app.add_typer(task, name="task")

    @app.command("context")
    def context_command(select: list[str] = typer.Option(None, "--select"),
                        files: list[str] = typer.Option(None, "--file"),
                        capability: list[str] = typer.Option(None, "--capability"),
                        project_dir: Project = Path("."), json_output: Json = False):
        """Discover metadata or load only selected resource bodies and mandatory policies."""
        emit(lambda: packs.context(project_dir.resolve(), selected=select or None, files=files, capabilities=capability))

    @pack.command("add")
    def add(sources: list[str] = typer.Argument(...), dry_run: bool = False,
            project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: packs.install(project_dir.resolve(), sources, dry_run=dry_run))

    @pack.command("update")
    def update(sources: list[str] = typer.Argument(...), dry_run: bool = False,
               project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: packs.install(project_dir.resolve(), sources, replace=True, dry_run=dry_run))

    @pack.command("refresh")
    def refresh(dry_run: bool = False, project_dir: Project = Path("."), json_output: Json = False):
        """Refresh the generated entry Skill using this CLI, preserving customized files."""
        emit(lambda: packs.install(project_dir.resolve(), [], dry_run=dry_run))

    @pack.command("remove")
    def remove(identity: str, dry_run: bool = False, project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: packs.remove(project_dir.resolve(), identity, dry_run=dry_run))

    @pack.command("restore")
    def restore(dry_run: bool = False, project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: packs.restore(project_dir.resolve(), dry_run=dry_run))

    @pack.command("recover")
    def recover(identity: str, apply: bool = False, project_dir: Project = Path("."), json_output: Json = False):
        """Preview an interrupted transaction rollback; --apply preserves subsequent user edits."""
        emit(lambda: recover_transaction(project_dir.resolve(), identity, apply=apply))

    @pack.command("list")
    def list_packs(project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: {"status": "ok", "packs": packs.locked(project_dir.resolve())["packs"]})

    @pack.command("doctor")
    def doctor(project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: packs.doctor(project_dir.resolve()))

    @pack.command("validate")
    def validate(directory: Path, json_output: Json = False):
        emit(lambda: {"status": "ok", "manifest": packs.validate_pack(directory.resolve()),
                      "sha256": tree_digest(directory.resolve())})

    @pack.command("bind")
    def bind(identity: str, scope: list[str] = typer.Option(None, "--scope"),
             require: list[str] = typer.Option(None, "--require"), layer: str = "project",
             project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: packs.bind(project_dir.resolve(), identity, scope or [], require or [], layer))

    @pack.command("migration-plan")
    def migration_plan(project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: packs.migration_plan(project_dir.resolve()))

    @pack.command("bootstrap")
    def bootstrap(identity: str = typer.Option(..., "--id"), output: str = typer.Option(..., "--output"),
                  project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: knowledge.bootstrap(project_dir.resolve(), identity, output))

    @pack.command("import-legacy")
    def import_legacy(source: str = typer.Option(..., "--source"), identity: str = typer.Option(..., "--id"),
                      output: str = typer.Option(..., "--output"), project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: knowledge.import_legacy(project_dir.resolve(), source, identity, output))

    @pack.command("release")
    def release(directory: str, bump: str = typer.Option(..., "--bump"), reason: str = typer.Option(..., "--reason"),
                review_file: Path = typer.Option(..., "--review-file"), project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: knowledge.release(project_dir.resolve(), directory, bump, reason, read_object(review_file)))

    @task.command("start")
    def start(request_file: Path = typer.Option(..., "--request-file"), source_ref: str = "current-user-request",
              identity: str = typer.Option(None, "--id"), project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: tasks.start(project_dir.resolve(), request_file.read_text(encoding="utf-8-sig"),
                                source_ref=source_ref, identity=identity))

    @task.command("record")
    def record(identity: str, event_file: Path = typer.Option(..., "--event-file"),
               project_dir: Project = Path("."), json_output: Json = False):
        def apply():
            event = read_object(event_file)
            return tasks.record(project_dir.resolve(), identity, event["type"], event["payload"])
        emit(apply)

    @task.command("inspect")
    def inspect(identity: str, project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: tasks.inspect(project_dir.resolve(), identity))

    @task.command("check")
    def check(identity: str, phase: str = "ai_accept", project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: tasks.check(project_dir.resolve(), identity, phase))

    @task.command("run")
    def run(identity: str, command_file: Path = typer.Option(..., "--command-file"),
            project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: tasks.run_check(project_dir.resolve(), identity, read_object(command_file)))

    @task.command("finish")
    def finish(identity: str, project_dir: Project = Path("."), json_output: Json = False):
        emit(lambda: tasks.finish(project_dir.resolve(), identity))

    @task.command("guard")
    def guard(identity: str, native: bool = False, project_dir: Project = Path("."), json_output: Json = False):
        """Optional bounded Stop-hook adapter; host registration is separate."""
        if native:
            try:
                result = tasks.guard(project_dir.resolve(), identity)
                print(json.dumps(result.get("hook_output", {}), ensure_ascii=False))
            except (RuntimeBlocked, OSError) as exc:
                print(json.dumps({"systemMessage": "Spec Kit guard unavailable: " + str(exc)}))
        else:
            emit(lambda: tasks.guard(project_dir.resolve(), identity))

    @task.command("list")
    def list_tasks(project_dir: Project = Path("."), json_output: Json = False):
        def records():
            root = project_dir.resolve()
            result = []
            for path in sorted((root / ".specify/tasks").glob("*/events.jsonl")):
                state = tasks.read_task(root, path.parent.name)
                result.append({key: state[key] for key in ["id", "status", "request", "updated_at"]})
            return {"status": "ok", "tasks": result}
        emit(records)
