import json
import os
import subprocess
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]

AUTOMATION_TOOLS = [
    "validate-feature-artifacts",
    "validate-generated-context",
    "select-knowledge",
    "validate-knowledge-index",
    "suggest-validation",
    "inspect-commit-scope",
    "validate-fact-layer-gate",
    "inspect-affected-repos",
    "inspect-delivery-facts",
    "validate-checklist-rules",
    "validate-root-cause-structure",
    "validate-implementation-slices",
    "inspect-source-artifact-consistency",
    "collect-workflow-facts",
    "parse-promotion-candidates",
    "inspect-package-sync",
    "normalize-workflow-state",
    "inspect-untracked-noise",
    "generate-acceptance-skeleton",
    "validate-commit-message",
    "sync-ui-runtime-artifacts",
    "inspect-desktop-shell-cdp-target",
    "ensure-desktop-shell-cdp-host",
]


def read_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def run_ps(tool: str, *args: str, cwd: Path | None = None) -> dict:
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / f"{tool}.ps1"),
            *args,
            "-Json",
        ],
        cwd=cwd or REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def assert_standard_shape(output: dict, tool: str):
    assert output["tool"] == tool
    assert output["status"] in {"ok", "blocked", "warning"}
    assert isinstance(output["facts"], dict)
    assert isinstance(output["blockers"], list)
    assert isinstance(output["unknowns"], list)
    assert isinstance(output["hints"], list)


def test_automation_assets_are_packaged_and_declared():
    pyproject = read_text("pyproject.toml")

    assert (REPO_ROOT / "config" / "automation-rules.yml").exists()
    assert (REPO_ROOT / "templates" / "layer-manifest.yml").exists()
    assert (REPO_ROOT / "templates" / "ai" / "knowledge" / "index.yml").exists()
    assert (REPO_ROOT / "templates" / "workflow-state-template.json").exists()
    assert '"config" = "specify_cli/core_pack/config"' in pyproject
    assert '"templates/workflow-state-template.json" = "specify_cli/core_pack/templates/workflow-state-template.json"' in pyproject

    config = yaml.safe_load(read_text("config/automation-rules.yml"))
    assert config["policy"]["automation_scope"] == "hard-facts-only"
    assert config["policy"]["natural_language_keyword_routing"] == "forbidden"
    assert "app-data/plugins/**" in config["paths"]["runtime_artifacts"]
    assert "frontend/plugins/**" in config["paths"]["runtime_artifacts"]
    assert "dist/**" in config["paths"]["generated"]

    state = json.loads(read_text("templates/workflow-state-template.json"))
    for key in ["workflow_model", "attempts", "validations", "fact_layer", "acceptance", "retrospective", "promotion"]:
        assert key in state
    assert state["workflow_model"]["manifest"] == ".specify/templates/layer-manifest.yml"

    manifest = yaml.safe_load(read_text("templates/layer-manifest.yml"))
    assert "artifact_sets" in manifest
    assert "artifact_sections" in manifest
    assert "Knowledge" in [layer["id"] for layer in manifest["layers"]]
    assert manifest["policy"]["knowledge_routing"] == "deterministic-index, no-full-text-search"
    assert "workflow-state.json" in manifest["artifact_sets"]["implement"]
    assert "workflow-record.md" in manifest["artifact_sets"]["commit"]
    assert "improvement-candidates.md" in manifest["artifact_sets"]["commit"]
    assert "workflow-record.md" in manifest["artifact_sets"]["full-sdd-commit"]
    assert "improvement-candidates.md" in manifest["artifact_sets"]["full-sdd-commit"]
    assert "improvement-candidates.md" in manifest["artifact_sets"]["retrospective"]
    assert "L1 Artifact Contract" in manifest["artifact_sections"]["spec.md"]
    assert "L2 Artifact Contract" in manifest["artifact_sections"]["plan.md"]
    assert "L3 Artifact Contract" in manifest["artifact_sections"]["tasks.md"]


def test_knowledge_index_assets_are_packaged_selectable_and_validated():
    index = yaml.safe_load(read_text("templates/ai/knowledge/index.yml"))

    assert index["policy"]["default_context"] is False
    assert index["policy"]["no_full_text_search_required"] is True
    assert index["policy"]["max_selected_guides"] == 3
    assert "CoreServicesLib" in index["repositories"]

    validation = run_ps("validate-knowledge-index", "-RepoRoot", str(REPO_ROOT))
    assert_standard_shape(validation, "validate-knowledge-index")
    assert validation["status"] == "ok"
    assert validation["facts"]["guide_count"] >= 10
    assert validation["facts"]["absolute_path_offenders"] == []

    selected = run_ps("select-knowledge", "-RepoRoot", str(REPO_ROOT), "-Stage", "validation")
    assert_standard_shape(selected, "select-knowledge")
    assert selected["status"] == "ok"
    selected_paths = {item["path"] for item in selected["facts"]["selected"]}
    assert "ai/knowledge/build/validation-matrix.yml" in selected_paths
    assert len(selected_paths) <= selected["facts"]["max_selected_guides"]


def test_validate_knowledge_index_blocks_machine_specific_paths(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".specify").mkdir(parents=True)
    (repo / ".specify" / "workspace.yml").write_text(
        'repositories:\n  - name: DemoRepo\n    path: "<workspace-root>/DemoRepo"\n',
        encoding="utf-8",
    )
    knowledge = repo / "ai" / "knowledge"
    (knowledge / "repositories").mkdir(parents=True)
    (knowledge / "index.yml").write_text(
        '\n'.join(
            [
                'schema_version: "1.0"',
                "policy:",
                "  no_full_text_search_required: true",
                '  repository_map_authority: ".specify/memory/repository-map.md"',
                "  max_selected_guides: 3",
                "repositories:",
                "  DemoRepo:",
                '    guide: "repositories/demo.md"',
                '    tags: ["demo"]',
            ]
        ),
        encoding="utf-8",
    )
    (knowledge / "repositories" / "demo.md").write_text(
        "Do not keep C:\\Internal\\Project\\local-only paths here.\n",
        encoding="utf-8",
    )

    output = run_ps("validate-knowledge-index", "-RepoRoot", str(repo))

    assert_standard_shape(output, "validate-knowledge-index")
    assert output["status"] == "blocked"
    assert any("machine-specific knowledge paths" in blocker for blocker in output["blockers"])


def test_all_automation_scripts_exist_in_powershell_and_bash():
    for tool in AUTOMATION_TOOLS:
        assert (REPO_ROOT / "scripts" / "powershell" / f"{tool}.ps1").exists()
        assert (REPO_ROOT / "scripts" / "bash" / f"{tool}.sh").exists()


def test_sync_ui_runtime_artifacts_copies_source_output_to_runtime(tmp_path):
    source = tmp_path / "dist"
    runtime = tmp_path / "runtime" / "product-device-tree"
    source.mkdir()
    runtime.mkdir(parents=True)
    (source / "index.html").write_text("<div>new ui</div>", encoding="utf-8")
    (source / "assets").mkdir()
    (source / "assets" / "style.css").write_text(".device-tree{height:100%;}", encoding="utf-8")
    (runtime / "stale.txt").write_text("kept", encoding="utf-8")

    output = run_ps(
        "sync-ui-runtime-artifacts",
        "-SourceDir",
        str(source),
        "-RuntimeDir",
        str(runtime),
        "-PluginId",
        "product-device-tree",
    )

    assert_standard_shape(output, "sync-ui-runtime-artifacts")
    assert output["status"] == "ok"
    assert output["facts"]["plugin_id"] == "product-device-tree"
    assert output["facts"]["copied_file_count"] == 2
    assert output["facts"]["removed_stale_count"] == 1
    assert (runtime / "index.html").read_text(encoding="utf-8") == "<div>new ui</div>"
    assert (runtime / "assets" / "style.css").read_text(encoding="utf-8") == ".device-tree{height:100%;}"
    assert not (runtime / "stale.txt").exists()


def test_sync_ui_runtime_artifacts_blocks_without_explicit_plugin_scope(tmp_path):
    source = tmp_path / "dist"
    runtime = tmp_path / "runtime" / "other-plugin"
    source.mkdir()
    runtime.mkdir(parents=True)
    (source / "index.html").write_text("<div>new ui</div>", encoding="utf-8")

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "sync-ui-runtime-artifacts.ps1"),
            "-SourceDir",
            str(source),
            "-RuntimeDir",
            str(runtime),
            "-PluginId",
            "product-device-tree",
            "-Json",
        ],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    output = json.loads(result.stdout)
    assert_standard_shape(output, "sync-ui-runtime-artifacts")
    assert output["status"] == "blocked"
    assert "must match PluginId" in "\n".join(output["blockers"])


def test_inspect_desktop_shell_cdp_target_selects_business_page_and_rejects_workbench():
    targets = json.dumps(
        [
            {
                "id": "devtools",
                "type": "page",
                "title": "DevTools",
                "url": "devtools://devtools/bundled/inspector.html",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools",
            },
            {
                "id": "base",
                "type": "page",
                "title": "ExampleCorp",
                "url": "file:///C:/ExampleWorkspace/DesktopShell/DesktopShell/src/window/base-win.html",
                "webSocketDebuggerUrl": "ws://127.0.0.1/base",
            },
            {
                "id": "workbench",
                "type": "page",
                "title": "Plugin Workbench",
                "url": "file:///C:/ExampleWorkspace/DesktopShell/DesktopShell/src/plugin-host/devtools/plugin-workbench.html#build",
                "webSocketDebuggerUrl": "ws://127.0.0.1/workbench",
            },
            {
                "id": "business",
                "type": "page",
                "title": "ExampleCorp",
                "url": "http://host.example.invalid/frontend/static/index.html#/product-homepage/productHome",
                "webSocketDebuggerUrl": "ws://127.0.0.1/business",
            },
        ]
    )

    output = run_ps("inspect-desktop-shell-cdp-target", "-TargetsJson", targets)

    assert_standard_shape(output, "inspect-desktop-shell-cdp-target")
    assert output["status"] == "ok"
    assert output["facts"]["selected_target"]["id"] == "business"
    assert output["facts"]["selected_target"]["reason"] == "host-app"
    rejected_reasons = {target["reason"] for target in output["facts"]["rejected_targets"]}
    assert {"devtools", "workbench", "base-window"} <= rejected_reasons


def test_inspect_desktop_shell_cdp_target_blocks_when_only_workbench_exists():
    targets = json.dumps(
        [
            {
                "id": "workbench",
                "type": "page",
                "title": "Plugin Workbench",
                "url": "file:///C:/ExampleWorkspace/DesktopShell/DesktopShell/src/plugin-host/devtools/plugin-workbench.html#build",
                "webSocketDebuggerUrl": "ws://127.0.0.1/workbench",
            }
        ]
    )

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "inspect-desktop-shell-cdp-target.ps1"),
            "-TargetsJson",
            targets,
            "-Json",
        ],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    output = json.loads(result.stdout)
    assert output["status"] == "blocked"
    assert "No matching DesktopShell CDP target found" in "\n".join(output["blockers"])


def test_ensure_desktop_shell_cdp_host_reuses_valid_running_target():
    targets = json.dumps(
        [
            {
                "id": "workbench",
                "type": "page",
                "title": "Plugin Workbench",
                "url": "file:///C:/ExampleWorkspace/DesktopShell/DesktopShell/src/plugin-host/devtools/plugin-workbench.html#build",
                "webSocketDebuggerUrl": "ws://127.0.0.1/workbench",
            },
            {
                "id": "business",
                "type": "page",
                "title": "ExampleCorp",
                "url": "http://host.example.invalid/frontend/static/index.html#/product-homepage/productHome",
                "webSocketDebuggerUrl": "ws://127.0.0.1/business",
            },
        ]
    )

    output = run_ps("ensure-desktop-shell-cdp-host", "-TargetsJson", targets)

    assert_standard_shape(output, "ensure-desktop-shell-cdp-host")
    assert output["status"] == "ok"
    assert output["facts"]["endpoint_reachable"] is True
    assert output["facts"]["selected_target"]["id"] == "business"
    assert output["facts"]["selected_target"]["reason"] == "host-app"
    assert output["facts"]["rejected_targets"][0]["reason"] == "workbench"


def test_ensure_desktop_shell_cdp_host_blocks_before_manual_acceptance_when_target_missing():
    targets = json.dumps(
        [
            {
                "id": "workbench",
                "type": "page",
                "title": "Plugin Workbench",
                "url": "file:///C:/ExampleWorkspace/DesktopShell/DesktopShell/src/plugin-host/devtools/plugin-workbench.html#build",
                "webSocketDebuggerUrl": "ws://127.0.0.1/workbench",
            }
        ]
    )

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "ensure-desktop-shell-cdp-host.ps1"),
            "-TargetsJson",
            targets,
            "-Json",
        ],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    output = json.loads(result.stdout)
    assert_standard_shape(output, "ensure-desktop-shell-cdp-host")
    assert output["status"] == "blocked"
    assert "before manual acceptance" in "\n".join(output["blockers"])
    assert "Do not switch to human acceptance" in "\n".join(output["hints"])


def test_command_templates_define_script_fact_llm_contract():
    command_paths = sorted((REPO_ROOT / "templates" / "commands").glob("*.md"))
    assert command_paths

    for command_path in command_paths:
        text = command_path.read_text(encoding="utf-8")
        assert "## Context Contract" in text
        assert "## Stage Continuation Rule" in text
        assert "Apply the central Stage Continuation Contract" in text
        assert "Auto-continue means executing the next stage" not in text
        assert "next_required_human_action" in text
        assert "Stop only for human acceptance" not in text
        assert ".specify/memory/repository-map.md" in text
        assert "ai/workflows/task-routing.md" in text
        assert "Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`" in text
        assert "## Automation / LLM Boundary" not in text
        assert "must not use natural-language keyword matching" not in text
        for phrase in ["facts", "blockers", "unknowns", "hints"]:
            assert phrase in text

    readme = read_text("TEAM-README.md")
    rules = read_text("templates/ai/rules/ai-coding-rules.md")
    assert "Scripts output `facts`, `blockers`, `unknowns`, and `hints`" in readme
    assert "Context Loading Policy" in readme
    assert "LLM owns semantic routing" in readme or "LLM owns" in readme
    assert "LLM owns semantic routing" in rules
    assert "natural-language" in rules


def test_validate_commit_message_blocks_truncated_template(tmp_path):
    valid_message = "\n".join(
        [
            "SpecKit: enforce retrospective completion gate",
            "",
            "为 Spec Kit completion 增加复盘产物硬门禁",
            "",
            "【提交类型】",
            "修复自测问题 - Spec Kit 阶段流转治理",
            "",
            "【问题描述】",
            "1. complete-branch 缺少复盘产物硬门禁",
            "",
            "【修改方案】",
            "1. 增加 validate-commit-message 脚本和模板约束",
            "",
            "【影响评估】",
            "影响一般，影响 Spec Kit commit 阶段",
            "",
            "【兼容性分析】",
            "1. 不改变已有提交内容，仅校验提交说明格式",
            "",
            "【需要同时入库的提交】",
            "无",
            "",
            "【自测结果】",
            "1. validate-commit-message 覆盖有效和截断消息",
            "2. 相关测试通过，自测通过",
            "",
        ]
    )
    valid_file = tmp_path / "valid-commit-message.txt"
    valid_file.write_text(valid_message, encoding="utf-8")
    output = run_ps("validate-commit-message", "-MessageFile", str(valid_file))
    assert output["status"] == "ok"

    bad_message = "\n".join(
        [
            "SpecKit: enforce retrospective completion gate",
            "",
            "为 Spec Kit completion 增加复盘产物硬门禁",
            "",
            "【提交类型】",
            "",
            "Change-Id: I0123456789abcdef",
            "",
        ]
    )
    bad_file = tmp_path / "bad-commit-message.txt"
    bad_file.write_text(bad_message, encoding="utf-8")
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "validate-commit-message.ps1"),
            "-MessageFile",
            str(bad_file),
            "-Json",
        ],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert any("Missing required section" in blocker for blocker in payload["blockers"])
    assert any("no content" in blocker for blocker in payload["blockers"])

    conventional_message = "\n".join(
        [
            "fix(product-device-tree): preserve non-device selection",
            "across device list refresh",
            "",
            "修复设备列表刷新后非设备条目选中状态被设备条目覆盖",
            "",
            "【提交类型】",
            "缺陷修复",
            "",
            "【问题描述】",
            "1. 通过 QTreeView::",
            "   currentIndex() 保持选中位置",
            "",
            "【修改方案】",
            "1. 调整设备树刷新选中恢复逻辑",
            "",
            "【影响评估】",
            "影响轻微，影响设备树刷新选中状态",
            "",
            "【兼容性分析】",
            "1. 不涉及 RPC 契约变化",
            "",
            "【需要同时入库的提交】",
            "无",
            "",
            "【自测结果】",
            "1. CDP 宿主验证通过",
            "",
        ]
    )
    conventional_file = tmp_path / "conventional-commit-message.txt"
    conventional_file.write_text(conventional_message, encoding="utf-8")
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "validate-commit-message.ps1"),
            "-MessageFile",
            str(conventional_file),
            "-Json",
        ],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    blockers = "\n".join(payload["blockers"])
    assert "Conventional Commit format" in blockers
    assert "Second non-empty line must be the Chinese summary" in blockers
    assert "【提交类型】 must use '<类型> - <范围或问题域>'" in blockers
    assert "【自测结果】 must end with '相关测试通过，自测通过'" in blockers
    assert "Technical token appears split across lines" in blockers

    generic_type_message = "\n".join(
        [
            "DeviceMenu: fix context menu disabled item hover",
            "",
            "修复设备菜单不可用条目的悬浮样式",
            "",
            "【提交类型】",
            "修复 - UI 交互",
            "",
            "【问题描述】",
            "1. 不可用菜单项 hover 样式不符合预期",
            "",
            "【修改方案】",
            "1. 调整菜单项 CSS 状态样式",
            "",
            "【影响评估】",
            "影响轻微，仅影响菜单显示",
            "",
            "【兼容性分析】",
            "1. 不涉及接口或数据结构变化",
            "",
            "【需要同时入库的提交】",
            "无",
            "",
            "【自测结果】",
            "1. 相关测试通过，自测通过",
            "",
        ]
    )
    generic_type_file = tmp_path / "generic-type-commit-message.txt"
    generic_type_file.write_text(generic_type_message, encoding="utf-8")
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "validate-commit-message.ps1"),
            "-MessageFile",
            str(generic_type_file),
            "-Json",
        ],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert "scope is too generic" in "\n".join(payload["blockers"])
    assert "修复 - UI 交互" in payload["facts"]["generic_type_blocklist"]


def test_validate_feature_artifacts_blocks_missing_commit_stage_files(tmp_path):
    feature_dir = tmp_path / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")

    output = run_ps(
        "validate-feature-artifacts",
        "-FeatureDir",
        str(feature_dir),
        "-Stage",
        "commit",
        "-DeliveryProfile",
        "full-sdd",
    )

    assert_standard_shape(output, "validate-feature-artifacts")
    assert output["status"] == "blocked"
    blocker_text = "\n".join(output["blockers"])
    for missing in [
        "plan.md",
        "tasks.md",
        "validation.md",
        "acceptance.md",
        "workflow-state.json",
        "workflow-record.md",
        "improvement-candidates.md",
    ]:
        assert missing in blocker_text
    assert output["facts"]["required_source"] == "layer-manifest.yml"


def test_validate_feature_artifacts_uses_layer_manifest_and_required_sections(tmp_path):
    feature_dir = tmp_path / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## L1 Artifact Contract\n\n## 人类审核摘要\n\n## 能力概览\n\n"
        "## 能力场景\n\n## 功能需求\n\n## 验证预期\n",
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text(
        "# Plan\n\n## L2 Artifact Contract\n\n## 人类审核摘要\n\n## Root Cause Evidence\n\n"
        "## 技术上下文\n\n## 影响模块与边界\n\n## Implementation Slices\n\n## 验证计划\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## L3 Artifact Contract\n\n## 人类审核摘要\n\n## Implementation Slices\n\n"
        "## Phase 1\n\n## Phase 2\n\n## Phase N\n",
        encoding="utf-8",
    )
    (feature_dir / "workflow-state.json").write_text(
        json.dumps(
            {
                "attempts": [],
                "validations": [],
                "fact_layer": {},
                "acceptance": {},
                "retrospective": {},
                "promotion": {},
            }
        ),
        encoding="utf-8",
    )
    (feature_dir / "analysis.md").write_text(
        "## 人类审核摘要\n\n## Specification Analysis Report\n\n"
        "## Traceability Summary\n\n## Suggested Next Action\n",
        encoding="utf-8",
    )
    checklist = feature_dir / "checklists" / "implementation-readiness.md"
    checklist.parent.mkdir()
    checklist.write_text("## 人类审核摘要\n\n## 生成策略\n\n## 验证\n", encoding="utf-8")

    output = run_ps(
        "validate-feature-artifacts",
        "-FeatureDir",
        str(feature_dir),
        "-Stage",
        "implement",
        "-DeliveryProfile",
        "full-sdd",
    )

    assert_standard_shape(output, "validate-feature-artifacts")
    assert output["status"] == "ok"
    assert output["facts"]["required_source"] == "layer-manifest.yml"
    assert "workflow-state.json" in output["facts"]["required"]
    assert output["facts"]["missing_sections"] == []


def test_validate_feature_artifacts_allows_standard_bugfix_plan_slices_without_tasks(tmp_path):
    feature_dir = tmp_path / "specs" / "001-standard"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## L1 Artifact Contract\n\n## 人类审核摘要\n\n## 能力概览\n\n"
        "## 能力场景\n\n## 功能需求\n\n## 验证预期\n",
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text(
        "# Plan\n\n## L2 Artifact Contract\n\n## 人类审核摘要\n\n## Root Cause Evidence\n\n"
        "## 技术上下文\n\n## 影响模块与边界\n\n## 验证计划\n\n## Implementation Slices\n",
        encoding="utf-8",
    )
    (feature_dir / "workflow-state.json").write_text(
        json.dumps(
            {
                "attempts": [],
                "validations": [],
                "fact_layer": {},
                "acceptance": {},
                "retrospective": {},
                "promotion": {},
            }
        ),
        encoding="utf-8",
    )

    output = run_ps(
        "validate-feature-artifacts",
        "-FeatureDir",
        str(feature_dir),
        "-Stage",
        "implement",
        "-DeliveryProfile",
        "standard-bugfix",
    )

    assert_standard_shape(output, "validate-feature-artifacts")
    assert output["status"] == "ok"
    assert "tasks.md" not in output["facts"]["required"]


def test_validate_feature_artifacts_enforces_full_sdd_implementation_gates(tmp_path):
    repo = tmp_path
    (repo / ".specify").mkdir()
    (repo / ".specify" / "feature.json").write_text(
        json.dumps(
            {
                "delivery_profile": "full-sdd",
                "risk_level": "high",
                "risk_flags": ["ui-parity", "host-embedded-ui"],
            }
        ),
        encoding="utf-8",
    )
    feature_dir = repo / "specs" / "001-full"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## L1 Artifact Contract\n\n## 人类审核摘要\n\n## 能力概览\n\n"
        "## 能力场景\n\n## 功能需求\n\n## 验证预期\n",
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text(
        "# Plan\n\n## L2 Artifact Contract\n\n## 人类审核摘要\n\n## Root Cause Evidence\n\n"
        "## 技术上下文\n\n## 影响模块与边界\n\n## Implementation Slices\n\n## 验证计划\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## L3 Artifact Contract\n\n## 人类审核摘要\n\n## Implementation Slices\n\n",
        encoding="utf-8",
    )
    (feature_dir / "workflow-state.json").write_text(
        '{"attempts":[],"validations":[],"fact_layer":{},"acceptance":{},"retrospective":{},"promotion":{}}',
        encoding="utf-8",
    )

    blocked = run_ps(
        "validate-feature-artifacts",
        "-RepoRoot",
        str(repo),
        "-FeatureDir",
        str(feature_dir),
        "-Stage",
        "implement",
        "-DeliveryProfile",
        "auto",
    )

    assert blocked["status"] == "blocked"
    assert blocked["facts"]["effective_delivery_profile"] == "full-sdd"
    assert "analysis.md" in blocked["facts"]["required"]
    assert "checklists/implementation-readiness.md" in blocked["facts"]["required"]
    assert "analysis.md" in "\n".join(blocked["blockers"])
    assert "checklists/implementation-readiness.md" in "\n".join(blocked["blockers"])

    (feature_dir / "analysis.md").write_text(
        "## 人类审核摘要\n\n## Specification Analysis Report\n\n"
        "## Traceability Summary\n\n## Suggested Next Action\n",
        encoding="utf-8",
    )
    checklist = feature_dir / "checklists" / "implementation-readiness.md"
    checklist.parent.mkdir()
    checklist.write_text("## 人类审核摘要\n\n## 生成策略\n\n## 验证\n", encoding="utf-8")

    ok = run_ps(
        "validate-feature-artifacts",
        "-RepoRoot",
        str(repo),
        "-FeatureDir",
        str(feature_dir),
        "-Stage",
        "implement",
        "-DeliveryProfile",
        "auto",
    )
    assert ok["status"] == "ok"


def test_validate_generated_context_reports_drift_and_accepts_required_phrases(tmp_path):
    repo = tmp_path
    (repo / ".specify" / "memory").mkdir(parents=True)
    (repo / ".specify" / "templates").mkdir(parents=True)
    (repo / "ai" / "workflows").mkdir(parents=True)
    (repo / "ai" / "rules").mkdir(parents=True)
    (repo / "tools" / "spec-kit" / "workflows" / "speckit").mkdir(parents=True)
    (repo / ".agents" / "skills" / "speckit-commit").mkdir(parents=True)
    (repo / ".agents" / "skills" / "speckit-implement").mkdir(parents=True)
    (repo / ".agents" / "skills" / "speckit-retrospective").mkdir(parents=True)
    (repo / ".agents" / "skills" / "speckit-tasks").mkdir(parents=True)
    (repo / "AGENTS.md").write_text("# old agents\n", encoding="utf-8")
    (repo / ".specify" / "memory" / "repository-map.md").write_text("# old map\n", encoding="utf-8")
    (repo / ".specify" / "templates" / "layer-manifest.yml").write_text("artifact_sets: {}\n", encoding="utf-8")
    (repo / "ai" / "workflows" / "task-routing.md").write_text("# old routing\n", encoding="utf-8")
    (repo / "ai" / "rules" / "ai-coding-rules.md").write_text("# old rules\n", encoding="utf-8")
    (repo / "tools" / "spec-kit" / "workflows" / "speckit" / "workflow.yml").write_text(
        "id: commit\nid: retrospective\n",
        encoding="utf-8",
    )
    (repo / "tools" / "spec-kit" / "TEAM-README.md").write_text(
        "commit -> retrospective/留痕\n",
        encoding="utf-8",
    )
    (repo / ".agents" / "skills" / "speckit-commit" / "SKILL.md").write_text(
        "Retrospective and lesson promotion are optional\n",
        encoding="utf-8",
    )
    (repo / ".agents" / "skills" / "speckit-tasks" / "SKILL.md").write_text(
        "optional test-hardening, commit, and branch completion\n",
        encoding="utf-8",
    )

    blocked = run_ps("validate-generated-context", "-RepoRoot", str(repo))
    assert blocked["status"] == "blocked"
    blocker_text = "\n".join(blocked["blockers"])
    assert "AGENTS.md missing required generated-context phrases" in blocker_text
    assert "ai/workflows/task-routing.md missing required generated-context phrases" in blocker_text
    assert ".agents/skills/speckit-commit/SKILL.md missing required generated-context phrases" in blocker_text

    (repo / "AGENTS.md").write_text(
        "Project Path Categories\nsource-to-runtime copy\nbest-effort self-validation\n"
        "direct runtime replacement\nDesktopShell CDP validation\n"
        "ensure-desktop-shell-cdp-host\n"
        "stale/current-feature hint\nread the current plan only\n"
        "select-knowledge\nvalidate-knowledge-index\n",
        encoding="utf-8",
    )
    (repo / ".specify" / "memory" / "repository-map.md").write_text(
        "Project Path Categories\n<workspace-root>/ProductUIPlugin/<plugin-id>/\n"
        "CDP target inventory\nDo not write machine-specific absolute paths here\n",
        encoding="utf-8",
    )
    (repo / ".specify" / "templates" / "layer-manifest.yml").write_text(
        "stage_gates:\nread_strategies:\nKnowledge\nvalidate-knowledge-index\n"
        "checklists/implementation-readiness.md\n",
        encoding="utf-8",
    )
    (repo / "ai" / "workflows" / "task-routing.md").write_text(
        "tasks -> analyze -> checklist\nvalidate-generated-context\nvalidate-knowledge-index\n"
        "select-knowledge\nartifact_sections\n"
        "Stage Continuation\ninspect-desktop-shell-cdp-target\n"
        "ensure-desktop-shell-cdp-host\n"
        "do not apply stale feature risk flags\n",
        encoding="utf-8",
    )
    (repo / "ai" / "rules" / "ai-coding-rules.md").write_text(
        "Generated Context Drift\nanalysis.md\nvalidate-generated-context\nvalidate-knowledge-index\n"
        "Stage Continuation Contract\nHost Frontend Delivery Chain\n"
        "ensure-desktop-shell-cdp-host\n"
        "Retrospective/留痕 is mandatory before commit\n",
        encoding="utf-8",
    )
    (repo / "tools" / "spec-kit" / "workflows" / "speckit" / "workflow.yml").write_text(
        "id: retrospective\nid: commit\nRequire workflow-record.md and improvement-candidates.md before commit\n"
        "automatic_stage_continuation\ninspect-desktop-shell-cdp-target\n"
        "ensure-desktop-shell-cdp-host\n"
        "validate-knowledge-index\ncurrent-feature state only\n",
        encoding="utf-8",
    )
    (repo / "tools" / "spec-kit" / "TEAM-README.md").write_text(
        "retrospective/留痕 -> commit\ncommit 前强制 retrospective\n"
        "source edit -> frontend build -> direct runtime replacement -> real host CDP verification\n"
        "select-knowledge\nfull-text/BM25 search\n",
        encoding="utf-8",
    )
    (repo / ".agents" / "skills" / "speckit-commit" / "SKILL.md").write_text(
        "validate-feature-artifacts\nStage commit\nworkflow-record.md\n"
        "improvement-candidates.md\nretrospective.status\n",
        encoding="utf-8",
    )
    (repo / ".agents" / "skills" / "speckit-implement" / "SKILL.md").write_text(
        "ensure-desktop-shell-cdp-host\nCDP host recovery ladder\nmanual acceptance\n",
        encoding="utf-8",
    )
    (repo / ".agents" / "skills" / "speckit-retrospective" / "SKILL.md").write_text(
        "Existing Constraint Audit\nAI workflow self-check\nTeam knowledge candidates\nretrospective.status\n",
        encoding="utf-8",
    )
    (repo / ".agents" / "skills" / "speckit-tasks" / "SKILL.md").write_text(
        "Run mandatory `speckit.retrospective` / 留痕 after quick acceptance and before commit\n"
        "optional test-hardening, retrospective/留痕\n",
        encoding="utf-8",
    )

    ok = run_ps("validate-generated-context", "-RepoRoot", str(repo))
    assert ok["status"] == "ok"


def test_validate_generated_context_uses_init_options_context_file(tmp_path):
    repo = tmp_path
    (repo / ".specify" / "memory").mkdir(parents=True)
    (repo / ".specify" / "templates").mkdir(parents=True)
    (repo / "ai" / "workflows").mkdir(parents=True)
    (repo / "ai" / "rules").mkdir(parents=True)
    (repo / "tools" / "spec-kit" / "workflows" / "speckit").mkdir(parents=True)
    (repo / ".claude" / "skills" / "speckit-commit").mkdir(parents=True)
    (repo / ".claude" / "skills" / "speckit-implement").mkdir(parents=True)
    (repo / ".claude" / "skills" / "speckit-retrospective").mkdir(parents=True)
    (repo / ".claude" / "skills" / "speckit-tasks").mkdir(parents=True)
    (repo / ".specify" / "init-options.json").write_text(
        json.dumps({"context_file": "CLAUDE.md", "canonical_context_file": "AGENTS.md"}),
        encoding="utf-8",
    )
    (repo / "CLAUDE.md").write_text(
        "@AGENTS.md\n.claude/skills\n/speckit-specify\n/speckit-plan\n"
        "/speckit-tasks\n/speckit-implement\n",
        encoding="utf-8",
    )
    (repo / "AGENTS.md").write_text(
        "Project Path Categories\nsource-to-runtime copy\nbest-effort self-validation\n"
        "direct runtime replacement\nDesktopShell CDP validation\n"
        "ensure-desktop-shell-cdp-host\n"
        "stale/current-feature hint\nread the current plan only\n"
        "select-knowledge\nvalidate-knowledge-index\n",
        encoding="utf-8",
    )
    (repo / ".specify" / "memory" / "repository-map.md").write_text(
        "Project Path Categories\n<workspace-root>/ProductUIPlugin/<plugin-id>/\n"
        "CDP target inventory\nDo not write machine-specific absolute paths here\n",
        encoding="utf-8",
    )
    (repo / ".specify" / "templates" / "layer-manifest.yml").write_text(
        "stage_gates:\nread_strategies:\nKnowledge\nvalidate-knowledge-index\n"
        "checklists/implementation-readiness.md\n",
        encoding="utf-8",
    )
    (repo / "ai" / "workflows" / "task-routing.md").write_text(
        "tasks -> analyze -> checklist\nvalidate-generated-context\nvalidate-knowledge-index\n"
        "select-knowledge\nartifact_sections\n"
        "Stage Continuation\ninspect-desktop-shell-cdp-target\n"
        "ensure-desktop-shell-cdp-host\n"
        "do not apply stale feature risk flags\n",
        encoding="utf-8",
    )
    (repo / "ai" / "rules" / "ai-coding-rules.md").write_text(
        "Generated Context Drift\nanalysis.md\nvalidate-generated-context\nvalidate-knowledge-index\n"
        "Stage Continuation Contract\nHost Frontend Delivery Chain\n"
        "ensure-desktop-shell-cdp-host\n"
        "Retrospective/留痕 is mandatory before commit\n",
        encoding="utf-8",
    )
    (repo / "tools" / "spec-kit" / "workflows" / "speckit" / "workflow.yml").write_text(
        "id: retrospective\nid: commit\nRequire workflow-record.md and improvement-candidates.md before commit\n"
        "automatic_stage_continuation\ninspect-desktop-shell-cdp-target\n"
        "ensure-desktop-shell-cdp-host\n"
        "validate-knowledge-index\ncurrent-feature state only\n",
        encoding="utf-8",
    )
    (repo / "tools" / "spec-kit" / "TEAM-README.md").write_text(
        "retrospective/留痕 -> commit\ncommit 前强制 retrospective\n"
        "source edit -> frontend build -> direct runtime replacement -> real host CDP verification\n"
        "select-knowledge\nfull-text/BM25 search\n",
        encoding="utf-8",
    )
    (repo / ".claude" / "skills" / "speckit-commit" / "SKILL.md").write_text(
        "validate-feature-artifacts\nStage commit\nworkflow-record.md\n"
        "improvement-candidates.md\nretrospective.status\n",
        encoding="utf-8",
    )
    (repo / ".claude" / "skills" / "speckit-implement" / "SKILL.md").write_text(
        "ensure-desktop-shell-cdp-host\nCDP host recovery ladder\nmanual acceptance\n",
        encoding="utf-8",
    )
    (repo / ".claude" / "skills" / "speckit-retrospective" / "SKILL.md").write_text(
        "Existing Constraint Audit\nAI workflow self-check\nTeam knowledge candidates\nretrospective.status\n",
        encoding="utf-8",
    )
    (repo / ".claude" / "skills" / "speckit-tasks" / "SKILL.md").write_text(
        "Run mandatory `speckit.retrospective` / 留痕 after quick acceptance and before commit\n"
        "optional test-hardening, retrospective/留痕\n",
        encoding="utf-8",
    )

    ok = run_ps("validate-generated-context", "-RepoRoot", str(repo))
    assert ok["status"] == "ok"
    checked_paths = [entry["path"] for entry in ok["facts"]["checked"]]
    assert checked_paths[0] == "CLAUDE.md"
    assert checked_paths[1] == "AGENTS.md"

    (repo / "CLAUDE.md").write_text(
        ".claude/skills\n/speckit-specify\n/speckit-plan\n"
        "/speckit-tasks\n/speckit-implement\n",
        encoding="utf-8",
    )
    blocked = run_ps("validate-generated-context", "-RepoRoot", str(repo))
    assert blocked["status"] == "blocked"
    assert any(
        "CLAUDE.md missing required generated-context phrases: @AGENTS.md" in blocker
        for blocker in blocked["blockers"]
    )


def test_validate_feature_artifacts_blocks_missing_layer_sections(tmp_path):
    feature_dir = tmp_path / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("L1 Artifact Contract\n人类审核摘要\n能力概览\n能力场景\n功能需求\n验证预期\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("Root Cause Evidence\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("L3 Artifact Contract\n人类审核摘要\nImplementation Slices\nPhase 1\nPhase 2\nPhase N\n", encoding="utf-8")
    (feature_dir / "workflow-state.json").write_text('{"attempts":[],"validations":[],"fact_layer":{},"acceptance":{},"retrospective":{},"promotion":{}}', encoding="utf-8")

    output = run_ps(
        "validate-feature-artifacts",
        "-FeatureDir",
        str(feature_dir),
        "-Stage",
        "implement",
    )

    assert output["status"] == "blocked"
    assert "plan.md missing required sections" in "\n".join(output["blockers"])
    assert output["facts"]["missing_sections"][0]["file"] == "plan.md"


def test_validate_feature_artifacts_blocks_commit_without_retrospective(tmp_path):
    feature_dir = tmp_path / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## L1 Artifact Contract\n\n## 人类审核摘要\n\n## 能力概览\n\n"
        "## 能力场景\n\n## 功能需求\n\n## 验证预期\n",
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text(
        "# Plan\n\n## L2 Artifact Contract\n\n## 人类审核摘要\n\n## Root Cause Evidence\n\n"
        "## 技术上下文\n\n## 影响模块与边界\n\n## Implementation Slices\n\n## 验证计划\n",
        encoding="utf-8",
    )
    (feature_dir / "validation.md").write_text(
        "# Validation\n\n## Validation Matrix\n\n## Result Interpretation\n\n## Evidence Links\n",
        encoding="utf-8",
    )
    (feature_dir / "acceptance.md").write_text("# Acceptance\n", encoding="utf-8")
    (feature_dir / "workflow-state.json").write_text(
        '{"attempts":[],"validations":[],"fact_layer":{},"acceptance":{},"retrospective":{},"promotion":{}}',
        encoding="utf-8",
    )

    blocked = run_ps(
        "validate-feature-artifacts",
        "-FeatureDir",
        str(feature_dir),
        "-Stage",
        "commit",
    )

    assert blocked["status"] == "blocked"
    blocker_text = "\n".join(blocked["blockers"])
    assert "workflow-record.md" in blocker_text
    assert "improvement-candidates.md" in blocker_text
    assert "retrospective.status must be completed before commit" in blocker_text
    assert blocked["facts"]["retrospective_gate"]["gate_status"] == "blocked"
    assert blocked["facts"]["retrospective_gate"]["status"] == ""

    (feature_dir / "workflow-record.md").write_text("# Workflow Record\n", encoding="utf-8")
    (feature_dir / "improvement-candidates.md").write_text("# Improvement Candidates\n", encoding="utf-8")
    still_blocked = run_ps(
        "validate-feature-artifacts",
        "-FeatureDir",
        str(feature_dir),
        "-Stage",
        "commit",
    )
    assert still_blocked["status"] == "blocked"
    assert "retrospective.status must be completed before commit" in "\n".join(still_blocked["blockers"])

    (feature_dir / "workflow-state.json").write_text(
        json.dumps(
            {
                "attempts": [],
                "validations": [],
                "fact_layer": {},
                "acceptance": {},
                "retrospective": {
                    "status": "completed",
                    "workflow_record": "workflow-record.md",
                    "improvement_candidates": "improvement-candidates.md",
                },
                "promotion": {},
            }
        ),
        encoding="utf-8",
    )
    ok = run_ps(
        "validate-feature-artifacts",
        "-FeatureDir",
        str(feature_dir),
        "-Stage",
        "commit",
    )
    assert ok["status"] == "ok"
    assert ok["facts"]["retrospective_gate"]["gate_status"] == "ok"
    assert ok["facts"]["retrospective_gate"]["status"] == "completed"


def test_suggest_validation_emits_candidates_without_sufficiency_claim(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run", "build": "vite build"}}),
        encoding="utf-8",
    )
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (repo / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n", encoding="utf-8")

    output = run_ps("suggest-validation", "-RepoRoot", str(repo))

    assert_standard_shape(output, "suggest-validation")
    assert output["status"] == "ok"
    commands = [hint["command"] for hint in output["hints"]]
    assert "npm test" in commands
    assert "npm run build" in commands
    assert "pytest" in commands
    assert "cmake --build <build-dir>" in commands
    assert all("sufficient" not in json.dumps(hint).lower() for hint in output["hints"])
    assert output["facts"]["validation_artifacts"] == ["validation.md", "acceptance.md"]
    assert output["facts"]["optional_evidence_artifacts"] == [
        "evidence.md",
        "fact-pack.md",
    ]
    assert output["facts"]["validation_template"] == "ai/templates/validation-template.md"
    assert output["facts"]["evidence_template"] == "ai/templates/evidence-template.md"
    assert output["facts"]["evidence_required"] == "complex_or_runtime_or_tool_heavy"

    bash_common = read_text("scripts/bash/automation-common.sh")
    assert "validation_artifacts" in bash_common
    assert "ai/templates/validation-template.md" in bash_common
    assert "ai/templates/evidence-template.md" in bash_common


def test_inspect_commit_scope_classifies_hard_boundaries(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "master")
    run_git(repo, "config", "user.email", "spec-kit@example.invalid")
    run_git(repo, "config", "user.name", "Spec Kit Test")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-m", "base")

    for rel in [
        "src/main.ts",
        "tests/test_main.py",
        "specs/001-demo/spec.md",
        "dist/bundle.js",
        "app-data/plugins/demo/dist/index.js",
        ".pytest_cache/cache.txt",
        "mystery.bin",
    ]:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("changed\n", encoding="utf-8")

    output = run_ps("inspect-commit-scope", "-RepoRoot", str(repo))

    assert_standard_shape(output, "inspect-commit-scope")
    classified = output["facts"]["classified"]
    assert "src/main.ts" in classified["source"]
    assert "tests/test_main.py" in classified["test"]
    assert "specs/001-demo/spec.md" in classified["spec"]
    assert "dist/bundle.js" in classified["generated"]
    assert "app-data/plugins/demo/dist/index.js" in classified["runtime"]
    assert ".pytest_cache/cache.txt" in classified["temp"]
    assert "mystery.bin" in classified["unknown"]
    assert "mystery.bin" in output["unknowns"]


def test_validate_fact_layer_gate_uses_structured_state_only(tmp_path):
    missing = run_ps("validate-fact-layer-gate", "-WorkflowState", str(tmp_path / "missing.json"))
    assert_standard_shape(missing, "validate-fact-layer-gate")
    assert missing["status"] == "blocked"

    state_path = tmp_path / "workflow-state.json"
    state_path.write_text(
        json.dumps(
            {
                "attempts": [
                    {
                        "id": "a1",
                        "area": "ui-layout",
                        "target": "info-panel",
                        "result": "failed",
                        "symptom_changed": False,
                        "fact_layer_after_failure": False,
                    }
                ],
                "fact_layer": {"status": "missing"},
            }
        ),
        encoding="utf-8",
    )
    blocked = run_ps("validate-fact-layer-gate", "-WorkflowState", str(state_path))
    assert blocked["status"] == "blocked"
    assert "a1" in "\n".join(blocked["blockers"])

    state_path.write_text(
        json.dumps(
            {
                "attempts": [
                    {
                        "id": "a1",
                        "area": "ui-layout",
                        "target": "info-panel",
                        "result": "failed",
                        "symptom_changed": False,
                        "fact_layer_after_failure": True,
                    }
                ],
                "fact_layer": {"status": "collected"},
            }
        ),
        encoding="utf-8",
    )
    ok = run_ps("validate-fact-layer-gate", "-WorkflowState", str(state_path))
    assert ok["status"] == "ok"


def test_inspect_source_artifact_consistency_blocks_runtime_only_patch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "master")
    run_git(repo, "config", "user.email", "spec-kit@example.invalid")
    run_git(repo, "config", "user.name", "Spec Kit Test")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-m", "base")

    runtime_file = repo / "app-data" / "plugins" / "demo" / "dist" / "index.js"
    runtime_file.parent.mkdir(parents=True, exist_ok=True)
    runtime_file.write_text("runtime patch\n", encoding="utf-8")

    output = run_ps("inspect-source-artifact-consistency", "-RepoRoot", str(repo))

    assert_standard_shape(output, "inspect-source-artifact-consistency")
    assert output["status"] == "blocked"
    assert "runtime/generated artifacts changed without repository source changes" in "\n".join(output["blockers"])


def test_parse_promotion_candidates_reports_review_states_only(tmp_path):
    candidates = tmp_path / "improvement-candidates.md"
    candidates.write_text(
        """
## Candidate A
人工审核结论: approved

## Candidate B
人工审核结论: pending

## Candidate C
人工审核结论: rejected
""",
        encoding="utf-8",
    )

    output = run_ps("parse-promotion-candidates", "-CandidatesPath", str(candidates))

    assert_standard_shape(output, "parse-promotion-candidates")
    assert output["status"] == "ok"
    assert output["facts"]["counts"] == {"approved": 1, "pending": 1, "rejected": 1}
    assert output["blockers"] == []
