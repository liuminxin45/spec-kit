from pathlib import Path

import yaml

from specify_cli.integrations.base import IntegrationBase
from specify_cli.integrations.codex import CodexIntegration
from specify_cli.integrations.manifest import IntegrationManifest
from specify_cli.shared_infra import (
    INIT_ONLY_TEMPLATE_FILES,
    RUNTIME_TEMPLATE_FILES,
    install_shared_infra,
    refresh_shared_templates,
)


SPEC_KIT_ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (SPEC_KIT_ROOT / relative_path).read_text(encoding="utf-8")


def resolve_installed_text(relative_path: str) -> str:
    text = read_text(relative_path)
    return IntegrationBase.resolve_command_refs(text, "-")


def load_manifest() -> dict:
    return yaml.safe_load(read_text("templates/layer-manifest.yml"))


class _NullConsole:
    def print(self, *args, **kwargs) -> None:
        pass


def test_manifest_declares_lean_architecture_buckets():
    manifest = load_manifest()

    assert manifest["schema_version"] == "2.0"
    assert manifest["policy"]["context_policy"] == "default-minimal, load-on-demand"
    assert manifest["policy"]["automation_contract"] == "facts / blockers / unknowns / hints"

    layers = {layer["id"]: layer for layer in manifest["layers"]}
    assert set(layers) == {"Foundation", "WorkItem", "Capabilities", "Evidence"}

    assert "templates/agents-template.md" in layers["Foundation"]["source_assets"]
    assert ".specify/memory/repository-map.md" in layers["Foundation"]["generated_assets"]
    assert "templates/commands/implement.md" in layers["WorkItem"]["source_assets"]
    assert "templates/subskills/*/SKILL.md" in layers["Capabilities"]["source_assets"]
    assert "templates/commands/complete-branch.md" in layers["Evidence"]["source_assets"]

    assert manifest["artifact_sets"]["implement"] == [
        "spec.md",
        "plan.md",
        "workflow-state.json",
    ]
    assert manifest["artifact_sets"]["full-sdd-implement"] == [
        "spec.md",
        "plan.md",
        "tasks.md",
        "analysis.md",
        "checklists/implementation-readiness.md",
        "workflow-state.json",
    ]
    assert manifest["artifact_sets"]["validation-only"] == ["validation.md"]
    assert "validation-report.md" not in read_text("templates/layer-manifest.yml")


def test_manifest_source_assets_resolve_to_current_files():
    manifest = load_manifest()

    missing = []
    for layer in manifest["layers"]:
        for asset in layer["source_assets"]:
            if "*" in asset:
                if not list(SPEC_KIT_ROOT.glob(asset)):
                    missing.append(asset)
                continue
            if not (SPEC_KIT_ROOT / asset).exists():
                missing.append(asset)

    assert missing == []


def test_agents_template_uses_minimal_default_context():
    agents_template = read_text("templates/agents-template.md")
    task_routing = read_text("templates/ai/workflows/task-routing.md")

    for expected in [
        ".specify/workspace.yml",
        ".specify/memory/repository-map.md",
        ".specify/feature.json",
        "ai/workflows/task-routing.md",
        "Do Not Load By Default",
        "Layered SDD for AI Coding.md",
        "old completed `specs/*`",
    ]:
        assert expected in agents_template

    assert "Layered SDD model" not in agents_template
    assert "ai/skills/code-review.skill.md" not in agents_template
    assert "route by matching user text keywords alone" in task_routing
    assert "Hard Upgrade Gates" in task_routing
    assert "Context Budget" in task_routing


def test_l0_and_project_fact_assets_are_packaged_but_not_default_context():
    agents_template = read_text("templates/agents-template.md")
    manifest_text = read_text("templates/layer-manifest.yml")

    for relative_path in [
        "templates/ai/rules/engineering-principles.md",
        "templates/ai/rules/architecture-constraints.md",
        "templates/ai/rules/ai-coding-rules.md",
        "templates/ai/knowledge/project-overview.md",
        "templates/ai/knowledge/domain-glossary.md",
        "templates/ai/knowledge/module-map.md",
        "templates/ai/knowledge/compatibility-notes.md",
        "templates/ai/knowledge/legacy-decisions.md",
        "templates/ai/knowledge/build-and-package-notes.md",
    ]:
        assert (SPEC_KIT_ROOT / relative_path).is_file()

    assert "ai/knowledge/*" in agents_template
    assert "Do Not Load By Default" in agents_template


def test_capability_assets_are_executable_skills_plus_tool_policy_only(tmp_path):
    manifest_text = read_text("templates/layer-manifest.yml")

    for relative_path in [
        "templates/ai/tools/tool-registry.md",
        "templates/ai/tools/mcp-servers.md",
        "templates/ai/tools/mcp-usage-policy.md",
        "templates/ai/tools/mcp-permissions.md",
    ]:
        assert (SPEC_KIT_ROOT / relative_path).is_file()
        assert relative_path in manifest_text

    for removed in [
        "templates/ai/skills/code-review.skill.md",
        "templates/ai/skills/compatibility-check.skill.md",
        "templates/ai/skills/ui-debug.skill.md",
    ]:
        assert not (SPEC_KIT_ROOT / removed).exists()
        assert removed not in manifest_text

    project_root = tmp_path / "project"
    project_root.mkdir()
    install_shared_infra(
        project_root,
        "ps",
        version="test",
        core_pack=None,
        repo_root=SPEC_KIT_ROOT,
        console=_NullConsole(),
        invoke_separator="-",
    )

    assert (project_root / "ai/tools/mcp-usage-policy.md").is_file()
    assert not (project_root / "ai/skills/code-review.skill.md").exists()


def test_validation_templates_are_minimal_and_installed(tmp_path):
    manifest = load_manifest()

    assert (SPEC_KIT_ROOT / "templates/ai/templates/validation-template.md").is_file()
    assert (SPEC_KIT_ROOT / "templates/ai/templates/evidence-template.md").is_file()
    assert not (SPEC_KIT_ROOT / "templates/ai/templates/knowledge-entry-template.md").exists()
    assert not (SPEC_KIT_ROOT / "templates/ai/templates/skill-template.md").exists()

    assert manifest["artifact_sets"]["validation"] == ["validation.md", "acceptance.md"]
    assert manifest["artifact_sets"]["validation-only"] == ["validation.md"]
    assert "Evidence Index" in manifest["artifact_sections"]["evidence.md"]

    project_root = tmp_path / "project"
    project_root.mkdir()
    install_shared_infra(
        project_root,
        "ps",
        version="test",
        core_pack=None,
        repo_root=SPEC_KIT_ROOT,
        console=_NullConsole(),
        invoke_separator="-",
    )

    assert (project_root / "ai/templates/validation-template.md").is_file()
    assert (project_root / "ai/templates/evidence-template.md").is_file()
    assert not (project_root / "ai/templates/knowledge-entry-template.md").exists()
    assert not (project_root / "ai/templates/skill-template.md").exists()


def test_init_infra_installs_runtime_templates_and_ai_source(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    install_shared_infra(
        project_root,
        "ps",
        version="test",
        core_pack=None,
        repo_root=SPEC_KIT_ROOT,
        console=_NullConsole(),
        invoke_separator="-",
    )

    source_to_dest = {
        f"templates/{name}": f".specify/templates/{name}"
        for name in RUNTIME_TEMPLATE_FILES
    }
    ai_source_root = SPEC_KIT_ROOT / "templates" / "ai"
    for source_path in ai_source_root.rglob("*"):
        if source_path.is_file():
            source_rel = source_path.relative_to(SPEC_KIT_ROOT).as_posix()
            dest_rel = (Path("ai") / source_path.relative_to(ai_source_root)).as_posix()
            source_to_dest[source_rel] = dest_rel

    for source_rel, dest_rel in source_to_dest.items():
        dest = project_root / dest_rel
        assert dest.is_file(), dest_rel
        assert dest.read_text(encoding="utf-8") == resolve_installed_text(source_rel)

    for init_only in INIT_ONLY_TEMPLATE_FILES:
        assert not (project_root / ".specify" / "templates" / init_only).exists()


def test_init_infra_removes_stale_managed_ai_assets(tmp_path):
    project_root = tmp_path / "project"
    stale = project_root / "ai" / "skills" / "code-review.skill.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("old managed skill doc", encoding="utf-8")

    manifest = IntegrationManifest("speckit", project_root, version="old")
    manifest.record_existing(stale.relative_to(project_root))
    manifest.save()

    install_shared_infra(
        project_root,
        "ps",
        version="test",
        core_pack=None,
        repo_root=SPEC_KIT_ROOT,
        console=_NullConsole(),
        invoke_separator="-",
        refresh_managed=True,
    )

    assert not stale.exists()
    updated_manifest = IntegrationManifest.load("speckit", project_root)
    assert "ai/skills/code-review.skill.md" not in updated_manifest.files


def test_refresh_shared_templates_preserves_custom_ai_assets_without_force(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    install_shared_infra(
        project_root,
        "ps",
        version="test",
        core_pack=None,
        repo_root=SPEC_KIT_ROOT,
        console=_NullConsole(),
        invoke_separator="-",
    )

    target = project_root / "ai" / "rules" / "engineering-principles.md"
    target.write_text("# Local Custom Principles\n", encoding="utf-8")
    core_pack = tmp_path / "core_pack"
    source = core_pack / "templates" / "ai" / "rules" / "engineering-principles.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Bundled Replacement\n", encoding="utf-8")

    refresh_shared_templates(
        project_root,
        version="test-2",
        core_pack=core_pack,
        repo_root=SPEC_KIT_ROOT,
        console=_NullConsole(),
        invoke_separator="-",
    )

    assert target.read_text(encoding="utf-8") == "# Local Custom Principles\n"


def test_codex_integration_installs_lean_agents_file(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    integration = CodexIntegration()
    manifest = IntegrationManifest(integration.key, project_root, version="test")
    integration.setup(project_root, manifest, script_type="ps")

    agents = project_root / "AGENTS.md"
    assert agents.is_file()
    agents_text = agents.read_text(encoding="utf-8")
    assert "Spec Kit for AI coding" in agents_text
    assert "Default Context" in agents_text
    assert "Do Not Load By Default" in agents_text
    assert "Layered SDD model" not in agents_text
