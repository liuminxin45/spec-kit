#!/usr/bin/env python3
"""Consolidated prerequisite checking script."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from common import (
        FeaturePaths,
        format_speckit_command,
        get_feature_delivery_profile,
        get_feature_paths,
        is_lean_delivery_profile,
        test_feature_branch,
    )
except ImportError:  # pragma: no cover - direct execution from unusual cwd
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from common import (
        FeaturePaths,
        format_speckit_command,
        get_feature_delivery_profile,
        get_feature_paths,
        is_lean_delivery_profile,
        test_feature_branch,
    )


HELP_TEXT = """Usage: check_prerequisites.py [OPTIONS]

Consolidated prerequisite checking for Spec-Driven Development workflow.

OPTIONS:
  --json              Output in JSON format
  --require-tasks     Require tasks.md to exist (for implementation phase)
  --include-tasks     Include tasks.md in AVAILABLE_DOCS list
  --paths-only        Only output path variables (no prerequisite validation)
  --spec-only         Require feature directory and spec.md only (clarify phase)
  --stage STAGE       Workflow stage for profile-aware artifact checks
  --delivery-profile PROFILE
                      Optional explicit delivery profile
  --help, -h          Show this help message

EXAMPLES:
  ./check_prerequisites.py --json
  ./check_prerequisites.py --json --require-tasks --include-tasks
  ./check_prerequisites.py --paths-only
  ./check_prerequisites.py --json --spec-only
"""


@dataclass(frozen=True)
class Args:
    json_mode: bool = False
    require_tasks: bool = False
    include_tasks: bool = False
    paths_only: bool = False
    spec_only: bool = False
    stage: str = ""
    delivery_profile: str = ""


def _json_line(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"


def _parse_args(argv: list[str]) -> Args:
    json_mode = False
    require_tasks = False
    include_tasks = False
    paths_only = False
    spec_only = False
    stage = ""
    delivery_profile = ""

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--json":
            json_mode = True
        elif arg == "--require-tasks":
            require_tasks = True
        elif arg == "--include-tasks":
            include_tasks = True
        elif arg == "--paths-only":
            paths_only = True
        elif arg == "--spec-only":
            spec_only = True
        elif arg == "--stage":
            i += 1
            if i >= len(argv):
                print("ERROR: --stage requires a value.", file=sys.stderr)
                raise SystemExit(1)
            stage = argv[i]
        elif arg.startswith("--stage="):
            stage = arg.split("=", 1)[1]
        elif arg == "--delivery-profile":
            i += 1
            if i >= len(argv):
                print("ERROR: --delivery-profile requires a value.", file=sys.stderr)
                raise SystemExit(1)
            delivery_profile = argv[i]
        elif arg.startswith("--delivery-profile="):
            delivery_profile = arg.split("=", 1)[1]
        elif arg in {"--help", "-h"}:
            sys.stdout.write(HELP_TEXT)
            raise SystemExit(0)
        else:
            print(
                f"ERROR: Unknown option '{arg}'. Use --help for usage information.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        i += 1

    return Args(
        json_mode=json_mode,
        require_tasks=require_tasks,
        include_tasks=include_tasks,
        paths_only=paths_only,
        spec_only=spec_only,
        stage=stage,
        delivery_profile=delivery_profile,
    )


def _dir_has_files(path: Path) -> bool:
    try:
        return path.is_dir() and any(child.is_file() for child in path.iterdir())
    except OSError:
        return False


def _available_docs(paths: FeaturePaths, include_tasks: bool) -> list[str]:
    docs: list[str] = []
    if paths.workpack.is_file():
        docs.append("workpack.md")
    if paths.research.is_file():
        docs.append("research.md")
    if paths.data_model.is_file():
        docs.append("data-model.md")
    if _dir_has_files(paths.contracts_dir):
        docs.append("contracts/")
    if paths.quickstart.is_file():
        docs.append("quickstart.md")
    if include_tasks and paths.tasks.is_file():
        docs.append("tasks.md")
    return docs


def _print_paths_only(paths: FeaturePaths, json_mode: bool, delivery_profile: str) -> None:
    if json_mode:
        sys.stdout.write(
            _json_line(
                {
                    "REPO_ROOT": str(paths.repo_root),
                    "BRANCH": paths.current_branch,
                    "FEATURE_DIR": str(paths.feature_dir),
                    "FEATURE_SPEC": str(paths.feature_spec),
                    "IMPL_PLAN": str(paths.impl_plan),
                    "WORKPACK": str(paths.workpack),
                    "TASKS": str(paths.tasks),
                    "DELIVERY_PROFILE": delivery_profile,
                }
            )
        )
        return

    print(f"REPO_ROOT: {paths.repo_root}")
    print(f"BRANCH: {paths.current_branch}")
    print(f"FEATURE_DIR: {paths.feature_dir}")
    print(f"FEATURE_SPEC: {paths.feature_spec}")
    print(f"IMPL_PLAN: {paths.impl_plan}")
    print(f"WORKPACK: {paths.workpack}")
    print(f"TASKS: {paths.tasks}")
    print(f"DELIVERY_PROFILE: {delivery_profile}")


def _check_file(path: Path, description: str) -> None:
    marker = "OK" if path.is_file() else "NO"
    print(f"  {marker} {description}")


def _check_dir(path: Path, description: str) -> None:
    marker = "OK" if _dir_has_files(path) else "NO"
    print(f"  {marker} {description}")


def _print_text_results(
    paths: FeaturePaths,
    include_tasks: bool,
    delivery_profile: str,
    planning_artifact_name: str,
) -> None:
    print(f"FEATURE_DIR:{paths.feature_dir}")
    print(f"DELIVERY_PROFILE:{delivery_profile}")
    print(f"PLANNING_ARTIFACT:{planning_artifact_name}")
    print("AVAILABLE_DOCS:")
    _check_file(paths.workpack, "workpack.md")
    _check_file(paths.research, "research.md")
    _check_file(paths.data_model, "data-model.md")
    _check_dir(paths.contracts_dir, "contracts/")
    _check_file(paths.quickstart, "quickstart.md")
    if include_tasks:
        _check_file(paths.tasks, "tasks.md")


def _print_spec_only(paths: FeaturePaths, json_mode: bool) -> None:
    if json_mode:
        sys.stdout.write(
            _json_line(
                {
                    "FEATURE_DIR": str(paths.feature_dir),
                    "FEATURE_SPEC": str(paths.feature_spec),
                    "AVAILABLE_DOCS": [],
                }
            )
        )
        return
    print(f"FEATURE_DIR:{paths.feature_dir}")
    print(f"FEATURE_SPEC:{paths.feature_spec}")
    print("AVAILABLE_DOCS:")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv if argv is not None else sys.argv[1:]))

    try:
        paths = get_feature_paths(
            no_persist=args.paths_only,
            script_file=Path(__file__),
        )
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1

    if not test_feature_branch(paths.current_branch, paths.has_git):
        return 1

    profile = get_feature_delivery_profile(
        paths.repo_root,
        paths.feature_dir,
        explicit_profile=args.delivery_profile,
    )

    if args.paths_only:
        _print_paths_only(paths, args.json_mode, profile)
        return 0

    if not paths.feature_dir.is_dir():
        print(f"ERROR: Feature directory not found: {paths.feature_dir}")
        print(
            f"Run {format_speckit_command('specify', paths.repo_root)} first to create the feature structure."
        )
        return 1

    if args.spec_only:
        if not paths.feature_spec.is_file():
            print(f"ERROR: spec.md not found in {paths.feature_dir}")
            print(
                f"Run {format_speckit_command('specify', paths.repo_root)} first to create the feature specification."
            )
            return 1
        _print_spec_only(paths, args.json_mode)
        return 0

    stage_key = args.stage.strip().lower()
    lean_workpack_stages = {
        "implement",
        "acceptance",
        "commit",
        "retrospective",
        "promote-lessons",
        "simplify",
        "test-hardening",
        "converge",
    }
    uses_lean_workpack = is_lean_delivery_profile(profile) and stage_key in lean_workpack_stages
    planning_artifact = paths.workpack if uses_lean_workpack else paths.impl_plan
    planning_artifact_name = "workpack.md" if uses_lean_workpack else "plan.md"

    if not planning_artifact.is_file():
        print(f"ERROR: {planning_artifact_name} not found in {paths.feature_dir}")
        action = "create the lean workpack" if uses_lean_workpack else "create the implementation plan"
        print(
            f"Run {format_speckit_command('plan', paths.repo_root)} first to {action}."
        )
        return 1

    if args.require_tasks and not paths.tasks.is_file():
        print(f"ERROR: tasks.md not found in {paths.feature_dir}")
        print(
            f"Run {format_speckit_command('tasks', paths.repo_root)} first to create the task list."
        )
        return 1

    docs = _available_docs(paths, args.include_tasks)
    if args.json_mode:
        sys.stdout.write(
            _json_line(
                {
                    "FEATURE_DIR": str(paths.feature_dir),
                    "AVAILABLE_DOCS": docs,
                    "DELIVERY_PROFILE": profile,
                    "PLANNING_ARTIFACT": planning_artifact_name,
                }
            )
        )
    else:
        _print_text_results(paths, args.include_tasks, profile, planning_artifact_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
