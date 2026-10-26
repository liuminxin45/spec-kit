#!/usr/bin/env python3
"""Run synthetic requirements through the real CLI in isolated new projects.

No human acceptance is invented. The UI fixture stops at its observation gate
until a real browser/host artifact is supplied. Use --source for a source checkout
or --python <installed-wheel-python> to exercise a packaged distribution.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--source", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Choose a new output directory; existing artifacts are preserved")
    output.mkdir(parents=True)
    environment = os.environ.copy()
    if args.source:
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    else:
        environment.pop("PYTHONPATH", None)
    environment["PYTHONUTF8"] = "1"
    traces = []

    def cli(root, *argv, expected_code=0):
        process = subprocess.run([args.python, "-c", "from specify_cli import main; main()", *argv, "--json"],
                                 cwd=root, env=environment, capture_output=True, encoding="utf-8", timeout=120)
        traces.append({"project": root.name, "argv": list(argv), "exit_code": process.returncode,
                       "stdout": process.stdout, "stderr": process.stderr})
        if process.returncode != expected_code:
            raise RuntimeError(f"Unexpected CLI exit: {argv}\n{process.stdout}\n{process.stderr}")
        return json.loads(process.stdout)

    def payload(root, name, data):
        path = root / ".specify/inputs" / (name + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def event(root, task, kind, data, **options):
        return cli(root, "task", "record", task, "--event-file", payload(root, kind, {"type": kind, "payload": data}), **options)

    def setup(name, request, workflow, requirements, files, flags=None):
        root = output / name
        root.mkdir()
        cli(root, "init", "--here", "--mode", "codex-skill", "--no-git")
        request_file = root / ".specify/inputs/request.txt"
        request_file.parent.mkdir(parents=True, exist_ok=True)
        request_file.write_text(request, encoding="utf-8")
        task = cli(root, "task", "start", "--request-file", str(request_file), "--source-ref", "synthetic:requirement")["id"]
        event(root, task, "clarification.recorded", {"status": "not-needed", "reason": "Synthetic fixture specifies the expected scope and behavior"})
        event(root, task, "workflow.selected", {"id": workflow, "reason": "Selected for the concrete fixture scope and risk"})
        event(root, task, "contract.recorded", {"requirements": requirements, "files": files, "flags": flags or {}})
        cli(root, "task", "check", task, "--phase", "contract")
        return root, task

    def accept(root, task, evidence, requirements):
        event(root, task, "ai.reviewed", {"status": "passed", "summary": "Synthetic requirement verified with actual CLI artifacts",
            "criteria": [{"id": requirement["id"], "result": "passed", "reason": requirement["criterion"], "evidence": evidence} for requirement in requirements]})
        event(root, task, "knowledge.recorded", {"status": "none", "reason": "Synthetic fixture; no production project knowledge to promote"})
        return cli(root, "task", "finish", task)

    results = []
    requirements = [{"id": "sum", "criterion": "Addition returns 5 for 2+3", "evidence_kinds": ["test"]},
                    {"id": "negative", "criterion": "Negative operands remain supported", "evidence_kinds": ["test"]}]
    root, task = setup("bugfix", "Fix addition while preserving negative operands.", "speckit/workflows::coding-lite", requirements,
                       ["calculator.py", "test_calculator.py"], {"changes_code": True})
    (root / "calculator.py").write_text("def add(a,b):\n    return a-b\n")
    (root / "test_calculator.py").write_text("import unittest\nfrom calculator import add\nclass Addition(unittest.TestCase):\n    def test_sum(self): self.assertEqual(add(2,3),5)\n    def test_negative(self): self.assertEqual(add(-2,-3),-5)\n")
    command = {"argv": [args.python, "-m", "unittest", "-v"], "requirements": ["sum", "negative"], "kind": "test"}
    command_file = payload(root, "command", command)
    failed = cli(root, "task", "run", task, "--command-file", command_file, expected_code=1)
    assert failed["status"] == "failed"
    (root / "calculator.py").write_text("def add(a,b):\n    return a+b\n")
    passed = cli(root, "task", "run", task, "--command-file", command_file)
    result = accept(root, task, [passed["evidence"]["id"]], requirements)
    assert result["status"] == "delivered-awaiting-human" and result["human_acceptance"] == "pending"
    results.append({"scenario": "bugfix", "task": task, "failure_receipt_retained": True, **result})

    requirements = [{"id": "cause", "criterion": "Missing endpoint is identified by an actual diagnostic", "evidence_kinds": ["diagnostic"], "evidence_status": "observed"}]
    root, task = setup("investigation", "Explain startup failure without modifying application code.", "speckit/workflows::investigation", requirements, ["settings.json"])
    (root / "settings.json").write_text('{"port":8080}')
    event(root, task, "contract.recorded", {"requirements": requirements, "files": ["settings.json"], "flags": {}})
    script = "import json; c=json.load(open('settings.json')); print(json.dumps({'status':'failed','cause':'missing endpoint','has_endpoint':'endpoint' in c})); raise SystemExit(2)"
    probe = cli(root, "task", "run", task, "--command-file", payload(root, "probe", {"argv": [args.python, "-c", script], "kind": "diagnostic", "requirements": ["cause"]}), expected_code=1)
    assert probe["evidence"]["exit_code"] == 2
    result = accept(root, task, [probe["evidence"]["id"]], requirements)
    assert result["status"] == "closed"
    results.append({"scenario": "investigation", "probe_really_failed": True, **result})

    requirements = [{"id": "map", "criterion": "Map identifies the actual manifest and unknown ownership", "evidence_kinds": ["check"]}]
    root, task = setup("knowledge", "Generate a repository map and declared debug commands for a new project.", "speckit/knowledge::bootstrap", requirements,
                       ["package.json", "knowledge/project"])
    (root / "package.json").write_text('{"name":"smoke-app","scripts":{"dev":"node server.js"}}')
    generated = cli(root, "pack", "bootstrap", "--id", "fixture/project", "--output", "knowledge/project")
    assert generated["status"] == "candidate"
    script = "from pathlib import Path; import json; p=Path('knowledge/project'); assert 'package.json' in (p/'repository-map.md').read_text(); assert 'Unknowns' in (p/'repository-map.md').read_text(); assert json.loads((p/'run-debug.json').read_text())['commands'][0]['declared_command']=='node server.js'"
    receipt = cli(root, "task", "run", task, "--command-file", payload(root, "verify-map", {"argv": [args.python, "-c", script], "kind": "check", "requirements": ["map"]}))
    event(root, task, "ai.reviewed", {"status": "passed", "summary": "Generated actual manifest map and labeled unknown facts", "criteria": [
        {"id": "map", "result": "passed", "reason": "Real filesystem assertions passed", "evidence": [receipt["evidence"]["id"]]}]})
    event(root, task, "knowledge.recorded", {"status": "candidate", "path": "knowledge/project/repository-map.md", "reason": "Generated source-backed candidate; human review pending"})
    result = cli(root, "task", "finish", task)
    assert result["status"] == "delivered-awaiting-human"
    results.append({"scenario": "knowledge-bootstrap", **result})

    requirements = [{"id": "counter", "criterion": "Clicking Add increments the visible count from 0 to 1", "evidence_kinds": ["screenshot", "interaction"]}]
    root, task = setup("browser-ui", "Add a working counter button and verify its rendered interaction.", "speckit/workflows::coding-lite", requirements,
                       ["index.html"], {"changes_visible_ui": True})
    (root / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>Spec Kit Counter Test</title><style>body{font:24px system-ui;margin:48px}button{font:inherit;padding:12px 24px}output{display:block;margin:24px 0}</style><h1>Counter</h1><output id="count">0</output><button id="add" onclick="count.value=Number(count.value)+1">Add</button>')
    blocked = cli(root, "task", "check", task, expected_code=1)
    assert blocked["status"] == "blocked"
    results.append({"scenario": "browser-ui", "task": task, "status": "awaiting-real-browser-evidence", "gate_blocked_without_evidence": True, "project": str(root)})

    (output / "cli-trace.json").write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"status": "ok", "synthetic_requirements": True, "human_acceptance_fabricated": False, "scenarios": results}
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
