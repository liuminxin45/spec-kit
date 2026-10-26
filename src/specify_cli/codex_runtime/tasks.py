"""Append-only task evidence and source-bound workflow gates.

This is an execution/recording boundary for Spec Kit, not a sandbox or an
independent attestation of who typed a referenced human message.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

from .common import RuntimeBlocked, atomic_write, digest, inside, json_bytes, mutex, now, read_json, read_yaml
from . import packs


TASK_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
SKIP = {".git", ".specify", ".agents", ".venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}
CODE = {".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".c", ".cpp", ".h", ".hpp", ".go", ".rs", ".cs"}
UI = {".vue", ".tsx", ".jsx", ".html", ".css", ".scss", ".qss", ".ui"}
EVENTS = {"request.amended", "clarification.recorded", "workflow.selected", "contract.recorded",
          "resources.selected", "evidence.added", "ai.reviewed", "human.recorded",
          "knowledge.recorded", "task.cancelled"}


def task_dir(root: Path, identity: str) -> Path:
    if not TASK_ID.fullmatch(identity):
        raise RuntimeBlocked("Invalid task id")
    return inside(root, f".specify/tasks/{identity}")


def _events(root: Path, identity: str) -> list[dict]:
    path = task_dir(root, identity) / "events.jsonl"
    if not path.is_file():
        raise RuntimeBlocked(f"Unknown task: {identity}")
    events, previous = [], None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if not isinstance(event, dict):
                raise RuntimeBlocked("Task journal needs event objects")
            proof = event.pop("sha256")
            if event.get("previous") != previous or event.get("seq") != len(events) + 1 or digest(event) != proof:
                raise RuntimeBlocked("Task journal integrity mismatch; preserve it before recovery")
            event["sha256"] = proof
            previous = proof
            events.append(event)
    except RuntimeBlocked:
        raise
    except (ValueError, KeyError) as exc:
        raise RuntimeBlocked(f"Incomplete task journal, inspect before recovery: {path}") from exc
    if not events or events[0].get("type") != "task.started" or events[0].get("payload", {}).get("id") != identity:
        raise RuntimeBlocked("Task journal is empty or belongs to another task")
    return events


def _reduce(events: list[dict]) -> dict:
    state = {"status": "active", "request": {}, "clarification": {"status": "pending"},
             "workflow": None, "contract": None, "resources": [], "evidence": [],
             "ai_acceptance": {"status": "pending"}, "human_acceptance": {"status": "pending"},
             "knowledge": None}
    for event in events:
        kind, payload = event["type"], deepcopy(event["payload"])
        if kind == "task.started":
            state.update(id=payload["id"], created_at=event["time"], request={"revision": 1, **payload["request"]})
            state["original_request"] = deepcopy(payload["request"])
        elif kind == "request.amended":
            state["request"] = {"revision": state["request"]["revision"] + 1, **payload}
            state.update(clarification={"status": "pending"}, contract=None, workflow=None, knowledge=None,
                         ai_acceptance={"status": "pending"}, human_acceptance={"status": "pending"}, status="active")
        elif kind == "clarification.recorded":
            state.update(clarification=payload, contract=None, ai_acceptance={"status": "pending"},
                         human_acceptance={"status": "pending"}, status="active")
        elif kind == "workflow.selected":
            state.update(workflow=payload, contract=None, resources=payload.get("resources", []),
                         ai_acceptance={"status": "pending"}, human_acceptance={"status": "pending"}, status="active")
        elif kind == "contract.recorded":
            state.update(contract=payload, ai_acceptance={"status": "pending"},
                         human_acceptance={"status": "pending"}, status="active")
        elif kind == "resources.selected":
            merged = {v["id"]: v for v in [*state["resources"], *payload["resources"]]}
            state["resources"] = list(merged.values())
        elif kind in {"evidence.added", "evidence.captured"}:
            state["evidence"].append({**payload, "event_id": event["id"]})
        elif kind == "ai.reviewed":
            state["ai_acceptance"] = payload
            state["human_acceptance"] = {"status": "pending"}
            state["status"] = "active" if payload["status"] != "blocked" else "blocked"
        elif kind == "human.recorded":
            state["human_acceptance"] = payload
            if payload["status"] == "rejected":
                state["status"] = "active"
        elif kind == "knowledge.recorded":
            state["knowledge"] = payload
        elif kind == "task.finished":
            state["status"] = payload["status"]
        elif kind == "task.cancelled":
            state["status"] = "cancelled"
        state["last_event"] = event["id"]
        state["updated_at"] = event["time"]
    return state


def read_task(root: Path, identity: str) -> dict:
    return _reduce(_events(root, identity))


def _append(root: Path, identity: str, kind: str, payload: dict) -> dict:
    folder = task_dir(root, identity)
    path = folder / "events.jsonl"
    previous = _events(root, identity) if path.exists() else []
    event = {"id": uuid.uuid4().hex, "seq": len(previous) + 1, "time": now(), "type": kind,
             "payload": payload, "previous": previous[-1]["sha256"] if previous else None}
    event["sha256"] = digest(event)
    folder.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    state = _reduce([*previous, event])
    atomic_write(folder / "task.json", json_bytes(state))
    return state


def start(root: Path, request: str, *, source_ref: str = "current-user-request", identity: str | None = None) -> dict:
    packs.locked(root)
    if not isinstance(request, str) or not request.strip():
        raise RuntimeBlocked("An original request is required")
    identity = identity or "t-" + uuid.uuid4().hex[:16]
    with mutex(root, "task-" + identity):
        if (task_dir(root, identity) / "events.jsonl").exists():
            raise RuntimeBlocked("Task already exists; resume it explicitly")
        return _append(root, identity, "task.started", {"id": identity,
                       "request": {"text": request, "source_ref": source_ref}})


def snapshot(root: Path, files: list[str]) -> dict:
    manifest = {}
    for relative in files:
        path = inside(root, relative, allow_root=True)
        if path.is_dir():
            for directory, folders, names in os.walk(path, followlinks=False):
                folders[:] = sorted(name for name in folders if name not in SKIP)
                for name in folders:
                    inside(root, (Path(directory) / name).relative_to(root).as_posix())
                for name in sorted(names):
                    relative_name = (Path(directory) / name).relative_to(root).as_posix()
                    if name in SKIP:
                        continue
                    safe = inside(root, relative_name)
                    if safe.is_file():
                        manifest[relative_name] = digest(safe.read_bytes())
        else:
            manifest[path.relative_to(root).as_posix()] = digest(path.read_bytes()) if path.is_file() else None
    try:
        git = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        head = git.stdout.strip() if git.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        head = None
    return {"fingerprint": digest(manifest), "files": manifest,
            "head": head, "captured_at": now()}


def _current(root: Path, state: dict) -> dict:
    if not state.get("contract"):
        raise RuntimeBlocked("Record a contract before collecting execution evidence")
    return snapshot(root, state["contract"]["files"] + state["contract"].get("inputs", []))


def _binding(root: Path, state: dict) -> dict:
    current = _current(root, state)
    available = packs.catalog(root)
    for item in state["resources"]:
        actual = available.get(item["id"])
        if not actual or any(actual[key] != item[key] for key in ["version", "pack_sha256", "path"]):
            raise RuntimeBlocked("Selected package binding changed; reselect workflow and contract: " + item["id"])
    return {"request_revision": state["request"]["revision"],
            "contract_sha256": digest(state["contract"]), "source_snapshot": current,
            "resources_sha256": digest(state["resources"])}


def _fresh(root: Path, state: dict, item: dict) -> bool:
    current = _binding(root, state)
    return (item.get("request_revision") == state["request"]["revision"] and
            item.get("contract_sha256") == digest(state["contract"]) and
            item.get("resources_sha256") == current["resources_sha256"] and
            item.get("source_snapshot", {}).get("fingerprint") == current["source_snapshot"]["fingerprint"])


def _requirements(state: dict) -> dict:
    return {v["id"]: v for v in state["contract"]["requirements"]}


def _flags(root: Path, state: dict) -> tuple[dict, list[str]]:
    flags = dict(state["contract"].get("flags", {}))
    before = state["contract"]["baseline"]["files"]
    after = _current(root, state)["files"]
    changed = [name for name in before.keys() | after.keys() if before.get(name) != after.get(name)]
    if any(Path(name).suffix.lower() in CODE for name in changed):
        flags["changes_code"] = True
    if any(Path(name).suffix.lower() in UI for name in changed) and not state["contract"].get("ui_not_affected_reason"):
        flags["changes_visible_ui"] = True
    return flags, changed


def _valid_evidence(root: Path, state: dict, item: dict) -> tuple[bool, str]:
    try:
        path = inside(root, item["artifact"])
        if not path.is_file() or digest(path.read_bytes()) != item["sha256"]:
            return False, "missing-or-modified-artifact"
        if not _fresh(root, state, item):
            return False, "stale-request-contract-or-source"
        if item.get("source_changed_during_run"):
            return False, "inputs-changed-during-execution"
        return True, "current"
    except (RuntimeBlocked, KeyError):
        return False, "invalid-evidence-reference"


def _clarification_ready(state: dict) -> tuple[bool, str]:
    clarification = state["clarification"]
    if clarification.get("status") == "not-needed":
        return bool(clarification.get("reason")), "clarification-not-needed"
    if clarification.get("status") != "answered":
        return False, "clarification-pending"
    questions = clarification.get("questions", [])
    if not questions:
        return False, "answers-missing"
    for question in questions:
        if not str(question.get("answer", "")).strip():
            return False, "answer-missing"
        if question.get("requires_human", True) and (
            question.get("answer_origin") != "human" or not question.get("source_ref")
        ):
            return False, "human-decision-not-established"
    return True, "clarification-answered"


def _review_errors(root: Path, state: dict, review: dict) -> list[str]:
    requirements = _requirements(state)
    rows = review.get("criteria", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return ["criteria must be a list"]
    ids = [row.get("id") for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(requirements):
        return ["AI review must cover each current requirement exactly once"]
    evidence = {v["id"]: v for v in state["evidence"]}
    errors = []
    for row in rows:
        if row.get("result") != "passed" or not row.get("reason") or not row.get("evidence"):
            errors.append(f"{row['id']}: needs a passed, explained, evidence-linked judgment")
            continue
        requirement = requirements[row["id"]]
        found_kinds = set()
        for reference in row["evidence"]:
            item = evidence.get(reference)
            if not item:
                errors.append(f"{row['id']}: unknown evidence {reference}")
                continue
            valid, reason = _valid_evidence(root, state, item)
            if not valid:
                errors.append(f"{row['id']}: {reference} is {reason}")
            if row["id"] not in item.get("requirements", []):
                errors.append(f"{row['id']}: evidence was not collected for this criterion")
            expected = requirement.get("evidence_status", "passed")
            if expected == "passed" and item.get("result") != "passed":
                errors.append(f"{row['id']}: evidence did not pass")
            if item["kind"] in {"test", "build", "check"} and item["origin"] != "runner-captured":
                errors.append(f"{row['id']}: execution evidence must come from the runner")
            found_kinds.add(item["kind"])
        for kind in requirement.get("evidence_kinds", []):
            if kind not in found_kinds:
                errors.append(f"{row['id']}: missing {kind} evidence")
    return errors


def _evaluate(root: Path, state: dict, phase: str, *, skip_review: bool = False) -> dict:
    blockers, results = [], []
    if not state.get("workflow") or not state.get("contract"):
        return {"status": "blocked", "blockers": ["Select a workflow and record the request contract"], "gates": []}
    ready, reason = _clarification_ready(state)
    if not ready:
        blockers.append(reason)
    flags, changed = _flags(root, state)
    if state["workflow"]["definition"].get("read_only") and changed:
        blockers.append("Read-only workflow source scope changed; choose an implementation workflow and contract")
    receipts = [v for v in state["evidence"] if _valid_evidence(root, state, v)[0]]
    phases = state["workflow"]["definition"]["phases"]
    if phase not in phases:
        raise RuntimeBlocked("Unknown workflow phase: " + phase)
    _binding(root, state)  # Check that locked resources still match the selected contract.
    available = packs.catalog(root)
    for selected in state["resources"]:
        resource = available[selected["id"]]
        compatibility = packs.compatibility(resource)
        if compatibility["status"] == "unsupported":
            blockers.append("Unsupported selected resource: " + selected["id"])
        if phase == "ai_accept" and compatibility["status"] == "needs-connection-verification" and not any(
            item.get("capability_id") == selected["id"] and item.get("tool_ref") and
            item["origin"] == "tool-observed" and item.get("target", {}).get("identity") and
            item.get("result") == "passed" for item in receipts
        ):
            blockers.append("Selected capability connection is not verified: " + selected["id"])
    gates = list(state["workflow"]["definition"].get("gates", []))
    # Essential proof cannot be disabled by omitting a standard gate in a custom workflow.
    for flag, builtin in [("changes_code", "builtin/validation-receipts"),
                          ("changes_visible_ui", "builtin/ui-evidence"),
                          ("changes_runtime", "builtin/runtime-evidence")]:
        if phase == "ai_accept" and flags.get(flag) and not any(g["check"] == builtin and g.get("required", True) and g.get("when", "always") in {"always", flag} for g in gates):
            gates.append({"id": "kernel-" + flag.replace("_", "-"), "phase": "ai_accept", "check": builtin, "kind": "machine"})
    for gate in gates:
        if phases.index(gate["phase"]) > phases.index(phase):
            continue
        applies = gate.get("when", "always") == "always" or flags.get(gate["when"], False)
        status, why = "passed", "current-contract-satisfied"
        check = gate["check"]
        if not applies:
            status, why = "not-applicable", f"condition {gate.get('when')} is false for current scope"
        elif check == "builtin/request-contract":
            if not ready:
                status, why = "blocked", reason
        elif check == "builtin/validation-receipts":
            if not any(v["origin"] == "runner-captured" and v["kind"] in {"test", "check"}
                       and v["result"] == "passed" for v in receipts):
                status, why = "blocked", "No current passing execution receipt"
        elif check in {"builtin/ui-evidence", "builtin/runtime-evidence"}:
            kind = "screenshot" if check == "builtin/ui-evidence" else "runtime"
            matches = [v for v in receipts if v["kind"] == kind and v.get("target", {}).get("identity")
                       and v.get("tool_ref") and v.get("result") == "passed" and v["origin"] in {"tool-observed", "human-supplied"}]
            if not matches:
                status, why = "blocked", f"Current {kind} evidence with real target and tool/source reference required"
        elif check == "builtin/criteria-review":
            if skip_review:
                continue
            review = state["ai_acceptance"]
            errors = _review_errors(root, state, review) if review.get("status") == "passed" else ["AI acceptance is not passed"]
            if not errors and not _fresh(root, state, review):
                errors = ["AI acceptance is stale"]
            if errors:
                status, why = "blocked", "; ".join(errors)
        else:
            if not any(v.get("check_resource") == check and v["result"] == "passed"
                       and v["origin"] == "runner-captured" for v in receipts):
                status, why = "blocked", f"Required project check has no passing receipt: {check}"
        results.append({"id": gate["id"], "status": status, "reason": why})
        if gate.get("required", True) and status not in {"passed", "not-applicable"}:
            blockers.append(f"{gate['id']}: {why}")
    if phase == "ai_accept" and not skip_review:
        review = state["ai_acceptance"]
        if review.get("status") != "passed" or not _fresh(root, state, review):
            blockers.append("Current AI acceptance is required")
        else:
            blockers.extend(_review_errors(root, state, review))
    return {"status": "blocked" if blockers else "ok", "phase": phase, "gates": results,
            "blockers": blockers, "effective_flags": flags, "changed_files": changed}


def check(root: Path, identity: str, phase: str = "ai_accept") -> dict:
    with mutex(root, "task-" + identity):
        state = read_task(root, identity)
        if state.get("workflow") and phase not in state["workflow"]["definition"]["phases"]:
            raise RuntimeBlocked(f"Phase is not in selected workflow: {phase}")
        result = _evaluate(root, state, phase)
        _append(root, identity, "phase.checked", result)
        return result


def record(root: Path, identity: str, kind: str, payload: dict) -> dict:
    if kind not in EVENTS or not isinstance(payload, dict):
        raise RuntimeBlocked("Unsupported event; runner evidence cannot be supplied through record")
    with mutex(root, "task-" + identity):
        state = read_task(root, identity)
        payload = deepcopy(payload)
        if state["status"] == "cancelled":
            raise RuntimeBlocked("Cancelled task is immutable; start a follow-up task")
        if kind == "request.amended":
            if not payload.get("text") or not payload.get("reason") or not payload.get("source_ref"):
                raise RuntimeBlocked("An amendment needs text, source_ref and reason")
        elif kind == "clarification.recorded":
            if payload.get("status") not in {"not-needed", "answered", "pending"}:
                raise RuntimeBlocked("Invalid clarification status")
            if payload["status"] == "not-needed" and not payload.get("reason"):
                raise RuntimeBlocked("Explain why no blocking clarification is needed")
            if payload["status"] == "answered":
                if not isinstance(payload.get("questions"), list) or not payload["questions"]:
                    raise RuntimeBlocked("Answered clarification needs question/answer records")
                for question in payload["questions"]:
                    if not question.get("id") or not question.get("question"):
                        raise RuntimeBlocked("Each question needs its original id and text")
                    if question.get("answer_origin") not in {"human", "host-auto", "agent-assumption", "unknown"}:
                        raise RuntimeBlocked("An answer must have explicit provenance")
        elif kind == "workflow.selected":
            if not payload.get("reason"):
                raise RuntimeBlocked("Record the workflow selection reason")
            selected = packs.context(root, selected=[payload.get("id", "")])["resources"]
            workflow = next((v for v in selected if v["id"] == payload["id"]), None)
            if not workflow or workflow["type"] != "workflow":
                raise RuntimeBlocked("Select an installed workflow resource")
            if workflow["compatibility_status"]["status"] != "supported":
                raise RuntimeBlocked("Selected workflow is not compatible with this host")
            definition = packs.validate_workflow(read_yaml(inside(root, workflow["path"])), workflow["id"], workflow["version"])
            payload = {"id": workflow["id"], "version": workflow["version"], "pack_sha256": workflow["pack_sha256"],
                       "reason": payload["reason"], "definition": definition,
                       "resources": [{k: v[k] for k in ["id", "version", "pack_sha256", "path"]} for v in selected]}
        elif kind == "contract.recorded":
            if not state["workflow"]:
                raise RuntimeBlocked("Select a workflow before recording its contract")
            requirements = payload.get("requirements")
            if not isinstance(requirements, list) or not requirements:
                raise RuntimeBlocked("The contract needs observable requirements")
            ids = set()
            for requirement in requirements:
                if not isinstance(requirement, dict):
                    raise RuntimeBlocked("Each requirement must be an object")
                rid = requirement.get("id", "")
                if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", rid) or rid in ids:
                    raise RuntimeBlocked("Requirements need distinct stable IDs")
                ids.add(rid)
                kinds = requirement.get("evidence_kinds")
                if (not isinstance(requirement.get("criterion"), str) or not requirement["criterion"].strip() or
                    not isinstance(kinds, list) or not kinds or any(not isinstance(value, str) or value not in {
                        "source", "screenshot", "runtime", "interaction", "log", "design", "note", "test", "build", "check", "diagnostic"
                    } for value in kinds)):
                    raise RuntimeBlocked("Each requirement needs an observable criterion and evidence kinds")
                if requirement.get("evidence_status", "passed") not in {"passed", "observed"}:
                    raise RuntimeBlocked("Evidence status must be passed or observed")
            if not isinstance(payload.get("files"), list) or not payload["files"]:
                raise RuntimeBlocked("Declare the source/diagnostic file scope")
            if not isinstance(payload.get("inputs", []), list):
                raise RuntimeBlocked("Contract inputs must be paths")
            flags = payload.get("flags", {})
            if not isinstance(flags, dict) or any(k not in packs.FLAGS or not isinstance(v, bool) for k, v in flags.items()):
                raise RuntimeBlocked("Contract flags must be supported booleans")
            payload["baseline"] = snapshot(root, payload["files"] + payload.get("inputs", []))
        elif kind == "resources.selected":
            selected = packs.context(root, selected=payload.get("ids", []))["resources"]
            payload = {"resources": [{k: v[k] for k in ["id", "version", "pack_sha256", "path"]} for v in selected],
                       "reason": payload.get("reason", "selected for the current task")}
        elif kind == "evidence.added":
            payload = _import_evidence(root, identity, state, payload)
        elif kind == "ai.reviewed":
            if payload.get("status") not in {"passed", "failed", "blocked"} or not payload.get("summary"):
                raise RuntimeBlocked("AI review needs an explicit status and summary")
            payload.update(_binding(root, state))
            if payload["status"] == "passed":
                errors = _review_errors(root, state, payload)
                if errors:
                    raise RuntimeBlocked("; ".join(errors))
                gates = _evaluate(root, state, "ai_accept", skip_review=True)
                if gates["blockers"]:
                    raise RuntimeBlocked("; ".join(gates["blockers"]))
        elif kind == "human.recorded":
            if payload.get("status") not in {"passed", "rejected", "accepted-with-gaps"}:
                raise RuntimeBlocked("Invalid human acceptance status")
            if payload.get("origin") != "human" or not payload.get("source_ref") or not payload.get("quote"):
                raise RuntimeBlocked("Human acceptance needs a referenced actual human message; automatic answers do not qualify")
            if not state["contract"]:
                raise RuntimeBlocked("Human acceptance must refer to a delivery contract")
            if payload["status"] != "rejected":
                gates = _evaluate(root, state, "ai_accept")
                if gates["blockers"]:
                    raise RuntimeBlocked("AI acceptance is not current/passed: " + "; ".join(gates["blockers"]))
            if payload["status"] == "accepted-with-gaps":
                if not state["workflow"]["definition"].get("human_acceptance", {}).get("allow_accepted_gaps") or not payload.get("gaps"):
                    raise RuntimeBlocked("The workflow must explicitly allow and describe accepted gaps")
            payload.update(_binding(root, state))
            payload["provenance_verification"] = "referenced-message; host identity is not independently attested"
        elif kind == "knowledge.recorded":
            if payload.get("status") not in {"none", "candidate", "maintained", "deferred"} or not payload.get("reason"):
                raise RuntimeBlocked("Record a knowledge disposition and reason")
            if payload["status"] in {"candidate", "maintained"}:
                path = inside(root, payload.get("path", ""))
                if not path.exists():
                    raise RuntimeBlocked("Knowledge output must exist")
                payload["output_sha256"] = digest(path.read_bytes()) if path.is_file() else None
        elif kind == "task.cancelled" and not payload.get("reason"):
            raise RuntimeBlocked("Cancellation needs a reason")
        return _append(root, identity, kind, payload)


def _import_evidence(root: Path, identity: str, state: dict, payload: dict) -> dict:
    if payload.get("origin") not in {"tool-observed", "human-supplied", "agent-authored"}:
        raise RuntimeBlocked("Imported evidence needs explicit provenance; runner-captured is reserved")
    if payload.get("kind") not in {"source", "screenshot", "runtime", "interaction", "log", "design", "note", "test", "build", "check"}:
        raise RuntimeBlocked("Unsupported evidence kind")
    if payload["kind"] in {"test", "build", "check"}:
        raise RuntimeBlocked("Use task run for execution receipts, not a hand-written test result")
    requirements = payload.get("requirements", [])
    if not requirements or set(requirements) - set(_requirements(state)):
        raise RuntimeBlocked("Evidence must reference current requirements")
    original = inside(root, payload.get("path", ""))
    if not original.is_file():
        raise RuntimeBlocked("Evidence file is missing")
    if payload["origin"] in {"tool-observed", "human-supplied"} and not payload.get("tool_ref"):
        raise RuntimeBlocked("Observed evidence needs its real tool call or human source reference")
    eid = "ev-" + uuid.uuid4().hex[:12]
    destination = task_dir(root, identity) / "artifacts" / (eid + original.suffix)
    data = original.read_bytes()
    if payload["kind"] == "screenshot" and not (
        data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff") or
        data.startswith((b"GIF87a", b"GIF89a")) or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
    ):
        raise RuntimeBlocked("Screenshot evidence must contain PNG, JPEG, GIF or WebP image bytes")
    if payload.get("result", "observed") not in {"observed", "passed", "failed", "blocked", "unknown"}:
        raise RuntimeBlocked("Unsupported observation result")
    atomic_write(destination, data)
    return {"id": eid, "kind": payload["kind"], "origin": payload["origin"],
            "artifact": destination.relative_to(root).as_posix(), "sha256": digest(data),
            "source_path": original.relative_to(root).as_posix(), "requirements": requirements,
            "tool_ref": payload.get("tool_ref"), "target": payload.get("target", {}),
            "capability_id": payload.get("capability_id"),
            "description": payload.get("description", ""), "result": payload.get("result", "observed"),
            "provenance_verification": "referenced; not independently host-attested",
            **_binding(root, state)}


def _redact(text: str, environment: dict[str, str]) -> str:
    for key, value in environment.items():
        if re.search(r"token|password|secret|api.?key|credential", key, re.I) and len(value) >= 4:
            text = text.replace(value, "[REDACTED]")
    text = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+", r"\1[REDACTED]", text)
    return re.sub(r"(?i)((?:password|token|api[_-]?key|secret)\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]", text)


def run_check(root: Path, identity: str, command: dict) -> dict:
    """Run a finite argv command and capture its actual result; never a shell string."""
    if not isinstance(command, dict):
        raise RuntimeBlocked("Command must be a JSON object")
    with mutex(root, "task-" + identity):
        state = read_task(root, identity)
        if not state.get("workflow") or not state.get("contract") or not _clarification_ready(state)[0]:
            raise RuntimeBlocked("An answered request, workflow and contract are required before execution")
        if command.get("check_resource") or command.get("action_resource"):
            field = "check_resource" if command.get("check_resource") else "action_resource"
            reference = command[field]
            resources = packs.context(root, selected=[reference])["resources"]
            resource = next(v for v in resources if v["id"] == reference)
            if resource["type"] != ("check" if field == "check_resource" else "action") or resource["compatibility_status"]["status"] != "supported":
                raise RuntimeBlocked("Required check is unavailable or incompatible")
            descriptor = read_yaml(inside(root, resource["path"]))
            if set(command) - {field, "requirements"}:
                raise RuntimeBlocked("A registered check cannot be replaced by caller-supplied execution options")
            command = {**descriptor, **command, "kind": "check" if field == "check_resource" else "diagnostic"}
            pack_folder = str(inside(root, resource["path"]).parent)
            command["argv"] = [arg.replace("{pack}", pack_folder).replace("{project}", str(root)) for arg in command["argv"]]
        argv = command.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and "\x00" not in arg for arg in argv):
            raise RuntimeBlocked("Command argv must be a nonempty array of strings")
        kind = command.get("kind", "test")
        if kind not in {"test", "build", "check", "diagnostic"}:
            raise RuntimeBlocked("Runner kind must be test, build, check or diagnostic")
        requirements = command.get("requirements", [])
        if not requirements or set(requirements) - set(_requirements(state)):
            raise RuntimeBlocked("Execution must reference current requirements")
        cwd = inside(root, command.get("cwd", "."), allow_root=True)
        if not cwd.is_dir():
            raise RuntimeBlocked("Execution cwd is not a directory")
        timeout = command.get("timeout_seconds", 120)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
            raise RuntimeBlocked("Execution timeout must be in (0, 3600] seconds")
        environment = os.environ.copy()
        extra = command.get("environment", {})
        if not isinstance(extra, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in extra.items()):
            raise RuntimeBlocked("Command environment must be a string mapping")
        environment.update(extra)
        before = _binding(root, state)
        started = now()
        try:
            result = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=timeout)
            code, stdout, stderr, timed_out = result.returncode, result.stdout, result.stderr, False
        except subprocess.TimeoutExpired as exc:
            code, timed_out = None, True
            stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
            stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else exc.stderr or ""
        except OSError as exc:
            code, stdout, stderr, timed_out = None, "", str(exc), False
        structured = None
        try:
            value = json.loads(stdout.strip())
            structured = value if isinstance(value, dict) else None
        except ValueError:
            pass
        status = "passed" if code == 0 else "blocked" if timed_out else "failed"
        if structured and structured.get("status") in {"blocked", "failed", "error", "incomplete"}:
            status = "blocked" if structured["status"] == "blocked" else "failed"
        if command.get("structured") and (not structured or structured.get("status") not in {"ok", "passed", "success", "current"}):
            status = "failed" if status == "passed" else status
        after = _binding(root, state)
        eid = "ev-" + uuid.uuid4().hex[:12]
        relative = f".specify/tasks/{identity}/artifacts/{eid}.json"
        details = {"argv": [_redact(arg, environment) for arg in argv], "cwd": command.get("cwd", "."),
                   "exit_code": code, "timed_out": timed_out, "started_at": started, "finished_at": now(),
                   "stdout": _redact(stdout, environment), "stderr": _redact(stderr, environment),
                   "structured_status": structured.get("status") if structured else None}
        content = json_bytes(details)
        atomic_write(inside(root, relative), content)
        item = {"id": eid, "kind": kind, "origin": "runner-captured", "artifact": relative,
                "sha256": digest(content), "result": status, "requirements": requirements,
                "exit_code": code, "check_resource": command.get("check_resource"),
                "action_resource": command.get("action_resource"),
                "source_changed_during_run": before["source_snapshot"]["fingerprint"] != after["source_snapshot"]["fingerprint"],
                **after}
        if item["source_changed_during_run"]:
            item["result"] = "blocked"
        _append(root, identity, "evidence.captured", item)
        return {"status": "ok" if item["result"] == "passed" else item["result"], "evidence": item,
                "note": "Runner captures the launched command; it is not an execution sandbox."}


def inspect(root: Path, identity: str) -> dict:
    state = read_task(root, identity)
    if state["contract"]:
        state["current_source"] = _current(root, state)
        state["evidence_validity"] = [{"id": item["id"], "valid": _valid_evidence(root, state, item)[0],
                                       "reason": _valid_evidence(root, state, item)[1]} for item in state["evidence"]]
        try:
            state["ai_applies_to_current_source"] = (
                state["ai_acceptance"].get("status") == "passed" and _fresh(root, state, state["ai_acceptance"]))
            _binding(root, state)
        except RuntimeBlocked as exc:
            state["ai_applies_to_current_source"] = False
            state["revalidation_blockers"] = [str(exc)]
        state["effective_status"] = "needs-revalidation" if state["status"] in {
            "closed", "closed-with-accepted-gaps", "delivered-awaiting-human"} and not state["ai_applies_to_current_source"] else state["status"]
    return state


def finish(root: Path, identity: str) -> dict:
    with mutex(root, "task-" + identity):
        state = read_task(root, identity)
        if state["status"] == "cancelled":
            raise RuntimeBlocked("Cancelled task cannot be finished")
        gates = _evaluate(root, state, "ai_accept")
        if not state.get("knowledge"):
            gates["blockers"].append("Record knowledge disposition, including none when appropriate")
        human = state["human_acceptance"]
        if human.get("status") == "rejected":
            gates["blockers"].append("User rejected this revision; amend and rework the task")
        if gates["blockers"]:
            raise RuntimeBlocked("; ".join(gates["blockers"]))
        required = state["workflow"]["definition"].get("human_acceptance", {}).get("required_for_close", True)
        if human.get("status") in {"passed", "accepted-with-gaps"}:
            if not _fresh(root, state, human):
                raise RuntimeBlocked("Human acceptance refers to a stale delivery")
            status = "closed-with-accepted-gaps" if human["status"] == "accepted-with-gaps" else "closed"
        else:
            status = "delivered-awaiting-human" if required else "closed"
        state = _append(root, identity, "task.finished", {"status": status,
                         "human_required": required, **_binding(root, state)})
        text = report(state)
        atomic_write(task_dir(root, identity) / "report.md", text.encode("utf-8"))
        return {"status": status, "task": identity, "ai_acceptance": state["ai_acceptance"]["status"],
                "human_acceptance": human.get("status") if required or human.get("status") != "pending" else "not-required",
                "report": f".specify/tasks/{identity}/report.md"}


def report(state: dict) -> str:
    lines = [f"# Task {state['id']}", "", f"Status: {state['status']}", "", "## Original request", "",
             state["original_request"]["text"], "", f"Source: {state['original_request']['source_ref']}", "",
             f"## Current request (revision {state['request']['revision']})", "", state["request"]["text"], "",
             "## Clarification", "", json.dumps(state["clarification"], ensure_ascii=False, indent=2), "",
             "## Workflow", "", f"{state['workflow']['id']} @ {state['workflow']['version']}", "",
             state["workflow"]["reason"], "", "## Acceptance criteria", ""]
    for row in state["ai_acceptance"].get("criteria", []):
        lines.append(f"- {row['id']}: {row.get('result')} — {row.get('reason')} ({', '.join(row.get('evidence', []))})")
    lines += ["", "## Evidence", ""]
    for item in state["evidence"]:
        lines.append(f"- {item['id']}: {item['kind']} / {item['origin']} / {item['result']} — {item['artifact']}")
    lines += ["", "## AI acceptance", "", state["ai_acceptance"].get("summary", "pending"), "",
              "## Human acceptance", "", json.dumps(state["human_acceptance"], ensure_ascii=False, indent=2), "",
              "## Knowledge disposition", "", json.dumps(state["knowledge"], ensure_ascii=False, indent=2), "",
              "## Delivery binding", "", f"Source fingerprint: {state['ai_acceptance'].get('source_snapshot', {}).get('fingerprint')}", "",
              "Selected resources: " + ", ".join(f"{item['id']}@{item['version']}" for item in state["resources"]), "",
              "The event journal retains original requests, revisions and historical outcomes.", ""]
    return "\n".join(lines)


def guard(root: Path, identity: str) -> dict:
    """Optional Stop-hook adapter: at most one continuation per unchanged state.

    The caller must register this adapter in its actual host. No hook is installed
    by initialization, and this adapter does not police unrelated shell commands.
    """
    with mutex(root, "task-" + identity):
        state = read_task(root, identity)
        if state["status"] in {"cancelled", "blocked", "closed", "closed-with-accepted-gaps", "delivered-awaiting-human"} or not _clarification_ready(state)[0]:
            return {"status": "ok", "decision": "allow", "reason": "Finished, blocked, or waiting for a real user decision"}
        try:
            result = _evaluate(root, state, "ai_accept")
            binding = _binding(root, state)
        except RuntimeBlocked as exc:
            return {"status": "ok", "decision": "allow", "reason": "Explicit blocker: " + str(exc)}
        if not result["blockers"]:
            return {"status": "ok", "decision": "allow", "reason": "Current AI acceptance is available"}
        key = digest({"request_revision": binding["request_revision"],
                      "contract_sha256": binding["contract_sha256"],
                      "resources_sha256": binding["resources_sha256"],
                      "source_fingerprint": binding["source_snapshot"]["fingerprint"]})
        # Bound continuation even if a host repeatedly calls Stop without work.
        if any(v["type"] == "guard.checked" and v["payload"].get("key") == key for v in _events(root, identity)):
            return {"status": "ok", "decision": "allow", "reason": "Continuation already requested for this state; report blockers to the user"}
        _append(root, identity, "guard.checked", {"key": key, "blockers": result["blockers"]})
        return {"status": "ok", "decision": "continue-once", "blockers": result["blockers"],
                "hook_output": {"decision": "block", "reason": "Complete required task evidence or report a concrete blocker: " + "; ".join(result["blockers"])}}
