"""Behavior regressions for the selective v1.0.6 alignment."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from specify_cli._github_http import build_github_request
from specify_cli.workflows.base import StepContext
from specify_cli.workflows.engine import RunState, WorkflowDefinition, WorkflowEngine, validate_workflow
from specify_cli.workflows.expressions import evaluate_condition, evaluate_expression
from specify_cli.workflows.steps.switch import SwitchStep


ROOT = Path(__file__).resolve().parents[1]


def definition(step=None, **defaults):
    return WorkflowDefinition({
        "workflow": {"id": "hardening", "name": "Hardening", "version": "1.0.0", **defaults},
        "steps": [step or {"id": "wait", "type": "gate", "message": "Review"}],
    })


@pytest.mark.parametrize("kind,body", [("if", {"then": []}), ("while", {"steps": []}), ("do-while", {"steps": []})])
@pytest.mark.parametrize("condition", [
    "inputs.ready", " ", "{{ false }} and {{ false }}", "not {{ false }}",
    "{{ false }} and {{ inputs.ready", "{{ inputs.value | default('oops }}", "{{ }}",
])
def test_invalid_condition_stops_before_run_creation(tmp_path, kind, body, condition):
    workflow = definition({"id": "branch", "type": kind, "condition": condition, **body})
    with pytest.raises(ValueError, match="condition"):
        WorkflowEngine(tmp_path).execute(workflow)
    assert not (tmp_path / ".specify/workflows/runs").exists()
    with pytest.raises(ValueError, match="condition"):
        evaluate_condition(condition, StepContext())


@pytest.mark.parametrize("condition,expected", [
    (False, False), (True, True), ("", False), (" false\n", False),
    ("{{ inputs.ready }}", False), ("{{ inputs.text | contains('}}') }}", True),
])
def test_valid_conditions_keep_typed_results(condition, expected):
    assert validate_workflow(definition({"id": "branch", "type": "if", "condition": condition, "then": []})) == []
    assert evaluate_condition(condition, StepContext(inputs={"ready": False, "text": "literal }}"})) is expected


@pytest.mark.parametrize("kind,fields,missing", [
    ("while", {"condition": False}, "steps"),
    ("do-while", {"condition": False}, "steps"),
    ("switch", {"expression": "{{ inputs.mode }}"}, "cases"),
])
def test_missing_control_flow_body_is_rejected(kind, fields, missing):
    errors = validate_workflow(definition({"id": "branch", "type": kind, **fields}))
    assert any(missing in error for error in errors)


@pytest.mark.parametrize("field,value", [("options", []), ("options", False), ("options", ""), ("integration", []), ("model", 3)])
def test_dispatch_defaults_rejected_on_execute_and_resume(tmp_path, field, value):
    engine = WorkflowEngine(tmp_path)
    bad = definition(**{field: value})
    with pytest.raises(ValueError, match=field):
        engine.execute(bad)
    assert not (tmp_path / ".specify/workflows/runs").exists()
    state = engine.execute(definition(), run_id="resume-hardening")
    run_copy = tmp_path / ".specify/workflows/runs" / state.run_id / "workflow.yml"
    run_copy.write_text(yaml.safe_dump(bad.data), encoding="utf-8")
    state_path = run_copy.with_name("state.json")
    original = state_path.read_bytes()
    with pytest.raises(ValueError, match=field):
        engine.resume(state.run_id)
    assert state_path.read_bytes() == original


@pytest.mark.parametrize("expression", [
    "{{ inputs.count > inputs.limit | default(5) }}",
    "{{ inputs.count | default(0) > 5 }}",
    "{{ not inputs.count | default(1) }}",
])
def test_ambiguous_filters_fail_loudly(expression):
    with pytest.raises(ValueError):
        evaluate_expression(expression, StepContext(inputs={"count": 1, "limit": 2}))


def test_filter_chain_and_switch_output_newline():
    context = StepContext(inputs={"rows": [{"name": "a"}, {"name": "b"}], "mode": "approve\r\n"})
    assert evaluate_expression("{{ inputs.rows | map('name') | join('|') }}", context) == "a|b"
    result = SwitchStep().execute({"expression": "{{ inputs.mode }}", "cases": {"approve": []}}, context)
    assert result.output == {"matched_case": "approve", "expression_value": "approve\r\n"}


@pytest.mark.parametrize("port", ["notaport", "65536", "-1"])
def test_invalid_port_rejected_before_request_construction(port):
    with patch("specify_cli._github_http.urllib.request.Request") as request:
        with pytest.raises(ValueError):
            build_github_request(f"https://github.com:{port}/file")
    request.assert_not_called()


def test_valid_port_preserves_credentials_and_url(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    request = build_github_request("https://github.com:8443/file")
    assert request.full_url == "https://github.com:8443/file"
    assert request.get_header("Authorization") == "Bearer test-token"


def test_run_state_missing_at_open_has_stable_error(tmp_path):
    # Simulate the file disappearing between a precheck and open. No precheck
    # should be necessary; both initially absent and raced-away files agree.
    with patch.object(Path, "exists", return_value=True):
        with pytest.raises(FileNotFoundError, match="Run state not found"):
            RunState.load("missing-run", tmp_path)


def test_null_defaults_remain_supported():
    assert validate_workflow(definition(options=None, model=None, integration=None)) == []


@pytest.mark.parametrize("shell", ["pwsh", "powershell"])
def test_windows_feature_paths_and_available_docs(tmp_path, shell):
    executable = shutil.which(shell)
    if not executable:
        pytest.skip(f"{shell} unavailable")
    project = tmp_path / "project"
    feature = project / "specs" / "001-中文功能"
    feature.mkdir(parents=True)
    subprocess.run(["git", "init", str(project)], check=True, capture_output=True)
    (project / ".specify").mkdir()
    templates = project / ".specify/templates"
    templates.mkdir()
    for name in ["tasks-template.md", "plan-template.md"]:
        shutil.copyfile(ROOT / "templates" / name, templates / name)
    (project / ".specify/feature.json").write_text(json.dumps({"feature_directory": "specs/001-中文功能", "delivery_profile": "full-sdd"}, ensure_ascii=False), encoding="utf-8")
    for name in ["spec.md", "plan.md", "research.md", "data-model.md", "quickstart.md"]:
        (feature / name).write_text("# Document\n", encoding="utf-8")
    (feature / "contracts").mkdir()
    (feature / "contracts/api.md").write_text("# API", encoding="utf-8")
    env = {**os.environ, "SPECIFY_ROOT": str(project), "SPECIFY_REPO_ROOT": str(project), "SPECIFY_FEATURE": "001-中文功能"}
    env.pop("SPECIFY_FEATURE_DIRECTORY", None)
    def run(script, *args):
        script_path = str(ROOT / "scripts/powershell" / script).replace("'", "''")
        # Keep transport UTF-8 in both hosts; the behavior under test is the
        # file reader, whose Windows PowerShell default is still ANSI.
        command = "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); & '" + script_path + "' " + " ".join(args)
        return subprocess.run([executable, "-NoProfile", "-Command", command], cwd=project, env=env, capture_output=True, text=True, encoding="utf-8")
    plan = run("setup-plan.ps1", "-Json")
    assert plan.returncode == 0, plan.stdout + plan.stderr
    assert plan.stdout.lstrip().startswith("{"), repr(plan.stdout) + repr(plan.stderr)
    payload = json.loads(plan.stdout)
    assert Path(payload["FEATURE_DIR"]) == feature
    assert payload["SPECS_DIR"] == payload["FEATURE_DIR"]
    tasks = run("setup-tasks.ps1")
    assert tasks.returncode == 0, tasks.stdout + tasks.stderr
    for name in ["research.md", "data-model.md", "contracts/", "quickstart.md"]:
        assert name in tasks.stdout
