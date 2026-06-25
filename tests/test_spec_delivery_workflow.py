import json
import os
import re
import subprocess
from pathlib import Path

import yaml

from specify_cli.integrations.base import IntegrationBase


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def compact_text(text: str) -> str:
    return " ".join(text.split())


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def write_retrospective_artifacts(repo: Path, branch: str = "feature") -> None:
    feature_dir = repo / "specs" / branch
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "workflow-record.md").write_text("# Workflow Record\n", encoding="utf-8")
    (feature_dir / "improvement-candidates.md").write_text("# Improvement Candidates\n", encoding="utf-8")


def load_workflow() -> dict:
    return yaml.safe_load(read_text("workflows/speckit/workflow.yml"))


def read_wrapper_text(name: str) -> str:
    wrapper_path = REPO_ROOT / "scripts" / "powershell" / name
    assert wrapper_path.is_file(), f"Spec Kit wrapper is missing: {wrapper_path}"
    return wrapper_path.read_text(encoding="utf-8")


def test_workflow_uses_lean_default_chain_with_conditional_stages():
    workflow_doc = load_workflow()

    integration = workflow_doc["inputs"]["integration"]
    assert integration["default"] == "codex"
    assert integration["enum"] == ["codex"]
    assert "fixed to Codex skills" in integration["prompt"]

    context_policy = workflow_doc["context_policy"]
    assert "AGENTS.md" in context_policy["default"]
    assert ".specify/memory/repository-map.md" in context_policy["default"]
    assert "ai/knowledge/index.yml or select-knowledge first; ai/knowledge/* only when a selected durable guide is needed" in context_policy["load_on_demand"]
    assert "TEAM-README.md" in context_policy["never_default"]

    risk_level = workflow_doc["inputs"]["risk_level"]
    assert risk_level["default"] == "medium"
    assert risk_level["enum"] == ["low", "medium", "high", "blocked"]

    delivery_profile = workflow_doc["inputs"]["delivery_profile"]
    assert delivery_profile["default"] == "auto"
    assert delivery_profile["enum"] == [
        "auto",
        "micro-fix",
        "standard-bugfix",
        "full-sdd",
        "blocked-investigation",
        "validation-only",
    ]

    steps = workflow_doc["steps"]
    assert [step["id"] for step in steps] == [
        "intake",
        "specify",
        "plan",
        "validation",
        "fact-layer",
        "tasks",
        "analyze",
        "checklist",
        "implement",
        "acceptance",
        "human-acceptance",
        "retrospective",
        "commit",
        "post-commit-self-check",
        "rubric-score",
        "complete-branch",
    ]

    by_id = {step["id"]: step for step in steps}
    assert "requires_confirmation" not in by_id["acceptance"]
    assert by_id["human-acceptance"]["type"] == "gate"
    assert by_id["human-acceptance"]["skip_profiles"] == ["validation-only", "blocked-investigation"]
    assert "requires_confirmation" not in by_id["commit"]
    assert "requires_confirmation" not in by_id["complete-branch"]
    assert "exactly one" in by_id["post-commit-self-check"]["input"]["args"]
    assert "validate-rubric-score" in by_id["rubric-score"]["input"]["args"]
    assert by_id["validation"]["profiles"] == ["validation-only"]
    assert by_id["fact-layer"]["profiles"] == ["blocked-investigation"]
    assert by_id["analyze"]["profiles"] == ["standard-bugfix", "full-sdd"]
    assert by_id["implement"]["skip_profiles"] == ["validation-only", "blocked-investigation"]
    assert "keep" in by_id["complete-branch"]["input"]["args"].lower()
    assert "spec branch" in by_id["complete-branch"]["input"]["args"].lower()
    assert "do not push" in by_id["complete-branch"]["input"]["args"].lower()
    assert "cherry-pick" in by_id["complete-branch"]["input"]["args"].lower()
    assert "merge commits" in by_id["complete-branch"]["input"]["args"].lower()

    conditional = workflow_doc["conditional_stages"]
    for stage in [
        "clarify",
        "tasks",
        "analyze",
        "checklist",
        "fact-layer",
        "validation",
        "simplify",
        "test-hardening",
        "promote-lessons",
    ]:
        assert stage in conditional
    assert "retrospective" not in conditional

    combined_args = "\n".join(step["input"]["args"] for step in steps if "input" in step)
    assert "delivery_profile" in combined_args
    assert "micro-fix" in combined_args
    assert "blocked-investigation" in combined_args
    assert "validation" in workflow_doc["conditional_stages"]


def test_conditional_stage_descriptions_do_not_weaken_hard_gates():
    workflow_doc = load_workflow()
    conditional = workflow_doc["conditional_stages"]
    steps = workflow_doc["steps"]
    combined_args = "\n".join(step["input"]["args"] for step in steps if "input" in step)

    assert conditional["analyze"].startswith("Required before implementation for standard-bugfix and full-sdd")
    assert conditional["checklist"].startswith("Required before implementation for full-sdd")
    assert "optional only for micro-fix" in conditional["analyze"]
    assert "runtime DOM/CSS/computed style/box metrics" in combined_args
    assert "installed runtime plugin directories" in combined_args

    stage_gate_policy = workflow_doc["stage_gate_policy"]
    assert stage_gate_policy["next_stage_routing"]["full-sdd"]["before_implement"].startswith(
        "tasks -> analyze -> checklist"
    )
    assert stage_gate_policy["hard_implementation_preflight"]["command"] == "validate-feature-artifacts"
    assert stage_gate_policy["generated_context_drift"]["command"] == "validate-generated-context"
    assert stage_gate_policy["knowledge_index_drift"]["command"] == "validate-knowledge-index"


def test_new_command_templates_define_delivery_stages():
    command_expectations = {
        "templates/commands/micro-fix.md": [
            "micro-fix.md",
            "Root Cause Evidence",
            "Acceptance Lite",
            "Do not search the whole `workspace_root`",
        ],
        "templates/commands/bounded-investigation.md": [
            "investigation.md",
            "Search scope",
            "Command budget",
            "Never default to scanning the whole `workspace_root`",
        ],
        "templates/commands/validation.md": [
            "validation.md",
            "evidence.md",
            "validation-only",
            "ai/templates/validation-template.md",
            "ai/templates/evidence-template.md",
            "Do not edit production code",
        ],
        "templates/commands/acceptance.md": [
            "acceptance.md",
            "acceptance-checklist.md",
            "用户确认",
            "验收通过",
        ],
        "templates/commands/simplify.md": [
            "code-simplifier",
            "不新增行为",
            "重跑",
        ],
        "templates/commands/test-hardening.md": [
            "optional",
            "额外测试强化",
            "必需测试",
        ],
        "templates/commands/test-plan.md": [
            "API/E2E",
            "approved-by-ai-obvious",
            "needs-human-review",
            "select-knowledge",
            "测试用例计划",
        ],
        "templates/commands/quality-vision.md": [
            "quality-vision.md",
            "UI Baseline",
            "needs-human-baseline",
            "owner-approved-n/a",
        ],
        "templates/commands/acceptance-rubric.md": [
            "acceptance-rubric.md",
            "Essential",
            "Pitfall",
            "L1 功能与需求闭合",
            "L5 上下文与自动化治理",
        ],
        "templates/commands/ai-self-acceptance.md": [
            "AI Self-Acceptance",
            "acceptance-rubric.md",
            "PASS",
            "FAIL",
            "BLOCKED",
            "CDP",
            "console",
            "logs",
        ],
        "templates/commands/retrospective.md": [
            "workflow-record.md",
            "improvement-candidates.md",
            "用户验收通过",
            "不自动修改 spec-kit",
            "Existing Constraint Audit",
            "Team knowledge candidates",
            "高级模型上下文效率复盘",
        ],
        "templates/commands/promote-lessons.md": [
            "improvement-candidates.md",
            "promotion-report.md",
            "approved",
            "spec-kit",
            "TEAM-README",
            ".specify/memory",
            "高级模型上下文收益",
        ],
        "templates/commands/fact-layer.md": [
            "fact-pack.md",
            "fact-pack-template.md",
            "<system-temp>/SDKLog",
            "<system-temp>/ServiceBridgeLog",
            "chrome-devtools",
            "computed style",
            "box metrics",
        ],
        "templates/commands/commit.md": [
            "validate-feature-artifacts",
            "validate-test-plan",
            "validate-ai-self-acceptance",
            "validate-plugin-package",
            "commit-message",
            "68 display columns",
            "spec 文档是否随代码提交",
            "retrospective.status",
            "不 push",
            "speckit.post-commit-self-check",
        ],
        "templates/commands/post-commit-self-check.md": [
            "exactly one",
            "post-commit self-check",
            "amend the commit once",
            "speckit.rubric-score",
        ],
        "templates/commands/rubric-score.md": [
            "L1 功能与需求闭合",
            "L2 验证与证据",
            "validate-rubric-score",
            "Weighted Score",
            "complete-branch",
        ],
        "templates/commands/complete-branch.md": [
            "post-commit-self-check",
            "validate-rubric-score",
            "preflight",
            "master",
            "cherry-pick",
            "保留 spec branch",
            "不删除",
            "不 push",
        ],
    }

    for path, expected_phrases in command_expectations.items():
        text = read_text(path)
        for phrase in expected_phrases:
            assert phrase in text


def test_retrospective_stage_is_mandatory_before_commit_and_completion():
    workflow_doc = load_workflow()
    step_ids = [step["id"] for step in workflow_doc["steps"]]
    cli = read_text("src/specify_cli/__init__.py")

    assert "retrospective" in step_ids
    assert "retrospective" not in workflow_doc["conditional_stages"]
    assert step_ids.index("retrospective") < step_ids.index("commit")
    assert step_ids.index("commit") < step_ids.index("post-commit-self-check")
    assert step_ids.index("post-commit-self-check") < step_ids.index("rubric-score")
    assert step_ids.index("rubric-score") < step_ids.index("complete-branch")

    commit_args = next(step for step in workflow_doc["steps"] if step["id"] == "commit")["input"]["args"]
    complete_args = next(step for step in workflow_doc["steps"] if step["id"] == "complete-branch")["input"]["args"]
    retrospective_template = read_text("templates/commands/retrospective.md")

    for text in [retrospective_template]:
        assert "workflow-record.md" in text
        assert "improvement-candidates.md" in text
        assert "关键用户输入" in text
        assert "AI 输出与动作链" in text
        assert "错误、返工" in text
        assert "验证证据" in text

    assert "不自动修改 spec-kit" in retrospective_template
    assert "human approval" in " ".join(retrospective_template.lower().split())
    assert "workflow-record.md" in commit_args
    assert "improvement-candidates.md" in commit_args
    assert "retrospective/留痕" in commit_args
    assert "retrospective/留痕" in complete_args
    assert "speckit.retrospective" in read_text("templates/commands/commit.md")
    assert "validate-feature-artifacts" in read_text("templates/commands/commit.md")
    assert "retrospective.status" in read_text("templates/commands/commit.md")
    assert "workflow-state.json" in read_text("templates/commands/commit.md")
    assert "Retrospective and lesson promotion are optional" not in read_text("templates/commands/commit.md")
    complete_template = read_text("templates/commands/complete-branch.md")
    powershell_script = read_text("scripts/powershell/complete-spec-branches.ps1")
    for text in [complete_template, powershell_script]:
        assert "workflow-record.md" in text
        assert "improvement-candidates.md" in text
    assert "retrospective_gate" in powershell_script
    step_ids = [step["id"] for step in workflow_doc["steps"]]
    assert "retrospective" in step_ids
    assert step_ids.index("retrospective") < step_ids.index("commit")
    assert step_ids.index("commit") < step_ids.index("post-commit-self-check")
    assert step_ids.index("post-commit-self-check") < step_ids.index("rubric-score")
    assert step_ids.index("rubric-score") < step_ids.index("complete-branch")
    assert "promote-lessons" not in step_ids
    by_id = {step["id"]: step for step in workflow_doc["steps"]}
    assert by_id["analyze"]["profiles"] == ["standard-bugfix", "full-sdd"]
    assert by_id["tasks"]["profiles"] == ["full-sdd"]
    assert by_id["checklist"]["profiles"] == ["full-sdd"]
    assert "run only when risk or evidence requires them" not in cli


def test_stage_handoffs_acceptance_retrospective_and_commit_are_rule_driven():
    workflow_doc = load_workflow()
    workflow_args = compact_text("\n".join(step["input"]["args"] for step in workflow_doc["steps"] if "input" in step))
    implement = compact_text(read_text("templates/commands/implement.md"))
    acceptance = compact_text(read_text("templates/commands/acceptance.md"))
    simplify = compact_text(read_text("templates/commands/simplify.md"))
    retrospective = compact_text(read_text("templates/commands/retrospective.md"))
    commit = compact_text(read_text("templates/commands/commit.md"))

    task_routing = read_text("templates/ai/workflows/task-routing.md")
    assert "Implementation completion gate" in implement
    assert "do not continue to `speckit.acceptance` while AI-owned validation is still pending" in implement
    assert "Stage Continuation" in task_routing
    assert "automatic_stage_continuation" in yaml.safe_load(read_text("workflows/speckit/workflow.yml"))["stage_gate_policy"]
    assert "execution_contract" in yaml.safe_load(read_text("workflows/speckit/workflow.yml"))["stage_gate_policy"]["automatic_stage_continuation"]
    assert "Auto-continue is a stage contract" in task_routing
    assert "A plain completion summary" in task_routing
    assert "自动进入" in task_routing
    assert "next_required_human_action" in read_text("templates/checklist-template.md")
    assert "before asking for `用户确认 验收通过`" in acceptance
    assert "pre-confirmed acceptance" in acceptance
    assert "Accepted Gaps" in acceptance
    assert "Accepted Gaps" in retrospective
    assert "If no product code changed during simplify" in simplify
    assert "reuse the existing user acceptance" in simplify
    assert "commit automatically" in commit
    assert "Show the scope first" in commit
    assert "ignored by `.gitignore`" in commit
    assert "Never force-add a whole ignored directory" in read_text("templates/commands/commit.md")
    assert "prefer scripts, deterministic checks, generated facts, or rule-based gates" in retrospective
    assert "do not outsource a deterministic check to LLM judgment" in retrospective
    assert "Existing Constraint Audit" in retrospective
    assert "AI workflow self-check" in retrospective
    assert "Team knowledge candidates" in retrospective
    assert "高级模型上下文效率复盘" in retrospective
    assert "最小决策证据包" in retrospective
    assert "nearly deterministic" in retrospective
    assert "retrospective.status" in retrospective
    assert "ensure-host-cdp" in implement
    assert "CDP host recovery ladder" in implement
    assert "post-commit self-check" in workflow_args
    assert "validate-rubric-score" in workflow_args
    assert "automation-first" in workflow_args


def test_native_runtime_proto_and_ai_acceptance_gates_are_enforced():
    workflow_doc = load_workflow()
    stage_policy = workflow_doc["stage_gate_policy"]
    workflow_args = compact_text("\n".join(step["input"]["args"] for step in workflow_doc["steps"] if "input" in step))
    implement = read_text("templates/commands/implement.md")
    acceptance = read_text("templates/commands/acceptance.md")
    plan = read_text("templates/commands/plan.md")
    validation_template = read_text("templates/ai/templates/validation-template.md")
    evidence_template = read_text("templates/ai/templates/evidence-template.md")
    routing = read_text("templates/ai/workflows/task-routing.md")
    build_notes = read_text("templates/ai/knowledge/build-and-package-notes.md")
    native_bridge = read_text("templates/ai/knowledge/domains/native-plugin-bridge.md")
    cdp = read_text("templates/ai/knowledge/domains/electron-host-cdp.md")

    for text in [implement, build_notes, native_bridge, routing]:
        assert "sync-native-runtime-artifacts" in text
        assert "validate-rpc-proto-bundle" in text

    assert "sync-native-runtime-artifacts" in workflow_args
    assert "Native Runtime Delivery Chain" in validation_template
    assert "AI Acceptance Result" in validation_template
    assert "E-NATIVE-001" in evidence_template
    assert "E-RPC-BUNDLE-001" in evidence_template
    assert "Minimal Decision Evidence Pack For Advanced Models" in evidence_template
    assert "AI acceptance `PASS`" in compact_text(acceptance)
    assert "Human acceptance is after AI-owned technical validation" in acceptance
    assert "Source Behavior Execution Map" in plan
    assert "Source Behavior Execution Map" in routing
    assert "safe process recovery" in cdp
    assert "Unknown owners are blockers" in build_notes
    assert "native_runtime_delivery_chain" in stage_policy
    assert stage_policy["native_runtime_delivery_chain"]["command"] == "sync-native-runtime-artifacts"
    assert "ai_acceptance_before_human_acceptance" in stage_policy
    assert "PASS" in stage_policy["ai_acceptance_before_human_acceptance"]["rule"]


def test_quality_vision_rubric_and_ai_self_acceptance_are_routed_on_demand():
    workflow_doc = load_workflow()
    routing = read_text("templates/ai/workflows/task-routing.md")
    skill_routing = read_text("templates/ai/workflows/skill-routing.yml")
    plan_template = read_text("templates/plan-template.md")
    quality_template = read_text("templates/quality-vision-template.md")
    rubric_template = read_text("templates/acceptance-rubric-template.md")
    implement = read_text("templates/commands/implement.md")
    acceptance = read_text("templates/commands/acceptance.md")
    validation_template = read_text("templates/ai/templates/validation-template.md")

    for phrase in [
        "speckit-quality-vision",
        "speckit-acceptance-rubric",
        "speckit-ai-self-acceptance",
    ]:
        assert phrase in skill_routing
        assert phrase in "\n".join(workflow_doc["context_policy"]["load_on_demand"])

    assert "quality-vision" in routing
    assert "acceptance-rubric.md" in routing
    assert "ai-self-acceptance" in routing
    assert "PASS is required before" in routing
    assert "Quality Vision Link" in plan_template
    assert "Acceptance Rubric Link" in plan_template
    assert "AI Self-Acceptance Contract" in plan_template
    assert "UI Baseline" in quality_template
    assert "needs-human-baseline" in quality_template
    assert "Essential" in rubric_template
    assert "Pitfall" in rubric_template
    assert "Actual Workflow Rubric Audit" in rubric_template
    assert "Hard gates" in rubric_template
    assert "Complete-branch allowed" in rubric_template
    for layer in ["L1 功能与需求闭合", "L2 验证与证据", "L3 工作流阶段合规", "L4 交付与仓库状态", "L5 上下文与自动化治理"]:
        assert layer in rubric_template
        assert layer in validation_template
    assert "Final Rubric Score (post-commit self-check only)" in validation_template
    assert "Overall Weighted Score" in validation_template
    assert "speckit-ai-self-acceptance" in implement
    assert "rubric judgment" in acceptance
    assert workflow_doc["stage_gate_policy"]["ai_self_acceptance_gate"]["command"] == "speckit-ai-self-acceptance"


def test_stage_progress_displays_include_one_sentence_objectives():
    routing = read_text("templates/ai/workflows/task-routing.md")

    assert "## Stage Progress Displays" in routing
    assert "`阶段`, `状态`, and `阶段目标`" in routing
    assert "speckit-analyze" in routing
    assert "Check spec/plan/task consistency, blockers, and implementation readiness." in routing
    assert "stage progress table with `阶段`, `状态`, and one-sentence `阶段目标`" in routing


def test_agents_template_does_not_force_plan_into_default_context():
    agents = read_text("templates/agents-template.md")

    assert "read the current plan only" in agents
    assert "when the selected workflow path requires `plan.md`" in agents
    assert "read the current plan\n" not in agents


def test_knowledge_layer_is_indexed_deterministic_and_load_on_demand():
    agents = read_text("templates/agents-template.md")
    routing = read_text("templates/ai/workflows/task-routing.md")
    rules = read_text("templates/ai/rules/ai-coding-rules.md")
    plan = read_text("templates/commands/plan.md")
    implement = read_text("templates/commands/implement.md")
    validation = read_text("templates/commands/validation.md")
    manifest = yaml.safe_load(read_text("templates/layer-manifest.yml"))
    workflow_doc = load_workflow()

    for text in [agents, routing, rules, plan, implement, validation]:
        assert "select-knowledge" in text
        assert "full-text/BM25 search" in text

    for text in [agents, routing, rules]:
        assert "validate-knowledge-index" in text
        assert "ai/knowledge/index.yml" in text

    assert manifest["policy"]["knowledge_routing"] == "deterministic-index, no-full-text-search"
    assert "knowledge" in manifest["read_strategies"]
    assert "Knowledge" in [layer["id"] for layer in manifest["layers"]]
    assert "validate-knowledge-index" in workflow_doc["stage_gate_policy"]["knowledge_index_drift"]["command"]


def test_agent_context_generator_does_not_force_plan_into_default_context():
    generic_section = IntegrationBase._build_context_section()
    plan_section = IntegrationBase._build_context_section("specs/001-demo/plan.md")

    assert "read the current plan only" in generic_section
    assert "when the selected workflow path requires `plan.md`" in generic_section
    assert "read the current plan\n" not in generic_section
    assert "Current plan: specs/001-demo/plan.md" in plan_section


def test_ai_rules_keep_retrospective_mandatory_and_promotion_optional():
    rules = read_text("templates/ai/rules/ai-coding-rules.md")

    assert "Retrospective/留痕 is mandatory before commit" in rules
    assert "Lesson promotion remains optional" in rules
    assert "Retrospective and lesson promotion are optional" not in rules


def test_stale_feature_state_does_not_drive_tooling_tasks():
    agents = read_text("templates/agents-template.md")
    routing = read_text("templates/ai/workflows/task-routing.md")
    workflow_doc = load_workflow()
    context_policy = "\n".join(workflow_doc["context_policy"]["default"])

    for text in [agents, routing, context_policy]:
        assert "current-feature" in text
    assert "stale/current-feature hint" in agents
    assert "spec-kit" in agents
    assert "do not apply stale feature risk flags" in routing


def test_templates_do_not_embed_machine_specific_paths():
    scanned_roots = [
        REPO_ROOT / "templates",
        REPO_ROOT / "workflows",
        REPO_ROOT / "checklist-rules",
    ]
    forbidden_patterns = [
        re.compile(r"[A-Za-z]:\\"),
        re.compile(r"(^|[\\/])Users[\\/][^\\/]+"),
    ]
    offenders = []

    for root in scanned_roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".yml", ".yaml", ".json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in forbidden_patterns:
                if pattern.search(text):
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)} contains {pattern.pattern}"
                    )

    assert offenders == []


def test_host_frontend_delivery_chain_and_cdp_target_gate_are_enforced():
    workflow_doc = load_workflow()
    workflow_args = compact_text("\n".join(step["input"]["args"] for step in workflow_doc["steps"] if "input" in step))
    stage_policy = workflow_doc["stage_gate_policy"]
    implement = read_text("templates/commands/implement.md")
    validation = read_text("templates/commands/validation.md")
    validation_template = read_text("templates/ai/templates/validation-template.md")
    evidence_template = read_text("templates/ai/templates/evidence-template.md")
    routing = read_text("templates/ai/workflows/task-routing.md")
    rules = read_text("templates/ai/rules/ai-coding-rules.md")
    checklist = read_text("templates/checklist-template.md")
    common_rules = read_text("checklist-rules/common.yml")
    build_notes = read_text("templates/ai/knowledge/build-and-package-notes.md")
    repo_map = read_text("templates/repository-map-template.md")

    for text in [implement, validation, validation_template, workflow_args, routing, rules, common_rules, build_notes]:
        assert "source edit -> frontend build -> direct runtime replacement -> real host CDP verification" in compact_text(text)
    assert "final `.plugin` build/package evidence" in validation
    assert "All plugin source edits" in validation
    assert "validate-plugin-package" in implement
    assert "validate-plugin-package" in workflow_doc["stage_gate_policy"]["plugin_package_build"]["command"]
    assert "sync-ui-runtime-artifacts" in implement
    assert "ensure-host-cdp" in implement
    assert "ensure-host-cdp" in validation
    assert "CDP host recovery ladder" in implement
    assert "CDP host recovery ladder" in validation
    assert "removed stale" in implement.lower()
    assert "Implementation completion gate" in implement
    assert "宿主运行时验证待执行" in implement
    assert "do not continue to\n     `speckit.acceptance` while AI-owned validation is still pending" in implement
    assert "Removed stale runtime files" in validation_template
    assert "Runtime replacement removed stale count" in evidence_template
    assert "runtime replacement directory" in checklist

    for text in [implement, validation, routing, rules, build_notes, repo_map, checklist, common_rules]:
        assert "inspect-host-cdp-target" in text or "/json/list" in text
        assert "Plugin Workbench" in text
        assert "base-win.html" in text
        assert "devtools://" in text
        assert "webSocketDebuggerUrl" in text
    assert "hostapplication_cdp_target" in stage_policy
    assert "hostapplication_cdp_host_recovery" in stage_policy
    assert stage_policy["hostapplication_cdp_host_recovery"]["command"] == "ensure-host-cdp"
    assert "frontend_runtime_delivery_chain" in stage_policy
    assert "wrong-target / insufficient" in validation


def test_host_cdp_validation_saves_key_path_screenshot_artifacts():
    workflow_doc = load_workflow()
    stage_policy = workflow_doc["stage_gate_policy"]
    gate = read_text("templates/ai/workflows/gates/host-cdp.yml")
    validation = read_text("templates/commands/validation.md")
    ai_self_acceptance = read_text("templates/commands/ai-self-acceptance.md")
    acceptance = read_text("templates/commands/acceptance.md")
    retrospective = read_text("templates/commands/retrospective.md")
    evidence_template = read_text("templates/ai/templates/evidence-template.md")
    validation_template = read_text("templates/ai/templates/validation-template.md")
    cdp_knowledge = read_text("templates/ai/knowledge/domains/electron-host-cdp.md")
    routing = read_text("templates/ai/workflows/task-routing.md")
    agents = read_text("templates/agents-template.md")

    for text in [gate, validation, cdp_knowledge, routing]:
        assert "capture-cdp-screenshot" in text

    for text in [
        gate,
        validation,
        ai_self_acceptance,
        acceptance,
        retrospective,
        evidence_template,
        validation_template,
        cdp_knowledge,
        routing,
        agents,
    ]:
        assert "FEATURE_DIR/cdp-screenshots" in text

    for text in [
        gate,
        validation,
        ai_self_acceptance,
        acceptance,
        retrospective,
        validation_template,
        cdp_knowledge,
    ]:
        assert "screenshots-index.md" in text

    for text in [gate, validation, acceptance, cdp_knowledge, routing, agents]:
        assert "screenshot directory" in compact_text(text)

    assert "hostapplication_cdp_screenshots" in stage_policy
    assert stage_policy["hostapplication_cdp_screenshots"]["command"] == "capture-cdp-screenshot"
    assert "key-path screenshots" in stage_policy["hostapplication_cdp_screenshots"]["rule"]


def test_qt_source_behavior_map_is_installed_and_referenced_before_broad_search():
    qt_map = read_text("templates/ai/knowledge/qt-source-behavior-map.md")
    implement = read_text("templates/commands/implement.md")
    routing = read_text("templates/ai/workflows/task-routing.md")
    rules = read_text("templates/ai/rules/ai-coding-rules.md")
    checklist = read_text("templates/checklist-template.md")
    common_rules = read_text("checklist-rules/common.yml")

    assert "Qt Source Behavior Map" in qt_map
    assert "example device list / device tree" in qt_map
    for text in [implement, routing, rules, checklist, common_rules]:
        assert "qt-source-behavior-map.md" in text
    assert "before broad source search" in rules


def test_promote_lessons_stage_applies_only_approved_candidates_when_requested():
    workflow_doc = load_workflow()
    step_ids = [step["id"] for step in workflow_doc["steps"]]

    assert "promote-lessons" not in step_ids
    assert "promote-lessons" in workflow_doc["conditional_stages"]

    promote_template = read_text("templates/commands/promote-lessons.md")
    retrospective_template = read_text("templates/commands/retrospective.md")

    for text in [promote_template]:
        assert "improvement-candidates.md" in text
        assert "promotion-report.md" in text
        assert "approved" in text
        assert "pending" in text
        assert "spec-kit" in text
        assert "TEAM-README" in text
        assert ".specify/memory" in text
        assert "human approval" in text

    assert "continue to `speckit.commit`" in promote_template
    assert "Promotion edits long-lived governance files" in promote_template
    assert "Required next stage: `speckit.commit`" in promote_template
    assert "Required next stage: `speckit.complete-branch`" not in promote_template
    assert "pending | approved | rejected" in retrospective_template
    assert "approved promotion candidates" in read_text("templates/commands/commit.md")


def test_fact_layer_assets_and_rules_are_standardized():
    fact_command = read_text("templates/commands/fact-layer.md")
    fact_template = read_text("templates/fact-pack-template.md")
    plan = read_text("templates/commands/plan.md")
    implement = read_text("templates/commands/implement.md")
    checklist = read_text("templates/commands/checklist.md")
    investigation = read_text("templates/commands/bounded-investigation.md")
    retrospective = read_text("templates/commands/retrospective.md")
    readme = read_text("TEAM-README.md")

    for text in [fact_command, fact_template, plan, implement, checklist, investigation, retrospective]:
        assert "fact-pack.md" in text
        assert "speckit.fact-layer" in text
    assert "fact-pack.md" in readme

    for text in [fact_command, fact_template, implement, checklist, investigation, readme]:
        assert "<system-temp>/SDKLog" in text
        assert "<system-temp>/ServiceBridgeLog" in text
        assert "SDK_*.log" in text
        assert "ServiceBridge_*.log" in text

    for text in [fact_command, fact_template, plan, implement, checklist, investigation]:
        text_lower = text.lower()
        assert "chrome-devtools" in text_lower
        assert "computed style" in text_lower
        assert "box metrics" in text_lower
        assert "second same-class fix" in text_lower
    assert "Chrome DevTools" in readme

    assert "collect-fact-layer.ps1" in fact_command
    assert "Do not use MCP for log files" in fact_command
    assert "是否及时启用 fact-layer" in retrospective


def test_stage_gate_policy_blocks_full_sdd_from_skipping_analysis_and_checklist():
    workflow_doc = load_workflow()
    manifest = yaml.safe_load(read_text("templates/layer-manifest.yml"))
    routing = read_text("templates/ai/workflows/task-routing.md")
    rules = read_text("templates/ai/rules/ai-coding-rules.md")
    plan = read_text("templates/commands/plan.md")
    analyze = read_text("templates/commands/analyze.md")
    checklist = read_text("templates/commands/checklist.md")
    implement = read_text("templates/commands/implement.md")

    assert "stage_gates" in manifest
    full_sdd_gate = manifest["stage_gates"]["implement"]["full-sdd"]
    assert full_sdd_gate["required_prior_stages"] == ["tasks", "analyze", "checklist"]
    assert "analysis.md" in full_sdd_gate["required_artifacts"]
    assert "checklists/implementation-readiness.md" in full_sdd_gate["required_artifacts"]
    assert "analysis.md" in manifest["artifact_sets"]["full-sdd-implement"]
    assert "checklists/implementation-readiness.md" in manifest["artifact_sets"]["full-sdd-implement"]

    assert "tasks -> analyze -> checklist" in workflow_doc["stage_gate_policy"]["next_stage_routing"]["full-sdd"]["before_implement"]
    for text in [routing, rules, implement]:
        assert "analysis.md" in text
        assert "checklists/implementation-readiness.md" in text

    assert "standard-bugfix" in plan
    assert "complete `Implementation Slices`" in plan
    assert "Write the prioritized" in analyze
    assert "FEATURE_DIR/analysis.md" in analyze
    assert "read_strategies.analyze" in analyze
    assert "implementation preflight checks this file" in " ".join(checklist.split())
    assert "validate-feature-artifacts" in implement


def test_analyze_and_checklist_use_manifest_section_first_read_strategy():
    manifest = yaml.safe_load(read_text("templates/layer-manifest.yml"))
    analyze = read_text("templates/commands/analyze.md")
    checklist = read_text("templates/commands/checklist.md")

    assert "read_strategies" in manifest
    assert "artifact_sections.spec.md" in manifest["read_strategies"]["analyze"]["first_pass"]
    assert "artifact_sections.plan.md" in manifest["read_strategies"]["checklist"]["first_pass"]
    assert "Expand to full files only" in analyze
    assert "Expand to full files only" in checklist


def test_l5_validation_evidence_and_retrospective_contract_is_standardized():
    acceptance = read_text("templates/commands/acceptance.md")
    validation = read_text("templates/commands/validation.md")
    retrospective = read_text("templates/commands/retrospective.md")
    promote = read_text("templates/commands/promote-lessons.md")
    fact_template = read_text("templates/fact-pack-template.md")
    readme = read_text("TEAM-README.md")
    agents = read_text("templates/agents-template.md")

    for text in [acceptance, validation, retrospective, promote, fact_template, readme]:
        assert "validation.md" in text
        assert "evidence.md" in text

    for text in [acceptance, validation, fact_template, readme]:
        assert "No validation claim is complete without" in text

    assert "acceptance.md` remains user-facing" in acceptance
    assert "evidence.md` remains tool/test-facing" in acceptance
    assert "AI automated validation" in acceptance
    assert "Human manual UI validation" in acceptance
    assert "Do not ask humans to manually verify these by eye" in acceptance
    assert "ai/templates/validation-template.md" in validation
    assert "ai/templates/evidence-template.md" in validation
    assert "Foundation rules or memory" in retrospective
    assert "Capabilities: skills/tools/MCP capability governance" in retrospective
    assert "Evidence: validation/evidence/retrospective flow" in retrospective
    assert "pending | approved | rejected" in retrospective
    assert "only candidates that a human explicitly changes to `approved`" in retrospective
    assert "spec-kit/templates/ai/templates/*.md" not in promote
    assert "pending` candidates" in promote
    assert "rejected` candidates" in promote


def test_fact_layer_collector_finds_latest_logs_and_reports_devtools_status(tmp_path):
    sdk_dir = tmp_path / "sdk"
    biz_dir = tmp_path / "biz"
    sdk_dir.mkdir()
    biz_dir.mkdir()

    old_sdk = sdk_dir / "SDK_20260528110000.log"
    latest_sdk = sdk_dir / "SDK_20260528113642.log"
    old_biz = biz_dir / "ServiceBridge_20260528110000.log"
    latest_biz = biz_dir / "ServiceBridge_20260528113642.log"
    old_sdk.write_text("old sdk", encoding="utf-8")
    latest_sdk.write_text("latest sdk", encoding="utf-8")
    old_biz.write_text("old biz", encoding="utf-8")
    latest_biz.write_text("latest biz", encoding="utf-8")

    script = REPO_ROOT / "scripts" / "powershell" / "collect-fact-layer.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-SdkLogDir",
            str(sdk_dir),
            "-BridgeLogDir",
            str(biz_dir),
            "-BrowserUrl",
            "http://127.0.0.1:65534",
            "-Json",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    output = json.loads(result.stdout)
    assert output["sdkLog"]["path"].endswith("SDK_20260528113642.log")
    assert output["bridgeLog"]["path"].endswith("ServiceBridge_20260528113642.log")
    assert output["devtools"]["available"] is False
    assert output["devtools"]["browserUrl"] == "http://127.0.0.1:65534"
    expected_target_pattern = "app-home|app-main-window|frontend/static/index.html"
    assert output["devtools"]["targetUrlPattern"] == expected_target_pattern
    assert output["devtools"]["selectedTarget"] is None
    assert output["devtools"]["directCdp"]["available"] is False
    assert output["defaults"]["sdkLogDir"] == str(sdk_dir)
    assert output["defaults"]["bridgeLogDir"] == str(biz_dir)
    assert output["defaults"]["targetUrlPattern"] == expected_target_pattern


def test_fact_layer_collector_has_direct_cdp_target_fallback():
    powershell = read_text("scripts/powershell/collect-fact-layer.ps1")
    fact_command = read_text("templates/commands/fact-layer.md")
    fact_template = read_text("templates/fact-pack-template.md")

    for text in [powershell, fact_command]:
        assert "TargetUrlPattern" in text

    assert "ClientWebSocket" in powershell
    assert "Runtime.evaluate" in powershell
    assert "directCdp" in powershell
    assert "selectedTarget" in powershell
    assert "devtools.selectedTarget" in fact_command
    assert "devtools.directCdp" in fact_command
    assert "direct CDP fallback" in fact_template


def test_tasks_and_implement_templates_use_slice_progress_contracts():
    tasks = read_text("templates/commands/tasks.md")
    tasks_template = read_text("templates/tasks-template.md")
    implement = read_text("templates/commands/implement.md")

    for text in [tasks, tasks_template]:
        assert "Implementation Slices" in text
        assert "允许写入范围" in text
        assert "禁止范围" in text
        assert "停止条件" in text

    assert "progress.md" in tasks
    assert "progress.md" in implement
    assert "slice loop" in implement.lower()
    assert "acceptance" in implement
    assert "delete the local spec branch unless explicitly kept" not in implement
    assert "Root Cause Evidence" in implement
    assert "bounded search" in implement
    assert "workspace_root" in implement


def test_review_progress_and_pitfall_artifacts_are_standardized():
    combined = "\n".join(
        [
            read_text("templates/commands/specify.md"),
            read_text("templates/commands/plan.md"),
            read_text("templates/commands/tasks.md"),
            read_text("templates/commands/implement.md"),
        ]
    )

    for phrase in [
        "review.md",
        "progress.md",
        "lessons.md",
        ".specify/memory/pitfalls.md",
    ]:
        assert phrase in combined

    pitfalls_template = read_text("templates/pitfalls-template.md")
    assert "Project Pitfalls" in pitfalls_template
    assert "lessons.md" in pitfalls_template
    assert "without explicit" in pitfalls_template


def test_delivery_profiles_and_root_cause_evidence_are_standardized():
    intake = read_text("templates/commands/intake.md")
    intake_template = read_text("templates/intake-template.md")
    plan = read_text("templates/commands/plan.md")
    plan_template = read_text("templates/plan-template.md")
    tasks = read_text("templates/commands/tasks.md")
    analyze = read_text("templates/commands/analyze.md")
    checklist = read_text("templates/commands/checklist.md")
    bugfix_rules = read_text("checklist-rules/bugfix.yml")

    for text in [intake, intake_template]:
        assert "delivery_profile" in text or "Delivery Profile" in text
        assert "micro-fix" in text
        assert "standard-bugfix" in text
        assert "full-sdd" in text
        assert "blocked-investigation" in text
        assert "validation-only" in text

    for text in [plan, plan_template, tasks, analyze, checklist, bugfix_rules]:
        assert "Root Cause Evidence" in text
        assert "Counterexample" in text
        assert "Blast Radius" in text
        assert "Validation Mapping" in text

    assert "Known Gap" in plan
    assert "blocking" in analyze
    assert "unproven patch" in tasks


def test_human_review_does_not_delegate_ai_owned_technical_judgment():
    for path in [
        "templates/commands/specify.md",
        "templates/commands/clarify.md",
        "templates/commands/plan.md",
        "templates/commands/tasks.md",
        "templates/commands/analyze.md",
        "templates/commands/checklist.md",
        "templates/commands/implement.md",
        "templates/commands/micro-fix.md",
    ]:
        text = read_text(path)
        assert "root cause correctness" in text
        assert "test sufficiency" in text
        assert "commit" in text or "acceptance" in text or "owner-approved" in text

    plan = read_text("templates/commands/plan.md")
    assert "Ask the developer to review the plan summary" not in plan
    tasks = read_text("templates/commands/tasks.md")
    assert "Ask the developer to review task grouping" not in tasks


def test_clarify_uses_spec_only_prerequisite_without_plan_requirement():
    clarify = read_text("templates/commands/clarify.md")
    ps = read_text("scripts/powershell/check-prerequisites.ps1")

    assert "--spec-only" in clarify
    assert "-SpecOnly" in clarify
    assert "-SpecOnly" in ps
    assert "Run /speckit.plan first" in ps


def test_bounded_search_rules_prevent_workspace_wide_scans():
    for path in [
        "templates/commands/plan.md",
        "templates/commands/tasks.md",
        "templates/commands/analyze.md",
        "templates/commands/implement.md",
        "templates/commands/bounded-investigation.md",
    ]:
        text = read_text(path)
        assert "workspace_root" in text
        assert "rg" in text
        assert "subagent" in text or "explorer" in text


def test_team_readme_describes_new_default_process_and_branch_policy():
    readme = read_text("TEAM-README.md")

    for phrase in [
        "acceptance",
        "simplify",
        "test-hardening",
        "commit",
        "complete-branch",
        "low / medium / high / blocked",
        "条件",
        "user acceptance",
        "keeps the local spec branch",
        "does not push",
    ]:
        assert phrase in readme


def test_ui_parity_runtime_rules_are_standardized():
    clarify = read_text("templates/commands/clarify.md")
    plan = read_text("templates/commands/plan.md")
    plan_template = read_text("templates/plan-template.md")
    spec_template = read_text("templates/spec-template.md")
    implement = read_text("templates/commands/implement.md")
    investigation = read_text("templates/commands/bounded-investigation.md")
    checklist = read_text("templates/commands/checklist.md")
    checklist_template = read_text("templates/checklist-template.md")
    acceptance = read_text("templates/commands/acceptance.md")
    tasks = read_text("templates/commands/tasks.md")
    ai_rules = read_text("templates/ai/rules/ai-coding-rules.md")
    common_rules = read_text("checklist-rules/common.yml")
    readme = read_text("TEAM-README.md")
    workflow_args = "\n".join(
        step["input"]["args"] for step in load_workflow()["steps"] if "input" in step
    )

    for text in [clarify, plan, plan_template, implement, checklist, checklist_template, acceptance, common_rules, readme]:
        text_lower = text.lower()
        assert "UI parity" in text
        assert "dynamic states" in text_lower
        assert "host" in text_lower

    for text in [clarify, plan, plan_template, implement, investigation, checklist, checklist_template, common_rules]:
        compact_text = " ".join(text.split())
        assert "runtime dom / computed style / box metrics" in compact_text.lower()
    assert "runtime DOM/CSS/computed style/box metrics" in readme
    assert "runtime DOM/CSS/computed style/box metrics" in workflow_args

    for text in [plan, implement, investigation, acceptance]:
        text_lower = text.lower()
        assert "scrollbar" in text_lower
        assert "clipping" in text_lower
        assert "compression" in text_lower

    assert "stop guessing CSS" in implement
    assert "sync-ui-runtime-artifacts" in implement
    assert "source-to-runtime mapping" in implement
    assert "host-served runtime plugin directory" in implement
    assert "best-effort AI self-validation" in implement
    assert "simulating core clicks" in " ".join(implement.split())
    assert "advisory rather than a hard gate" in implement
    assert "UI element traversal inventory" in plan
    assert "UI Element Traversal Inventory / 0px Alignment Matrix" in plan_template
    assert "0px-level visual repair" in implement
    assert "batch patch strategy" in plan_template.lower()
    assert "baseline anchors" in plan_template.lower()
    assert "CHK014F" in checklist_template
    assert "UI element traversal inventory" in common_rules
    assert "agent-collected screenshots" in acceptance
    assert "unsupported automation remains a visible gap" in " ".join(acceptance.split())
    assert "bounded UI runtime investigation" in investigation
    assert "Static design files" in " ".join(readme.split())

    evidence_gate_text = "\n".join([
        clarify,
        plan,
        plan_template,
        spec_template,
        implement,
        tasks,
        checklist_template,
        ai_rules,
    ])
    compact_evidence_gate = " ".join(evidence_gate_text.split())
    assert "UI / UX / Copy Evidence Gate" in ai_rules
    assert "UI / UX / 文案 Evidence Gate" in plan_template
    assert "UI / UX / 文案依据追踪" in spec_template
    assert "CHK014G" in checklist_template
    assert "Do not invent UI shape" in ai_rules
    assert "Do not substitute a text button for an icon+tooltip" in implement
    assert "stop for clarify or blocked investigation" in compact_evidence_gate
    for phrase in [
        "Qt UI/source/delegate/QSS/resource",
        "product design/mockup/export",
        "tooltip",
        "visible copy",
        "owner/user decision",
    ]:
        assert phrase in evidence_gate_text


def test_test_case_planning_is_skill_routed_and_human_negotiated():
    routing = read_text("templates/ai/workflows/task-routing.md")
    skill_routing = read_text("templates/ai/workflows/skill-routing.yml")
    test_plan = read_text("templates/commands/test-plan.md")
    plan = read_text("templates/commands/plan.md")
    clarify = read_text("templates/commands/clarify.md")
    plan_template = read_text("templates/plan-template.md")
    analyze = read_text("templates/commands/analyze.md")
    checklist = read_text("templates/commands/checklist.md")

    assert "test-plan" in skill_routing
    assert "speckit-test-plan" in skill_routing
    assert "During `clarify` and `plan`" in routing
    assert "API, E2E/interface" in routing
    assert "do not load all\n`ai/knowledge/*`" in test_plan
    assert "inspect-validation-capabilities" in test_plan
    assert "API plan remains required" in test_plan
    assert "E2E unsupported" in test_plan
    assert "approved-by-ai-obvious" in test_plan
    assert "needs-human-review" in test_plan
    assert "owner-approved-gap" in test_plan

    for text in [plan, clarify]:
        assert "speckit-test-plan" in text
        assert "API, E2E/interface" in text

    assert "## 测试用例计划" in plan_template
    assert "Review Status" in plan_template
    assert "测试用例计划" in analyze
    assert "ambiguous API/E2E" in checklist


def test_plugin_changes_must_target_source_not_runtime_artifacts():
    implement = read_text("templates/commands/implement.md")
    checklist = read_text("templates/commands/checklist.md")
    commit = read_text("templates/commands/commit.md")
    constitution = read_text("templates/constitution-template.md")
    constitution_command = read_text("templates/commands/constitution.md")
    checklist_template = read_text("templates/checklist-template.md")
    common_rules = read_text("checklist-rules/common.yml")
    workflow_args = "\n".join(
        step["input"]["args"] for step in load_workflow()["steps"] if "input" in step
    )

    for text in [implement, checklist, commit, constitution_command, common_rules, workflow_args]:
        compact_text = " ".join(text.split()).lower()
        assert "repository source" in compact_text
        assert "installed runtime plugin directories" in compact_text
        assert "built artifacts" in compact_text

    for text in [implement, checklist, commit, constitution, constitution_command, checklist_template]:
        assert "app-data/plugins/**" in text
        assert "frontend/plugins/**" in text

    compact_implement = " ".join(implement.split())
    assert "emergency diagnosis" in compact_implement
    assert "artifact patch" in compact_implement
    assert "runtime artifacts a durable fix location or commit target" in compact_implement
    assert "blocking" in checklist
    assert "Do not commit installed runtime plugin directories" in commit
    assert "仓库源码" in constitution
    assert "验收/提交前必须回写到源码" in constitution
    assert "CHK010N" in checklist_template


def test_completion_scripts_keep_spec_branch_by_default():
    workspace_template = read_text("templates/workspace-template.yml")
    powershell_script = read_text("scripts/powershell/complete-spec-branches.ps1")

    assert "delete_local_spec_branch_after_merge: false" in workspace_template
    assert "keep_local_spec_branch_after_merge: true" in workspace_template
    assert "[switch]$DeleteBranch" in powershell_script
    assert "$shouldKeepBranch = -not [bool]$DeleteBranch" in powershell_script
    assert "git cherry-pick" in powershell_script
    assert "completion_ready" in powershell_script
    assert "Legacy JSON alias retained for older callers" in powershell_script
    assert "switch-to-base" in powershell_script
    assert "git merge --no-ff" not in powershell_script


def test_complete_branch_blocks_without_retrospective_artifacts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "master")
    run_git(repo, "config", "user.email", "spec-kit@example.invalid")
    run_git(repo, "config", "user.name", "Spec Kit Test")

    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "file.txt")
    run_git(repo, "commit", "-m", "base")

    run_git(repo, "switch", "-c", "feature")
    (repo / "file.txt").write_text("feature\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "feature change")

    script = REPO_ROOT / "scripts" / "powershell" / "complete-spec-branches.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-Branch",
            "feature",
            "-BaseBranch",
            "master",
            "-PreflightOnly",
            "-Json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["action"] == "preflight-failed"
    assert payload["retrospective_gate"]["status"] == "blocked"
    assert payload["retrospective_gate"]["missing"] == [
        "workflow-record.md",
        "improvement-candidates.md",
    ]
    assert "Run speckit.retrospective before complete-branch" in payload["errors"][0]


def test_complete_branch_cherry_picks_without_merge_commit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "master")
    run_git(repo, "config", "user.email", "spec-kit@example.invalid")
    run_git(repo, "config", "user.name", "Spec Kit Test")

    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "file.txt")
    run_git(repo, "commit", "-m", "base")
    base_commit = run_git(repo, "rev-parse", "HEAD")

    run_git(repo, "switch", "-c", "feature")
    (repo / "file.txt").write_text("feature 1\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "feature change 1")
    (repo / "second.txt").write_text("feature 2\n", encoding="utf-8")
    run_git(repo, "add", "second.txt")
    run_git(repo, "commit", "-m", "feature change 2")
    write_retrospective_artifacts(repo)

    script = REPO_ROOT / "scripts" / "powershell" / "complete-spec-branches.ps1"
    subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-Branch",
            "feature",
            "-BaseBranch",
            "master",
            "-ConfirmCompletion",
            "-Json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    assert run_git(repo, "branch", "--show-current") == "master"
    assert "feature" in run_git(repo, "branch", "--list", "feature")
    assert run_git(repo, "log", "-1", "--pretty=%s") == "feature change 2"
    assert run_git(repo, "log", "-1", "--pretty=%P").count(" ") == 0
    assert run_git(repo, "log", "--reverse", "--pretty=%s", f"{base_commit}..master").splitlines() == [
        "feature change 1",
        "feature change 2",
    ]


def test_complete_branch_reports_already_up_to_date(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "master")
    run_git(repo, "config", "user.email", "spec-kit@example.invalid")
    run_git(repo, "config", "user.name", "Spec Kit Test")

    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "file.txt")
    run_git(repo, "commit", "-m", "base")
    run_git(repo, "switch", "-c", "feature")
    write_retrospective_artifacts(repo)

    script = REPO_ROOT / "scripts" / "powershell" / "complete-spec-branches.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-Branch",
            "feature",
            "-BaseBranch",
            "master",
            "-ConfirmCompletion",
            "-Json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    assert '"status":"already-up-to-date"' in result.stdout
    assert "switched-to-master" in result.stdout
    assert run_git(repo, "branch", "--show-current") == "master"


def test_complete_branch_switches_all_repositories_back_to_base(tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    for repo in [repo_a, repo_b]:
        repo.mkdir()
        run_git(repo, "init", "-b", "master")
        run_git(repo, "config", "user.email", "spec-kit@example.invalid")
        run_git(repo, "config", "user.name", "Spec Kit Test")
        (repo / "file.txt").write_text("base\n", encoding="utf-8")
        run_git(repo, "add", "file.txt")
        run_git(repo, "commit", "-m", "base")
        run_git(repo, "switch", "-c", "feature")

    (repo_a / "file.txt").write_text("feature\n", encoding="utf-8")
    run_git(repo_a, "commit", "-am", "feature change")
    write_retrospective_artifacts(repo_a)

    (repo_a / ".specify").mkdir()
    (repo_a / ".specify" / "workspace.yml").write_text(
        "\n".join(
            [
                "root: ..",
                "default_base_branch: master",
                "repositories:",
                "  - name: repo-a",
                "    path: repo-a",
                "    required: true",
                "  - name: repo-b",
                "    path: repo-b",
                "    required: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    script = REPO_ROOT / "scripts" / "powershell" / "complete-spec-branches.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-Branch",
            "feature",
            "-BaseBranch",
            "master",
            "-ConfirmCompletion",
            "-Json",
        ],
        cwd=repo_a,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    assert run_git(repo_a, "branch", "--show-current") == "master"
    assert run_git(repo_b, "branch", "--show-current") == "master"
    assert "cherry-picked-to-master; kept-local-branch" in result.stdout
    assert "already-up-to-date; switched-to-master" in result.stdout


def test_complete_branch_allows_untracked_noise_in_up_to_date_repo(tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    for repo in [repo_a, repo_b]:
        repo.mkdir()
        run_git(repo, "init", "-b", "master")
        run_git(repo, "config", "user.email", "spec-kit@example.invalid")
        run_git(repo, "config", "user.name", "Spec Kit Test")
        (repo / "file.txt").write_text("base\n", encoding="utf-8")
        run_git(repo, "add", "file.txt")
        run_git(repo, "commit", "-m", "base")
        run_git(repo, "switch", "-c", "feature")

    (repo_a / "file.txt").write_text("feature\n", encoding="utf-8")
    run_git(repo_a, "commit", "-am", "feature change")
    (repo_b / "local-note.md").write_text("unrelated local scratch\n", encoding="utf-8")
    write_retrospective_artifacts(repo_a)
    (repo_a / ".specify").mkdir(exist_ok=True)
    (repo_a / ".specify" / "workspace.yml").write_text(
        "\n".join(
            [
                "workspace:",
                "  root: \"..\"",
                "  primary_repo: repo-a",
                "  default_base_branch: master",
                "repositories:",
                "  - name: repo-a",
                "    path: repo-a",
                "    required: true",
                "  - name: repo-b",
                "    path: repo-b",
                "    required: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    script = REPO_ROOT / "scripts" / "powershell" / "complete-spec-branches.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-Branch",
            "feature",
            "-BaseBranch",
            "master",
            "-ConfirmCompletion",
            "-Json",
        ],
        cwd=repo_a,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    repo_b_preflight = next(item for item in payload["preflight"] if item["repository"] == "repo-b")
    assert repo_b_preflight["status"] == "already-up-to-date"
    assert repo_b_preflight["dirty_state"]["unclassified_untracked"] == ["local-note.md"]
    assert run_git(repo_a, "branch", "--show-current") == "master"
    assert run_git(repo_b, "branch", "--show-current") == "master"
    assert (repo_b / "local-note.md").read_text(encoding="utf-8") == "unrelated local scratch\n"


def test_complete_branch_blocks_untracked_source_when_repo_has_commits(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "master")
    run_git(repo, "config", "user.email", "spec-kit@example.invalid")
    run_git(repo, "config", "user.name", "Spec Kit Test")

    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "file.txt")
    run_git(repo, "commit", "-m", "base")
    run_git(repo, "switch", "-c", "feature")
    (repo / "file.txt").write_text("feature\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "feature change")
    (repo / "forgotten-source.txt").write_text("maybe belongs to feature\n", encoding="utf-8")
    write_retrospective_artifacts(repo)

    script = REPO_ROOT / "scripts" / "powershell" / "complete-spec-branches.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-Branch",
            "feature",
            "-BaseBranch",
            "master",
            "-PreflightOnly",
            "-Json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["action"] == "preflight-failed"
    assert payload["preflight"][0]["dirty_state"]["unclassified_untracked"] == ["forgotten-source.txt"]


def test_complete_branch_auto_resolves_generated_artifact_conflict(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "master")
    run_git(repo, "config", "user.email", "spec-kit@example.invalid")
    run_git(repo, "config", "user.name", "Spec Kit Test")

    (repo / "dist").mkdir()
    (repo / "dist" / "bundle.js").write_text("base artifact\n", encoding="utf-8")
    (repo / "source.txt").write_text("base source\n", encoding="utf-8")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "base")

    run_git(repo, "switch", "-c", "feature")
    (repo / "dist" / "bundle.js").write_text("feature artifact\n", encoding="utf-8")
    (repo / "source.txt").write_text("feature source\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "feature source and artifact")
    write_retrospective_artifacts(repo)

    run_git(repo, "switch", "master")
    (repo / "dist" / "bundle.js").write_text("master artifact\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "master artifact")

    script = REPO_ROOT / "scripts" / "powershell" / "complete-spec-branches.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-Branch",
            "feature",
            "-BaseBranch",
            "master",
            "-ConfirmCompletion",
            "-Json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    assert run_git(repo, "branch", "--show-current") == "master"
    assert (repo / "dist" / "bundle.js").read_text(encoding="utf-8") == "master artifact\n"
    assert (repo / "source.txt").read_text(encoding="utf-8") == "feature source\n"
    assert "auto-resolved-artifact-conflicts=dist/bundle.js" in result.stdout


def test_complete_branch_stops_on_cherry_pick_conflict(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "master")
    run_git(repo, "config", "user.email", "spec-kit@example.invalid")
    run_git(repo, "config", "user.name", "Spec Kit Test")

    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "file.txt")
    run_git(repo, "commit", "-m", "base")

    run_git(repo, "switch", "-c", "feature")
    (repo / "file.txt").write_text("feature\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "feature change")
    write_retrospective_artifacts(repo)

    run_git(repo, "switch", "master")
    (repo / "file.txt").write_text("master\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "master change")

    script = REPO_ROOT / "scripts" / "powershell" / "complete-spec-branches.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-Branch",
            "feature",
            "-BaseBranch",
            "master",
            "-ConfirmCompletion",
            "-Json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert "Cherry-pick failed in" in combined_output
    assert "file.txt" in combined_output


def test_create_spec_branch_scripts_emit_workspace_role_metadata():
    powershell_script = read_text("scripts/powershell/create-spec-branch.ps1")
    complete_script = read_text("scripts/powershell/complete-spec-branches.ps1")
    workspace_template = read_text("templates/workspace-template.yml")

    for text in [powershell_script]:
        assert "workspace_root" in text
        assert "default_base_branch" in text
        assert "participates_in_spec_branches" in text
    assert "default_base_branch" in complete_script
    assert "participates_in_spec_branches" in complete_script

    assert "role = $repo.role" in powershell_script
    assert "workspace_root = $workspace.workspace_root" in powershell_script
    assert "default_base_branch = $workspace.default_base_branch" in powershell_script
    assert 'name: "spec-kit"' in workspace_template
    assert 'path: "spec-kit"' in workspace_template
    assert "participates_in_spec_branches: false" in workspace_template


def test_create_spec_branch_skips_non_participating_tooling_repo(tmp_path):
    repo_a = tmp_path / "repo-a"
    tool_repo = tmp_path / "spec-kit"
    for repo in [repo_a, tool_repo]:
        repo.mkdir()
        run_git(repo, "init", "-b", "master")
        run_git(repo, "config", "user.email", "spec-kit@example.invalid")
        run_git(repo, "config", "user.name", "Spec Kit Test")
        (repo / "file.txt").write_text("base\n", encoding="utf-8")
        run_git(repo, "add", "file.txt")
        run_git(repo, "commit", "-m", "base")

    run_git(tool_repo, "switch", "-c", "999-existing-tooling")
    (tool_repo / "local-tooling-note.txt").write_text("dirty but skipped\n", encoding="utf-8")

    (repo_a / ".specify").mkdir()
    (repo_a / ".specify" / "workspace.yml").write_text(
        "\n".join(
            [
                "workspace:",
                "  root: \"..\"",
                "  primary_repo: repo-a",
                "  default_base_branch: master",
                "repositories:",
                "  - name: repo-a",
                "    path: repo-a",
                "    role: product",
                "    required: true",
                "  - name: spec-kit",
                "    path: spec-kit",
                "    role: ai-delivery-tooling",
                "    required: false",
                "    participates_in_spec_branches: false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    script = REPO_ROOT / "scripts" / "powershell" / "create-spec-branch.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-FeatureName",
            "Skip Tooling Repo",
            "-Json",
        ],
        cwd=repo_a,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["branch"] == "001-skip-tooling-repo"
    skipped = next(item for item in payload["repositories"] if item["repository"] == "spec-kit")
    assert skipped["status"] == "skipped"
    assert skipped["participates_in_spec_branches"] is False
    assert run_git(repo_a, "branch", "--show-current") == "001-skip-tooling-repo"
    assert run_git(tool_repo, "branch", "--show-current") == "999-existing-tooling"


def test_complete_spec_branch_skips_non_participating_tooling_repo(tmp_path):
    repo_a = tmp_path / "repo-a"
    tool_repo = tmp_path / "spec-kit"
    for repo in [repo_a, tool_repo]:
        repo.mkdir()
        run_git(repo, "init", "-b", "master")
        run_git(repo, "config", "user.email", "spec-kit@example.invalid")
        run_git(repo, "config", "user.name", "Spec Kit Test")
        (repo / "file.txt").write_text("base\n", encoding="utf-8")
        run_git(repo, "add", "file.txt")
        run_git(repo, "commit", "-m", "base")

    run_git(repo_a, "switch", "-c", "feature")
    (repo_a / "file.txt").write_text("feature\n", encoding="utf-8")
    run_git(repo_a, "commit", "-am", "feature change")
    write_retrospective_artifacts(repo_a)
    (tool_repo / "local-tooling-note.txt").write_text("dirty but skipped\n", encoding="utf-8")

    (repo_a / ".specify").mkdir(exist_ok=True)
    (repo_a / ".specify" / "workspace.yml").write_text(
        "\n".join(
            [
                "workspace:",
                "  root: \"..\"",
                "  primary_repo: repo-a",
                "  default_base_branch: master",
                "repositories:",
                "  - name: repo-a",
                "    path: repo-a",
                "    required: true",
                "  - name: spec-kit",
                "    path: spec-kit",
                "    required: false",
                "    participates_in_spec_branches: false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    script = REPO_ROOT / "scripts" / "powershell" / "complete-spec-branches.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-Branch",
            "feature",
            "-BaseBranch",
            "master",
            "-ConfirmCompletion",
            "-Json",
        ],
        cwd=repo_a,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    skipped = next(item for item in payload["repositories"] if item["repository"] == "spec-kit")
    assert skipped["status"] == "skipped"
    assert skipped["participates_in_spec_branches"] is False
    assert run_git(repo_a, "branch", "--show-current") == "master"
    assert run_git(tool_repo, "branch", "--show-current") == "master"


def test_create_spec_branch_ignores_untracked_generated_artifacts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "master")
    run_git(repo, "config", "user.email", "spec-kit@example.invalid")
    run_git(repo, "config", "user.name", "Spec Kit Test")
    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "file.txt")
    run_git(repo, "commit", "-m", "base")

    (repo / "dist").mkdir()
    (repo / "dist" / "bundle.js").write_text("generated\n", encoding="utf-8")
    (repo / ".specify").mkdir()
    (repo / ".pytest_cache").mkdir()
    (repo / ".pytest_cache" / "README.md").write_text("cache\n", encoding="utf-8")

    script = REPO_ROOT / "scripts" / "powershell" / "create-spec-branch.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-FeatureName",
            "Generated Artifact Ignore",
            "-Json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    assert '"branch":"001-generated-artifact-ignore"' in result.stdout
    assert run_git(repo, "branch", "--show-current") == "001-generated-artifact-ignore"


def test_create_spec_branch_records_untracked_risks_without_blocking(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "master")
    run_git(repo, "config", "user.email", "spec-kit@example.invalid")
    run_git(repo, "config", "user.name", "Spec Kit Test")
    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "file.txt")
    run_git(repo, "commit", "-m", "base")

    (repo / "local-note.md").write_text("scratch\n", encoding="utf-8")
    (repo / "dist").mkdir()
    (repo / "dist" / "bundle.js").write_text("generated\n", encoding="utf-8")

    script = REPO_ROOT / "scripts" / "powershell" / "create-spec-branch.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-FeatureName",
            "Untracked Risk",
            "-Json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    dirty_state = payload["preflight"][0]["dirty_state"]
    assert dirty_state["tracked_dirty"] == []
    assert dirty_state["unclassified_untracked"] == ["local-note.md"]
    assert dirty_state["generated_or_temp"] == ["dist/"]
    assert payload["dirty_risks"][0]["repository"] == "repo"
    assert payload["allow_dirty_used"] is True
    assert run_git(repo, "branch", "--show-current") == "001-untracked-risk"
    assert (repo / "local-note.md").read_text(encoding="utf-8") == "scratch\n"


def test_create_spec_branch_blocks_tracked_dirty_before_any_switch(tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    for repo in [repo_a, repo_b]:
        repo.mkdir()
        run_git(repo, "init", "-b", "master")
        run_git(repo, "config", "user.email", "spec-kit@example.invalid")
        run_git(repo, "config", "user.name", "Spec Kit Test")
        (repo / "file.txt").write_text("base\n", encoding="utf-8")
        run_git(repo, "add", "file.txt")
        run_git(repo, "commit", "-m", "base")

    (repo_b / "file.txt").write_text("dirty tracked\n", encoding="utf-8")
    (repo_a / ".specify").mkdir()
    (repo_a / ".specify" / "workspace.yml").write_text(
        "\n".join(
            [
                "workspace:",
                "  root: \"..\"",
                "  primary_repo: repo-a",
                "  default_base_branch: master",
                "repositories:",
                "  - name: repo-a",
                "    path: repo-a",
                "    required: true",
                "  - name: repo-b",
                "    path: repo-b",
                "    required: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    script = REPO_ROOT / "scripts" / "powershell" / "create-spec-branch.ps1"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-FeatureName",
            "Tracked Dirty",
            "-AllowDirty",
            "-Json",
        ],
        cwd=repo_a,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "tracked uncommitted changes" in combined_output
    assert "stash, clean up, or commit" in combined_output
    assert run_git(repo_a, "branch", "--show-current") == "master"
    assert run_git(repo_b, "branch", "--show-current") == "master"


def test_repository_map_template_is_fixed_ai_context():
    repository_map = read_text("templates/repository-map-template.md")

    for phrase in [
        "# Workspace Repository Map",
        "| Repository | Path | Role | Capability / Ownership | AI Usage Notes |",
        "Project Path Categories",
        "<workspace-root>/FrontendPlugin/<plugin-id>/",
        "<workspace-root>/FrontendPlugin/<plugin-id>/dist/",
        "<workspace-root>/HostApplication/HostApplication/dist/plugins/<plugin-id>-<version>.plugin",
        "<host-app-root>/app-data/plugins/<plugin-id>/<version>/",
        "<host-app-root>/frontend/<location>/<plugin-id>/",
        "<app-data-root>/<brand-name>/<project-name>/<front-plugins-config-file>",
        "Do not write machine-specific absolute paths here",
        "CoreRuntime",
        "SdkConsumer",
        "NativePlugin",
        "HostApplication",
        "single source of truth",
        "Do not infer repository purpose by scanning source trees",
    ]:
        assert phrase in repository_map


def test_plugin_path_knowledge_is_relative_and_discoverable():
    repository_map = read_text("templates/repository-map-template.md")
    build_notes = read_text("templates/ai/knowledge/build-and-package-notes.md")
    repository_map_skill = read_text("templates/subskills/speckit-repository-map/SKILL.md")
    agents_template = read_text("templates/agents-template.md")

    for text in [repository_map, build_notes, repository_map_skill, agents_template]:
        assert "<workspace-root>" in text
        assert "<plugin-id>" in text
        assert "machine-specific absolute paths" in text
        assert not re.search(r"[A-Za-z]:\\", text)

    for phrase in [
        "Plugin Path Knowledge",
        "<workspace-root>/FrontendPlugin/<plugin-id>/src/",
        "<workspace-root>/FrontendPlugin/<plugin-id>/plugin-out/<version>/staging/",
        "<host-app-root>/frontend/<location>/<plugin-id>/",
        "<host-app-root>/mock_data/api/pluginManager/v1/getFrontDescriptorList.json",
        "<host-app-root>/app-data/plugins/<plugin-id>/<version>/",
        "<host-app-root>/app-data/plugins/<plugin-id>/<version>/native/",
        "<workspace-root>/NativePlugin/<plugin-id>/build/<generator>/<arch>/<config>/",
        "<workspace-root>/NativePlugin/<plugin-id>/export/",
        "<host-app-root>/plugins/<legacy-plugin-id>",
    ]:
        assert phrase in build_notes

    compact_skill = " ".join(repository_map_skill.split())
    assert "Project Path Categories" in compact_skill
    assert "path categories needed by the task" in compact_skill
    assert "ai/knowledge/build-and-package-notes.md" in repository_map_skill
    assert "Project Path Categories" in agents_template


def test_specify_requires_workspace_repository_map_for_spec_and_review():
    specify = read_text("templates/commands/specify.md")

    for phrase in [
        "speckit-repository-map",
        ".specify/memory/repository-map.md",
        "Workspace Repository Map",
        "Repository / Path / Role / Capability",
        "Do not guess repository roles",
        "Do not infer repository roles by scanning repository files",
        "spec.md",
        "review.md",
        "workspace_root",
        "default_base_branch",
    ]:
        assert phrase in specify


def test_hot_pluggable_subskills_are_packaged_and_referenced():
    pyproject = read_text("pyproject.toml")
    base_integration = read_text("src/specify_cli/integrations/base.py")
    repository_map_skill = read_text("templates/subskills/speckit-repository-map/SKILL.md")
    code_simplifier_skill = read_text("templates/subskills/code-simplifier/SKILL.md")
    commit_message_skill = read_text("templates/subskills/commit-message/SKILL.md")
    simplify_command = read_text("templates/commands/simplify.md")
    commit_command = read_text("templates/commands/commit.md")

    assert '"templates/subskills" = "specify_cli/core_pack/subskills"' in pyproject
    assert "shared_subskills_dir" in base_integration
    assert "list_subskill_templates" in base_integration
    assert "install_subskills" in base_integration

    assert "name: speckit-repository-map" in repository_map_skill
    assert ".specify/memory/repository-map.md" in repository_map_skill
    assert "Do not infer repository purpose" in repository_map_skill
    assert "Spec Kit L4 Governance" in repository_map_skill
    assert "ai/tools/*" in repository_map_skill

    assert "name: code-simplifier" in code_simplifier_skill
    assert "Simplifies and refines code" in code_simplifier_skill
    assert "Spec Kit L4 Governance" in code_simplifier_skill
    assert "ai/tools/mcp-usage-policy.md" in code_simplifier_skill
    assert "Use the `code-simplifier` subskill" in simplify_command

    assert "name: commit-message" in commit_message_skill
    assert "single HostApplication / application Chinese commit-message template" in commit_message_skill
    assert "68 display columns" in commit_message_skill
    assert "Spec Kit L4 Governance" in commit_message_skill
    assert "Commit-message generation does not require MCP" in commit_message_skill
    assert "Use the `commit-message` skill" in commit_command
    assert "validate-commit-message" in commit_command
    assert "git commit -F <message-file>" in commit_command
    assert "git commit -m" in commit_command


def test_init_is_codex_only_without_ai_selector():
    cli = read_text("src/specify_cli/__init__.py")
    readme = read_text("TEAM-README.md")
    wrapper = read_wrapper_text("init.ps1")
    wrapper_readme = read_wrapper_text("spec-kit-local-tools.md")
    registry = read_text("src/specify_cli/integrations/__init__.py")
    agents = read_text("src/specify_cli/agents.py")
    base_integration = read_text("src/specify_cli/integrations/base.py")

    assert 'INIT_INTEGRATION = "codex"' in cli
    assert "INIT_AI_CHOICES" not in cli
    assert "Spec Kit init exposes one Codex entry skill" in cli
    assert "Initialize the Codex entry skill and internal stage skills" in cli

    init_doc = cli[cli.index("def init("):cli.index("show_banner()", cli.index("def init("))]
    assert "--ai" not in init_doc
    assert "selected_ai not in INIT_AI_CHOICES" not in cli
    assert "Start {integration_name} in this project directory" in cli
    assert "_get_skills_dir(project_path, selected_ai)" in cli
    assert '"canonical_context_file": getattr(' in cli
    assert 'not wf_registry.is_installed("speckit") or force' in cli
    assert '"speckit refreshed" if force else "speckit installed"' in cli
    assert "--knowledge-pack" in init_doc
    assert "--knowledge-pack-apply-profiles" in init_doc
    assert "_mount_knowledge_pack(" in cli
    assert 'content.replace("# AGENTS.md", f"# {context_file}", 1)' in read_text(
        "src/specify_cli/integrations/base.py"
    )
    assert 'from .codex import CodexIntegration' in registry
    assert "ClaudeIntegration" not in registry
    assert "CopilotIntegration" not in registry
    assert "GenericIntegration" not in registry
    assert "ForgeIntegration" not in registry
    assert not (REPO_ROOT / "presets" / "catalog.json").exists()
    assert not (REPO_ROOT / "extensions" / "catalog.json").exists()
    assert "app.add_typer(preset_app" not in cli
    assert "app.add_typer(extension_app" not in cli
    assert "app.add_typer(integration_catalog_app" not in cli
    assert "register_commands_for_non_skill_agents" not in agents
    assert "render_toml_command" not in agents
    assert "render_yaml_command" not in agents
    assert "MarkdownIntegration" not in base_integration
    assert "TomlIntegration" not in base_integration
    assert "YamlIntegration" not in base_integration

    for phrase in [
        "--ai",
        "--ai-commands-dir",
        "--ai-skills",
        "--integration",
        "--integration-options",
        "--integration claude",
        "--integration copilot",
        "--integration generic",
        "ai_assistant",
        "ai_commands_dir",
        "ai_skills",
        "integration_options",
        "interactive integration selection",
    ]:
        assert phrase not in init_doc

    assert "不再提供其它 AI 初始化路径" in readme
    assert ".agents/skills/speckit-specify" in readme
    assert ".agents/spec-kit/skills" in readme

    assert '[ValidateSet("codex", "claude")]' not in wrapper
    assert '"--ai"' not in wrapper
    assert "$Ai" not in wrapper
    assert "[string]$Ide" not in wrapper
    assert "--integration" not in wrapper
    assert "Codex-only" in wrapper_readme
    assert ".\\script\\SpecKit\\init.ps1 -Ai claude" not in wrapper_readme
    assert ".claude/skills" not in wrapper_readme
    assert "-Ide" not in wrapper_readme
    assert "specific IDE" not in wrapper_readme


def test_open_source_readme_documents_pack_and_generated_knowledge_starts():
    readme = read_text("README.md")

    assert "specify init --here --knowledge-pack <pack-dir>" in readme
    assert "--knowledge-pack-apply-profiles" in readme
    assert "does not generate an AI review packet" in readme
    assert "specify knowledge bootstrap --project-dir . --json" in readme
    assert "specify knowledge generate-pack --project-dir . --pack-id <id> --include-profiles --json" in readme
    assert "specify knowledge finalize-pack --project-dir . --pack-id <id> --include-profiles --apply --force" in readme
    assert "specify knowledge repack --project-dir . --pack-id <id> --include-profiles --force --json" in readme
    assert ".specify/knowledge-pack-generation/ai-synthesis/ai/knowledge/" in readme
    assert "source-coverage-ledger.json" in readme
    assert "evaluate-knowledge-pack-synthesis.ps1" in readme
    assert ".specify/knowledge-bootstrap/ai-review/" in readme
    assert "Project-specific facts belong" in readme
    assert "validate-knowledge-pack.ps1" in readme
    assert "github/spec-kit" in readme
    assert "本仓库不是 GitHub 官方项目" in readme
    assert "specify upgrade --project-dir <project-dir> --dry-run" in readme
    assert ".specify/spec-kit.lock.yml" in readme
    assert ".specify/integrations/speckit.manifest.json" in readme


def test_init_wrapper_documents_layered_assets_and_cherry_pick_completion():
    wrapper = read_wrapper_text("init.ps1")
    wrapper_readme = read_wrapper_text("spec-kit-local-tools.md")

    for phrase in [
        "Initializes layered assets",
        ".specify/checklist-rules",
        "ai/**",
        "By default, init targets the workspace root and refreshes bundled shared assets with --force",
        "use -NoForce to preserve existing shared files",
    ]:
        assert phrase in wrapper

    for phrase in [
        "Initialization also installs the layered Spec Kit assets",
        "`ai/rules`, `ai/knowledge`, `ai/workflows`, `ai/tools`, and `ai/templates`",
        "human-acceptance gate -> retrospective -> commit",
        "post-commit-self-check -> rubric-score -> complete-branch",
        "cherry-pick the local Spec",
        "Cherry-pick completion is automated after commit",
    ]:
        assert phrase in wrapper_readme


def test_init_wrapper_configures_codex_mcp_without_agent_selector():
    wrapper = read_wrapper_text("init.ps1")
    wrapper_readme = read_wrapper_text("spec-kit-local-tools.md")
    team_readme = read_text("TEAM-README.md")
    mcp_policy = read_text("templates/ai/tools/mcp-usage-policy.md")
    mcp_permissions = read_text("templates/ai/tools/mcp-permissions.md")
    mcp_script = read_text("scripts/powershell/configure-mcp-agents.ps1")

    for text in [wrapper, wrapper_readme, team_readme]:
        assert "Codex" in text
        assert "McpAgents" not in text
        assert "ClaudeCode" not in text
        assert "GeminiCli" not in text
        assert "OpenCode" not in text
        assert "OpenClaw" not in text

    assert "configure-mcp-agents.ps1" in wrapper
    assert 'Agents = @("Codex")' in wrapper
    assert '[string[]]$McpAgents' not in wrapper
    assert "ProjectPath = $ResolvedProjectPath" in wrapper
    assert "[switch]$SkipMcpAgentConfig" in wrapper
    assert "-SkipMcpAgentConfig" in wrapper
    assert "CreateMissingMcpConfig" in wrapper
    assert "DryRunMcp" in wrapper
    assert "[switch]$ConfigureMcpAgent" in wrapper
    assert "$ConfigureMcpAgent -and -not $SkipMcpAgentConfig" in wrapper
    assert "McpChromeMode" in wrapper
    assert "electron-slim" in wrapper
    assert "McpBrowserUrl" in wrapper
    assert "Chrome DevTools MCP modes" in wrapper_readme
    assert "-ConfigureMcpAgent" in wrapper_readme
    assert "-SkipMcpAgentConfig" in wrapper_readme
    assert "默认 init 不写 Codex MCP 配置" in team_readme
    assert "MCP is an L4 capability layer" in mcp_policy
    assert "not always-on actions" in mcp_policy
    assert "explicit human confirmation" in mcp_permissions
    assert "MCP tools are optional capabilities" in mcp_script
    assert "Set-CodexMcpServer" in mcp_script
    assert "Set-ClaudeCodeMcpServer" not in mcp_script
    assert "ai/tools/mcp-usage-policy.md" in mcp_script


def test_hostapplication_cdp_defaults_are_in_generated_context_templates():
    repository_map = read_text("templates/repository-map-template.md")
    build_notes = read_text("templates/ai/knowledge/build-and-package-notes.md")
    task_routing = read_text("templates/ai/workflows/task-routing.md")
    mcp_servers = read_text("templates/ai/tools/mcp-servers.md")
    mcp_policy = read_text("templates/ai/tools/mcp-usage-policy.md")
    implement = read_text("templates/commands/implement.md")
    acceptance = read_text("templates/commands/acceptance.md")
    fact_layer = read_text("templates/commands/fact-layer.md")
    validation = read_text("templates/commands/validation.md")
    ps_fact_script = read_text("scripts/powershell/collect-fact-layer.ps1")

    for text in [
        repository_map,
        build_notes,
        task_routing,
        mcp_servers,
        mcp_policy,
        implement,
        acceptance,
        fact_layer,
        validation,
        ps_fact_script,
    ]:
        assert "http://127.0.0.1:9222" in text
        assert "app-main-window" in text

    assert "npm run debug" in repository_map
    assert "<workspace-root>/HostApplication/HostApplication/" in build_notes
    assert "UTILITY_ENABLE_PLUGIN_DEVTOOLS=1" in build_notes
    assert "Node inspector also starts on `5858`" in build_notes
    assert "Plugin Workbench|plugin-workbench.html" in build_notes
    assert "Plugin Workbench\\|plugin-workbench.html" in repository_map
    assert "`plugin-host` DevTools /" in implement
    assert "Workbench itself" in implement
    assert "Workbench target override" in fact_layer
    assert "#/app-home/appHome" in build_notes
    assert "click the target app card such as" in build_notes
    assert "Page.captureScreenshot" in build_notes
    assert "UTILITY_CHROME_REMOTE_DEBUGGING_PORT=9222" in mcp_servers
    assert "CSS.forcePseudoState(['hover'])" in mcp_servers
    assert "Codex TOML" in mcp_servers
    assert "real HostApplication Electron host" in " ".join(task_routing.split())
    assert "Isolated plugin preview is fallback evidence" in " ".join(implement.split())


def compatible_node_env(tmp_path: Path) -> dict[str, str]:
    fake_bin = tmp_path / "fake-compatible-node"
    fake_bin.mkdir()
    (fake_bin / "node.cmd").write_text("@echo v22.14.0\r\n", encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    return env


def test_mcp_agent_config_script_writes_codex_toml_only(tmp_path):
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)

    (home / ".codex" / "config.toml").write_text('[profile]\nname = "default"\n', encoding="utf-8")

    script = REPO_ROOT / "scripts" / "powershell" / "configure-mcp-agents.ps1"
    env = compatible_node_env(tmp_path)
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-HomePath",
            str(home),
            "-Agents",
            "Codex",
            "-ServerId",
            "chrome-devtools",
            "-Command",
            "npm",
            "-Json",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
        env=env,
    )

    output = json.loads(result.stdout)
    if isinstance(output, dict):
        output = [output]
    by_agent = {entry["agent"]: entry for entry in output}
    assert list(by_agent.keys()) == ["Codex"]
    assert by_agent["Codex"]["status"] == "configured"
    expected_command = "npm.cmd" if os.name == "nt" else "npm"

    codex = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert '[profile]' in codex
    assert "[mcp_servers.chrome-devtools]" in codex
    assert f'command = "{expected_command}"' in codex
    assert (
        'args = ["exec", "--yes", "--package=chrome-devtools-mcp@latest", "-c", "chrome-devtools-mcp --browserUrl http://127.0.0.1:9222 --slim"]'
        in codex
    )

    rejected = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-HomePath",
            str(home),
            "-Agents",
            "ClaudeCode",
            "-Json",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
    )
    assert rejected.returncode != 0
    assert "Cannot validate argument on parameter 'Agents'" in (rejected.stdout + rejected.stderr)


def test_mcp_agent_config_supports_chrome_connection_modes(tmp_path):
    script = REPO_ROOT / "scripts" / "powershell" / "configure-mcp-agents.ps1"

    cases = {
        "auto": "chrome-devtools-mcp",
        "electron": "chrome-devtools-mcp --browserUrl http://127.0.0.1:9223",
        "electron-slim": "chrome-devtools-mcp --browserUrl http://127.0.0.1:9223 --slim",
    }

    expected_command = "npm.cmd" if os.name == "nt" else "npm"
    for mode, expected_call in cases.items():
        home = tmp_path / mode
        (home / ".codex").mkdir(parents=True)
        (home / ".codex" / "config.toml").write_text("", encoding="utf-8")
        env = compatible_node_env(tmp_path / mode)

        subprocess.run(
            [
                "pwsh",
                "-NoProfile",
                "-File",
                str(script),
                "-HomePath",
                str(home),
                "-Agents",
                "Codex",
                "-ServerId",
                "chrome-devtools",
                "-Command",
                "npm",
                "-ChromeMode",
                mode,
                "-BrowserUrl",
                "http://127.0.0.1:9223",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=True,
            env=env,
        )

        codex = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
        assert f'command = "{expected_command}"' in codex
        assert (
            f'args = ["exec", "--yes", "--package=chrome-devtools-mcp@latest", "-c", "{expected_call}"]'
            in codex
        )


def test_mcp_agent_config_allows_explicit_args_override(tmp_path):
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    (home / ".codex" / "config.toml").write_text("", encoding="utf-8")

    script = REPO_ROOT / "scripts" / "powershell" / "configure-mcp-agents.ps1"
    env = compatible_node_env(tmp_path)
    subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-Command",
            (
                f"& '{script}' "
                f"-HomePath '{home}' "
                "-Agents Codex "
                "-ServerId chrome-devtools "
                "-Command npm "
                "-ChromeMode electron-slim "
                "-ServerArgs @('exec','--yes','chrome-devtools-mcp@latest')"
            ),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
        env=env,
    )

    codex = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert 'args = ["exec", "--yes", "chrome-devtools-mcp@latest"]' in codex
    assert "--browserUrl" not in codex


def test_mcp_agent_config_requires_compatible_global_node(tmp_path):
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    (home / ".codex" / "config.toml").write_text("", encoding="utf-8")

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    (fake_bin / "node.cmd").write_text("@echo v14.16.0\r\n", encoding="utf-8")

    script = REPO_ROOT / "scripts" / "powershell" / "configure-mcp-agents.ps1"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-HomePath",
            str(home),
            "-Agents",
            "Codex",
            "-ServerId",
            "chrome-devtools",
            "-Command",
            "npm",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
    )

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "global node is v14.16.0" in combined_output
    assert "requires Node.js" in combined_output
    assert "^20.19.0 || ^22.12.0 || >=23" in combined_output
    assert "with -SkipMcpAgentConfig" in combined_output
