"""Behavior tests for the opt-in runtime; all human responses here are synthetic fixtures."""
from __future__ import annotations

from copy import deepcopy
import base64
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from specify_cli import app
from specify_cli.codex_runtime import common, knowledge, packs, tasks
from specify_cli.codex_runtime.common import RuntimeBlocked, digest, json_bytes, read_json, read_yaml, tree_digest, yaml_bytes


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "AGENTS.md").write_text("# User rules\nKeep this custom rule.\n", encoding="utf-8")
    (root / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    packs.initialize(root)
    return root


def author(tmp_path, identity="example/project", contents=None, requires=None, version="0.1.0"):
    path = tmp_path / (identity.replace("/", "-") + "-" + version)
    path.mkdir(exist_ok=True)
    (path / "guide.md").write_text("# A project fact\n", encoding="utf-8")
    manifest = {"schema_version": "2.0", "id": identity, "version": version, "description": "Synthetic project pack",
                "contents": contents if contents is not None else [{"id": "guide", "type": "reference", "path": "guide.md"}],
                "requires": requires or []}
    (path / "pack.yml").write_bytes(yaml_bytes(manifest))
    return path


def begin(root, workflow="speckit/workflows::coding-lite", evidence_kind="test", observed=False, flags=None):
    identity = tasks.start(root, "Synthetic request: correct addition", source_ref="fixture:user-request")["id"]
    tasks.record(root, identity, "clarification.recorded", {"status": "not-needed", "reason": "Exact inputs and expected behavior supplied"})
    tasks.record(root, identity, "workflow.selected", {"id": workflow, "reason": "Bounded single-function change"})
    tasks.record(root, identity, "contract.recorded", {
        "requirements": [{"id": "R1", "criterion": "add(2, 3) equals 5", "evidence_kinds": [evidence_kind],
                          "evidence_status": "observed" if observed else "passed"}],
        "files": ["calc.py"], "flags": flags or {}})
    return identity


def run(root, identity, script="from calc import add; assert add(2,3)==5", **options):
    return tasks.run_check(root, identity, {"argv": [sys.executable, "-c", script], "requirements": ["R1"], **options})


def review(root, identity, evidence):
    return tasks.record(root, identity, "ai.reviewed", {"status": "passed", "summary": "Observed required result",
        "criteria": [{"id": "R1", "result": "passed", "reason": "Executable assertion confirms the requested output", "evidence": [evidence]}]})


def disposition(root, identity):
    return tasks.record(root, identity, "knowledge.recorded", {"status": "none", "reason": "No durable new domain fact"})


def test_init_preserves_user_files_and_is_idempotent(project):
    agents = (project / "AGENTS.md").read_bytes()
    assert b"Keep this custom rule" in agents
    assert len(packs.catalog(project)) == 8
    assert not (project / "ai").exists()
    assert not (project / ".specify/feature.json").exists()
    packs.initialize(project)
    assert (project / "AGENTS.md").read_bytes() == agents
    assert packs.doctor(project)["status"] == "ok"


def test_cli_init_and_native_skill(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["init", "trial", "--mode", "codex-skill", "--no-git", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert not (tmp_path / "trial/.git").exists()
    metadata = read_yaml(tmp_path / "trial/.agents/skills/speckit/agents/openai.yaml")
    assert metadata["policy"]["allow_implicit_invocation"] is True
    assert "$speckit" in metadata["interface"]["default_prompt"]


def test_cli_bad_mode_and_json_blocker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["init", "trial", "--mode", "unknown", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["status"] == "blocked"


def test_legacy_project_is_not_overwritten(tmp_path):
    (tmp_path / ".specify").mkdir()
    old = tmp_path / ".specify/workspace.yml"
    old.write_text("original: data")
    with pytest.raises(RuntimeBlocked, match="legacy"):
        packs.initialize(tmp_path)
    assert old.read_text() == "original: data"
    assert packs.migration_plan(tmp_path)["writes"] == []


def test_customized_entry_is_preserved(project):
    path = project / ".agents/skills/speckit/SKILL.md"
    path.write_text("customized")
    with pytest.raises(RuntimeBlocked, match="Customized"):
        packs.install(project, [])
    assert path.read_text() == "customized"


def test_same_version_is_immutable(project, tmp_path):
    path = author(tmp_path)
    packs.install(project, [str(path)])
    (path / "guide.md").write_text("changed")
    with pytest.raises(RuntimeBlocked, match="immutable"):
        packs.install(project, [str(path)], replace=True)


def test_exact_dependencies_toposort_and_remove_block(project, tmp_path):
    a = author(tmp_path, "example/base")
    b = author(tmp_path, "example/child", requires=[{"id": "example/base", "version": "0.1.0"}])
    result = packs.install(project, [str(b), str(a)])
    assert result["packs"].index("example/base") < result["packs"].index("example/child")
    with pytest.raises(RuntimeBlocked, match="Missing dependency"):
        packs.remove(project, "example/base")


@pytest.mark.parametrize("mode", ["missing", "conflict", "cycle"])
def test_dependencies_fail_atomically(project, tmp_path, mode):
    a = author(tmp_path, "example/a", requires=[{"id": "example/b", "version": "0.1.0"}])
    b = author(tmp_path, "example/b", version="0.2.0" if mode == "conflict" else "0.1.0",
               requires=[{"id": "example/a", "version": "0.1.0"}] if mode == "cycle" else [])
    before = (project / packs.LOCK).read_bytes()
    with pytest.raises(RuntimeBlocked):
        packs.install(project, [str(a)] if mode == "missing" else [str(a), str(b)])
    assert (project / packs.LOCK).read_bytes() == before


def test_pure_knowledge_and_scoped_policy_discovery(project, tmp_path):
    contents = [{"id": "guide", "type": "reference", "path": "guide.md"},
                {"id": "rules", "type": "policy", "path": "guide.md"}]
    path = author(tmp_path, contents=contents)
    packs.install(project, [str(path)])
    packs.bind(project, "example/project", ["src/**"], ["example/project::rules"], "component")
    discovery = packs.context(project, files=["docs/a.md"], capabilities=["unrelated"])
    assert "example/project::guide" in [v["id"] for v in discovery["excluded"]]
    assert "example/project::rules" in [v["id"] for v in discovery["resources"]]
    selected = packs.context(project, selected=["speckit/workflows::coding-lite"])
    assert selected["resources"][0]["content"].startswith("# A project")


def test_dry_run_no_scripts_and_unowned_file_preserved(project, tmp_path):
    path = author(tmp_path)
    (path / "install.py").write_text("raise Exception('must not execute')")
    before = (project / packs.LOCK).read_bytes()
    assert packs.install(project, [str(path)], dry_run=True)["status"] == "planned"
    assert before == (project / packs.LOCK).read_bytes()
    assert packs.install(project, [str(path)])["auto_run_scripts"] is False


@pytest.mark.parametrize("path", ["../outside", "C:/Windows/file", "/root", "a/../../b", "a\\..\\b"])
def test_unsafe_pack_paths_are_rejected(tmp_path, path):
    pack = author(tmp_path, contents=[{"id": "bad", "type": "reference", "path": path}])
    with pytest.raises(RuntimeBlocked):
        packs.validate_pack(pack)


def test_unpinned_git_source_is_rejected(project):
    with pytest.raises(RuntimeBlocked, match="full-40"):
        packs.install(project, ["git+https://example.test/repo.git@main"])


def test_pinned_git_source_and_cache_restore(project, tmp_path):
    path = author(tmp_path)
    for argv in [["git", "init", str(path)], ["git", "-C", str(path), "add", "."],
                 ["git", "-C", str(path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-m", "fixture"]]:
        subprocess.run(argv, capture_output=True, check=True)
    revision = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    packs.install(project, ["git+" + path.as_posix() + "@" + revision])
    entry = next(v for v in packs.locked(project)["packs"] if v["id"] == "example/project")
    cache = (project / entry["path"]).resolve()
    assert cache.is_relative_to(project.resolve())
    shutil.rmtree(cache)
    assert packs.restore(project)["status"] == "ok"
    assert packs.locked(project)["packs"]


def test_mcp_is_descriptor_not_connection(project, tmp_path):
    path = author(tmp_path, contents=[{"id": "browser", "type": "mcp", "path": "guide.md"}])
    packs.install(project, [str(path)])
    resource = packs.context(project, selected=["example/project::browser"])["resources"][0]
    assert resource["compatibility_status"]["status"] == "needs-connection-verification"
    assert not (project / ".codex").exists()


def test_actual_fail_fix_pass_and_human_pending(project):
    identity = begin(project, flags={"changes_code": True})
    failure = run(project, identity)
    assert failure["status"] == "failed"
    with pytest.raises(RuntimeBlocked, match="did not pass"):
        review(project, identity, failure["evidence"]["id"])
    (project / "calc.py").write_text("def add(a,b):\n    return a+b\n")
    success = run(project, identity)
    review(project, identity, success["evidence"]["id"])
    disposition(project, identity)
    delivered = tasks.finish(project, identity)
    assert delivered["status"] == "delivered-awaiting-human"
    assert delivered["human_acceptance"] == "pending"
    journal = tasks._events(project, identity)
    assert any(v["payload"].get("result") == "failed" for v in journal)
    assert (project / delivered["report"]).is_file()


@pytest.mark.parametrize("status", ["blocked", "failed", "error", "incomplete"])
def test_zero_exit_negative_json_never_passes(project, status):
    identity = begin(project)
    result = run(project, identity, "print(" + repr(json.dumps({"status": status})) + ")")
    assert result["evidence"]["exit_code"] == 0
    assert result["status"] in {"failed", "blocked"}
    with pytest.raises(RuntimeBlocked):
        review(project, identity, result["evidence"]["id"])


def test_structured_mode_rejects_non_json(project):
    identity = begin(project)
    assert run(project, identity, "print('ok')", structured=True)["status"] == "failed"


def test_timeout_and_execution_failure_are_captured(project):
    identity = begin(project)
    result = run(project, identity, "import time; time.sleep(2)", timeout_seconds=0.03)
    assert result["status"] == "blocked"
    assert read_json(project / result["evidence"]["artifact"])["timed_out"]
    failure = tasks.run_check(project, identity, {"argv": ["missing-speckit-fixture-command"], "requirements": ["R1"]})
    assert failure["status"] == "failed"


def test_changed_source_invalidates_ai_and_execution(project):
    identity = begin(project)
    receipt = run(project, identity, "assert 2+3==5")
    review(project, identity, receipt["evidence"]["id"])
    disposition(project, identity)
    (project / "calc.py").write_text("changed source")
    assert tasks.inspect(project, identity)["ai_applies_to_current_source"] is False
    with pytest.raises(RuntimeBlocked, match="stale|current"):
        tasks.finish(project, identity)


def test_source_mutation_during_check_is_not_proof(project):
    identity = begin(project)
    result = run(project, identity, "from pathlib import Path; Path('calc.py').write_text('changed')")
    assert result["status"] == "blocked"
    assert result["evidence"]["source_changed_during_run"]


def test_evidence_artifact_tamper_is_detected(project):
    identity = begin(project)
    receipt = run(project, identity, "assert True")
    (project / receipt["evidence"]["artifact"]).write_text("tampered")
    with pytest.raises(RuntimeBlocked, match="modified-artifact"):
        review(project, identity, receipt["evidence"]["id"])


def test_manual_execution_receipt_is_rejected(project):
    identity = begin(project)
    with pytest.raises(RuntimeBlocked, match="runner evidence"):
        tasks.record(project, identity, "evidence.captured", {"result": "passed"})
    with pytest.raises(RuntimeBlocked, match="task run"):
        tasks.record(project, identity, "evidence.added", {"kind": "test", "origin": "agent-authored", "path": "calc.py", "requirements": ["R1"]})


@pytest.mark.parametrize("origin", ["host-auto", "agent-assumption", "unknown"])
def test_nonhuman_answer_cannot_approve_required_decision(project, origin):
    identity = begin(project)
    tasks.record(project, identity, "clarification.recorded", {"status": "answered", "questions": [
        {"id": "Q1", "question": "Delete existing data?", "answer": "yes", "answer_origin": origin, "requires_human": True}]})
    tasks.record(project, identity, "contract.recorded", {"files": ["calc.py"], "requirements": [{"id": "R1", "criterion": "reviewed scope", "evidence_kinds": ["test"]}]})
    assert "human-decision-not-established" in tasks.check(project, identity, "contract")["blockers"]


def test_automatic_human_acceptance_is_rejected(project):
    identity = begin(project)
    with pytest.raises(RuntimeBlocked, match="actual human"):
        tasks.record(project, identity, "human.recorded", {"status": "passed", "origin": "host-auto", "source_ref": "auto", "quote": "yes"})


def test_synthetic_human_acceptance_closes_exact_delivery(project):
    identity = begin(project)
    receipt = run(project, identity, "assert True")
    review(project, identity, receipt["evidence"]["id"])
    disposition(project, identity)
    tasks.record(project, identity, "human.recorded", {"status": "passed", "origin": "human", "source_ref": "fixture:synthetic-human", "quote": "Synthetic acceptance fixture"})
    assert tasks.finish(project, identity)["status"] == "closed"


def test_amendment_invalidates_old_decisions(project):
    identity = begin(project)
    tasks.record(project, identity, "request.amended", {"text": "Also support decimals", "reason": "Scope extension", "source_ref": "fixture:steering"})
    state = tasks.inspect(project, identity)
    assert state["request"]["revision"] == 2
    assert state["contract"] is None and state["workflow"] is None
    assert tasks._events(project, identity)[0]["payload"]["request"]["text"].endswith("addition")


def test_journal_integrity_and_projection_rebuild(project):
    identity = begin(project)
    projection = project / f".specify/tasks/{identity}/task.json"
    projection.write_text('{"status":"closed"}')
    assert tasks.inspect(project, identity)["status"] == "active"
    journal = projection.with_name("events.jsonl")
    content = journal.read_text().replace("Synthetic request", "Changed request", 1)
    journal.write_text(content)
    with pytest.raises(RuntimeBlocked, match="integrity"):
        tasks.inspect(project, identity)


def test_diagnosis_accepts_observed_failure_without_claiming_test_pass(project):
    identity = begin(project, "speckit/workflows::investigation", "diagnostic", observed=True)
    failed_probe = run(project, identity, "raise RuntimeError('missing config')", kind="diagnostic")
    review(project, identity, failed_probe["evidence"]["id"])
    disposition(project, identity)
    result = tasks.finish(project, identity)
    assert result["status"] == "closed" and result["human_acceptance"] == "not-required"
    assert tasks.inspect(project, identity)["evidence"][0]["result"] == "failed"


def test_ui_gate_rejects_authored_screenshot(project):
    identity = begin(project, evidence_kind="screenshot", flags={"changes_visible_ui": True})
    (project / "synthetic.png").write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lfoAAAAASUVORK5CYII="))
    imported = tasks.record(project, identity, "evidence.added", {"kind": "screenshot", "origin": "agent-authored", "path": "synthetic.png", "requirements": ["R1"], "result": "passed"})
    with pytest.raises(RuntimeBlocked, match="screenshot evidence"):
        review(project, identity, imported["evidence"][-1]["id"])


def test_registered_check_cannot_be_replaced(project, tmp_path):
    path = author(tmp_path, contents=[{"id": "required", "type": "check", "path": "check.yml"}])
    (path / "check.yml").write_bytes(yaml_bytes({"argv": [sys.executable, "-c", "raise SystemExit(2)"]}))
    packs.install(project, [str(path)])
    identity = begin(project)
    with pytest.raises(RuntimeBlocked, match="cannot be replaced"):
        tasks.run_check(project, identity, {"check_resource": "example/project::required", "argv": [sys.executable, "-c", "pass"], "requirements": ["R1"]})
    receipt = tasks.run_check(project, identity, {"check_resource": "example/project::required", "requirements": ["R1"]})
    assert receipt["status"] == "failed" and receipt["evidence"]["exit_code"] == 2


def test_stop_guard_is_bounded_and_human_wait_does_not_continue(project):
    identity = begin(project)
    assert tasks.guard(project, identity)["decision"] == "continue-once"
    assert tasks.guard(project, identity)["decision"] == "allow"
    receipt = run(project, identity, "assert True")
    review(project, identity, receipt["evidence"]["id"])
    disposition(project, identity)
    tasks.finish(project, identity)
    assert tasks.guard(project, identity)["decision"] == "allow"


def test_knowledge_bootstrap_does_not_invent_architecture(project):
    (project / "package.json").write_text('{"scripts":{"test":"node --test"}}')
    result = knowledge.bootstrap(project, "fixture/project", "knowledge/project")
    assert result["status"] == "candidate" and not result["automatically_installed"]
    manifest = packs.validate_pack(project / "knowledge/project")
    assert len(manifest["contents"]) == 3
    commands = read_json(project / "knowledge/project/run-debug.json")
    assert commands["commands"][0]["verification"].startswith("declared-only")
    assert "Unknowns" in (project / "knowledge/project/repository-map.md").read_text()


def test_legacy_import_preserves_and_does_not_promote_policy(project):
    legacy = project / "old-guides"
    legacy.mkdir()
    (legacy / "mandatory.md").write_text("Old commands and machine paths need review")
    before = tree_digest(legacy)
    result = knowledge.import_legacy(project, "old-guides", "fixture/legacy", "knowledge/imported")
    assert result["references"] == 1 and tree_digest(legacy) == before
    assert packs.validate_pack(project / "knowledge/imported")["contents"][0]["type"] == "reference"


def test_reviewed_local_release_and_immutable_install(project):
    knowledge.bootstrap(project, "fixture/knowledge", "knowledge/authored")
    path = project / "knowledge/authored"
    with pytest.raises(RuntimeBlocked, match="human review"):
        knowledge.release(project, "knowledge/authored", "minor", "Add guide", {"origin": "host-auto"})
    synthetic_review = {"status": "passed", "origin": "human", "source_ref": "fixture:synthetic-human-review",
                        "quote": "Synthetic review fixture", "content_sha256": tree_digest(path)}
    result = knowledge.release(project, "knowledge/authored", "minor", "Add verified guide", synthetic_review)
    assert result["version"] == "0.2.0" and not result["published_remote"]
    packs.install(project, [str(path)])
    assert tree_digest(path) == result["sha256"]
    (path / "repository-map.md").write_text("modified published version")
    with pytest.raises(RuntimeBlocked, match="Released pack was modified"):
        packs.install(project, [str(path)], replace=True)


def test_transaction_rolls_back_partial_writes(project, monkeypatch):
    (project / "first.txt").write_text("before")
    real = common.atomic_write
    failed = False
    def flaky(path, data):
        nonlocal failed
        if path.name == "second.txt" and not failed:
            failed = True
            raise OSError("synthetic disk failure")
        return real(path, data)
    monkeypatch.setattr(common, "atomic_write", flaky)
    with pytest.raises(OSError):
        common.transaction(project, {"first.txt": b"after", "second.txt": b"new"})
    assert (project / "first.txt").read_text() == "before"
    assert not (project / "second.txt").exists()
    assert any(read_json(path)["status"] == "rolled-back" for path in (project / ".specify/transactions").glob("*/transaction.json"))


def test_reinitialize_preserves_modified_cached_pack(project):
    path = project / packs.locked(project)["packs"][0]["path"] / "pack.yml"
    path.write_text("modified cache")
    with pytest.raises(RuntimeBlocked, match="content changed"):
        packs.initialize(project)
    assert path.read_text() == "modified cache"


def test_required_policy_cannot_be_removed_implicitly(project, tmp_path):
    path = author(tmp_path, contents=[{"id": "rules", "type": "policy", "path": "guide.md"}])
    packs.install(project, [str(path)])
    packs.bind(project, "example/project", [], ["example/project::rules"], "project")
    with pytest.raises(RuntimeBlocked, match="Unbind"):
        packs.remove(project, "example/project")
    packs.bind(project, "example/project", [], [], "project")
    assert packs.remove(project, "example/project")["status"] == "ok"


def test_package_update_invalidates_selected_workflow(project, tmp_path):
    path = author(tmp_path)
    packs.install(project, [str(path)])
    identity = begin(project)
    tasks.record(project, identity, "resources.selected", {"ids": ["example/project::guide"]})
    updated = author(tmp_path, version="0.2.0")
    packs.install(project, [str(updated)], replace=True)
    with pytest.raises(RuntimeBlocked, match="binding changed"):
        run(project, identity, "assert True")
    assert tasks.inspect(project, identity)["revalidation_blockers"]


def test_read_only_workflow_rejects_source_mutation(project):
    identity = begin(project, "speckit/workflows::investigation", "diagnostic", observed=True)
    (project / "calc.py").write_text("a product patch")
    result = tasks.check(project, identity)
    assert any("Read-only" in item for item in result["blockers"])


def test_action_executes_only_when_explicitly_invoked(project, tmp_path):
    path = author(tmp_path, contents=[{"id": "probe", "type": "action", "path": "probe.yml"}])
    (path / "probe.yml").write_bytes(yaml_bytes({"argv": [sys.executable, "-c", "print('observed target')"]}))
    packs.install(project, [str(path)])
    identity = begin(project, "speckit/workflows::investigation", "diagnostic", observed=True)
    receipt = tasks.run_check(project, identity, {"action_resource": "example/project::probe", "requirements": ["R1"]})
    assert receipt["status"] == "ok" and receipt["evidence"]["kind"] == "diagnostic"
    assert receipt["evidence"]["action_resource"] == "example/project::probe"


def test_custom_workflow_cannot_omit_code_validation(project, tmp_path):
    path = author(tmp_path, contents=[{"id": "custom", "type": "workflow", "path": "custom.yml"}])
    (path / "custom.yml").write_bytes(yaml_bytes({"schema_version": "2.0", "id": "example/project::custom", "version": "0.1.0",
        "phases": ["contract", "ai_accept"], "gates": []}))
    packs.install(project, [str(path)])
    identity = begin(project, "example/project::custom", "source", flags={"changes_code": True})
    result = tasks.record(project, identity, "evidence.added", {"kind": "source", "origin": "agent-authored", "path": "calc.py", "requirements": ["R1"], "result": "passed"})
    with pytest.raises(RuntimeBlocked, match="execution receipt"):
        review(project, identity, result["evidence"][-1]["id"])


def test_selected_mcp_needs_actual_connection_evidence(project, tmp_path):
    path = author(tmp_path, contents=[{"id": "browser", "type": "mcp", "path": "guide.md"}])
    packs.install(project, [str(path)])
    identity = begin(project, "speckit/workflows::investigation", "diagnostic", observed=True)
    tasks.record(project, identity, "resources.selected", {"ids": ["example/project::browser"]})
    receipt = run(project, identity, "assert True", kind="diagnostic")
    with pytest.raises(RuntimeBlocked, match="connection is not verified"):
        review(project, identity, receipt["evidence"]["id"])
    # Explicitly synthetic host-observation fixture; not a real browser claim.
    tasks.record(project, identity, "evidence.added", {"kind": "runtime", "path": "calc.py", "origin": "tool-observed", "tool_ref": "fixture:host-observation",
        "target": {"identity": "fixture:synthetic-browser"}, "capability_id": "example/project::browser", "requirements": ["R1"], "result": "passed"})
    assert review(project, identity, receipt["evidence"]["id"])["ai_acceptance"]["status"] == "passed"


def test_screenshot_cannot_be_a_text_file(project):
    identity = begin(project, evidence_kind="screenshot")
    with pytest.raises(RuntimeBlocked, match="image bytes"):
        tasks.record(project, identity, "evidence.added", {"kind": "screenshot", "origin": "tool-observed", "tool_ref": "fixture:observation", "path": "calc.py", "requirements": ["R1"]})


def test_runner_redacts_common_secret_values(project):
    identity = begin(project)
    secret = "synthetic-secret-123456"
    receipt = run(project, identity, "import os; print('token='+os.environ['TEST_API_TOKEN'])", environment={"TEST_API_TOKEN": secret})
    contents = (project / receipt["evidence"]["artifact"]).read_text()
    assert secret not in contents and "[REDACTED]" in contents


def test_interrupted_transaction_recovery_and_user_edit_protection(project):
    (project / "item.txt").write_text("before")
    txid = common.transaction(project, {"item.txt": b"after"})
    journal_path = project / f".specify/transactions/{txid}/transaction.json"
    journal = read_json(journal_path)
    journal["status"] = "prepared"  # Simulate termination after write, before commit marker.
    journal_path.write_bytes(json_bytes(journal))
    assert packs.doctor(project)["status"] == "blocked"
    assert common.recover_transaction(project, txid)["status"] == "planned"
    (project / "item.txt").write_text("subsequent user change")
    with pytest.raises(RuntimeBlocked, match="user change preserved"):
        common.recover_transaction(project, txid, apply=True)
    (project / "item.txt").write_bytes(b"after")
    assert common.recover_transaction(project, txid, apply=True)["status"] == "ok"
    assert (project / "item.txt").read_text() == "before"
    assert packs.doctor(project)["status"] == "ok"


def test_cli_doctor_self_check_and_upgrade_use_new_mode(project):
    runner = CliRunner()
    for args in [["pack", "doctor"], ["self", "check"], ["upgrade", "--dry-run"]]:
        result = runner.invoke(app, [*args, "--project-dir", str(project), "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["status"] in {"ok", "planned"}
    assert not (project / "ai").exists()


def test_source_backed_knowledge_reports_stale_manifests(project):
    (project / "package.json").write_text('{"scripts":{"test":"node --test"}}')
    knowledge.bootstrap(project, "fixture/source-map", "knowledge/project")
    packs.install(project, [str(project / "knowledge/project")])
    (project / "package.json").write_text('{"scripts":{"test":"node new-test.js"}}')
    selected = packs.context(project, selected=["fixture/source-map::map"])["resources"][0]
    assert selected["knowledge_status"]["status"] == "needs-revalidation"
    assert packs.doctor(project)["status"] == "warning"


def test_directory_snapshot_prunes_dependencies(project):
    dependency = project / "node_modules/heavy"
    dependency.mkdir(parents=True)
    (dependency / "ignored.py").write_text("dependency implementation")
    snapshot = tasks.snapshot(project, ["."])
    assert "calc.py" in snapshot["files"]
    assert not any("node_modules" in name or ".specify" in name for name in snapshot["files"])


@pytest.mark.parametrize("phases", [["ai_accept", "contract"], ["contract", "ai_accept", "unchecked-tail"]])
def test_workflow_order_cannot_hide_required_gates(phases):
    with pytest.raises(RuntimeBlocked, match="must start"):
        packs.validate_workflow({"schema_version": "2.0", "id": "fixture/workflow::bad", "phases": phases}, "fixture/workflow::bad", "1.0.0")
