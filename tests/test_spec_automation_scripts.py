import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]

AUTOMATION_TOOLS = [
    "validate-feature-artifacts",
    "validate-generated-context",
    "select-knowledge",
    "select-gates",
    "validate-knowledge-index",
    "select-capability",
    "validate-context-budget",
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
    "inspect-validation-capabilities",
    "validate-commit-message",
    "sync-ui-runtime-artifacts",
    "sync-native-runtime-artifacts",
    "validate-rpc-proto-bundle",
    "inspect-host-cdp-target",
    "ensure-host-cdp",
    "capture-cdp-screenshot",
    "cdp-common",
    "inspect-workspace-repositories",
    "validate-test-plan",
    "validate-ai-self-acceptance",
    "inspect-plugin-build-plan",
    "validate-plugin-package",
    "post-commit-self-check",
    "validate-rubric-score",
    "cleanup-host-cdp",
    "generate-knowledge-pack",
    "evaluate-knowledge-pack-synthesis",
    "export-knowledge-pack",
    "install-knowledge-pack",
    "compose-knowledge-packs",
    "apply-knowledge-pack",
    "update-knowledge-pack",
    "uninstall-knowledge-pack",
    "repack-knowledge-pack",
    "validate-knowledge-pack",
    "compare-knowledge-pack-equivalence",
    "get-spec-kit-version",
    "validate-spec-kit-version",
    "bump-spec-kit-version",
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


def run_specify_cli(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "import specify_cli; specify_cli.main()",
            *args,
        ],
        cwd=project,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
    )


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
    assert (REPO_ROOT / "templates" / "ai" / "knowledge" / "build" / "validation-capabilities.yml").exists()
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
    assert "gates" in manifest["read_strategies"]
    assert "Knowledge" in [layer["id"] for layer in manifest["layers"]]
    assert manifest["policy"]["knowledge_routing"] == "deterministic-index, no-full-text-search"
    assert manifest["policy"]["gate_routing"] == "deterministic-gate-packs, no-command-manuals"
    assert "workflow-state.json" in manifest["artifact_sets"]["implement"]
    assert "workflow-record.md" in manifest["artifact_sets"]["commit"]
    assert "improvement-candidates.md" in manifest["artifact_sets"]["commit"]
    assert "workflow-record.md" in manifest["artifact_sets"]["full-sdd-commit"]
    assert "improvement-candidates.md" in manifest["artifact_sets"]["full-sdd-commit"]
    assert "improvement-candidates.md" in manifest["artifact_sets"]["retrospective"]
    assert "L1 Artifact Contract" in manifest["artifact_sections"]["spec.md"]
    assert "L2 Artifact Contract" in manifest["artifact_sections"]["plan.md"]
    assert "AI Context Contract" in manifest["artifact_sections"]["plan.md"]
    assert "Validation Context Contract" in manifest["artifact_sections"]["validation.md"]
    assert "L3 Artifact Contract" in manifest["artifact_sections"]["tasks.md"]


def test_gate_packs_are_selectable_and_context_budgeted():
    index = yaml.safe_load(read_text("templates/ai/workflows/gates/index.yml"))

    assert index["policy"]["default_context"] is False
    assert index["policy"]["max_selected_gates"] == 6
    assert "host-cdp" in index["gates"]
    assert "native-bridge" in index["gates"]

    selected = run_ps("select-gates", "-RepoRoot", str(REPO_ROOT), "-Stage", "implement")
    assert_standard_shape(selected, "select-gates")
    assert selected["status"] == "ok"
    selected_ids = {item["id"] for item in selected["facts"]["selected"]}
    assert {"host-cdp", "frontend-runtime-sync", "native-bridge", "qt-parity", "real-device", "plugin-package"} <= selected_ids
    assert all(item["path"].startswith("ai/workflows/gates/") for item in selected["facts"]["selected"])

    repo = REPO_ROOT.parent
    budget = run_ps("validate-context-budget", "-RepoRoot", str(repo))
    assert_standard_shape(budget, "validate-context-budget")
    assert budget["status"] == "ok"
    assert budget["facts"]["over_budget"] == []


def test_knowledge_index_assets_are_packaged_selectable_and_validated():
    index = yaml.safe_load(read_text("templates/ai/knowledge/index.yml"))

    assert index["policy"]["default_context"] is False
    assert index["policy"]["no_full_text_search_required"] is True
    assert index["policy"]["max_selected_guides"] == 3
    assert index["policy"]["default_authority"] == "generated"
    assert "authority_levels" in index["policy"]
    assert index["repositories"] is None

    validation = run_ps("validate-knowledge-index", "-RepoRoot", str(REPO_ROOT))
    assert_standard_shape(validation, "validate-knowledge-index")
    assert validation["status"] == "ok"
    assert validation["facts"]["guide_count"] >= 10
    assert validation["facts"]["absolute_path_offenders"] == []
    assert validation["facts"]["invalid_authorities"] == []
    assert validation["facts"]["generated_guides"]

    selected = run_ps("select-knowledge", "-RepoRoot", str(REPO_ROOT), "-Stage", "validation")
    assert_standard_shape(selected, "select-knowledge")
    assert selected["status"] == "ok"
    selected_paths = {item["path"] for item in selected["facts"]["selected"]}
    assert "ai/knowledge/build/validation-matrix.yml" in selected_paths
    assert all(item["authority"] == "generated" for item in selected["facts"]["selected"])
    assert len(selected_paths) <= selected["facts"]["max_selected_guides"]

    selected_plan = run_ps("select-knowledge", "-RepoRoot", str(REPO_ROOT), "-Stage", "plan")
    plan_paths = {item["path"] for item in selected_plan["facts"]["selected"]}
    assert "ai/knowledge/build/validation-capabilities.yml" in plan_paths


def test_bootstrap_knowledge_generates_reviewable_draft(tmp_path):
    workspace = tmp_path / "workspace"
    repo = workspace / "demo-api"
    repo.mkdir(parents=True)
    (workspace / ".specify").mkdir()
    (workspace / ".specify" / "workspace.yml").write_text(
        '\n'.join(
            [
                'repositories:',
                '  - name: DemoApi',
                '    path: "demo-api"',
                '    required: true',
            ]
        ),
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text("[project]\nname='demo-api'\n", encoding="utf-8")
    (repo / "tests").mkdir()

    output = run_ps("bootstrap-knowledge", "-RepoRoot", str(workspace), cwd=workspace)

    assert_standard_shape(output, "bootstrap-knowledge")
    assert output["status"] == "ok"
    assert output["facts"]["mode"] == "generated-draft"
    assert output["facts"]["generated_review_packet"] is True
    draft_dir = Path(output["facts"]["draft_knowledge_dir"])
    assert (draft_dir / "index.yml").exists()
    assert Path(output["facts"]["source_read_plan"]).exists()
    assert Path(output["facts"]["claim_ledger"]).exists()
    assert Path(output["facts"]["evaluation_scenarios"]).exists()
    overview = (draft_dir / "workspace" / "overview.md").read_text(encoding="utf-8")
    assert str(workspace) not in overview
    assert "Workspace root: ." in overview
    repo_guide = (draft_dir / "repositories" / "demoapi.md").read_text(encoding="utf-8")
    assert "authority: generated" in repo_guide
    assert "python -m pytest" in repo_guide
    claim_ledger = json.loads(Path(output["facts"]["claim_ledger"]).read_text(encoding="utf-8"))
    assert claim_ledger["status"] == "needs_ai_review"
    assert claim_ledger["claims"][0]["status"] == "needs_ai_review"


def test_bootstrap_knowledge_exports_generated_pack_with_ai_review_contract(tmp_path):
    workspace = tmp_path / "workspace"
    repo = workspace / "demo-api"
    repo.mkdir(parents=True)
    (workspace / ".specify" / "memory").mkdir(parents=True)
    (workspace / ".specify" / "workspace.yml").write_text(
        '\n'.join(
            [
                'repositories:',
                '  - name: DemoApi',
                '    path: "demo-api"',
                '    required: true',
            ]
        ),
        encoding="utf-8",
    )
    (workspace / ".specify" / "memory" / "repository-map.md").write_text(
        "# Repository Map\n\n## Project Path Categories\n\nDo not write machine-specific absolute paths here.\n",
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text("[project]\nname='demo-api'\n", encoding="utf-8")
    (repo / "README.md").write_text("# Demo API\n", encoding="utf-8")
    (repo / "tests").mkdir()

    output = run_ps(
        "bootstrap-knowledge",
        "-RepoRoot",
        str(workspace),
        "-ExportPack",
        "-PackId",
        "demo-ai-pack",
        "-IncludeProfiles",
        cwd=workspace,
    )

    assert_standard_shape(output, "bootstrap-knowledge")
    assert output["status"] == "ok"
    assert output["facts"]["mode"] == "generated-draft"
    assert output["facts"]["generated_review_packet"] is True
    assert output["facts"]["export_pack"] is True
    pack = output["facts"]["pack"]
    assert pack["status"] == "ok"
    assert pack["facts"]["pack_id"] == "demo-ai-pack"
    assert pack["facts"]["workspace_profile"] is True
    assert pack["facts"]["repository_map_profile"] is True
    assert pack["facts"]["evaluation_scenarios"] is True
    assert pack["facts"]["validation"]["status"] == "ok"
    assert pack["facts"]["validation"]["facts"]["evaluation_scenario_count"] == 1

    pack_root = Path(pack["facts"]["pack_root"])
    assert (pack_root / "knowledge-pack.yml").exists()
    assert (pack_root / "profiles" / "workspace.yml").exists()
    assert (pack_root / "profiles" / "repository-map.md").exists()
    scenarios = json.loads((pack_root / "evaluation" / "scenarios.json").read_text(encoding="utf-8"))
    assert scenarios[0]["affected_repositories"] == ["DemoApi"]
    pack_overview = (pack_root / "ai" / "knowledge" / "workspace" / "overview.md").read_text(encoding="utf-8")
    assert str(workspace) not in pack_overview
    assert "Workspace root: ." in pack_overview


def test_generate_knowledge_pack_creates_ai_contract_workspace_and_pack(tmp_path):
    workspace = tmp_path / "workspace"
    repo = workspace / "demo-api"
    repo.mkdir(parents=True)
    (workspace / ".specify" / "memory").mkdir(parents=True)
    (workspace / ".specify" / "workspace.yml").write_text(
        '\n'.join(
            [
                'repositories:',
                '  - name: DemoApi',
                '    path: "demo-api"',
                '    required: true',
            ]
        ),
        encoding="utf-8",
    )
    (workspace / ".specify" / "memory" / "repository-map.md").write_text(
        "# Repository Map\n\nDemoApi owns API behavior.\n",
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text("[project]\nname='demo-api'\n", encoding="utf-8")
    (repo / "README.md").write_text("# Demo API\n", encoding="utf-8")
    (repo / "tests").mkdir()

    output = run_ps(
        "generate-knowledge-pack",
        "-RepoRoot",
        str(workspace),
        "-PackId",
        "demo-ai-generated-pack",
        "-IncludeProfiles",
        cwd=workspace,
    )

    assert_standard_shape(output, "generate-knowledge-pack")
    assert output["status"] == "ok"
    assert output["facts"]["mode"] == "ai-assisted-pack-generation"
    assert output["facts"]["ai_synthesis_required"] is True

    contract_path = Path(output["facts"]["generation_contract"])
    plan_path = Path(output["facts"]["ai_synthesis_plan"])
    queue_path = Path(output["facts"]["source_read_queue"])
    synthesis_dir = Path(output["facts"]["synthesis_knowledge_dir"])
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    assert contract["mode"] == "ai-assisted-pack-generation"
    assert contract["status"] == "needs_ai_synthesis"
    assert contract["target_pack_id"] == "demo-ai-generated-pack"
    assert "DemoApi" in contract["repository_candidates"]
    assert "perform targeted source reads" in "\n".join(contract["ai_responsibilities"])
    assert "do not full-text scan the whole workspace by default" in "\n".join(contract["guardrails"])
    assert (synthesis_dir / "index.yml").exists()
    assert "AI responsibilities" in plan_path.read_text(encoding="utf-8")
    assert "Do not full-text scan" in queue_path.read_text(encoding="utf-8")

    pack = output["facts"]["pack"]
    assert pack["status"] == "ok"
    assert pack["facts"]["pack_id"] == "demo-ai-generated-pack"
    assert pack["facts"]["workspace_profile"] is True
    assert pack["facts"]["repository_map_profile"] is True
    assert pack["facts"]["validation"]["status"] == "ok"
    assert pack["facts"]["validation"]["facts"]["evaluation_scenario_count"] == 1
    assert output["facts"]["quality"]["status"] == "warning"
    assert output["facts"]["quality"]["facts"]["total_score"] < output["facts"]["quality"]["facts"]["minimum_score"]
    assert Path(output["facts"]["quality"]["facts"]["source_coverage_ledger"]).exists()
    assert Path(output["facts"]["quality"]["facts"]["claim_verification_report"]).exists()
    assert output["facts"]["equivalence"]["status"] == "ok"

    for path in synthesis_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".yml", ".yaml", ".json"}:
            text = path.read_text(encoding="utf-8")
            updated = text.replace(
                ".specify/knowledge-bootstrap/facts.json",
                ".specify/knowledge-pack-generation/bootstrap/facts.json",
            )
            if updated != text:
                path.write_text(updated, encoding="utf-8")

    reviewed = run_ps(
        "generate-knowledge-pack",
        "-RepoRoot",
        str(workspace),
        "-PackId",
        "demo-ai-generated-pack",
        "-ReviewedKnowledgeDir",
        str(synthesis_dir),
        "-IncludeProfiles",
        cwd=workspace,
    )

    assert_standard_shape(reviewed, "generate-knowledge-pack")
    assert reviewed["status"] == "ok"
    assert reviewed["facts"]["ai_synthesis_required"] is False
    assert reviewed["facts"]["quality"]["status"] == "ok"
    assert reviewed["facts"]["quality"]["facts"]["total_score"] >= reviewed["facts"]["quality"]["facts"]["minimum_score"]
    assert reviewed["facts"]["quality"]["facts"]["unresolved_refs"] == []
    assert reviewed["facts"]["equivalence"]["status"] == "ok"


def test_bootstrap_knowledge_mounts_existing_pack_without_ai_review_packet(tmp_path):
    source = tmp_path / "source-knowledge"
    (source / "workspace").mkdir(parents=True)
    (source / "build").mkdir()
    (source / "index.yml").write_text(
        '\n'.join(
            [
                'schema_version: "1.0"',
                "policy:",
                "  default_context: false",
                "  no_full_text_search_required: true",
                '  repository_map_authority: ".specify/memory/repository-map.md"',
                "  max_selected_guides: 3",
                "workspace:",
                "  overview:",
                '    guide: "workspace/overview.md"',
                '    tags: ["workspace", "legacy-tool"]',
                "build:",
                "  command-matrix:",
                '    guide: "build/command-matrix.yml"',
                '    tags: ["build"]',
            ]
        ),
        encoding="utf-8",
    )
    (source / "workspace" / "overview.md").write_text(
        "Run `legacy-tool` before validation.\n",
        encoding="utf-8",
    )
    (source / "build" / "command-matrix.yml").write_text(
        'schema_version: "1.0"\ncommands: []\n',
        encoding="utf-8",
    )

    pack = tmp_path / "packs" / "mounted-pack"
    exported = run_ps(
        "export-knowledge-pack",
        "-SourceKnowledgeDir",
        str(source),
        "-PackId",
        "mounted-pack",
        "-OutputDir",
        str(pack),
        "-ToolAlias",
        "legacy-tool=modern-tool",
        "-Force",
    )
    assert exported["status"] == "ok"

    workspace = tmp_path / "workspace"
    (workspace / ".specify").mkdir(parents=True)
    mounted = run_ps(
        "bootstrap-knowledge",
        "-RepoRoot",
        str(workspace),
        "-PackPath",
        str(pack),
        "-Force",
        cwd=workspace,
    )

    assert_standard_shape(mounted, "bootstrap-knowledge")
    assert mounted["status"] == "ok"
    assert mounted["facts"]["mode"] == "mount-pack"
    assert mounted["facts"]["generated_review_packet"] is False
    assert mounted["facts"]["draft_knowledge_dir"] is None
    assert mounted["facts"]["ai_review_dir"] is None
    assert mounted["facts"]["applied_pack"]["status"] == "ok"
    assert mounted["facts"]["applied_pack"]["facts"]["validation"]["status"] == "ok"
    assert not (workspace / ".specify" / "knowledge-bootstrap" / "ai-review").exists()

    materialized = (workspace / "ai" / "knowledge" / "workspace" / "overview.md").read_text(encoding="utf-8")
    assert "modern-tool" in materialized
    assert "legacy-tool" not in materialized
    assert (workspace / ".specify" / "knowledge" / "packs" / "mounted-pack" / "knowledge-pack.yml").exists()
    assert (workspace / ".specify" / "knowledge" / "lock.yml").exists()


def test_specify_init_mounts_knowledge_pack(tmp_path):
    source = tmp_path / "source-knowledge"
    (source / "workspace").mkdir(parents=True)
    (source / "build").mkdir()
    (source / "index.yml").write_text(
        '\n'.join(
            [
                'schema_version: "1.0"',
                "policy:",
                "  default_context: false",
                "  no_full_text_search_required: true",
                '  repository_map_authority: ".specify/memory/repository-map.md"',
                "  max_selected_guides: 3",
                "workspace:",
                "  overview:",
                '    guide: "workspace/overview.md"',
                '    tags: ["workspace", "legacy-tool"]',
                "build:",
                "  command-matrix:",
                '    guide: "build/command-matrix.yml"',
                '    tags: ["build"]',
            ]
        ),
        encoding="utf-8",
    )
    (source / "workspace" / "overview.md").write_text(
        "Run `legacy-tool` before validation.\n",
        encoding="utf-8",
    )
    (source / "build" / "command-matrix.yml").write_text(
        'schema_version: "1.0"\ncommands: []\n',
        encoding="utf-8",
    )

    pack = tmp_path / "packs" / "init-pack"
    exported = run_ps(
        "export-knowledge-pack",
        "-SourceKnowledgeDir",
        str(source),
        "-PackId",
        "init-pack",
        "-OutputDir",
        str(pack),
        "-ToolAlias",
        "legacy-tool=modern-tool",
        "-Force",
    )
    assert exported["status"] == "ok"

    project = tmp_path / "project"
    project.mkdir()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    initialized = subprocess.run(
        [
            sys.executable,
            "-c",
            "import specify_cli; specify_cli.main()",
            "init",
            "--here",
            "--force",
            "--ignore-agent-tools",
            "--no-git",
            "--knowledge-pack",
            str(pack),
        ],
        cwd=project,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    materialized = (project / "ai" / "knowledge" / "workspace" / "overview.md").read_text(encoding="utf-8")
    assert "modern-tool" in materialized
    assert "legacy-tool" not in materialized
    assert (project / ".specify" / "knowledge" / "packs" / "init-pack" / "knowledge-pack.yml").exists()
    assert (project / ".specify" / "knowledge" / "lock.yml").exists()
    assert not (project / ".specify" / "knowledge-bootstrap" / "ai-review").exists()

    init_options = json.loads((project / ".specify" / "init-options.json").read_text(encoding="utf-8"))
    assert init_options["knowledge_pack"]["id"] == "init-pack"
    assert init_options["knowledge_pack"]["status"] == "ok"
    assert init_options["knowledge_pack"]["apply_profiles"] is False


def test_knowledge_pack_exports_installs_and_materializes_with_aliases(tmp_path):
    source = tmp_path / "source-knowledge"
    (source / "workspace").mkdir(parents=True)
    (source / "build").mkdir()
    (source / "index.yml").write_text(
        '\n'.join(
            [
                'schema_version: "1.0"',
                "policy:",
                "  default_context: false",
                "  no_full_text_search_required: true",
                '  repository_map_authority: ".specify/memory/repository-map.md"',
                "  max_selected_guides: 3",
                "workspace:",
                "  overview:",
                '    guide: "workspace/overview.md"',
                '    tags: ["workspace", "legacy-tool"]',
                "build:",
                "  command-matrix:",
                '    guide: "build/command-matrix.yml"',
                '    tags: ["build"]',
            ]
        ),
        encoding="utf-8",
    )
    (source / "workspace" / "overview.md").write_text(
        "Run `legacy-tool` before host validation.\n",
        encoding="utf-8",
    )
    (source / "build" / "command-matrix.yml").write_text(
        'schema_version: "1.0"\ncommands: []\n',
        encoding="utf-8",
    )

    pack = tmp_path / "packs" / "demo-pack"
    exported = run_ps(
        "export-knowledge-pack",
        "-SourceKnowledgeDir",
        str(source),
        "-PackId",
        "demo-pack",
        "-OutputDir",
        str(pack),
        "-ToolAlias",
        "legacy-tool=modern-tool",
        "-Force",
    )

    assert_standard_shape(exported, "export-knowledge-pack")
    assert exported["status"] == "ok"
    assert (pack / "knowledge-pack.yml").exists()
    assert "legacy-tool" in (pack / "ai" / "knowledge" / "workspace" / "overview.md").read_text(encoding="utf-8")

    workspace = tmp_path / "workspace"
    (workspace / ".specify").mkdir(parents=True)
    applied = run_ps(
        "apply-knowledge-pack",
        "-RepoRoot",
        str(workspace),
        "-PackPath",
        str(pack),
        "-ApplyProfiles",
        "-Force",
    )

    assert_standard_shape(applied, "apply-knowledge-pack")
    assert applied["status"] == "ok"
    materialized = (workspace / "ai" / "knowledge" / "workspace" / "overview.md").read_text(encoding="utf-8")
    assert "modern-tool" in materialized
    assert "legacy-tool" not in materialized
    assert (workspace / ".specify" / "knowledge" / "packs" / "demo-pack" / "knowledge-pack.yml").exists()
    assert (workspace / ".specify" / "knowledge" / "lock.yml").exists()
    assert applied["facts"]["validation"]["status"] == "ok"
    assert applied["facts"]["profiles_applied"] == []


def test_capability_pack_exports_materializes_and_repacks_layers(tmp_path):
    source = tmp_path / "source-knowledge"
    (source / "workspace").mkdir(parents=True)
    (source / "build").mkdir()
    (source / "index.yml").write_text(
        '\n'.join(
            [
                'schema_version: "1.0"',
                "policy:",
                "  default_context: false",
                "  no_full_text_search_required: true",
                '  repository_map_authority: ".specify/memory/repository-map.md"',
                "  max_selected_guides: 3",
                "workspace:",
                "  overview:",
                '    guide: "workspace/overview.md"',
                '    tags: ["workspace"]',
                "build:",
                "  command-matrix:",
                '    guide: "build/command-matrix.yml"',
                '    tags: ["build"]',
            ]
        ),
        encoding="utf-8",
    )
    (source / "workspace" / "overview.md").write_text("Capability pack overview.\n", encoding="utf-8")
    (source / "build" / "command-matrix.yml").write_text(
        'schema_version: "1.0"\ncommands: []\n',
        encoding="utf-8",
    )

    capability_source = tmp_path / "capability-source"
    skill = capability_source / "skills" / "runtime-debug"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: runtime-debug\ndescription: Debug runtime issues.\n---\n\n# Runtime Debug\n",
        encoding="utf-8",
    )
    (capability_source / "tools").mkdir()
    (capability_source / "tools" / "runtime-tools.md").write_text("Use readonly inspectors first.\n", encoding="utf-8")
    (capability_source / "scripts").mkdir()
    (capability_source / "scripts" / "inspect-runtime.ps1").write_text(
        "param([switch]$Json)\n@{ facts = @{} } | ConvertTo-Json\n",
        encoding="utf-8",
    )
    (capability_source / "commands").mkdir()
    (capability_source / "commands" / "debug-runtime.md").write_text("# Debug Runtime\n", encoding="utf-8")
    (capability_source / "prompts").mkdir()
    (capability_source / "prompts" / "runtime-prompt.md").write_text("# Runtime Prompt\n", encoding="utf-8")
    (capability_source / "resources").mkdir()
    (capability_source / "resources" / "runtime-notes.md").write_text("# Runtime Notes\n", encoding="utf-8")

    pack = tmp_path / "packs" / "capability-demo"
    exported = run_ps(
        "export-knowledge-pack",
        "-SourceKnowledgeDir",
        str(source),
        "-PackId",
        "capability-demo",
        "-OutputDir",
        str(pack),
        "-SkillsDir",
        str(capability_source / "skills"),
        "-ToolsDir",
        str(capability_source / "tools"),
        "-ScriptsDir",
        str(capability_source / "scripts"),
        "-CommandsDir",
        str(capability_source / "commands"),
        "-PromptsDir",
        str(capability_source / "prompts"),
        "-ResourcesDir",
        str(capability_source / "resources"),
        "-Force",
    )

    assert_standard_shape(exported, "export-knowledge-pack")
    assert exported["status"] == "ok"
    assert exported["facts"]["capability_layers"]["skills"] is True
    assert (pack / "capabilities" / "index.yml").exists()
    assert (pack / "skills" / "runtime-debug" / "SKILL.md").exists()
    assert (pack / "scripts" / "inspect-runtime.ps1").exists()
    validation = exported["facts"]["validation"]["facts"]
    assert validation["kind"] == "capability-pack"
    assert validation["capability_layers"]["skills"]["present"] is True
    assert validation["capability_layers"]["scripts"]["file_count"] == 1
    assert validation["script_hashes"][0]["path"] == "scripts/inspect-runtime.ps1"

    workspace = tmp_path / "workspace"
    (workspace / ".specify").mkdir(parents=True)
    applied = run_ps(
        "apply-knowledge-pack",
        "-RepoRoot",
        str(workspace),
        "-PackPath",
        str(pack),
        "-Force",
    )

    assert_standard_shape(applied, "apply-knowledge-pack")
    assert applied["status"] == "ok"
    assert (workspace / ".agents" / "spec-kit" / "skills" / "capability-demo__runtime-debug" / "SKILL.md").exists()
    assert (workspace / "ai" / "tools" / "capability-demo" / "runtime-tools.md").exists()
    assert (workspace / ".specify" / "scripts" / "packs" / "capability-demo" / "inspect-runtime.ps1").exists()
    assert (workspace / ".specify" / "capabilities" / "commands" / "capability-demo" / "debug-runtime.md").exists()
    assert (workspace / ".specify" / "capabilities" / "prompts" / "capability-demo" / "runtime-prompt.md").exists()
    capability_lock = (workspace / ".specify" / "capabilities" / "lock.yml").read_text(encoding="utf-8")
    assert 'auto_run_scripts: false' in capability_lock
    assert 'capability-demo__runtime-debug' in capability_lock

    selected_capabilities = run_ps(
        "select-capability",
        "-RepoRoot",
        str(workspace),
        "-Layer",
        "skills",
    )
    assert_standard_shape(selected_capabilities, "select-capability")
    assert selected_capabilities["status"] == "ok"
    assert selected_capabilities["facts"]["progressive_disclosure"] is True
    assert selected_capabilities["facts"]["auto_run_scripts"] is False
    assert selected_capabilities["facts"]["selected"][0]["path"] == ".agents/spec-kit/skills/capability-demo__runtime-debug"

    core_skill = workspace / ".agents" / "spec-kit" / "skills" / "speckit-core"
    core_skill.mkdir(parents=True)
    (core_skill / "SKILL.md").write_text(
        "---\nname: speckit-core\ndescription: Core skill should not be repacked.\n---\n",
        encoding="utf-8",
    )
    local_skill = workspace / ".specify" / "capabilities" / "overlays" / "local" / "skills" / "local-runtime"
    local_skill.mkdir(parents=True)
    (local_skill / "SKILL.md").write_text(
        "---\nname: local-runtime\ndescription: Local runtime overlay.\n---\n\n# Local Runtime\n",
        encoding="utf-8",
    )

    repacked_dir = tmp_path / "packs" / "capability-demo-repacked"
    repacked = run_ps(
        "repack-knowledge-pack",
        "-RepoRoot",
        str(workspace),
        "-PackId",
        "capability-demo-repacked",
        "-OutputDir",
        str(repacked_dir),
        "-Force",
    )

    assert_standard_shape(repacked, "repack-knowledge-pack")
    assert repacked["status"] == "ok"
    assert repacked["facts"]["mode"] == "full-snapshot"
    assert (repacked_dir / "knowledge-pack.yml").exists()
    assert (repacked_dir / "skills" / "capability-demo__runtime-debug" / "SKILL.md").exists()
    assert (repacked_dir / "skills" / "local-runtime" / "SKILL.md").exists()
    assert not (repacked_dir / "skills" / "speckit-core" / "SKILL.md").exists()
    assert (repacked_dir / "tools" / "capability-demo" / "runtime-tools.md").exists()
    assert repacked["facts"]["export"]["facts"]["capability_layers"]["skills"] is True

    source_v2 = tmp_path / "source-knowledge-v2"
    (source_v2 / "workspace").mkdir(parents=True)
    (source_v2 / "build").mkdir()
    (source_v2 / "index.yml").write_text(
        '\n'.join(
            [
                'schema_version: "1.0"',
                "policy:",
                "  default_context: false",
                "  no_full_text_search_required: true",
                '  repository_map_authority: ".specify/memory/repository-map.md"',
                "  max_selected_guides: 3",
                "workspace:",
                "  overview:",
                '    guide: "workspace/overview.md"',
                '    tags: ["workspace"]',
                "build:",
                "  command-matrix:",
                '    guide: "build/command-matrix.yml"',
                '    tags: ["build"]',
            ]
        ),
        encoding="utf-8",
    )
    (source_v2 / "workspace" / "overview.md").write_text("Capability pack overview v2.\n", encoding="utf-8")
    (source_v2 / "build" / "command-matrix.yml").write_text(
        'schema_version: "1.0"\ncommands: []\n',
        encoding="utf-8",
    )

    capability_source_v2 = tmp_path / "capability-source-v2"
    skill_v2 = capability_source_v2 / "skills" / "runtime-trace"
    skill_v2.mkdir(parents=True)
    (skill_v2 / "SKILL.md").write_text(
        "---\nname: runtime-trace\ndescription: Trace runtime issues.\n---\n\n# Runtime Trace\n",
        encoding="utf-8",
    )
    (capability_source_v2 / "tools").mkdir()
    (capability_source_v2 / "tools" / "runtime-tools.md").write_text(
        "Use updated readonly inspectors first.\n",
        encoding="utf-8",
    )
    (capability_source_v2 / "scripts").mkdir()
    (capability_source_v2 / "scripts" / "inspect-runtime-v2.ps1").write_text(
        "param([switch]$Json)\n@{ facts = @{ version = 2 } } | ConvertTo-Json\n",
        encoding="utf-8",
    )

    pack_v2 = tmp_path / "packs" / "capability-demo-v2"
    exported_v2 = run_ps(
        "export-knowledge-pack",
        "-SourceKnowledgeDir",
        str(source_v2),
        "-PackId",
        "capability-demo",
        "-OutputDir",
        str(pack_v2),
        "-SkillsDir",
        str(capability_source_v2 / "skills"),
        "-ToolsDir",
        str(capability_source_v2 / "tools"),
        "-ScriptsDir",
        str(capability_source_v2 / "scripts"),
        "-Force",
    )
    assert_standard_shape(exported_v2, "export-knowledge-pack")
    assert exported_v2["status"] == "ok"

    updated = run_ps(
        "update-knowledge-pack",
        "-RepoRoot",
        str(workspace),
        "-PackPath",
        str(pack_v2),
    )
    assert_standard_shape(updated, "update-knowledge-pack")
    assert updated["status"] == "ok"
    assert (workspace / "ai" / "knowledge" / "workspace" / "overview.md").read_text(encoding="utf-8") == "Capability pack overview v2.\n"
    assert not (workspace / ".agents" / "spec-kit" / "skills" / "capability-demo__runtime-debug").exists()
    assert (workspace / ".agents" / "spec-kit" / "skills" / "capability-demo__runtime-trace" / "SKILL.md").exists()
    assert not (workspace / ".specify" / "scripts" / "packs" / "capability-demo" / "inspect-runtime.ps1").exists()
    assert (workspace / ".specify" / "scripts" / "packs" / "capability-demo" / "inspect-runtime-v2.ps1").exists()
    assert "updated readonly" in (workspace / "ai" / "tools" / "capability-demo" / "runtime-tools.md").read_text(encoding="utf-8")
    capability_lock_v2 = (workspace / ".specify" / "capabilities" / "lock.yml").read_text(encoding="utf-8")
    assert "capability-demo__runtime-trace" in capability_lock_v2
    assert "capability-demo__runtime-debug" not in capability_lock_v2

    uninstalled = run_ps(
        "uninstall-knowledge-pack",
        "-RepoRoot",
        str(workspace),
        "-PackId",
        "capability-demo",
    )
    assert_standard_shape(uninstalled, "uninstall-knowledge-pack")
    assert uninstalled["status"] == "ok"
    assert not (workspace / ".specify" / "knowledge" / "packs" / "capability-demo").exists()
    assert not (workspace / ".agents" / "spec-kit" / "skills" / "capability-demo__runtime-trace").exists()
    assert not (workspace / "ai" / "tools" / "capability-demo").exists()
    assert not (workspace / ".specify" / "scripts" / "packs" / "capability-demo").exists()

    selected_after_uninstall = run_ps(
        "select-capability",
        "-RepoRoot",
        str(workspace),
        "-PackId",
        "capability-demo",
    )
    assert_standard_shape(selected_after_uninstall, "select-capability")
    assert selected_after_uninstall["status"] == "ok"
    assert selected_after_uninstall["facts"]["selected"] == []


def test_compare_knowledge_pack_equivalence_scores_indexed_guides_routing_and_aliases(tmp_path):
    source = tmp_path / "source-knowledge"
    (source / "repositories").mkdir(parents=True)
    (source / "domains").mkdir()
    (source / "build").mkdir()
    (source / "index.yml").write_text(
        '\n'.join(
            [
                'schema_version: "1.0"',
                "policy:",
                "  default_context: false",
                "  no_full_text_search_required: true",
                '  repository_map_authority: ".specify/memory/repository-map.md"',
                "  max_selected_guides: 3",
                "repositories:",
                "  DemoRepo:",
                '    guide: "repositories/demo-repo.md"',
                '    tags: ["demo", "api"]',
                "domains:",
                "  demo-runtime:",
                '    guide: "domains/demo-runtime.md"',
                '    tags: ["runtime"]',
                "build:",
                "  validation-capabilities:",
                '    guide: "build/validation-capabilities.yml"',
                '    tags: ["validation", "api", "e2e"]',
            ]
        ),
        encoding="utf-8",
    )
    (source / "repositories" / "demo-repo.md").write_text(
        "Use `legacy-cdp-tool` for demo validation.\n",
        encoding="utf-8",
    )
    (source / "domains" / "demo-runtime.md").write_text("Runtime guide.\n", encoding="utf-8")
    (source / "build" / "validation-capabilities.yml").write_text(
        'schema_version: "1.0"\ncapabilities: {}\n',
        encoding="utf-8",
    )

    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "workspace.yml").write_text(
        'repositories:\n  - name: DemoRepo\n    path: "."\n    required: false\n',
        encoding="utf-8",
    )
    (profile / "repository-map.md").write_text(
        "# Repository Map\n\n## Project Path Categories\n\nCDP target inventory\n\nDo not write machine-specific absolute paths here.\n",
        encoding="utf-8",
    )
    scenarios = tmp_path / "scenarios.json"
    scenarios.write_text(
        json.dumps(
            [
                {
                    "name": "demo-repo-api-routing",
                    "stage": "plan",
                    "affected_repositories": ["DemoRepo"],
                    "risk_flags": ["public-api"],
                    "capability_tags": ["api", "e2e"],
                    "request_summary": "plan API validation for demo repository",
                }
            ]
        ),
        encoding="utf-8",
    )

    pack = tmp_path / "pack"
    exported = run_ps(
        "export-knowledge-pack",
        "-SourceKnowledgeDir",
        str(source),
        "-WorkspaceFile",
        str(profile / "workspace.yml"),
        "-RepositoryMap",
        str(profile / "repository-map.md"),
        "-PackId",
        "demo-equivalence",
        "-OutputDir",
        str(pack),
        "-ComposeStrategy",
        "replace-active-knowledge",
        "-EvaluationScenariosFile",
        str(scenarios),
        "-ToolAlias",
        "legacy-cdp-tool=modern-cdp-tool",
        "-Force",
    )
    assert exported["status"] == "ok"

    report_dir = pack / "reports" / "equivalence"
    compared = run_ps(
        "compare-knowledge-pack-equivalence",
        "-SourceKnowledgeDir",
        str(source),
        "-PackRoot",
        str(pack),
        "-OutputDir",
        str(report_dir),
    )

    assert_standard_shape(compared, "compare-knowledge-pack-equivalence")
    assert compared["status"] == "ok"
    scores = compared["facts"]["scores"]
    assert scores["index_parity_percent"] == 100
    assert scores["indexed_guide_parity_percent"] == 100
    assert scores["routing_parity_percent"] == 100
    assert scores["alias_percent"] == 100
    assert scores["overall_percent"] == 100
    assert compared["facts"]["guides"]["extra_unindexed_candidate_files"] == []
    assert compared["facts"]["scenario_count"] == 1
    assert compared["facts"]["aliases"]["leakage_files"] == []
    assert (report_dir / "equivalence-report.json").exists()
    assert (report_dir / "equivalence-summary.md").exists()
    assert not (report_dir / "candidate").exists()
    assert not (report_dir / "reference").exists()
    assert compared["facts"]["report_root"] == str(report_dir)
    assert compared["facts"]["work_root_removed"] is True


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
        "Do not keep " + "D:" + "\\local-only paths here.\n",
        encoding="utf-8",
    )

    output = run_ps("validate-knowledge-index", "-RepoRoot", str(repo))

    assert_standard_shape(output, "validate-knowledge-index")
    assert output["status"] == "blocked"
    assert any("machine-specific knowledge paths" in blocker for blocker in output["blockers"])


def test_all_automation_scripts_exist_in_powershell():
    for tool in AUTOMATION_TOOLS:
        assert (REPO_ROOT / "scripts" / "powershell" / f"{tool}.ps1").exists()
    script_dirs = sorted(path.name for path in (REPO_ROOT / "scripts").iterdir() if path.is_dir())
    assert script_dirs == ["powershell"]


def test_spec_kit_core_version_scripts_use_pyproject_as_source(tmp_path):
    pyproject = tomllib.loads(read_text("pyproject.toml"))
    expected_version = pyproject["project"]["version"]
    expected_package = pyproject["project"]["name"]

    version_info = run_ps("get-spec-kit-version", "-RepoRoot", str(REPO_ROOT))

    assert_standard_shape(version_info, "get-spec-kit-version")
    assert version_info["status"] == "ok"
    assert version_info["facts"]["version_source"] == "pyproject.toml"
    assert version_info["facts"]["package_name"] == expected_package
    assert version_info["facts"]["version"] == expected_version
    assert version_info["facts"]["tag_name"] == f"v{expected_version}"

    validation = run_ps("validate-spec-kit-version", "-RepoRoot", str(REPO_ROOT))

    assert_standard_shape(validation, "validate-spec-kit-version")
    assert validation["status"] == "ok"
    assert validation["facts"]["version"] == version_info["facts"]["version"]
    assert validation["facts"]["package_name"] == expected_package
    assert validation["facts"]["version_source"] == "pyproject.toml"
    assert "pyproject.toml" in read_text("src/specify_cli/_assets.py")
    assert 'importlib.metadata.version("specify-cli")' in read_text("src/specify_cli/_assets.py")

    temp_repo = tmp_path / "spec-kit"
    temp_repo.mkdir()
    (temp_repo / "pyproject.toml").write_text(
        '[project]\nname = "specify-cli"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    bumped = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "bump-spec-kit-version.ps1"),
            "-RepoRoot",
            str(temp_repo),
            "-Version",
            "0.1.1",
            "-Json",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )
    output = json.loads(bumped.stdout)

    assert_standard_shape(output, "bump-spec-kit-version")
    assert output["status"] == "ok"
    assert output["facts"]["previous_version"] == "0.1.0"
    assert output["facts"]["version"] == "0.1.1"
    assert output["facts"]["tag_name"] == "v0.1.1"
    assert 'version = "0.1.1"' in (temp_repo / "pyproject.toml").read_text(encoding="utf-8")


def test_specify_upgrade_uses_lock_manifest_and_dry_run(tmp_path):
    pyproject = tomllib.loads(read_text("pyproject.toml"))
    expected_version = pyproject["project"]["version"]
    project = tmp_path / "project"
    project.mkdir()

    initialized = run_specify_cli(
        project,
        "init",
        "--here",
        "--force",
        "--ignore-agent-tools",
        "--no-git",
    )

    assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    lock_path = project / ".specify" / "spec-kit.lock.yml"
    manifest_path = project / ".specify" / "integrations" / "speckit.manifest.json"
    assert lock_path.exists()
    assert manifest_path.exists()

    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    assert lock["spec_kit"]["version"] == expected_version
    assert "source_path" not in lock["spec_kit"]
    assert lock["managed_assets"]["manifest"] == ".specify/integrations/speckit.manifest.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["version"] == expected_version
    assert ".specify/workflows/speckit/workflow.yml" in manifest["files"]

    dry_run = run_specify_cli(tmp_path, "upgrade", "--project-dir", str(project), "--dry-run", "--json")
    assert dry_run.returncode == 0, dry_run.stdout + dry_run.stderr
    dry_payload = json.loads(dry_run.stdout)
    assert dry_payload["status"] == "planned"
    assert dry_payload["dry_run"] is True
    assert dry_payload["plan"]["current_version"] == expected_version
    assert dry_payload["plan"]["target_version"] == expected_version
    assert dry_payload["plan"]["lock_file"] == ".specify/spec-kit.lock.yml"

    managed_script = project / ".specify" / "scripts" / "powershell" / "check-prerequisites.ps1"
    managed_script.write_text(
        managed_script.read_text(encoding="utf-8") + "\n# local customization\n",
        encoding="utf-8",
    )
    customized_plan = run_specify_cli(project, "upgrade", "--dry-run", "--json")
    assert customized_plan.returncode == 0, customized_plan.stdout + customized_plan.stderr
    customized_payload = json.loads(customized_plan.stdout)
    assert ".specify/scripts/powershell/check-prerequisites.ps1" in customized_payload["plan"]["preserved_customized"]

    managed_script.write_bytes((REPO_ROOT / "scripts" / "powershell" / "check-prerequisites.ps1").read_bytes())
    upgraded = run_specify_cli(project, "upgrade", "--skip-validation", "--json")
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    upgraded_payload = json.loads(upgraded.stdout)
    assert upgraded_payload["status"] == "ok"
    assert upgraded_payload["applied"]["version"] == expected_version
    assert upgraded_payload["applied"]["manifest"] == ".specify/integrations/speckit.manifest.json"
    upgraded_lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    assert "source_path" not in upgraded_lock["spec_kit"]


def test_specify_knowledge_commands_wrap_project_scripts(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    initialized = run_specify_cli(
        project,
        "init",
        "--here",
        "--force",
        "--ignore-agent-tools",
        "--no-git",
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    bootstrap = run_specify_cli(
        tmp_path,
        "knowledge",
        "bootstrap",
        "--project-dir",
        str(project),
        "--json",
    )
    assert bootstrap.returncode == 0, bootstrap.stdout + bootstrap.stderr
    bootstrap_payload = json.loads(bootstrap.stdout)
    assert_standard_shape(bootstrap_payload, "bootstrap-knowledge")
    assert bootstrap_payload["facts"]["generated_review_packet"] is True
    assert ".specify" in bootstrap_payload["facts"]["draft_knowledge_dir"]

    generated = run_specify_cli(
        tmp_path,
        "knowledge",
        "generate-pack",
        "--project-dir",
        str(project),
        "--pack-id",
        "generated-demo",
        "--force",
        "--json",
    )
    assert generated.returncode == 0, generated.stdout + generated.stderr
    generated_payload = json.loads(generated.stdout)
    assert_standard_shape(generated_payload, "generate-knowledge-pack")
    assert generated_payload["facts"]["ai_synthesis_required"] is True
    assert generated_payload["facts"]["synthesis_knowledge_dir"].endswith("ai\\knowledge")

    pack_dir = tmp_path / "demo-pack"
    exported = run_specify_cli(
        tmp_path,
        "knowledge",
        "export-pack",
        "--project-dir",
        str(project),
        "--pack-id",
        "demo-pack",
        "--output-dir",
        str(pack_dir),
        "--force",
        "--json",
    )
    assert exported.returncode == 0, exported.stdout + exported.stderr
    exported_payload = json.loads(exported.stdout)
    assert_standard_shape(exported_payload, "export-knowledge-pack")
    assert exported_payload["facts"]["pack_id"] == "demo-pack"
    assert (pack_dir / "knowledge-pack.yml").exists()

    validated = run_specify_cli(
        tmp_path,
        "knowledge",
        "validate-pack",
        str(pack_dir),
        "--json",
    )
    assert validated.returncode == 0, validated.stdout + validated.stderr
    validated_payload = json.loads(validated.stdout)
    assert_standard_shape(validated_payload, "validate-knowledge-pack")
    assert validated_payload["status"] == "ok"

    applied = run_specify_cli(
        tmp_path,
        "knowledge",
        "apply-pack",
        str(pack_dir),
        "--project-dir",
        str(project),
        "--force",
        "--json",
    )
    assert applied.returncode == 0, applied.stdout + applied.stderr
    applied_payload = json.loads(applied.stdout)
    assert_standard_shape(applied_payload, "apply-knowledge-pack")
    assert applied_payload["facts"]["pack_id"] == "demo-pack"

    repack_dir = tmp_path / "demo-repack"
    repacked = run_specify_cli(
        tmp_path,
        "knowledge",
        "repack",
        "--project-dir",
        str(project),
        "--pack-id",
        "demo-repack",
        "--output-dir",
        str(repack_dir),
        "--force",
        "--json",
    )
    assert repacked.returncode == 0, repacked.stdout + repacked.stderr
    repacked_payload = json.loads(repacked.stdout)
    assert_standard_shape(repacked_payload, "repack-knowledge-pack")
    assert repacked_payload["facts"]["pack_id"] == "demo-repack"
    assert (repack_dir / "knowledge-pack.yml").exists()


def test_ai_knowledge_pack_generator_assets_define_ai_loop():
    command = read_text("templates/commands/knowledge-pack-generate.md")
    skill = read_text("templates/subskills/speckit-knowledge-pack-generator/SKILL.md")
    script = read_text("scripts/powershell/generate-knowledge-pack.ps1")
    evaluator = read_text("scripts/powershell/evaluate-knowledge-pack-synthesis.ps1")
    skill_routing = read_text("templates/ai/workflows/skill-routing.yml")
    layer_manifest = read_text("templates/layer-manifest.yml")

    for text in [command, skill, script]:
        assert "generate-knowledge-pack.ps1" in text
    for text in [command, skill, script]:
        assert "AI synthesis" in text
        assert "source" in text.lower()

    assert "-ReviewedKnowledgeDir" in command
    assert "facts.ai_synthesis_required" in command
    assert "AI owns semantic synthesis" in skill
    assert "evaluate-knowledge-pack-synthesis.ps1" in command
    assert "claim verification" in evaluator.lower()
    assert "source-coverage-ledger.json" in evaluator
    assert "do not full-text scan the whole workspace by default" in script.lower()
    assert "knowledge-pack-generator" in skill_routing
    assert "speckit-knowledge-pack-generator" in skill_routing
    assert "templates/commands/knowledge-pack-generate.md" in layer_manifest
    assert "scripts/powershell/*knowledge-pack*.ps1" in layer_manifest


def test_inspect_validation_capabilities_reports_api_and_optional_e2e(tmp_path):
    repo = tmp_path / "repo"
    (repo / "script").mkdir(parents=True)
    (repo / "script" / "run-e2e.ps1").write_text("param([switch]$List)\n", encoding="utf-8")
    (repo / "tests" / "e2e" / "scenarios").mkdir(parents=True)
    (repo / "tests" / "e2e" / "scenarios" / "demo.yaml").write_text(
        "name: demo-scenario\nsteps: []\n",
        encoding="utf-8",
    )
    (repo / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n", encoding="utf-8")

    output = run_ps("inspect-validation-capabilities", "-RepoRoot", str(repo))

    assert_standard_shape(output, "inspect-validation-capabilities")
    assert output["status"] == "ok"
    assert output["facts"]["api_test_plan_required"] is True
    assert output["facts"]["e2e"]["supported"] is True
    assert output["facts"]["e2e"]["scenario_count"] == 1
    assert output["facts"]["e2e"]["known_scenarios"][0]["id"] == "demo"
    assert output["facts"]["e2e_may_be_na_when_unsupported"] is True
    assert output["facts"]["api"]["candidate_commands"]


def test_inspect_validation_capabilities_writes_workspace_matrix(tmp_path):
    workspace = tmp_path / "workspace"
    repo_a = workspace / "repo-a"
    repo_b = workspace / "repo-b"
    (workspace / ".specify").mkdir(parents=True)
    repo_a.mkdir(parents=True)
    repo_b.mkdir(parents=True)
    (workspace / ".specify" / "workspace.yml").write_text(
        "\n".join(
            [
                "workspace:",
                "  root: \".\"",
                "repositories:",
                "  - name: repo-a",
                "    path: repo-a",
                "    role: api-owner",
                "    required: true",
                "  - name: repo-b",
                "    path: repo-b",
                "    role: ui-owner",
                "    required: true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (repo_a / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n", encoding="utf-8")
    (repo_a / "tests").mkdir()
    (repo_b / "script").mkdir()
    (repo_b / "script" / "run-e2e.ps1").write_text("param([switch]$List)\n", encoding="utf-8")
    (repo_b / "tests" / "e2e" / "scenarios").mkdir(parents=True)
    (repo_b / "tests" / "e2e" / "scenarios" / "flow.yaml").write_text("steps: []\n", encoding="utf-8")

    output = run_ps(
        "inspect-validation-capabilities",
        "-RepoRoot",
        str(workspace),
        "-Workspace",
        "-OutputPath",
        "ai/knowledge/build/validation-capabilities.yml",
    )

    assert_standard_shape(output, "inspect-validation-capabilities")
    assert output["facts"]["workspace"] is True
    assert output["facts"]["repository_count"] == 2
    matrix_path = workspace / "ai" / "knowledge" / "build" / "validation-capabilities.yml"
    assert matrix_path.exists()
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    by_repo = {entry["repository"]: entry for entry in matrix["repositories"]}
    assert by_repo["repo-a"]["api"]["supported"] is True
    assert by_repo["repo-b"]["e2e"]["supported"] is True
    assert by_repo["repo-b"]["e2e"]["known_scenarios"][0]["id"] == "flow"


def test_inspect_workspace_repositories_blocks_missing_required_repo(tmp_path):
    workspace = tmp_path / "workspace"
    repo_a = workspace / "repo-a"
    workspace.mkdir()
    repo_a.mkdir()
    run_git(repo_a, "init", "-b", "master")
    (workspace / ".specify").mkdir()
    (workspace / ".specify" / "workspace.yml").write_text(
        "\n".join(
            [
                "workspace:",
                "  root: \".\"",
                "repositories:",
                "  - name: repo-a",
                "    path: repo-a",
                "    required: true",
                "  - name: missing-repo",
                "    path: missing-repo",
                "    required: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "inspect-workspace-repositories.ps1"),
            "-RepoRoot",
            str(workspace),
            "-Json",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    output = json.loads(result.stdout)

    assert result.returncode == 0
    assert_standard_shape(output, "inspect-workspace-repositories")
    assert output["status"] == "blocked"
    assert output["facts"]["required_missing"] == ["missing-repo"]
    assert "Do not scan other repositories" in output["hints"][0]


def test_validate_test_plan_requires_api_and_e2e_review_status(tmp_path):
    feature_dir = tmp_path / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "plan.md").write_text(
        "## 测试用例计划\n\n"
        "| Kind | Plan | Review status |\n"
        "| --- | --- | --- |\n"
        "| API | interface regression row | approved-by-ai-obvious |\n"
        "| E2E | N/A: repository runner unsupported | approved-by-ai-obvious |\n",
        encoding="utf-8",
    )

    ok = run_ps("validate-test-plan", "-FeatureDir", str(feature_dir))
    assert_standard_shape(ok, "validate-test-plan")
    assert ok["status"] == "ok"

    (feature_dir / "plan.md").write_text("## 测试用例计划\n\n| E2E | N/A |\n", encoding="utf-8")
    blocked = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "validate-test-plan.ps1"),
            "-FeatureDir",
            str(feature_dir),
            "-Json",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    output = json.loads(blocked.stdout)
    assert output["status"] == "blocked"
    assert "API/interface test plan" in "\n".join(output["blockers"])


def test_validate_ai_self_acceptance_requires_pass(tmp_path):
    feature_dir = tmp_path / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "validation.md").write_text(
        "## AI Acceptance Result\n\nAI Self-Acceptance: FAIL\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "validate-ai-self-acceptance.ps1"),
            "-FeatureDir",
            str(feature_dir),
            "-Json",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    output = json.loads(result.stdout)
    assert output["status"] == "blocked"
    assert "must be PASS" in "\n".join(output["blockers"])

    (feature_dir / "validation.md").write_text(
        "## AI Acceptance Result\n\nAI Self-Acceptance: PASS\n",
        encoding="utf-8",
    )
    ok = run_ps("validate-ai-self-acceptance", "-FeatureDir", str(feature_dir))
    assert ok["status"] == "ok"


def test_plugin_build_plan_and_package_validation(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        json.dumps({"scripts": {"build-builtin-plugins": "node scripts/build-plugins.js"}}),
        encoding="utf-8",
    )
    package = repo / "dist" / "plugins" / "demo-1.0.0.plugin"
    package.parent.mkdir(parents=True)
    package.write_bytes(b"plugin-package")

    plan = run_ps("inspect-plugin-build-plan", "-RepoRoot", str(repo))
    assert_standard_shape(plan, "inspect-plugin-build-plan")
    assert plan["status"] == "ok"
    assert plan["facts"]["candidates"][0]["command"] == "npm run build-builtin-plugins"

    ok = run_ps("validate-plugin-package", "-RepoRoot", str(repo), "-PackagePath", str(package))
    assert_standard_shape(ok, "validate-plugin-package")
    assert ok["status"] == "ok"
    assert ok["facts"]["extension"] == ".plugin"

    bad = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "validate-plugin-package.ps1"),
            "-RepoRoot",
            str(repo),
            "-PackagePath",
            str(repo / "dist" / "plugins" / "demo.zip"),
            "-Json",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    output = json.loads(bad.stdout)
    assert output["status"] == "blocked"
    assert "must use .plugin extension" in "\n".join(output["blockers"])


def test_post_commit_self_check_and_rubric_score_gate(tmp_path):
    feature_dir = tmp_path / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    for name in ["validation.md", "acceptance.md", "workflow-record.md", "improvement-candidates.md"]:
        (feature_dir / name).write_text(f"# {name}\n", encoding="utf-8")
    (feature_dir / "workflow-state.json").write_text(
        json.dumps({"retrospective": {"status": "completed"}}),
        encoding="utf-8",
    )

    check = run_ps("post-commit-self-check", "-FeatureDir", str(feature_dir))
    assert_standard_shape(check, "post-commit-self-check")
    assert check["status"] == "ok"
    assert check["facts"]["single_pass"] is True

    rubric = feature_dir / "rubric-score.md"
    rubric.write_text(
        "\n".join(
            [
                "# Rubric",
                "| Dimension | Weight | Score / Status | Evidence | 扣分原因 |",
                "| --- | --- | --- | --- | --- |",
                "| L1 功能与需求闭合 | 0.30 | 95 | validation.md | 无 |",
                "| L2 验证与证据 | 0.25 | 94 | evidence.md | 无 |",
                "| L3 工作流阶段合规 | 0.25 | 93 | workflow-record.md | 无 |",
                "| L4 交付与仓库状态 | 0.10 | 92 | git show | 无 |",
                "| L5 上下文与自动化治理 | 0.10 | 91 | AGENTS.md | 无 |",
                "- Overall Weighted Score: 93.8",
                "- Hard gate: PASS",
                "- complete-branch allowed: yes",
                "- 证据路径: validation.md",
            ]
        ),
        encoding="utf-8",
    )
    ok = run_ps("validate-rubric-score", "-FeatureDir", str(feature_dir))
    assert_standard_shape(ok, "validate-rubric-score")
    assert ok["status"] == "ok"
    assert ok["facts"]["complete_branch_allowed"] is True

    rubric.write_text(
        "L1 95\nL2 95\nL3 95\nL4 95\nL5 95\nOverall Weighted Score: 89\nHard gate: PASS\n证据\n扣分\ncomplete-branch\n",
        encoding="utf-8",
    )
    blocked = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "validate-rubric-score.ps1"),
            "-FeatureDir",
            str(feature_dir),
            "-Json",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    output = json.loads(blocked.stdout)
    assert output["status"] == "blocked"
    assert "below 90" in "\n".join(output["blockers"])


def test_cdp_common_and_cleanup_process_boundaries():
    capture = read_text("scripts/powershell/capture-cdp-screenshot.ps1")
    common = read_text("scripts/powershell/cdp-common.ps1")
    assert 'cdp-common.ps1' in capture
    assert "Invoke-CdpCommand" in common
    assert "Invoke-CdpScreenshotData" in capture

    output = run_ps("cleanup-host-cdp", "-DryRun")
    assert_standard_shape(output, "cleanup-host-cdp")
    assert output["status"] == "ok"
    assert "no AI-started process ids provided" in output["facts"]["skipped"]


def test_sync_ui_runtime_artifacts_copies_source_output_to_runtime(tmp_path):
    source = tmp_path / "dist"
    runtime = tmp_path / "runtime" / "example-device-tree"
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
        "example-device-tree",
    )

    assert_standard_shape(output, "sync-ui-runtime-artifacts")
    assert output["status"] == "ok"
    assert output["facts"]["plugin_id"] == "example-device-tree"
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
            "example-device-tree",
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


def test_sync_native_runtime_artifacts_copies_addon_metadata_and_hashes(tmp_path):
    source = tmp_path / "export" / "native"
    runtime = tmp_path / "app-data" / "plugins" / "service-bridge-plugin" / "1.0.0"
    source.mkdir(parents=True)
    runtime.mkdir(parents=True)
    (source / "ServiceBridge.node").write_bytes(b"native-addon")
    proto = tmp_path / "export" / "ServiceBridge.proto"
    exports = tmp_path / "export" / "native-exports.json"
    proto.write_text('syntax = "proto3";\nmessage DeviceInfo { string uuid = 1; }\n', encoding="utf-8")
    exports.write_text('{"exports":["getDeviceTree"]}', encoding="utf-8")

    output = run_ps(
        "sync-native-runtime-artifacts",
        "-SourceNativeDir",
        str(source),
        "-RuntimePluginDir",
        str(runtime),
        "-PluginId",
        "service-bridge-plugin",
        "-ProtoFile",
        str(proto),
        "-NativeExportsFile",
        str(exports),
    )

    assert_standard_shape(output, "sync-native-runtime-artifacts")
    assert output["status"] == "ok"
    assert (runtime / "native" / "ServiceBridge.node").read_bytes() == b"native-addon"
    assert (runtime / "ServiceBridge.proto").read_text(encoding="utf-8").startswith("syntax")
    assert (runtime / "native-exports.json").read_text(encoding="utf-8").startswith("{")
    assert output["facts"]["duplicate_native_proto_files"] == []
    assert output["facts"]["hashes"][0]["source_sha256"] == output["facts"]["hashes"][0]["target_sha256"]


def test_sync_native_runtime_artifacts_blocks_duplicate_native_proto(tmp_path):
    source = tmp_path / "export" / "native"
    runtime = tmp_path / "app-data" / "plugins" / "service-bridge-plugin" / "1.0.0"
    source.mkdir(parents=True)
    (runtime / "native").mkdir(parents=True)
    (source / "ServiceBridge.node").write_bytes(b"native-addon")
    (runtime / "native" / "ServiceBridge.proto").write_text("stale duplicate\n", encoding="utf-8")

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "sync-native-runtime-artifacts.ps1"),
            "-SourceNativeDir",
            str(source),
            "-RuntimePluginDir",
            str(runtime),
            "-PluginId",
            "service-bridge-plugin",
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
    assert_standard_shape(output, "sync-native-runtime-artifacts")
    assert output["status"] == "blocked"
    assert "Duplicate proto files found under runtime native" in "\n".join(output["blockers"])


def test_validate_rpc_proto_bundle_blocks_missing_required_field(tmp_path):
    bundle = tmp_path / "service-proto-bundle-json.js"
    bundle.write_text(
        'window.serviceProtoBundleJson={"nested":{"ServiceBridge":{"nested":{'
        '"DeviceInfo":{"fields":{"uuid":{"type":"string","id":1}}}'
        '}}}};',
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "validate-rpc-proto-bundle.ps1"),
            "-BundleJs",
            str(bundle),
            "-ServiceName",
            "ServiceBridge",
            "-RequiredFields",
            "DeviceInfo:uuid,ifDHCP",
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
    assert_standard_shape(output, "validate-rpc-proto-bundle")
    assert output["status"] == "blocked"
    assert "Required field 'DeviceInfo.ifDHCP'" in "\n".join(output["blockers"])


def test_validate_rpc_proto_bundle_accepts_required_messages_and_fields(tmp_path):
    bundle = tmp_path / "service-proto-bundle-json.js"
    bundle.write_text(
        'window.serviceProtoBundleJson={"nested":{"ServiceBridge":{"nested":{'
        '"DeviceInfo":{"fields":{"uuid":{"type":"string","id":1},"ifDHCP":{"type":"bool","id":2},'
        '"ipConfigCurrent":{"type":"uint32","id":3}}},'
        '"DeviceTreeSnapshotNode":{"fields":{"uuid":{"type":"string","id":1},"ipConfigOption":{"type":"uint32","id":2}}}'
        '}}}};',
        encoding="utf-8",
    )

    output = run_ps(
        "validate-rpc-proto-bundle",
        "-BundleJs",
        str(bundle),
        "-ServiceName",
        "ServiceBridge",
        "-RequiredMessages",
        "DeviceInfo,DeviceTreeSnapshotNode",
        "-RequiredFields",
        "DeviceInfo:uuid,ifDHCP,ipConfigCurrent;DeviceTreeSnapshotNode:uuid,ipConfigOption",
    )

    assert_standard_shape(output, "validate-rpc-proto-bundle")
    assert output["status"] == "ok"
    assert output["facts"]["discovered_messages"]["DeviceInfo"] == [
        "uuid",
        "ifDHCP",
        "ipConfigCurrent",
    ]


def test_inspect_hostapplication_cdp_target_selects_business_page_and_rejects_workbench():
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
                "title": "ExampleHost",
                "url": "file:///<workspace-root>/HostApplication/HostApplication/src/window/base-win.html",
                "webSocketDebuggerUrl": "ws://127.0.0.1/base",
            },
            {
                "id": "workbench",
                "type": "page",
                "title": "Plugin Workbench",
                "url": "file:///<workspace-root>/HostApplication/HostApplication/src/plugin-host/devtools/plugin-workbench.html#build",
                "webSocketDebuggerUrl": "ws://127.0.0.1/workbench",
            },
            {
                "id": "business",
                "type": "page",
                "title": "ExampleHost",
                "url": "http://example.local/frontend/static/index.html#/app-home/appHome",
                "webSocketDebuggerUrl": "ws://127.0.0.1/business",
            },
        ]
    )

    output = run_ps("inspect-host-cdp-target", "-TargetsJson", targets)

    assert_standard_shape(output, "inspect-host-cdp-target")
    assert output["status"] == "ok"
    assert output["facts"]["selected_target"]["id"] == "business"
    assert output["facts"]["selected_target"]["reason"] == "host-app"
    rejected_reasons = {target["reason"] for target in output["facts"]["rejected_targets"]}
    assert {"devtools", "workbench", "base-window"} <= rejected_reasons


def test_inspect_hostapplication_cdp_target_blocks_when_only_workbench_exists():
    targets = json.dumps(
        [
            {
                "id": "workbench",
                "type": "page",
                "title": "Plugin Workbench",
                "url": "file:///<workspace-root>/HostApplication/HostApplication/src/plugin-host/devtools/plugin-workbench.html#build",
                "webSocketDebuggerUrl": "ws://127.0.0.1/workbench",
            }
        ]
    )

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "inspect-host-cdp-target.ps1"),
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
    assert "No matching host CDP target found" in "\n".join(output["blockers"])


def test_capture_cdp_screenshot_dry_run_uses_feature_artifact_directory(tmp_path):
    repo = tmp_path / "repo"
    feature_dir = repo / "specs" / "001-cdp-evidence"
    feature_dir.mkdir(parents=True)
    (repo / ".specify").mkdir()
    (repo / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-cdp-evidence"}),
        encoding="utf-8",
    )
    targets = json.dumps(
        [
            {
                "id": "business",
                "type": "page",
                "title": "ExampleHost",
                "url": "http://example.local/frontend/static/index.html#/app-home/appHome",
                "webSocketDebuggerUrl": "ws://127.0.0.1/business",
            }
        ]
    )

    output = run_ps(
        "capture-cdp-screenshot",
        "-RepoRoot",
        str(repo),
        "-TargetsJson",
        targets,
        "-Scenario",
        "after save dialog",
        "-DryRun",
    )

    assert_standard_shape(output, "capture-cdp-screenshot")
    assert output["status"] == "ok"
    facts = output["facts"]
    assert facts["selected_target"]["id"] == "business"
    assert facts["screenshot_dir"] == str(feature_dir / "cdp-screenshots")
    assert facts["screenshots_index"] == str(feature_dir / "cdp-screenshots" / "screenshots-index.md")
    assert facts["screenshot_path"].endswith("-after-save-dialog.png")
    assert Path(facts["screenshot_dir"]).is_dir()
    assert any("Tell the human the screenshot directory" in hint for hint in output["hints"])


def test_capture_cdp_screenshot_blocks_output_outside_feature_dir(tmp_path):
    repo = tmp_path / "repo"
    feature_dir = repo / "specs" / "001-cdp-evidence"
    feature_dir.mkdir(parents=True)
    outside = repo / "outside"
    outside.mkdir()
    targets = json.dumps(
        [
            {
                "id": "business",
                "type": "page",
                "title": "ExampleHost",
                "url": "http://example.local/frontend/static/index.html#/app-home/appHome",
                "webSocketDebuggerUrl": "ws://127.0.0.1/business",
            }
        ]
    )

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "capture-cdp-screenshot.ps1"),
            "-RepoRoot",
            str(repo),
            "-FeatureDir",
            str(feature_dir),
            "-OutputDir",
            str(outside),
            "-TargetsJson",
            targets,
            "-DryRun",
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
    assert_standard_shape(output, "capture-cdp-screenshot")
    assert output["status"] == "blocked"
    assert "OutputDir must stay under the feature directory" in "\n".join(output["blockers"])


def test_ensure_hostapplication_cdp_host_reuses_valid_running_target():
    targets = json.dumps(
        [
            {
                "id": "workbench",
                "type": "page",
                "title": "Plugin Workbench",
                "url": "file:///<workspace-root>/HostApplication/HostApplication/src/plugin-host/devtools/plugin-workbench.html#build",
                "webSocketDebuggerUrl": "ws://127.0.0.1/workbench",
            },
            {
                "id": "business",
                "type": "page",
                "title": "ExampleHost",
                "url": "http://example.local/frontend/static/index.html#/app-home/appHome",
                "webSocketDebuggerUrl": "ws://127.0.0.1/business",
            },
        ]
    )

    output = run_ps("ensure-host-cdp", "-TargetsJson", targets)

    assert_standard_shape(output, "ensure-host-cdp")
    assert output["status"] == "ok"
    assert output["facts"]["endpoint_reachable"] is True
    assert output["facts"]["selected_target"]["id"] == "business"
    assert output["facts"]["selected_target"]["reason"] == "host-app"
    assert output["facts"]["rejected_targets"][0]["reason"] == "workbench"


def test_ensure_hostapplication_cdp_host_blocks_before_manual_acceptance_when_target_missing():
    targets = json.dumps(
        [
            {
                "id": "workbench",
                "type": "page",
                "title": "Plugin Workbench",
                "url": "file:///<workspace-root>/HostApplication/HostApplication/src/plugin-host/devtools/plugin-workbench.html#build",
                "webSocketDebuggerUrl": "ws://127.0.0.1/workbench",
            }
        ]
    )

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "ensure-host-cdp.ps1"),
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
    assert_standard_shape(output, "ensure-host-cdp")
    assert output["status"] == "blocked"
    blocker_text = "\n".join(output["blockers"])
    assert "before manual acceptance" in blocker_text
    assert "Do not switch to human acceptance" in "\n".join(output["hints"])


def test_ensure_hostapplication_cdp_host_reports_safe_process_recovery_without_unknown_kill(tmp_path):
    owner = json.dumps(
        [
            {
                "local_address": "127.0.0.1",
                "local_port": 9222,
                "owning_process_id": 123456,
                "process_name": "node",
                "process_path": str(tmp_path / "HostApplication" / "node.exe"),
                "command_line": f'node "{tmp_path / "HostApplication" / "scripts" / "debug.js"}"',
            }
        ]
    )
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "powershell" / "ensure-host-cdp.ps1"),
            "-Endpoint",
            "http://127.0.0.1:9",
            "-HostRoot",
            str(tmp_path / "HostApplication"),
            "-PortOwnersJson",
            owner,
            "-AllowProcessRecovery",
            "-DryRunRecovery",
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
    assert_standard_shape(output, "ensure-host-cdp")
    assert output["status"] == "blocked"
    assert output["facts"]["recovery"]["requested"] is True
    assert output["facts"]["recovery"]["killed_process_ids"] == [123456]
    assert output["facts"]["recovery"]["unsafe_owners"] == []
    assert "recovery was attempted" in "\n".join(output["blockers"])


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
            "fix(example-device-tree): preserve non-device selection",
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
            "DeviceListMenu: fix context menu disabled item hover",
            "",
            "修复设备列表右键菜单不可用条目的悬浮样式",
            "",
            "【提交类型】",
            "修复 - UI 交互",
            "",
            "【问题描述】",
            "1. 不可用菜单项 hover 样式不符合 Qt 表现",
            "",
            "【修改方案】",
            "1. 调整设备列表菜单项 CSS 状态样式",
            "",
            "【影响评估】",
            "影响轻微，仅影响设备列表右键菜单显示",
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
        "## 技术上下文\n\n## AI Context Contract\n\n## 影响模块与边界\n\n"
        "## Quality Vision Link\n\n## 测试用例计划\n\n## Acceptance Rubric Link\n\n"
        "## Implementation Slices\n\n## 验证计划\n\n## AI Self-Acceptance Contract\n",
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
        "## 技术上下文\n\n## AI Context Contract\n\n## 影响模块与边界\n\n"
        "## Quality Vision Link\n\n## 测试用例计划\n\n## Acceptance Rubric Link\n\n"
        "## 验证计划\n\n## AI Self-Acceptance Contract\n\n## Implementation Slices\n",
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
        "## 技术上下文\n\n## AI Context Contract\n\n## 影响模块与边界\n\n"
        "## Quality Vision Link\n\n## 测试用例计划\n\n## Acceptance Rubric Link\n\n"
        "## Implementation Slices\n\n## 验证计划\n\n## AI Self-Acceptance Contract\n",
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
    (repo / ".specify" / "scripts" / "powershell").mkdir(parents=True)
    (repo / "spec-kit" / "workflows" / "speckit").mkdir(parents=True)
    (repo / "spec-kit" / "templates").mkdir(parents=True)
    visible_skill_dir = repo / ".agents" / "skills" / "speckit-specify"
    internal_skills_dir = repo / ".agents" / "spec-kit" / "skills"
    visible_skill_dir.mkdir(parents=True)
    for skill_name in [
        "speckit-commit",
        "speckit-implement",
        "speckit-retrospective",
        "speckit-tasks",
    ]:
        (internal_skills_dir / skill_name).mkdir(parents=True)
    (repo / "AGENTS.md").write_text("# old agents\n", encoding="utf-8")
    (repo / ".specify" / "memory" / "repository-map.md").write_text("# old map\n", encoding="utf-8")
    (repo / ".specify" / "templates" / "layer-manifest.yml").write_text("artifact_sets: {}\n", encoding="utf-8")
    (repo / "ai" / "workflows" / "task-routing.md").write_text("# old routing\n", encoding="utf-8")
    (repo / "ai" / "workflows" / "skill-routing.yml").write_text("# old skill routing\n", encoding="utf-8")
    (repo / "ai" / "rules" / "ai-coding-rules.md").write_text("# old rules\n", encoding="utf-8")
    (repo / "spec-kit" / "workflows" / "speckit" / "workflow.yml").write_text(
        "id: commit\nid: retrospective\n",
        encoding="utf-8",
    )
    (repo / "spec-kit" / "TEAM-README.md").write_text(
        "commit -> retrospective/留痕\n",
        encoding="utf-8",
    )
    (visible_skill_dir / "SKILL.md").write_text("old specify\n", encoding="utf-8")
    (internal_skills_dir / "speckit-commit" / "SKILL.md").write_text(
        "Retrospective and lesson promotion are optional\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-tasks" / "SKILL.md").write_text(
        "optional test-hardening, commit, and branch completion\n",
        encoding="utf-8",
    )

    blocked = run_ps("validate-generated-context", "-RepoRoot", str(repo))
    assert blocked["status"] == "blocked"
    blocker_text = "\n".join(blocked["blockers"])
    assert "AGENTS.md missing required generated-context phrases" in blocker_text
    assert "ai/workflows/task-routing.md missing required generated-context phrases" in blocker_text
    assert "ai/workflows/skill-routing.yml missing required generated-context phrases" in blocker_text
    assert ".agents/skills/speckit-specify/SKILL.md missing required generated-context phrases" in blocker_text
    assert ".agents/spec-kit/skills/speckit-commit/SKILL.md missing required generated-context phrases" in blocker_text

    (repo / "AGENTS.md").write_text(
        "Project Path Categories\nsource-to-runtime copy\nbest-effort self-validation\n"
        "direct runtime replacement\nhost CDP validation\n"
        "ensure-host-cdp\n"
        "stale/current-feature hint\nread the current plan only\n"
        "select-knowledge\nselect-gates\nvalidate-knowledge-index\nvalidate-context-budget\n"
        "inspect-validation-capabilities\n",
        encoding="utf-8",
    )
    (repo / ".specify" / "memory" / "repository-map.md").write_text(
        "Project Path Categories\n<workspace-root>/FrontendPlugin/<plugin-id>/\n"
        "CDP target inventory\nDo not write machine-specific absolute paths here\n",
        encoding="utf-8",
    )
    (repo / ".specify" / "templates" / "layer-manifest.yml").write_text(
        "stage_gates:\nread_strategies:\nKnowledge\ngate_routing\nselect-gates\n"
        "validate-context-budget\nvalidate-knowledge-index\n"
        "checklists/implementation-readiness.md\n",
        encoding="utf-8",
    )
    (repo / "spec-kit" / "templates" / "acceptance-rubric-template.md").write_text(
        read_text("templates/acceptance-rubric-template.md"),
        encoding="utf-8",
    )
    (repo / "spec-kit" / "templates" / "checklist-template.md").write_text(
        read_text("templates/checklist-template.md"),
        encoding="utf-8",
    )
    (repo / ".specify" / "templates" / "acceptance-rubric-template.md").write_text(
        read_text("templates/acceptance-rubric-template.md"),
        encoding="utf-8",
    )
    (repo / ".specify" / "templates" / "checklist-template.md").write_text(
        read_text("templates/checklist-template.md"),
        encoding="utf-8",
    )
    (repo / "ai" / "workflows" / "task-routing.md").write_text(
        "tasks -> analyze -> checklist\nvalidate-generated-context\nvalidate-knowledge-index\n"
        "validate-context-budget\nselect-knowledge\nselect-gates\nskill-routing.yml\nartifact_sections\n"
        "Stage Continuation\ninspect-host-cdp-target\n"
        "ensure-host-cdp\n"
        "capture-cdp-screenshot\n"
        "do not apply stale feature risk flags\n",
        encoding="utf-8",
    )
    (repo / "ai" / "workflows" / "skill-routing.yml").write_text(
        "internal_skill_root\n.agents/spec-kit/skills\nload_only_selected_skill\n"
        "speckit-fact-layer\nspeckit-test-plan\nspeckit-quality-vision\n"
        "speckit-acceptance-rubric\nspeckit-ai-self-acceptance\ncommit-message\n",
        encoding="utf-8",
    )
    (repo / "ai" / "rules" / "ai-coding-rules.md").write_text(
        "Generated Context Drift\nanalysis.md\nvalidate-generated-context\nvalidate-knowledge-index\n"
        "Stage Continuation Contract\nHost Frontend Delivery Chain\n"
        "ensure-host-cdp\n"
        "Retrospective/留痕 is mandatory before commit\n",
        encoding="utf-8",
    )
    (repo / "spec-kit" / "workflows" / "speckit" / "workflow.yml").write_text(
        "id: retrospective\nid: commit\nRequire workflow-record.md and improvement-candidates.md before commit\n"
        "automatic_stage_continuation\ninspect-host-cdp-target\n"
        "ensure-host-cdp\n"
        "capture-cdp-screenshot\n"
        "validate-knowledge-index\nvalidate-context-budget\nselect-gates\ncurrent-feature state only\n",
        encoding="utf-8",
    )
    (repo / "spec-kit" / "TEAM-README.md").write_text(
        "retrospective/留痕 -> commit\ncommit 前强制 retrospective\n"
        "source edit -> frontend build -> direct runtime replacement -> real host CDP verification\n"
        "select-knowledge\nselect-gates\nvalidate-context-budget\nfull-text/BM25 search\n",
        encoding="utf-8",
    )
    (visible_skill_dir / "SKILL.md").write_text(
        "Internal Stage Loading\n.agents/spec-kit/skills/speckit-<stage>/SKILL.md\n"
        "Do not pre-load\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-commit" / "SKILL.md").write_text(
        "validate-feature-artifacts\nStage commit\nworkflow-record.md\n"
        "improvement-candidates.md\nretrospective.status\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-implement" / "SKILL.md").write_text(
        "ensure-host-cdp\nCDP host recovery ladder\nmanual acceptance\nselect-gates\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-retrospective" / "SKILL.md").write_text(
        "Existing Constraint Audit\nAI workflow self-check\nTeam knowledge candidates\nretrospective.status\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-tasks" / "SKILL.md").write_text(
        "Run mandatory `speckit.retrospective` / 留痕 after quick acceptance and before commit\n"
        "optional test-hardening, retrospective/留痕\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-test-plan").mkdir(parents=True)
    (internal_skills_dir / "speckit-test-plan" / "SKILL.md").write_text(
        "API/E2E\nselect-knowledge\napproved-by-ai-obvious\n"
        "needs-human-review\n测试用例计划\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-quality-vision").mkdir(parents=True)
    (internal_skills_dir / "speckit-quality-vision" / "SKILL.md").write_text(
        "quality-vision.md\nUI Baseline\nneeds-human-baseline\nowner-approved-n/a\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-acceptance-rubric").mkdir(parents=True)
    (internal_skills_dir / "speckit-acceptance-rubric" / "SKILL.md").write_text(
        "acceptance-rubric.md\nEssential\nPitfall\nL1 功能正确性\nL4 交互体验\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-ai-self-acceptance").mkdir(parents=True)
    (internal_skills_dir / "speckit-ai-self-acceptance" / "SKILL.md").write_text(
        "AI Self-Acceptance\nPASS\nFAIL\nBLOCKED\nCDP\nconsole\nlogs\ncdp-screenshots\n",
        encoding="utf-8",
    )
    for script_name in [
        "select-gates.ps1",
        "inspect-workspace-repositories.ps1",
        "validate-test-plan.ps1",
        "validate-ai-self-acceptance.ps1",
        "inspect-plugin-build-plan.ps1",
        "validate-plugin-package.ps1",
        "post-commit-self-check.ps1",
        "validate-rubric-score.ps1",
        "cleanup-host-cdp.ps1",
        "validate-context-budget.ps1",
        "sync-native-runtime-artifacts.ps1",
        "validate-rpc-proto-bundle.ps1",
        "capture-cdp-screenshot.ps1",
        "cdp-common.ps1",
    ]:
        (repo / ".specify" / "scripts" / "powershell" / script_name).write_text(
            "# placeholder\n",
            encoding="utf-8",
        )

    ok = run_ps("validate-generated-context", "-RepoRoot", str(repo))
    assert ok["status"] == "ok"

    (repo / ".specify" / "templates" / "acceptance-rubric-template.md").write_text(
        "old acceptance rubric\n",
        encoding="utf-8",
    )
    blocked_template = run_ps("validate-generated-context", "-RepoRoot", str(repo))
    assert blocked_template["status"] == "blocked"
    assert any(
        ".specify/templates/acceptance-rubric-template.md differs from source template"
        in blocker
        for blocker in blocked_template["blockers"]
    )


def test_validate_generated_context_uses_codex_context_even_with_stale_init_options(tmp_path):
    repo = tmp_path
    (repo / ".specify" / "memory").mkdir(parents=True)
    (repo / ".specify" / "templates").mkdir(parents=True)
    (repo / "ai" / "workflows").mkdir(parents=True)
    (repo / "ai" / "rules").mkdir(parents=True)
    (repo / ".specify" / "scripts" / "powershell").mkdir(parents=True)
    (repo / "spec-kit" / "workflows" / "speckit").mkdir(parents=True)
    visible_skill_dir = repo / ".agents" / "skills" / "speckit-specify"
    internal_skills_dir = repo / ".agents" / "spec-kit" / "skills"
    visible_skill_dir.mkdir(parents=True)
    for skill_name in [
        "speckit-commit",
        "speckit-implement",
        "speckit-retrospective",
        "speckit-tasks",
        "speckit-test-plan",
        "speckit-quality-vision",
        "speckit-acceptance-rubric",
        "speckit-ai-self-acceptance",
    ]:
        (internal_skills_dir / skill_name).mkdir(parents=True)
    (repo / ".specify" / "init-options.json").write_text(
        json.dumps({"context_file": "CLAUDE.md", "canonical_context_file": "AGENTS.md"}),
        encoding="utf-8",
    )
    (repo / "AGENTS.md").write_text(
        "Project Path Categories\nsource-to-runtime copy\nbest-effort self-validation\n"
        "direct runtime replacement\nhost CDP validation\n"
        "ensure-host-cdp\n"
        "stale/current-feature hint\nread the current plan only\n"
        "select-knowledge\nselect-gates\nvalidate-knowledge-index\nvalidate-context-budget\n"
        "inspect-validation-capabilities\n",
        encoding="utf-8",
    )
    (repo / ".specify" / "memory" / "repository-map.md").write_text(
        "Project Path Categories\n<workspace-root>/FrontendPlugin/<plugin-id>/\n"
        "CDP target inventory\nDo not write machine-specific absolute paths here\n",
        encoding="utf-8",
    )
    (repo / ".specify" / "templates" / "layer-manifest.yml").write_text(
        "stage_gates:\nread_strategies:\nKnowledge\ngate_routing\nselect-gates\n"
        "validate-context-budget\nvalidate-knowledge-index\n"
        "checklists/implementation-readiness.md\n",
        encoding="utf-8",
    )
    (repo / ".specify" / "templates" / "acceptance-rubric-template.md").write_text(
        read_text("templates/acceptance-rubric-template.md"),
        encoding="utf-8",
    )
    (repo / ".specify" / "templates" / "checklist-template.md").write_text(
        read_text("templates/checklist-template.md"),
        encoding="utf-8",
    )
    (repo / "ai" / "workflows" / "task-routing.md").write_text(
        "tasks -> analyze -> checklist\nvalidate-generated-context\nvalidate-knowledge-index\n"
        "validate-context-budget\nselect-knowledge\nselect-gates\nskill-routing.yml\nartifact_sections\n"
        "Stage Continuation\ninspect-host-cdp-target\n"
        "ensure-host-cdp\n"
        "capture-cdp-screenshot\n"
        "do not apply stale feature risk flags\n",
        encoding="utf-8",
    )
    (repo / "ai" / "workflows" / "skill-routing.yml").write_text(
        "internal_skill_root\n.agents/spec-kit/skills\nload_only_selected_skill\n"
        "speckit-fact-layer\nspeckit-test-plan\nspeckit-quality-vision\n"
        "speckit-acceptance-rubric\nspeckit-ai-self-acceptance\ncommit-message\n",
        encoding="utf-8",
    )
    (repo / "ai" / "rules" / "ai-coding-rules.md").write_text(
        "Generated Context Drift\nanalysis.md\nvalidate-generated-context\nvalidate-knowledge-index\n"
        "Stage Continuation Contract\nHost Frontend Delivery Chain\n"
        "ensure-host-cdp\n"
        "Retrospective/留痕 is mandatory before commit\n",
        encoding="utf-8",
    )
    (repo / "spec-kit" / "workflows" / "speckit" / "workflow.yml").write_text(
        "id: retrospective\nid: commit\nRequire workflow-record.md and improvement-candidates.md before commit\n"
        "automatic_stage_continuation\ninspect-host-cdp-target\n"
        "ensure-host-cdp\n"
        "capture-cdp-screenshot\n"
        "validate-knowledge-index\nvalidate-context-budget\nselect-gates\ncurrent-feature state only\n",
        encoding="utf-8",
    )
    (repo / "spec-kit" / "TEAM-README.md").write_text(
        "retrospective/留痕 -> commit\ncommit 前强制 retrospective\n"
        "source edit -> frontend build -> direct runtime replacement -> real host CDP verification\n"
        "select-knowledge\nselect-gates\nvalidate-context-budget\nfull-text/BM25 search\n",
        encoding="utf-8",
    )
    (visible_skill_dir / "SKILL.md").write_text(
        "Internal Stage Loading\n.agents/spec-kit/skills/speckit-<stage>/SKILL.md\n"
        "Do not pre-load\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-commit" / "SKILL.md").write_text(
        "validate-feature-artifacts\nStage commit\nworkflow-record.md\n"
        "improvement-candidates.md\nretrospective.status\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-implement" / "SKILL.md").write_text(
        "ensure-host-cdp\nCDP host recovery ladder\nmanual acceptance\nselect-gates\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-retrospective" / "SKILL.md").write_text(
        "Existing Constraint Audit\nAI workflow self-check\nTeam knowledge candidates\nretrospective.status\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-tasks" / "SKILL.md").write_text(
        "Run mandatory `speckit.retrospective` / 留痕 after quick acceptance and before commit\n"
        "optional test-hardening, retrospective/留痕\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-test-plan" / "SKILL.md").write_text(
        "API/E2E\nselect-knowledge\napproved-by-ai-obvious\n"
        "needs-human-review\n测试用例计划\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-quality-vision" / "SKILL.md").write_text(
        "quality-vision.md\nUI Baseline\nneeds-human-baseline\nowner-approved-n/a\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-acceptance-rubric" / "SKILL.md").write_text(
        "acceptance-rubric.md\nEssential\nPitfall\nL1 功能正确性\nL4 交互体验\n",
        encoding="utf-8",
    )
    (internal_skills_dir / "speckit-ai-self-acceptance" / "SKILL.md").write_text(
        "AI Self-Acceptance\nPASS\nFAIL\nBLOCKED\nCDP\nconsole\nlogs\ncdp-screenshots\n",
        encoding="utf-8",
    )
    for script_name in [
        "select-gates.ps1",
        "inspect-workspace-repositories.ps1",
        "validate-test-plan.ps1",
        "validate-ai-self-acceptance.ps1",
        "inspect-plugin-build-plan.ps1",
        "validate-plugin-package.ps1",
        "post-commit-self-check.ps1",
        "validate-rubric-score.ps1",
        "cleanup-host-cdp.ps1",
        "validate-context-budget.ps1",
        "sync-native-runtime-artifacts.ps1",
        "validate-rpc-proto-bundle.ps1",
        "capture-cdp-screenshot.ps1",
        "cdp-common.ps1",
    ]:
        (repo / ".specify" / "scripts" / "powershell" / script_name).write_text(
            "# placeholder\n",
            encoding="utf-8",
        )

    ok = run_ps("validate-generated-context", "-RepoRoot", str(repo))
    assert ok["status"] == "ok"
    checked_paths = [entry["path"] for entry in ok["facts"]["checked"]]
    assert checked_paths[0] == "AGENTS.md"
    assert ".agents/skills/speckit-specify/SKILL.md" in checked_paths
    assert "ai/workflows/skill-routing.yml" in checked_paths
    assert ".agents/spec-kit/skills/speckit-commit/SKILL.md" in checked_paths
    assert ".agents/spec-kit/skills/speckit-ai-self-acceptance/SKILL.md" in checked_paths
    assert all("CLAUDE.md" not in path for path in checked_paths)
    assert all(".claude/" not in path for path in checked_paths)

    (repo / "AGENTS.md").write_text(
        "Project Path Categories\n",
        encoding="utf-8",
    )
    blocked = run_ps("validate-generated-context", "-RepoRoot", str(repo))
    assert blocked["status"] == "blocked"
    assert any(
        "AGENTS.md missing required generated-context phrases" in blocker
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
        "## 技术上下文\n\n## AI Context Contract\n\n## 影响模块与边界\n\n"
        "## Quality Vision Link\n\n## 测试用例计划\n\n"
        "| Kind | Plan | Review status |\n| --- | --- | --- |\n"
        "| API | interface regression row | approved-by-ai-obvious |\n"
        "| E2E | N/A: unsupported in this repo | approved-by-ai-obvious |\n\n"
        "## Acceptance Rubric Link\n\n"
        "## Implementation Slices\n\n## 验证计划\n\n## AI Self-Acceptance Contract\n",
        encoding="utf-8",
    )
    (feature_dir / "validation.md").write_text(
        "# Validation\n\n## Validation Matrix\n\n## Result Interpretation\n\n"
        "## Validation Context Contract\n\n## Evidence Links\n\n"
        "## AI Acceptance Result\n\nAI Self-Acceptance: PASS\n",
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

    powershell_common = read_text("scripts/powershell/automation-common.ps1")
    assert "validation_artifacts" in powershell_common
    assert "ai/templates/validation-template.md" in powershell_common
    assert "ai/templates/evidence-template.md" in powershell_common


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
