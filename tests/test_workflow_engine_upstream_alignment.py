import sys
import threading
import time
from pathlib import Path

import pytest

from specify_cli.workflows import STEP_REGISTRY
from specify_cli.workflows.base import StepBase, StepContext, StepResult, StepStatus
from specify_cli.workflows.engine import RunState, WorkflowDefinition, WorkflowEngine, validate_workflow
from specify_cli.workflows.expressions import evaluate_condition, evaluate_expression
from specify_cli.workflows.steps.shell import ShellStep


def test_from_json_filter_is_strict_and_typed():
    context = StepContext(inputs={"raw": '{"items":[1,2],"name":"demo"}', "bad": "{", "obj": {}})

    assert evaluate_expression("{{ inputs.raw | from_json }}", context) == {
        "items": [1, 2],
        "name": "demo",
    }

    with pytest.raises(ValueError, match="invalid JSON"):
        evaluate_expression("{{ inputs.bad | from_json }}", context)
    with pytest.raises(ValueError, match="expected a JSON string"):
        evaluate_expression("{{ inputs.obj | from_json }}", context)
    with pytest.raises(ValueError, match="with no arguments"):
        evaluate_expression("{{ inputs.raw | from_json() }}", context)


def test_expression_parser_is_quote_aware_for_braces_commas_pipes_and_keywords():
    context = StepContext(inputs={"text": "literal }} token", "mode": "read and write", "needle": "a|b"})

    assert evaluate_expression("before {{ inputs.text | contains('}}') }} after", context) == "before True after"
    assert evaluate_expression("{{ ['x,y', inputs.needle] | join('|') }}", context) == "x,y|a|b"
    assert evaluate_condition("inputs.mode == 'read and write' and inputs.needle in ['a|b', 'c']", context)
    assert evaluate_condition("'b' > 'aa'", context)

    with pytest.raises(ValueError, match="unknown filter"):
        evaluate_expression("{{ inputs.text | missing_filter('x') }}", context)


def test_shell_output_format_json_parses_data_and_fails_loudly(tmp_path):
    shell = ShellStep()
    context = StepContext(project_root=str(tmp_path))
    python = Path(sys.executable).as_posix()

    ok = shell.execute(
        {
            "id": "json",
            "run": f'"{python}" -c "import json; print(json.dumps(dict(value=3)))"',
            "output_format": "json",
        },
        context,
    )
    assert ok.status == StepStatus.COMPLETED
    assert ok.output["data"] == {"value": 3}

    bad = shell.execute(
        {
            "id": "bad-json",
            "run": f'"{python}" -c "print(\'not json\')"',
            "output_format": "json",
        },
        context,
    )
    assert bad.status == StepStatus.FAILED
    assert "not valid JSON" in (bad.error or "")

    raw = shell.execute(
        {"id": "raw", "run": f'"{python}" -c "print(\'plain\')"'},
        context,
    )
    assert raw.status == StepStatus.COMPLETED
    assert "data" not in raw.output


class _CaptureStep(StepBase):
    type_key = "capture"

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def execute(self, config: dict, context: StepContext) -> StepResult:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.05)
            if context.item == "bad":
                return StepResult(
                    status=StepStatus.FAILED,
                    output={"item": context.item, "failed": True},
                    error="bad item",
                )
            return StepResult(status=StepStatus.COMPLETED, output={"item": context.item})
        finally:
            with self.lock:
                self.active -= 1


class _RaceStep(StepBase):
    type_key = "race-capture"

    def execute(self, config: dict, context: StepContext) -> StepResult:
        if context.item == "slow":
            time.sleep(0.2)
            return StepResult(
                status=StepStatus.COMPLETED,
                output={"item": context.item},
            )
        time.sleep(0.02)
        return StepResult(
            status=StepStatus.FAILED,
            output={"item": context.item},
            error="bad item",
        )


@pytest.fixture
def capture_step(monkeypatch):
    step = _CaptureStep()
    monkeypatch.setitem(STEP_REGISTRY, "capture", step)
    return step


def _fanout_definition(items: list, max_concurrency, *, continue_on_error: bool = False) -> WorkflowDefinition:
    coe = "\n      continue_on_error: true" if continue_on_error else ""
    return WorkflowDefinition.from_string(
        f"""
schema_version: "1.0"
workflow:
  id: "demo"
  name: "Demo"
  version: "1.0.0"
steps:
  - id: fan
    type: fan-out
    items: {items!r}
    max_concurrency: {max_concurrency!r}
    step:
      id: capture
      type: capture{coe}
"""
    )


def test_fanout_max_concurrency_preserves_order_and_uses_bounded_parallelism(tmp_path, capture_step):
    definition = _fanout_definition([1, 2, 3, 4], 2)
    state = WorkflowEngine(tmp_path).execute(definition)

    assert state.status.value == "completed"
    assert [item["item"] for item in state.step_results["fan"]["output"]["results"]] == [1, 2, 3, 4]
    assert capture_step.max_active >= 2


def test_fanout_failure_truncates_unless_continue_on_error(tmp_path, capture_step):
    halted = WorkflowEngine(tmp_path / "halted").execute(
        _fanout_definition(["ok", "bad", "later"], 1),
    )
    assert halted.status.value == "failed"
    assert [item.get("item") for item in halted.step_results["fan"]["output"]["results"]] == ["ok", "bad"]

    continued = WorkflowEngine(tmp_path / "continued").execute(
        _fanout_definition(["ok", "bad", "later"], "not-an-int", continue_on_error=True),
    )
    assert continued.status.value == "completed"
    assert [item.get("item") for item in continued.step_results["fan"]["output"]["results"]] == ["ok", "bad", "later"]


def test_parallel_fanout_halt_is_not_overwritten_by_running_sibling(tmp_path, monkeypatch):
    monkeypatch.setitem(STEP_REGISTRY, "race-capture", _RaceStep())
    definition = WorkflowDefinition.from_string(
        """
schema_version: "1.0"
workflow:
  id: "demo"
  name: "Demo"
  version: "1.0.0"
steps:
  - id: fan
    type: fan-out
    items: [bad, slow]
    max_concurrency: 2
    step:
      id: race
      type: race-capture
"""
    )

    state = WorkflowEngine(tmp_path).execute(definition)

    assert state.status.value == "failed"
    assert state.current_step_id == "fan:race:0"
    assert "fan:race:0" in state.step_results
    assert "fan:race:1" not in state.step_results
    assert state.step_results["fan"]["output"]["results"] == [{"item": "bad"}]


def test_run_state_load_rejects_malicious_run_id_before_filesystem_lookup(tmp_path):
    with pytest.raises(ValueError, match="Invalid run_id"):
        RunState.load("../escape", tmp_path)


def test_workflow_validation_fails_loud_for_ambiguous_authoring():
    workflow = WorkflowDefinition.from_string(
        """
schema_version: "1.0"
workflow:
  id: "demo"
  name: "Demo"
  version: "1.0.0"
requires:
  permissions: ["write"]
  typo: true
inputs:
  count:
    type: number
    default: true
steps:
  - id: first
    type: shell
    run: "echo ok"
    continue_on_error: "true"
  - id: join-self
    type: fan-in
    wait_for: ["join-self", "missing", 123]
  - id: review
    type: gate
    message: "Approve?"
    options: ["approve", 7]
"""
    )

    errors = validate_workflow(workflow)
    joined = "\n".join(errors)
    assert "requires.permissions" in joined
    assert "Unknown 'requires' key" in joined
    assert "invalid default" in joined
    assert "continue_on_error" in joined
    assert "references itself" in joined
    assert "unknown or not-yet-declared" in joined
    assert "entries must be step-id strings" in joined
    assert "all options must be strings" in joined
