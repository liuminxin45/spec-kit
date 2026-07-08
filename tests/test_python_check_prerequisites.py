import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=run_env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
    )


def _json_from_stdout(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"No JSON object found in stdout: {stdout!r}")


def _make_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    feature = project / "specs" / "001-demo"
    (project / ".specify").mkdir(parents=True)
    feature.mkdir(parents=True)
    for name in ["spec.md", "plan.md", "tasks.md", "research.md", "data-model.md", "quickstart.md"]:
        (feature / name).write_text(f"# {name}\n", encoding="utf-8")
    contracts = feature / "contracts"
    contracts.mkdir()
    (contracts / "openapi.yml").write_text("openapi: 3.0.0\n", encoding="utf-8")
    return project, feature


def test_python_check_prerequisites_matches_powershell_json(tmp_path):
    project, feature = _make_project(tmp_path)

    ps = _run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "check-prerequisites.ps1"),
            "-Json",
            "-RequireTasks",
            "-IncludeTasks",
        ],
        cwd=project,
    )
    py = _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "python" / "check_prerequisites.py"),
            "--json",
            "--require-tasks",
            "--include-tasks",
        ],
        cwd=project,
    )

    assert ps.returncode == 0, ps.stdout + ps.stderr
    assert py.returncode == 0, py.stdout + py.stderr
    ps_payload = _json_from_stdout(ps.stdout)
    py_payload = _json_from_stdout(py.stdout)
    assert Path(ps_payload["FEATURE_DIR"]).resolve() == feature.resolve()
    assert Path(py_payload["FEATURE_DIR"]).resolve() == feature.resolve()
    assert py_payload["AVAILABLE_DOCS"] == ps_payload["AVAILABLE_DOCS"]


def test_python_check_prerequisites_supports_spec_only_and_paths_only_has_no_state_side_effect(tmp_path):
    project, feature = _make_project(tmp_path)
    feature_json = project / ".specify" / "feature.json"
    env = {"SPECIFY_FEATURE_DIRECTORY": str(feature)}

    for cmd in [
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "check-prerequisites.ps1"),
            "-Json",
            "-PathsOnly",
        ],
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "python" / "check_prerequisites.py"),
            "--json",
            "--paths-only",
        ],
    ]:
        result = _run(cmd, cwd=project, env=env)
        assert result.returncode == 0, result.stdout + result.stderr
        payload = _json_from_stdout(result.stdout)
        assert Path(payload["FEATURE_DIR"]).resolve() == feature.resolve()
        assert not feature_json.exists()

    spec_only = _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "python" / "check_prerequisites.py"),
            "--json",
            "--spec-only",
        ],
        cwd=project,
    )
    assert spec_only.returncode == 0, spec_only.stdout + spec_only.stderr
    payload = _json_from_stdout(spec_only.stdout)
    assert Path(payload["FEATURE_SPEC"]).resolve() == (feature / "spec.md").resolve()
    assert payload["AVAILABLE_DOCS"] == []
