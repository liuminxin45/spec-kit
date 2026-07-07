"""Workflow engine — loads, validates, and executes workflow YAML definitions.

The engine is the orchestrator that:
- Parses workflow YAML definitions
- Validates step configurations and requirements
- Executes steps sequentially, dispatching to the correct step type
- Manages state persistence for resume capability
- Handles control flow (branching, loops, fan-out/fan-in)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .base import RunStatus, StepContext, StepResult, StepStatus


# -- Workflow Definition --------------------------------------------------


class WorkflowDefinition:
    """Parsed and validated workflow YAML definition."""

    def __init__(self, data: dict[str, Any], source_path: Path | None = None) -> None:
        self.data = data
        self.source_path = source_path

        workflow = data.get("workflow", {})
        self.id: str = workflow.get("id", "")
        self.name: str = workflow.get("name", "")
        self.version: str = workflow.get("version", "0.0.0")
        self.author: str = workflow.get("author", "")
        self.description: str = workflow.get("description", "")
        self.schema_version: str = data.get("schema_version", "1.0")

        # Defaults
        self.default_integration: str | None = workflow.get("integration")
        self.default_model: str | None = workflow.get("model")
        self.default_options: dict[str, Any] = workflow.get("options") or {}
        if not isinstance(self.default_options, dict):
            self.default_options = {}

        # Requirements (declared but not yet enforced at runtime;
        # enforcement is a planned enhancement)
        self.requires: dict[str, Any] = data.get("requires", {})

        # Inputs
        self.inputs: dict[str, Any] = data.get("inputs", {})

        # Steps
        self.steps: list[dict[str, Any]] = data.get("steps", [])

    @classmethod
    def from_yaml(cls, path: Path) -> WorkflowDefinition:
        """Load a workflow definition from a YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            msg = f"Workflow YAML must be a mapping, got {type(data).__name__}."
            raise ValueError(msg)
        return cls(data, source_path=path)

    @classmethod
    def from_string(cls, content: str) -> WorkflowDefinition:
        """Load a workflow definition from a YAML string."""
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            msg = f"Workflow YAML must be a mapping, got {type(data).__name__}."
            raise ValueError(msg)
        return cls(data)


# -- Workflow Validation --------------------------------------------------

# ID format: lowercase alphanumeric with hyphens
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")

# Valid step types (matching STEP_REGISTRY keys)
def _get_valid_step_types() -> set[str]:
    """Return valid step types from the registry, with a built-in fallback."""
    from . import STEP_REGISTRY
    if STEP_REGISTRY:
        return set(STEP_REGISTRY.keys())
    return {
        "command", "shell", "prompt", "gate", "if",
        "switch", "while", "do-while", "fan-out", "fan-in",
    }


def validate_workflow(definition: WorkflowDefinition) -> list[str]:
    """Validate a workflow definition and return a list of error messages.

    An empty list means the workflow is valid.
    """
    errors: list[str] = []

    # -- Schema version ---------------------------------------------------
    if definition.schema_version not in ("1.0", "1"):
        errors.append(
            f"Unsupported schema_version {definition.schema_version!r}. "
            f"Expected '1.0'."
        )

    # -- Top-level fields -------------------------------------------------
    if not definition.id:
        errors.append("Workflow is missing 'workflow.id'.")
    elif not _ID_PATTERN.match(definition.id):
        errors.append(
            f"Workflow ID {definition.id!r} must be lowercase alphanumeric "
            f"with hyphens."
        )

    if not definition.name:
        errors.append("Workflow is missing 'workflow.name'.")

    if not definition.version:
        errors.append("Workflow is missing 'workflow.version'.")
    elif not re.match(r"^\d+\.\d+\.\d+$", definition.version):
        errors.append(
            f"Workflow version {definition.version!r} is not valid "
            f"semantic versioning (expected X.Y.Z)."
        )

    # -- Inputs -----------------------------------------------------------
    if not isinstance(definition.inputs, dict):
        errors.append("'inputs' must be a mapping (or omitted).")
    else:
        for input_name, input_def in definition.inputs.items():
            if not isinstance(input_def, dict):
                errors.append(f"Input {input_name!r} must be a mapping.")
                continue
            input_type = input_def.get("type")
            if input_type and input_type not in ("string", "number", "boolean"):
                errors.append(
                    f"Input {input_name!r} has invalid type {input_type!r}. "
                    f"Must be 'string', 'number', or 'boolean'."
                )

    # -- Steps ------------------------------------------------------------
    if not isinstance(definition.steps, list):
        errors.append("'steps' must be a list.")
        return errors
    if not definition.steps:
        errors.append("Workflow has no steps defined.")

    seen_ids: set[str] = set()
    _validate_steps(definition.steps, seen_ids, errors)

    return errors


def _validate_steps(
    steps: list[dict[str, Any]],
    seen_ids: set[str],
    errors: list[str],
) -> None:
    """Recursively validate a list of steps."""
    from . import STEP_REGISTRY

    for step_config in steps:
        if not isinstance(step_config, dict):
            errors.append(f"Step must be a mapping, got {type(step_config).__name__}.")
            continue

        step_id = step_config.get("id")
        if not step_id:
            errors.append("Step is missing 'id' field.")
            continue

        if ":" in step_id:
            errors.append(
                f"Step ID {step_id!r} contains ':' which is reserved "
                f"for engine-generated nested IDs (parentId:childId)."
            )

        if step_id in seen_ids:
            errors.append(f"Duplicate step ID {step_id!r}.")
        seen_ids.add(step_id)

        # Determine step type
        step_type = step_config.get("type", "command")
        if step_type not in _get_valid_step_types():
            errors.append(
                f"Step {step_id!r} has invalid type {step_type!r}."
            )
            continue

        # Delegate to step-specific validation
        step_impl = STEP_REGISTRY.get(step_type)
        if step_impl:
            step_errors = step_impl.validate(step_config)
            errors.extend(step_errors)

        # Recursively validate nested steps
        for nested_key in ("then", "else", "steps"):
            nested = step_config.get(nested_key)
            if isinstance(nested, list):
                _validate_steps(nested, seen_ids, errors)

        # Validate switch cases
        cases = step_config.get("cases")
        if isinstance(cases, dict):
            for _case_key, case_steps in cases.items():
                if isinstance(case_steps, list):
                    _validate_steps(case_steps, seen_ids, errors)

        # Validate switch default
        default = step_config.get("default")
        if isinstance(default, list):
            _validate_steps(default, seen_ids, errors)

        # Validate fan-out nested step (template — not added to seen_ids
        # since the engine generates parentId:templateId:index at runtime)
        fan_step = step_config.get("step")
        if isinstance(fan_step, dict):
            fan_errors: list[str] = []
            _validate_steps([fan_step], set(), fan_errors)
            errors.extend(fan_errors)


# -- Run State Persistence ------------------------------------------------


class RunState:
    """Manages workflow run state for persistence and resume."""

    def __init__(
        self,
        run_id: str | None = None,
        workflow_id: str = "",
        project_root: Path | None = None,
    ) -> None:
        self.run_id = run_id or str(uuid.uuid4())[:8]
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$', self.run_id):
            msg = f"Invalid run_id {self.run_id!r}: must be alphanumeric with hyphens/underscores only."
            raise ValueError(msg)
        self.workflow_id = workflow_id
        self.project_root = project_root or Path(".")
        self.status = RunStatus.CREATED
        self.current_step_index = 0
        self.current_step_id: str | None = None
        self.step_results: dict[str, dict[str, Any]] = {}
        self.hook_results: dict[str, Any] = {}
        self.pending_hook: dict[str, Any] | None = None
        self.inputs: dict[str, Any] = {}
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.log_entries: list[dict[str, Any]] = []

    @property
    def runs_dir(self) -> Path:
        return self.project_root / ".specify" / "workflows" / "runs" / self.run_id

    def save(self) -> None:
        """Persist current state to disk."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
        runs_dir = self.runs_dir
        runs_dir.mkdir(parents=True, exist_ok=True)

        state_data = {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "current_step_index": self.current_step_index,
            "current_step_id": self.current_step_id,
            "step_results": self.step_results,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.hook_results:
            state_data["hook_results"] = self.hook_results
        if self.pending_hook is not None:
            state_data["pending_hook"] = self.pending_hook
        with open(runs_dir / "state.json", "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)

        inputs_data = {"inputs": self.inputs}
        with open(runs_dir / "inputs.json", "w", encoding="utf-8") as f:
            json.dump(inputs_data, f, indent=2)

    @classmethod
    def load(cls, run_id: str, project_root: Path) -> RunState:
        """Load a run state from disk."""
        runs_dir = project_root / ".specify" / "workflows" / "runs" / run_id
        state_path = runs_dir / "state.json"
        if not state_path.exists():
            msg = f"Run state not found: {state_path}"
            raise FileNotFoundError(msg)

        with open(state_path, encoding="utf-8") as f:
            state_data = json.load(f)

        state = cls(
            run_id=state_data["run_id"],
            workflow_id=state_data["workflow_id"],
            project_root=project_root,
        )
        state.status = RunStatus(state_data["status"])
        state.current_step_index = state_data.get("current_step_index", 0)
        state.current_step_id = state_data.get("current_step_id")
        state.step_results = state_data.get("step_results", {})
        state.hook_results = state_data.get("hook_results", {})
        state.pending_hook = state_data.get("pending_hook")
        state.created_at = state_data.get("created_at", "")
        state.updated_at = state_data.get("updated_at", "")

        inputs_path = runs_dir / "inputs.json"
        if inputs_path.exists():
            with open(inputs_path, encoding="utf-8") as f:
                inputs_data = json.load(f)
            state.inputs = inputs_data.get("inputs", {})

        return state

    def append_log(self, entry: dict[str, Any]) -> None:
        """Append a log entry to the run log."""
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.log_entries.append(entry)

        runs_dir = self.runs_dir
        runs_dir.mkdir(parents=True, exist_ok=True)
        with open(runs_dir / "log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


# -- Workflow Engine ------------------------------------------------------


class WorkflowEngine:
    """Orchestrator that loads, validates, and executes workflow definitions."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(".")
        self.on_step_start: Any = None  # Callable[[str, str], None] | None

    def load_workflow(self, source: str | Path) -> WorkflowDefinition:
        """Load a workflow from an installed ID or a local YAML path.

        Parameters
        ----------
        source:
            Either a workflow ID (looked up in the installed workflows
            directory) or a path to a YAML file.

        Returns
        -------
        A parsed ``WorkflowDefinition`` (not yet validated; call
        ``validate_workflow()`` or ``engine.validate()`` separately).

        Raises
        ------
        FileNotFoundError:
            If the workflow file cannot be found.
        ValueError:
            If the workflow YAML is invalid.
        """
        path = Path(source)

        # Try as a direct file path first
        if path.suffix in (".yml", ".yaml") and path.exists():
            return WorkflowDefinition.from_yaml(path)

        # Try as an installed workflow ID
        installed_path = (
            self.project_root
            / ".specify"
            / "workflows"
            / str(source)
            / "workflow.yml"
        )
        if installed_path.exists():
            return WorkflowDefinition.from_yaml(installed_path)

        msg = f"Workflow not found: {source}"
        raise FileNotFoundError(msg)

    def validate(self, definition: WorkflowDefinition) -> list[str]:
        """Validate a workflow definition."""
        return validate_workflow(definition)

    def execute(
        self,
        definition: WorkflowDefinition,
        inputs: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> RunState:
        """Execute a workflow definition.

        Parameters
        ----------
        definition:
            The validated workflow definition.
        inputs:
            User-provided input values.
        run_id:
            Optional run ID (auto-generated if not provided).

        Returns
        -------
        The final ``RunState`` after execution completes (or pauses).
        """
        from . import STEP_REGISTRY

        state = RunState(
            run_id=run_id,
            workflow_id=definition.id,
            project_root=self.project_root,
        )

        # Persist a copy of the workflow definition so resume can
        # reload it even if the original source is no longer available
        # (e.g. a local YAML path that was moved or deleted).
        run_dir = self.project_root / ".specify" / "workflows" / "runs" / state.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        workflow_copy = run_dir / "workflow.yml"
        import yaml
        with open(workflow_copy, "w", encoding="utf-8") as f:
            yaml.safe_dump(definition.data, f, sort_keys=False)

        # Resolve inputs
        resolved_inputs = self._resolve_inputs(definition, inputs or {})
        state.inputs = resolved_inputs
        state.status = RunStatus.RUNNING
        state.save()

        context = StepContext(
            inputs=resolved_inputs,
            default_integration=definition.default_integration,
            default_model=definition.default_model,
            default_options=definition.default_options,
            project_root=str(self.project_root),
            run_id=state.run_id,
            workflow_id=definition.id,
        )

        # Execute steps
        try:
            selected_steps = self._select_steps(definition.steps, resolved_inputs)
            self._execute_steps(selected_steps, context, state, STEP_REGISTRY)
        except KeyboardInterrupt:
            state.status = RunStatus.PAUSED
            state.append_log({"event": "workflow_interrupted"})
            state.save()
            return state
        except Exception as exc:
            state.status = RunStatus.FAILED
            state.append_log({"event": "workflow_failed", "error": str(exc)})
            state.save()
            raise

        if state.status == RunStatus.RUNNING:
            state.status = RunStatus.COMPLETED
        state.append_log({"event": "workflow_finished", "status": state.status.value})
        state.save()
        return state

    def resume(self, run_id: str) -> RunState:
        """Resume a paused or failed workflow run."""
        state = RunState.load(run_id, self.project_root)
        if state.status not in (RunStatus.PAUSED, RunStatus.FAILED):
            msg = f"Cannot resume run {run_id!r} with status {state.status.value!r}."
            raise ValueError(msg)

        # Load the workflow definition — try the persisted copy in the
        # run directory first so resume works even if the original
        # source (e.g. a local YAML path) is no longer available.
        run_dir = self.project_root / ".specify" / "workflows" / "runs" / run_id
        run_copy = run_dir / "workflow.yml"
        if run_copy.exists():
            definition = WorkflowDefinition.from_yaml(run_copy)
        else:
            definition = self.load_workflow(state.workflow_id)

        # Restore context
        context = StepContext(
            inputs=state.inputs,
            steps=state.step_results,
            default_integration=definition.default_integration,
            default_model=definition.default_model,
            default_options=definition.default_options,
            project_root=str(self.project_root),
            run_id=state.run_id,
            workflow_id=definition.id,
        )

        from . import STEP_REGISTRY

        state.status = RunStatus.RUNNING
        state.save()

        skip_hook_events: set[str] = set()
        if state.pending_hook:
            pending_hook = dict(state.pending_hook)
            if not self._resolve_pending_hook(context, state):
                return state
            pending_event = str(pending_hook.get("event") or "")
            if pending_event:
                skip_hook_events.add(pending_event)

        # Resume from the current step — re-execute it so gates
        # can prompt interactively again.
        selected_steps = self._select_steps(definition.steps, state.inputs)
        remaining_steps = selected_steps[state.current_step_index :]
        step_offset = state.current_step_index

        try:
            self._execute_steps(
                remaining_steps, context, state, STEP_REGISTRY,
                step_offset=step_offset,
                skip_hook_events=skip_hook_events,
            )
        except KeyboardInterrupt:
            state.status = RunStatus.PAUSED
            state.append_log({"event": "workflow_interrupted"})
            state.save()
            return state
        except Exception as exc:
            state.status = RunStatus.FAILED
            state.append_log({"event": "resume_failed", "error": str(exc)})
            state.save()
            raise

        if state.status == RunStatus.RUNNING:
            state.status = RunStatus.COMPLETED
        state.append_log({"event": "workflow_finished", "status": state.status.value})
        state.save()
        return state

    def dispatch_hooks(
        self,
        *,
        workflow_id: str,
        stage_id: str,
        phase: str,
        run_id: str | None = None,
        inputs: dict[str, Any] | None = None,
        step_results: dict[str, dict[str, Any]] | None = None,
        default_integration: str | None = "codex",
        default_model: str | None = None,
    ) -> RunState:
        """Dispatch workflow hooks without executing the workflow stage itself.

        This is the public hook boundary used by stage-skill executions that do
        not run through ``specify workflow run``. It intentionally reuses the
        same hook dispatcher as the YAML workflow engine so ``workflow-shell``
        and ``workflow-agent-chain`` have one execution contract.
        """
        normalized_phase = phase.strip().lower()
        if normalized_phase not in {"before", "after"}:
            msg = f"Invalid hook phase {phase!r}: expected 'before' or 'after'."
            raise ValueError(msg)
        if not workflow_id.strip():
            raise ValueError("workflow_id is required")
        if not stage_id.strip():
            raise ValueError("stage_id is required")

        state = RunState(
            run_id=run_id,
            workflow_id=workflow_id.strip(),
            project_root=self.project_root,
        )
        state.inputs = inputs or {}
        state.step_results = step_results or {}
        state.current_step_id = stage_id.strip()
        state.current_step_index = 0
        state.status = RunStatus.RUNNING
        state.save()

        context = StepContext(
            inputs=state.inputs,
            steps=state.step_results,
            default_integration=default_integration,
            default_model=default_model,
            default_options={},
            project_root=str(self.project_root),
            run_id=state.run_id,
            workflow_id=state.workflow_id,
        )

        try:
            can_continue = self._dispatch_step_hooks(
                stage_id.strip(),
                normalized_phase,
                context,
                state,
                pause_step_index=0,
            )
        except Exception as exc:
            state.status = RunStatus.FAILED
            state.append_log({"event": "workflow_hook_dispatch_failed", "error": str(exc)})
            state.save()
            raise

        if can_continue and state.status == RunStatus.RUNNING:
            state.status = RunStatus.COMPLETED
        state.append_log({"event": "workflow_hook_dispatch_finished", "status": state.status.value})
        state.save()
        return state

    def _execute_steps(
        self,
        steps: list[dict[str, Any]],
        context: StepContext,
        state: RunState,
        registry: dict[str, Any],
        *,
        step_offset: int = 0,
        skip_hook_events: set[str] | None = None,
    ) -> None:
        """Execute a list of steps sequentially."""
        skip_hook_events = skip_hook_events or set()
        for i, step_config in enumerate(steps):
            step_id = step_config.get("id", f"step-{i}")
            step_type = step_config.get("type", "command")
            is_top_level_step = step_offset >= 0

            state.current_step_id = step_id
            if step_offset >= 0:
                state.current_step_index = step_offset + i
            state.save()

            state.append_log(
                {"event": "step_started", "step_id": step_id, "type": step_type}
            )

            if is_top_level_step:
                before_event = self._workflow_hook_event_name(
                    context.workflow_id or state.workflow_id,
                    step_id,
                    "before",
                )
                if before_event in skip_hook_events:
                    skip_hook_events.remove(before_event)
                elif not self._dispatch_step_hooks(
                    step_id,
                    "before",
                    context,
                    state,
                    pause_step_index=state.current_step_index,
                ):
                    return

            if not self._confirm_step_if_required(step_config, state):
                return

            # Log progress — use the engine's on_step_start callback if set,
            # otherwise stay silent (library-safe default).
            label = step_config.get("command", "") or step_type
            if self.on_step_start is not None:
                self.on_step_start(step_id, label)

            step_impl = registry.get(step_type)
            if not step_impl:
                state.status = RunStatus.FAILED
                state.append_log(
                    {
                        "event": "step_failed",
                        "step_id": step_id,
                        "error": f"Unknown step type: {step_type!r}",
                    }
                )
                state.save()
                return

            result: StepResult = step_impl.execute(step_config, context)

            # Record step results — prefer resolved values from step output
            step_data = {
                "integration": result.output.get("integration")
                or step_config.get("integration")
                or context.default_integration,
                "model": result.output.get("model")
                or step_config.get("model")
                or context.default_model,
                "options": result.output.get("options")
                or step_config.get("options", {}),
                "input": result.output.get("input")
                or step_config.get("input", {}),
                "output": result.output,
                "status": result.status.value,
            }
            context.steps[step_id] = step_data
            state.step_results[step_id] = step_data

            state.append_log(
                {
                    "event": "step_completed",
                    "step_id": step_id,
                    "status": result.status.value,
                }
            )

            # Handle gate pauses
            if result.status == StepStatus.PAUSED:
                state.status = RunStatus.PAUSED
                state.save()
                return

            # Handle failures
            if result.status == StepStatus.FAILED:
                # Gate abort (output.aborted) maps to ABORTED status
                if result.output.get("aborted"):
                    state.status = RunStatus.ABORTED
                    state.append_log(
                        {
                            "event": "workflow_aborted",
                            "step_id": step_id,
                        }
                    )
                else:
                    state.status = RunStatus.FAILED
                    state.append_log(
                        {
                            "event": "step_failed",
                            "step_id": step_id,
                            "error": result.error,
                        }
                    )
                state.save()
                return

            # Execute nested steps (from control flow)
            # NOTE: Nested steps run with step_offset=-1 so they don't
            # update current_step_index.  If a nested step pauses,
            # resume will re-run the parent step and its nested body.
            # A step-path stack for exact nested resume is a future
            # enhancement.
            if result.next_steps:
                self._execute_steps(
                    result.next_steps, context, state, registry,
                    step_offset=-1,
                )
                if state.status in (
                    RunStatus.PAUSED,
                    RunStatus.FAILED,
                    RunStatus.ABORTED,
                ):
                    return

                # Loop iteration: while/do-while re-evaluate after body
                if step_type in ("while", "do-while"):
                    from .expressions import evaluate_condition

                    max_iters = step_config.get("max_iterations")
                    if not isinstance(max_iters, int) or max_iters < 1:
                        max_iters = 10
                    condition = step_config.get("condition", False)
                    for _loop_iter in range(max_iters - 1):
                        if not evaluate_condition(condition, context):
                            break
                        # Namespace nested step IDs per iteration
                        iter_steps = []
                        for ns in result.next_steps:
                            ns_copy = dict(ns)
                            if "id" in ns_copy:
                                ns_copy["id"] = f"{step_id}:{ns_copy['id']}:{_loop_iter + 1}"
                            iter_steps.append(ns_copy)
                        self._execute_steps(
                            iter_steps, context, state, registry,
                            step_offset=-1,
                        )
                        if state.status in (
                            RunStatus.PAUSED,
                            RunStatus.FAILED,
                            RunStatus.ABORTED,
                        ):
                            return

            # Fan-out: execute nested step template per item with unique IDs
            if step_type == "fan-out":
                items = result.output.get("items", [])
                template = result.output.get("step_template", {})
                if template and items:
                    fan_out_results = []
                    for item_idx, item_val in enumerate(result.output["items"]):
                        context.item = item_val
                        # Per-item ID: parentId:templateId:index
                        item_step = dict(template)
                        base_id = item_step.get("id", "item")
                        item_step["id"] = f"{step_id}:{base_id}:{item_idx}"
                        self._execute_steps(
                            [item_step], context, state, registry,
                            step_offset=-1,
                        )
                        # Collect per-item result for fan-in
                        item_result = context.steps.get(item_step["id"], {})
                        fan_out_results.append(item_result.get("output", {}))
                        if state.status in (
                            RunStatus.PAUSED,
                            RunStatus.FAILED,
                            RunStatus.ABORTED,
                        ):
                            break
                    context.item = None
                    # Preserve original output and add collected results
                    fan_out_output = dict(result.output)
                    fan_out_output["results"] = fan_out_results
                    context.steps[step_id]["output"] = fan_out_output
                    state.step_results[step_id]["output"] = fan_out_output
                    if state.status in (
                        RunStatus.PAUSED,
                        RunStatus.FAILED,
                        RunStatus.ABORTED,
                    ):
                        return
                else:
                    # Empty items or no template — normalize output
                    result.output["results"] = []
                    context.steps[step_id]["output"] = result.output
                    state.step_results[step_id]["output"] = result.output

            if is_top_level_step:
                after_event = self._workflow_hook_event_name(
                    context.workflow_id or state.workflow_id,
                    step_id,
                    "after",
                )
                if after_event in skip_hook_events:
                    skip_hook_events.remove(after_event)
                elif not self._dispatch_step_hooks(
                    step_id,
                    "after",
                    context,
                    state,
                    pause_step_index=state.current_step_index + 1,
                ):
                    return

    def _dispatch_step_hooks(
        self,
        step_id: str,
        phase: str,
        context: StepContext,
        state: RunState,
        *,
        pause_step_index: int,
    ) -> bool:
        """Run synchronous workflow hooks for a top-level step phase."""
        if not self._workflow_hooks_registry_path().is_file():
            return True

        workflow_id = context.workflow_id or state.workflow_id
        event_name = self._workflow_hook_event_name(workflow_id, step_id, phase)
        hook_facts: list[dict[str, Any]] = []

        shell_result = self._invoke_workflow_hook_runner(
            event_name=event_name,
            workflow_id=workflow_id,
            stage_id=step_id,
            phase=phase,
            state=state,
        )
        shell_facts = self._extract_hook_facts(shell_result)
        if shell_facts is not None:
            hook_facts.append(shell_facts)
            if not self._hook_facts_auto_continue(shell_facts):
                facts = self._merge_hook_facts(event_name, hook_facts)
                return self._record_hook_dispatch(
                    event_name,
                    workflow_id,
                    step_id,
                    phase,
                    state,
                    facts,
                    pause_step_index=pause_step_index,
                )

        agent_chain_result = self._invoke_agent_chain_hooks(
            event_name=event_name,
            workflow_id=workflow_id,
            stage_id=step_id,
            phase=phase,
            context=context,
            state=state,
        )
        agent_chain_facts = self._extract_hook_facts(agent_chain_result)
        if agent_chain_facts is not None:
            hook_facts.append(agent_chain_facts)

        if not hook_facts:
            return True

        facts = self._merge_hook_facts(event_name, hook_facts)
        return self._record_hook_dispatch(
            event_name,
            workflow_id,
            step_id,
            phase,
            state,
            facts,
            pause_step_index=pause_step_index,
        )

    def _extract_hook_facts(self, hook_result: dict[str, Any]) -> dict[str, Any] | None:
        facts = hook_result.get("facts", {})
        if not isinstance(facts, dict):
            return None
        hook_count = self._as_int(facts.get("hook_count"))
        if hook_count <= 0:
            return None
        return facts

    def _hook_facts_auto_continue(self, facts: dict[str, Any]) -> bool:
        aggregate_status = str(facts.get("aggregate_status") or "failed")
        return self._as_bool(
            facts.get("auto_continue"),
            default=aggregate_status in {"passed", "warning", "skipped"},
        )

    def _record_hook_dispatch(
        self,
        event_name: str,
        workflow_id: str,
        step_id: str,
        phase: str,
        state: RunState,
        facts: dict[str, Any],
        *,
        pause_step_index: int,
    ) -> bool:
        hook_count = self._as_int(facts.get("hook_count"))
        aggregate_status = str(facts.get("aggregate_status") or "failed")
        action = str(facts.get("action") or self._default_hook_action(aggregate_status))
        auto_continue = self._as_bool(
            facts.get("auto_continue"),
            default=aggregate_status in {"passed", "warning", "skipped"},
        )
        summary = str(facts.get("summary") or "")
        artifacts = self._as_string_list(facts.get("artifact_paths"))
        results = facts.get("results")
        if not isinstance(results, list):
            results = []
        if auto_continue and phase == "after" and step_id == "commit":
            dirty_files = self._git_tracked_dirty_files()
            if dirty_files:
                results.append(
                    {
                        "schema_version": "1.0",
                        "id": f"{event_name}.post-commit-mutation-guard",
                        "event": event_name,
                        "type": "workflow-hook-mutation-guard",
                        "status": "requires_rework",
                        "action": "rework",
                        "auto_continue": False,
                        "summary": "workflow hook left tracked files dirty after commit",
                        "artifact_paths": [],
                        "dirty_files": dirty_files,
                    }
                )
                aggregate_status = "requires_rework"
                action = "rework"
                auto_continue = False
                summary = (
                    f"{summary}; workflow hook left tracked files dirty after commit"
                    if summary
                    else "workflow hook left tracked files dirty after commit"
                )

        event_record = {
            "schema_version": "1.0",
            "event": event_name,
            "workflow_id": workflow_id,
            "stage_id": step_id,
            "phase": phase,
            "status": aggregate_status,
            "action": action,
            "auto_continue": auto_continue,
            "summary": summary,
            "artifact_paths": artifacts,
            "results": results,
        }
        state.hook_results[event_name] = event_record
        state.append_log(
            {
                "event": "workflow_hook_completed",
                "hook_event": event_name,
                "step_id": step_id,
                "phase": phase,
                "status": aggregate_status,
                "auto_continue": auto_continue,
                "hook_count": hook_count,
            }
        )
        if auto_continue:
            if state.pending_hook and state.pending_hook.get("event") == event_name:
                state.pending_hook = None
            state.save()
            return True

        state.status = RunStatus.PAUSED
        state.current_step_index = pause_step_index
        state.pending_hook = {
            **event_record,
            "resume_step_index": pause_step_index,
            "retry_on_resume": True,
        }
        state.append_log(
            {
                "event": "workflow_hook_paused",
                "hook_event": event_name,
                "step_id": step_id,
                "phase": phase,
                "status": aggregate_status,
                "action": action,
                "summary": summary,
            }
        )
        state.save()
        return False

    def _merge_hook_facts(
        self,
        event_name: str,
        facts_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        statuses: list[str] = []
        results: list[Any] = []
        artifacts: list[str] = []
        summaries: list[str] = []
        hook_count = 0
        auto_continue = True

        for facts in facts_items:
            hook_count += self._as_int(facts.get("hook_count"))
            status = str(facts.get("aggregate_status") or facts.get("status") or "failed")
            statuses.append(status)
            auto_continue = auto_continue and self._as_bool(
                facts.get("auto_continue"),
                default=status in {"passed", "warning", "skipped"},
            )
            summary = str(facts.get("summary") or "").strip()
            if summary:
                summaries.append(summary)
            artifacts.extend(self._as_string_list(facts.get("artifact_paths")))
            facts_results = facts.get("results")
            if isinstance(facts_results, list):
                results.extend(facts_results)

        aggregate_status = self._aggregate_hook_status(statuses)
        if aggregate_status in {"blocked", "failed", "requires_rework"}:
            auto_continue = False
        action = self._hook_action_for_result(aggregate_status, auto_continue)

        return {
            "event": event_name,
            "hook_count": hook_count,
            "aggregate_status": aggregate_status,
            "status": aggregate_status,
            "action": action,
            "auto_continue": auto_continue,
            "summary": "; ".join(summaries) if summaries else "workflow hooks completed",
            "artifact_paths": list(dict.fromkeys(artifacts)),
            "results": results,
        }

    def _resolve_pending_hook(self, context: StepContext, state: RunState) -> bool:
        pending = state.pending_hook or {}
        stage_id = str(pending.get("stage_id") or pending.get("step_id") or "")
        phase = str(pending.get("phase") or "")
        if not stage_id or phase not in {"before", "after"}:
            state.pending_hook = None
            state.save()
            return True

        pause_step_index = self._as_int(
            pending.get("resume_step_index"),
            default=state.current_step_index,
        )
        if self._dispatch_step_hooks(
            stage_id,
            phase,
            context,
            state,
            pause_step_index=pause_step_index,
        ):
            state.pending_hook = None
            state.append_log(
                {
                    "event": "workflow_hook_resolved",
                    "hook_event": pending.get("event"),
                    "step_id": stage_id,
                    "phase": phase,
                }
            )
            state.save()
            return True
        return False

    @staticmethod
    def _workflow_hook_event_name(
        workflow_id: str,
        step_id: str,
        phase: str,
    ) -> str:
        return f"workflow.{workflow_id}.{step_id}.{phase}"

    def _workflow_hooks_registry_path(self) -> Path:
        return self.project_root / ".specify" / "workflow-hooks.yml"

    def _workflow_hook_runner_script(self) -> Path | None:
        candidates = [
            self.project_root / "scripts" / "powershell" / "invoke-workflow-hooks.ps1",
            Path(__file__).resolve().parents[3]
            / "scripts"
            / "powershell"
            / "invoke-workflow-hooks.ps1",
            Path(__file__).resolve().parents[1]
            / "core_pack"
            / "scripts"
            / "powershell"
            / "invoke-workflow-hooks.ps1",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def _invoke_workflow_hook_runner(
        self,
        *,
        event_name: str,
        workflow_id: str,
        stage_id: str,
        phase: str,
        state: RunState,
    ) -> dict[str, Any]:
        script = self._workflow_hook_runner_script()
        if script is None:
            return self._runner_failure_result(
                event_name,
                "invoke-workflow-hooks.ps1 not found",
            )

        context_payload = {
            "inputs": state.inputs,
            "steps": state.step_results,
            "current_step_id": state.current_step_id,
            "current_step_index": state.current_step_index,
            "project_root": str(self.project_root),
            "run_id": state.run_id,
        }
        event_slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", event_name).strip("-") or "hook"
        context_dir = (
            self.project_root
            / ".specify"
            / "workflows"
            / "runs"
            / state.run_id
            / "hooks"
            / event_slug
        )
        context_dir.mkdir(parents=True, exist_ok=True)
        context_path = context_dir / "context.json"
        with open(context_path, "w", encoding="utf-8") as f:
            json.dump(context_payload, f, ensure_ascii=False, indent=2)

        command = [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-RepoRoot",
            str(self.project_root),
            "-WorkflowId",
            workflow_id,
            "-StageId",
            stage_id,
            "-Phase",
            phase,
            "-RunId",
            state.run_id,
            "-ContextPath",
            str(context_path),
            "-Json",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=3600,
            )
        except subprocess.TimeoutExpired:
            return self._runner_failure_result(
                event_name,
                "workflow hook runner timed out",
            )

        payload = self._read_json_object_from_text(completed.stdout)
        if payload is None:
            payload = self._runner_failure_result(
                event_name,
                "workflow hook runner did not return JSON",
            )
            stderr = completed.stderr.strip()
            if stderr:
                payload["hints"] = [stderr]
        if completed.returncode != 0 and payload.get("status") == "ok":
            payload["status"] = "blocked"
            facts = payload.setdefault("facts", {})
            if isinstance(facts, dict):
                facts["aggregate_status"] = "failed"
                facts["action"] = "fail"
                facts["auto_continue"] = False
                facts["summary"] = facts.get("summary") or "workflow hook runner failed"
        return payload

    def _invoke_agent_chain_hooks(
        self,
        *,
        event_name: str,
        workflow_id: str,
        stage_id: str,
        phase: str,
        context: StepContext,
        state: RunState,
    ) -> dict[str, Any]:
        try:
            registry = self._read_workflow_hook_registry()
        except Exception as exc:
            return self._runner_failure_result(
                event_name,
                f"workflow hook registry could not be parsed: {exc}",
            )

        overrides = self._read_workflow_hook_overrides()
        hook_results: list[dict[str, Any]] = []
        disabled_hooks: list[dict[str, str]] = []

        for hook in registry:
            events = self._as_string_list(hook.get("events"))
            if event_name not in events:
                continue
            disabled_reason = self._workflow_hook_disabled_reason(
                hook,
                event_name,
                overrides,
            )
            if disabled_reason:
                disabled_hooks.append(
                    {
                        "id": str(hook.get("id") or ""),
                        "pack_id": str(hook.get("pack_id") or ""),
                        "reason": disabled_reason,
                    }
                )
                continue
            if str(hook.get("type") or "").strip() != "workflow-agent-chain":
                continue

            hook_result = self._execute_agent_chain_hook(
                hook,
                event_name=event_name,
                workflow_id=workflow_id,
                stage_id=stage_id,
                phase=phase,
                context=context,
                state=state,
            )
            hook_results.append(hook_result)
            if not self._as_bool(
                hook_result.get("auto_continue"),
                default=hook_result.get("status") in {"passed", "warning", "skipped"},
            ):
                break

        aggregate_status = self._aggregate_hook_status(
            [str(item.get("status") or "") for item in hook_results]
        )
        auto_continue = aggregate_status in {"passed", "warning", "skipped"} and all(
            self._as_bool(
                item.get("auto_continue"),
                default=item.get("status") in {"passed", "warning", "skipped"},
            )
            for item in hook_results
        )
        action = self._hook_action_for_result(aggregate_status, auto_continue)
        summary_items = [
            str(item.get("summary") or "").strip()
            for item in hook_results
            if str(item.get("summary") or "").strip()
        ]
        artifact_paths: list[str] = []
        for item in hook_results:
            artifact_paths.extend(self._as_string_list(item.get("artifact_paths")))
            result_path = str(item.get("result_path") or "")
            if result_path:
                artifact_paths.append(result_path)

        return {
            "tool": "workflow-agent-chain",
            "status": "ok" if auto_continue else "blocked",
            "facts": {
                "event": event_name,
                "workflow_id": workflow_id,
                "stage_id": stage_id,
                "phase": phase,
                "run_id": state.run_id,
                "hook_count": len(hook_results),
                "disabled_hook_count": len(disabled_hooks),
                "disabled_hooks": disabled_hooks,
                "aggregate_status": aggregate_status,
                "status": aggregate_status,
                "action": action,
                "auto_continue": auto_continue,
                "summary": "; ".join(summary_items) if summary_items else "no matching workflow-agent-chain hooks",
                "artifact_paths": list(dict.fromkeys(artifact_paths)),
                "results": hook_results,
            },
            "blockers": [] if auto_continue else summary_items,
            "unknowns": [],
            "hints": [],
        }

    def _execute_agent_chain_hook(
        self,
        hook: dict[str, Any],
        *,
        event_name: str,
        workflow_id: str,
        stage_id: str,
        phase: str,
        context: StepContext,
        state: RunState,
    ) -> dict[str, Any]:
        hook_id = str(hook.get("id") or "agent-chain").strip() or "agent-chain"
        pack_id = str(hook.get("pack_id") or "").strip()
        event_slug = self._workflow_hook_slug(event_name)
        hook_slug = self._workflow_hook_slug(hook_id)
        chain_dir = (
            self.project_root
            / ".specify"
            / "workflows"
            / "runs"
            / state.run_id
            / "hooks"
            / event_slug
            / hook_slug
        )
        chain_dir.mkdir(parents=True, exist_ok=True)
        chain_result_path = chain_dir / "chain-result.json"

        try:
            chain_config = self._load_agent_chain_config(hook)
        except Exception as exc:
            result = self._agent_chain_hook_failure(
                hook,
                event_name,
                str(exc),
                result_path=chain_result_path,
            )
            self._write_json(chain_result_path, result)
            return result

        steps = chain_config["steps"]
        previous_results: list[dict[str, Any]] = []
        artifact_paths: list[str] = []
        short_circuited = False

        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                step = {"id": f"step-{index + 1}", "invalid": True}
            step_id = str(step.get("id") or f"step-{index + 1}").strip() or f"step-{index + 1}"
            step_slug = self._workflow_hook_slug(step_id)
            input_path = chain_dir / f"{step_slug}.input.json"
            result_path = chain_dir / f"{step_slug}.result.json"

            if not self._agent_chain_step_enabled(step, previous_results):
                integration_key = str(
                    step.get("integration")
                    or chain_config.get("integration")
                    or hook.get("integration")
                    or context.default_integration
                    or "codex"
                )
                skipped = self._normalize_agent_chain_step_result(
                    raw_result={
                        "status": "skipped",
                        "action": "continue",
                        "auto_continue": True,
                        "summary": "chain step skipped by run_if_previous_status",
                        "artifact_paths": [],
                    },
                    hook=hook,
                    step=step,
                    event_name=event_name,
                    result_path=result_path,
                    exit_code=0,
                    timed_out=False,
                    command="",
                    integration_key=integration_key,
                )
                previous_results.append(skipped)
                self._write_json(result_path, skipped)
                continue

            resolved_skill_path = self._resolve_agent_chain_skill_path(
                str(step.get("skill") or ""),
                hook,
                step,
            )
            input_payload = {
                "schema_version": "1.0",
                "event": event_name,
                "workflow_id": workflow_id,
                "stage_id": stage_id,
                "phase": phase,
                "run_id": state.run_id,
                "project_root": str(self.project_root),
                "hook": {
                    "id": hook_id,
                    "pack_id": pack_id,
                    "type": "workflow-agent-chain",
                    "failure_policy": hook.get("failure_policy") or "block",
                },
                "chain_step": {
                    "index": index,
                    "id": step_id,
                    "skill": step.get("skill"),
                    "skill_path": self._display_project_path(resolved_skill_path)
                    if resolved_skill_path
                    else "",
                },
                "inputs": state.inputs,
                "steps": state.step_results,
                "previous_result": previous_results[-1] if previous_results else None,
                "previous_results": previous_results,
                "artifact_paths": artifact_paths,
                "result_path": str(result_path),
            }
            self._write_json(input_path, input_payload)
            if result_path.exists():
                result_path.unlink()

            command_result = self._execute_agent_chain_skill_step(
                hook=hook,
                chain_config=chain_config,
                step=step,
                input_path=input_path,
                result_path=result_path,
                context=context,
            )
            raw_result = command_result.get("raw_result")
            normalized = self._normalize_agent_chain_step_result(
                raw_result=raw_result if isinstance(raw_result, dict) else None,
                hook=hook,
                step=step,
                event_name=event_name,
                result_path=result_path,
                exit_code=self._as_int(command_result.get("exit_code")),
                timed_out=bool(command_result.get("timed_out")),
                command=str(command_result.get("command") or ""),
                integration_key=str(command_result.get("integration") or ""),
            )
            self._write_json(result_path, normalized)
            previous_results.append(normalized)
            artifact_paths.extend(self._as_string_list(normalized.get("artifact_paths")))
            artifact_paths.append(str(input_path))
            artifact_paths.append(str(result_path))
            if not normalized["auto_continue"]:
                short_circuited = True
                break

        dirty_files = []
        if phase == "after" and stage_id == "commit":
            dirty_files = self._git_tracked_dirty_files()
            if dirty_files:
                previous_results.append(
                    {
                        "schema_version": "1.0",
                        "id": f"{hook_id}.post-commit-mutation-guard",
                        "hook_id": hook_id,
                        "pack_id": pack_id,
                        "event": event_name,
                        "type": "workflow-agent-chain",
                        "chain_step_id": "post-commit-mutation-guard",
                        "skill": "",
                        "status": "requires_rework",
                        "action": "rework",
                        "auto_continue": False,
                        "summary": "workflow-agent-chain left tracked files dirty after commit",
                        "artifact_paths": [],
                        "dirty_files": dirty_files,
                        "result_path": "",
                        "exit_code": 0,
                        "timed_out": False,
                        "command": "",
                    }
                )
                short_circuited = True

        aggregate_status = self._aggregate_hook_status(
            [str(item.get("status") or "") for item in previous_results]
        )
        auto_continue = aggregate_status in {"passed", "warning", "skipped"} and all(
            self._as_bool(
                item.get("auto_continue"),
                default=item.get("status") in {"passed", "warning", "skipped"},
            )
            for item in previous_results
        )
        if dirty_files:
            auto_continue = False
        action = self._hook_action_for_result(aggregate_status, auto_continue)
        summary_items = [
            str(item.get("summary") or "").strip()
            for item in previous_results
            if str(item.get("summary") or "").strip()
        ]
        result = {
            "schema_version": "1.0",
            "id": hook_id,
            "pack_id": pack_id,
            "event": event_name,
            "type": "workflow-agent-chain",
            "status": aggregate_status,
            "action": action,
            "auto_continue": auto_continue,
            "summary": "; ".join(summary_items) if summary_items else "workflow-agent-chain completed",
            "artifact_paths": list(dict.fromkeys(artifact_paths + [str(chain_result_path)])),
            "result_path": str(chain_result_path),
            "steps": previous_results,
            "short_circuited": short_circuited,
        }
        self._write_json(chain_result_path, result)
        return result

    def _execute_agent_chain_skill_step(
        self,
        *,
        hook: dict[str, Any],
        chain_config: dict[str, Any],
        step: dict[str, Any],
        input_path: Path,
        result_path: Path,
        context: StepContext,
    ) -> dict[str, Any]:
        from specify_cli.integrations import get_integration

        skill = str(step.get("skill") or "").strip()
        integration_key = str(
            step.get("integration")
            or chain_config.get("integration")
            or hook.get("integration")
            or context.default_integration
            or "codex"
        ).strip()
        model = str(step.get("model") or chain_config.get("model") or context.default_model or "").strip() or None
        timeout = self._as_int(
            step.get("timeout_seconds")
            or chain_config.get("timeout_seconds")
            or hook.get("timeout_seconds"),
            default=600,
        )
        if timeout < 1:
            timeout = 600
        if not skill:
            return {
                "raw_result": {
                    "status": "failed",
                    "action": "fail",
                    "auto_continue": False,
                    "summary": "workflow-agent-chain step missing skill",
                    "artifact_paths": [],
                },
                "exit_code": 1,
                "timed_out": False,
                "command": "",
                "integration": integration_key,
            }

        integration = get_integration(integration_key)
        if integration is None:
            return {
                "raw_result": {
                    "status": "blocked",
                    "action": "pause",
                    "auto_continue": False,
                    "summary": f"unknown integration for workflow-agent-chain: {integration_key}",
                    "artifact_paths": [],
                },
                "exit_code": 1,
                "timed_out": False,
                "command": "",
                "integration": integration_key,
            }

        prompt = self._build_agent_chain_skill_prompt(
            skill=skill,
            skill_path=self._resolve_agent_chain_skill_path(skill, hook, step),
            input_path=input_path,
            result_path=result_path,
        )
        exec_args = integration.build_exec_args(prompt, model=model, output_json=True)
        if exec_args is None:
            return {
                "raw_result": {
                    "status": "blocked",
                    "action": "pause",
                    "auto_continue": False,
                    "summary": f"integration {integration_key} does not support workflow-agent-chain dispatch",
                    "artifact_paths": [],
                },
                "exit_code": 1,
                "timed_out": False,
                "command": "",
                "integration": integration_key,
            }
        resolved_args = integration.resolve_exec_args(exec_args)
        if resolved_args is None:
            return {
                "raw_result": {
                    "status": "blocked",
                    "action": "pause",
                    "auto_continue": False,
                    "summary": f"executable not found for integration {integration_key}: {exec_args[0]}",
                    "artifact_paths": [],
                },
                "exit_code": 1,
                "timed_out": False,
                "command": " ".join(exec_args),
                "integration": integration_key,
            }

        try:
            completed = subprocess.run(
                resolved_args,
                cwd=self.project_root,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=timeout,
            )
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            return {
                "raw_result": {
                    "status": "failed",
                    "action": "fail",
                    "auto_continue": False,
                    "summary": "workflow-agent-chain step timed out",
                    "artifact_paths": [],
                },
                "exit_code": 124,
                "timed_out": True,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "command": " ".join(resolved_args),
                "integration": integration_key,
            }

        raw_result = self._read_json_object_from_file(result_path)
        if raw_result is None:
            raw_result = self._read_json_object_from_text(completed.stdout)
        if raw_result is None:
            raw_result = {
                "status": "failed",
                "action": "fail",
                "auto_continue": False,
                "summary": "workflow-agent-chain step did not return hook result JSON",
                "artifact_paths": [],
            }
            stderr = completed.stderr.strip()
            if stderr:
                raw_result["stderr"] = stderr

        return {
            "raw_result": raw_result,
            "exit_code": completed.returncode,
            "timed_out": timed_out,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "command": " ".join(resolved_args),
            "integration": integration_key,
        }

    def _normalize_agent_chain_step_result(
        self,
        *,
        raw_result: dict[str, Any] | None,
        hook: dict[str, Any],
        step: dict[str, Any],
        event_name: str,
        result_path: Path,
        exit_code: int,
        timed_out: bool,
        command: str,
        integration_key: str,
    ) -> dict[str, Any]:
        raw = raw_result if isinstance(raw_result, dict) else {}
        status = self._normalize_hook_status(str(raw.get("status") or "failed"))
        if timed_out:
            status = "failed"
        if exit_code != 0 and status in {"passed", "warning", "skipped"}:
            status = "failed"

        failure_policy = str(hook.get("failure_policy") or "block").strip().lower()
        summary = str(raw.get("summary") or "").strip()
        if not summary:
            if timed_out:
                summary = "workflow-agent-chain step timed out"
            elif exit_code == 0:
                summary = "workflow-agent-chain step passed"
            else:
                summary = f"workflow-agent-chain step failed with exit code {exit_code}"
        if failure_policy in {"warn", "warning", "advisory"} and status in {"failed", "blocked"}:
            status = "warning"
            summary = f"advisory workflow-agent-chain warning: {summary}"

        action = str(raw.get("action") or "").strip() or self._default_hook_action(status)
        auto_continue = self._as_bool(
            raw.get("auto_continue"),
            default=status in {"passed", "warning", "skipped"} and action == "continue",
        )
        if status in {"blocked", "failed", "requires_rework"}:
            auto_continue = False

        hook_id = str(hook.get("id") or "agent-chain").strip() or "agent-chain"
        step_id = str(step.get("id") or "step").strip() or "step"
        artifacts = self._as_string_list(raw.get("artifact_paths"))
        return {
            "schema_version": "1.0",
            "id": f"{hook_id}.{step_id}",
            "hook_id": hook_id,
            "pack_id": str(hook.get("pack_id") or ""),
            "event": event_name,
            "type": "workflow-agent-chain",
            "chain_step_id": step_id,
            "skill": str(step.get("skill") or ""),
            "integration": integration_key,
            "status": status,
            "action": action,
            "auto_continue": auto_continue,
            "summary": summary,
            "artifact_paths": artifacts,
            "result_path": str(result_path),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "command": command,
        }

    def _load_agent_chain_config(self, hook: dict[str, Any]) -> dict[str, Any]:
        manifest_data: dict[str, Any] = {}
        manifest_value = str(hook.get("chain_manifest") or "").strip()
        if manifest_value:
            manifest_path = self._resolve_project_relative_hook_path(manifest_value)
            if not manifest_path.is_file():
                raise FileNotFoundError(f"workflow-agent-chain manifest not found: {manifest_value}")
            if manifest_path.suffix.lower() == ".json":
                with open(manifest_path, encoding="utf-8") as f:
                    loaded = json.load(f)
            else:
                with open(manifest_path, encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
            if not isinstance(loaded, dict):
                raise ValueError(f"workflow-agent-chain manifest must be a mapping: {manifest_value}")
            manifest_data = loaded

        steps = hook.get("steps")
        if not isinstance(steps, list):
            steps = manifest_data.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("workflow-agent-chain must declare non-empty steps or chain_manifest")

        return {
            **manifest_data,
            "integration": hook.get("integration") or manifest_data.get("integration"),
            "model": hook.get("model") or manifest_data.get("model"),
            "timeout_seconds": hook.get("timeout_seconds") or manifest_data.get("timeout_seconds"),
            "steps": steps,
        }

    def _resolve_project_relative_hook_path(self, value: str) -> Path:
        candidate = Path(value)
        if candidate.is_absolute():
            raise ValueError(f"workflow hook path must be project-relative: {value}")
        resolved = (self.project_root / candidate).resolve()
        try:
            resolved.relative_to(self.project_root.resolve())
        except ValueError as exc:
            raise ValueError(f"workflow hook path escapes project root: {value}") from exc
        return resolved

    def _agent_chain_step_enabled(
        self,
        step: dict[str, Any],
        previous_results: list[dict[str, Any]],
    ) -> bool:
        allowed = step.get("run_if_previous_status")
        if allowed is None:
            return True
        allowed_statuses = set(self._as_string_list(allowed))
        previous_status = str(previous_results[-1].get("status") or "") if previous_results else ""
        return previous_status in allowed_statuses

    def _build_agent_chain_skill_prompt(
        self,
        *,
        skill: str,
        skill_path: Path | None,
        input_path: Path,
        result_path: Path,
    ) -> str:
        input_label = self._display_project_path(input_path)
        result_label = self._display_project_path(result_path)
        skill_instruction = f"Run the installed Codex skill `{skill}`"
        if skill_path is not None:
            skill_instruction = (
                f"Run the Codex skill `{skill}` by first reading "
                f"`{self._display_project_path(skill_path)}`"
            )
        return (
            f"{skill_instruction} as a Spec Kit workflow hook chain step. "
            f"Read the hook input JSON at `{input_label}`. "
            "Return a Spec Kit workflow hook result JSON object with schema_version, "
            "status, action, auto_continue, summary, and artifact_paths. "
            f"Write that JSON object to `{result_label}`. "
            "Use the previous_result and previous_results fields from the input to decide "
            "whether this step may continue. Do not report success unless the result file "
            "contains the final hook JSON."
        )

    def _resolve_agent_chain_skill_path(
        self,
        skill: str,
        hook: dict[str, Any],
        _step: dict[str, Any],
    ) -> Path | None:
        candidates: list[Path] = []

        clean_skill = skill.strip().strip("/\\")
        pack_id = str(hook.get("pack_id") or "").strip()
        if clean_skill:
            if pack_id:
                candidates.append(
                    self.project_root
                    / ".agents"
                    / "spec-kit"
                    / "skills"
                    / f"{pack_id}__{clean_skill}"
                    / "SKILL.md"
                )
            candidates.extend(
                [
                    self.project_root / ".agents" / "spec-kit" / "skills" / clean_skill / "SKILL.md",
                    self.project_root / ".agents" / "skills" / clean_skill / "SKILL.md",
                ]
            )

        for candidate in candidates:
            resolved = candidate.resolve()
            try:
                resolved.relative_to(self.project_root.resolve())
            except ValueError:
                continue
            if resolved.is_file():
                return resolved
        return None

    def _agent_chain_hook_failure(
        self,
        hook: dict[str, Any],
        event_name: str,
        summary: str,
        *,
        result_path: Path,
    ) -> dict[str, Any]:
        hook_id = str(hook.get("id") or "agent-chain").strip() or "agent-chain"
        return {
            "schema_version": "1.0",
            "id": hook_id,
            "pack_id": str(hook.get("pack_id") or ""),
            "event": event_name,
            "type": "workflow-agent-chain",
            "status": "failed",
            "action": "fail",
            "auto_continue": False,
            "summary": summary,
            "artifact_paths": [str(result_path)],
            "result_path": str(result_path),
            "steps": [],
            "short_circuited": True,
        }

    def _read_workflow_hook_registry(self) -> list[dict[str, Any]]:
        registry_path = self._workflow_hooks_registry_path()
        if not registry_path.is_file():
            return []
        with open(registry_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return []
        hooks = data.get("hooks") or []
        if not isinstance(hooks, list):
            return []
        return [hook for hook in hooks if isinstance(hook, dict)]

    def _read_workflow_hook_overrides(self) -> dict[str, Any]:
        overrides_path = self.project_root / ".specify" / "workflow-hooks.local.yml"
        defaults: dict[str, Any] = {
            "enabled": True,
            "disabled_events": [],
            "disabled_hooks": [],
            "disabled_packs": [],
        }
        if not overrides_path.is_file():
            return defaults
        try:
            with open(overrides_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            return defaults
        if not isinstance(data, dict):
            return defaults
        return {
            "enabled": self._as_bool(data.get("enabled"), default=True),
            "disabled_events": self._as_string_list(data.get("disabled_events")),
            "disabled_hooks": self._as_string_list(data.get("disabled_hooks")),
            "disabled_packs": self._as_string_list(data.get("disabled_packs")),
        }

    def _workflow_hook_disabled_reason(
        self,
        hook: dict[str, Any],
        event_name: str,
        overrides: dict[str, Any],
    ) -> str:
        if not self._as_bool(overrides.get("enabled"), default=True):
            return "workflow hooks disabled by .specify/workflow-hooks.local.yml"
        if event_name in self._as_string_list(overrides.get("disabled_events")):
            return "event disabled by .specify/workflow-hooks.local.yml"
        hook_id = str(hook.get("id") or "")
        if hook_id and hook_id in self._as_string_list(overrides.get("disabled_hooks")):
            return "hook disabled by .specify/workflow-hooks.local.yml"
        pack_id = str(hook.get("pack_id") or "")
        if pack_id and pack_id in self._as_string_list(overrides.get("disabled_packs")):
            return "pack disabled by .specify/workflow-hooks.local.yml"
        return ""

    def _git_tracked_dirty_files(self) -> list[str]:
        try:
            completed = subprocess.run(
                ["git", "-C", str(self.project_root), "status", "--porcelain", "--untracked-files=no"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if completed.returncode != 0:
            return []
        files: list[str] = []
        for line in completed.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:].strip()
            if path:
                files.append(path)
        return sorted(dict.fromkeys(files))

    def _display_project_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.project_root.resolve()).as_posix()
        except ValueError:
            return str(path)

    @staticmethod
    def _workflow_hook_slug(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "hook"

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _read_json_object_from_file(path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _runner_failure_result(event_name: str, summary: str) -> dict[str, Any]:
        return {
            "tool": "invoke-workflow-hooks",
            "status": "blocked",
            "facts": {
                "event": event_name,
                "hook_count": 1,
                "aggregate_status": "failed",
                "action": "fail",
                "auto_continue": False,
                "summary": summary,
                "artifact_paths": [],
                "results": [],
            },
            "blockers": [summary],
            "unknowns": [],
            "hints": [],
        }

    @staticmethod
    def _read_json_object_from_text(text: str) -> dict[str, Any] | None:
        stripped = text.strip()
        if not stripped:
            return None
        candidates = [stripped]
        lines = [line.strip() for line in stripped.splitlines() if line.strip()]
        candidates.extend(line for line in lines if line.startswith("{") and line.endswith("}"))
        first = stripped.find("{")
        last = stripped.rfind("}")
        if first >= 0 and last > first:
            candidates.append(stripped[first : last + 1])
        for candidate in candidates:
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
        return None

    @staticmethod
    def _default_hook_action(status: str) -> str:
        if status == "requires_rework":
            return "rework"
        if status == "failed":
            return "fail"
        if status == "blocked":
            return "pause"
        return "continue"

    @staticmethod
    def _hook_action_for_result(status: str, auto_continue: bool) -> str:
        action = WorkflowEngine._default_hook_action(status)
        if not auto_continue and action == "continue":
            return "pause"
        return action

    @staticmethod
    def _normalize_hook_status(status: str) -> str:
        normalized = status.strip().lower()
        if normalized in {"passed", "pass", "ok", "success"}:
            return "passed"
        if normalized in {"warning", "warn", "advisory"}:
            return "warning"
        if normalized in {"skipped", "skip"}:
            return "skipped"
        if normalized in {"blocked", "block", "paused", "pause"}:
            return "blocked"
        if normalized in {"requires_rework", "requires-rework", "rework"}:
            return "requires_rework"
        if normalized in {"failed", "failure", "fail", "error"}:
            return "failed"
        return "failed"

    @staticmethod
    def _aggregate_hook_status(statuses: list[str]) -> str:
        normalized = [WorkflowEngine._normalize_hook_status(status) for status in statuses if status]
        if not normalized:
            return "skipped"
        if "requires_rework" in normalized:
            return "requires_rework"
        if "blocked" in normalized:
            return "blocked"
        if "failed" in normalized:
            return "failed"
        if "warning" in normalized:
            return "warning"
        if all(status == "skipped" for status in normalized):
            return "skipped"
        return "passed"

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_bool(value: Any, *, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return default

    @staticmethod
    def _as_string_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        return [str(value)]

    def _confirm_step_if_required(
        self,
        step_config: dict[str, Any],
        state: RunState,
    ) -> bool:
        """Pause or prompt before a step that declares ``requires_confirmation``."""
        if not step_config.get("requires_confirmation", False):
            return True

        step_id = step_config.get("id", "?")
        message = step_config.get(
            "confirmation_message",
            f"Confirm before running workflow step {step_id!r}.",
        )
        output = {
            "confirmation_required": True,
            "message": message,
            "choice": None,
        }

        if not sys.stdin.isatty():
            state.status = RunStatus.PAUSED
            state.step_results[step_id] = {
                "integration": step_config.get("integration"),
                "model": step_config.get("model"),
                "options": step_config.get("options", {}),
                "input": step_config.get("input", {}),
                "output": output,
                "status": StepStatus.PAUSED.value,
            }
            state.append_log(
                {
                    "event": "confirmation_required",
                    "step_id": step_id,
                    "message": message,
                }
            )
            state.save()
            return False

        print("\n  Confirmation required")
        print(f"  Step: {step_id}")
        print(f"  {message}")
        raw = input("  Continue? [y/N]: ").strip().lower()
        if raw not in {"y", "yes", "approve", "approved"}:
            output["choice"] = raw or "reject"
            output["aborted"] = True
            state.status = RunStatus.ABORTED
            state.step_results[step_id] = {
                "integration": step_config.get("integration"),
                "model": step_config.get("model"),
                "options": step_config.get("options", {}),
                "input": step_config.get("input", {}),
                "output": output,
                "status": StepStatus.FAILED.value,
            }
            state.append_log(
                {
                    "event": "confirmation_rejected",
                    "step_id": step_id,
                    "choice": output["choice"],
                }
            )
            state.save()
            return False

        state.append_log(
            {
                "event": "confirmation_approved",
                "step_id": step_id,
                "choice": raw,
            }
        )
        return True

    def _select_steps(
        self,
        steps: list[dict[str, Any]],
        inputs: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return steps enabled for the resolved delivery profile."""
        profile = str(inputs.get("delivery_profile") or "auto").strip() or "auto"
        selected: list[dict[str, Any]] = []
        for step in steps:
            if self._step_enabled_for_profile(step, profile):
                selected.append(step)
        return selected

    @staticmethod
    def _as_string_set(value: Any) -> set[str]:
        if value is None:
            return set()
        if isinstance(value, str):
            return {value}
        if isinstance(value, (list, tuple, set)):
            return {str(item) for item in value}
        return {str(value)}

    def _step_enabled_for_profile(self, step: dict[str, Any], profile: str) -> bool:
        profiles = self._as_string_set(step.get("profiles"))
        skip_profiles = self._as_string_set(step.get("skip_profiles"))
        if profile in skip_profiles:
            return False
        if profiles and profile not in profiles:
            return False
        return True

    def _resolve_inputs(
        self,
        definition: WorkflowDefinition,
        provided: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve workflow inputs against definitions and provided values."""
        resolved: dict[str, Any] = {}
        for name, input_def in definition.inputs.items():
            if not isinstance(input_def, dict):
                continue
            if name in provided:
                resolved[name] = self._coerce_input(
                    name, provided[name], input_def
                )
            elif "default" in input_def:
                resolved[name] = input_def["default"]
            elif input_def.get("required", False):
                msg = f"Required input {name!r} not provided."
                raise ValueError(msg)
        return resolved

    @staticmethod
    def _coerce_input(
        name: str, value: Any, input_def: dict[str, Any]
    ) -> Any:
        """Coerce a provided input value to the declared type."""
        input_type = input_def.get("type", "string")
        enum_values = input_def.get("enum")

        if input_type == "number":
            try:
                value = float(value)
                if value == int(value):
                    value = int(value)
            except (ValueError, TypeError):
                msg = f"Input {name!r} expected a number, got {value!r}."
                raise ValueError(msg) from None
        elif input_type == "boolean":
            if isinstance(value, str):
                if value.lower() in ("true", "1", "yes"):
                    value = True
                elif value.lower() in ("false", "0", "no"):
                    value = False
                else:
                    msg = f"Input {name!r} expected a boolean, got {value!r}."
                    raise ValueError(msg)

        if enum_values is not None and value not in enum_values:
            msg = (
                f"Input {name!r} value {value!r} not in allowed "
                f"values: {enum_values}."
            )
            raise ValueError(msg)

        return value

    def list_runs(self) -> list[dict[str, Any]]:
        """List all workflow runs in the project."""
        runs_dir = self.project_root / ".specify" / "workflows" / "runs"
        if not runs_dir.exists():
            return []

        runs: list[dict[str, Any]] = []
        for run_dir in sorted(runs_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            state_path = run_dir / "state.json"
            if state_path.exists():
                with open(state_path, encoding="utf-8") as f:
                    state_data = json.load(f)
                runs.append(state_data)
        return runs


class WorkflowAbortError(Exception):
    """Raised when a workflow is aborted (e.g., gate rejection)."""
