import tomllib
from pathlib import Path

import pytest
import yaml

from specify_cli._assets import UPSTREAM_BASELINE
from specify_cli._upgrade import write_spec_kit_lock
from specify_cli.catalogs import CatalogStackBase
from specify_cli.integrations.catalog import IntegrationCatalog, IntegrationValidationError


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_local_version_and_upstream_baseline_are_explicit(tmp_path):
    pyproject = tomllib.loads(read_text("pyproject.toml"))
    workflow = yaml.safe_load(read_text("workflows/speckit/workflow.yml"))
    readme = read_text("README.md")

    assert pyproject["project"]["version"] == "0.10.3"
    assert workflow["requires"]["speckit_version"] == ">=0.10.3"
    assert UPSTREAM_BASELINE == "github/spec-kit@v0.12.5"
    assert "upstream_baseline: github/spec-kit@v0.12.5" in readme

    lock_path = write_spec_kit_lock(tmp_path, version="0.10.3", source="test")
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    assert lock["spec_kit"]["upstream_baseline"] == UPSTREAM_BASELINE


def test_catalog_url_validation_rejects_hostless_urls_and_duplicate_priorities(tmp_path):
    with pytest.raises(ValueError, match="host"):
        CatalogStackBase._validate_catalog_url("https:///catalog.json")
    with pytest.raises(ValueError, match="HTTPS"):
        CatalogStackBase._validate_catalog_url("http://example.com/catalog.json")

    CatalogStackBase._validate_catalog_url("http://localhost/catalog.json")

    config_dir = tmp_path / ".specify"
    config_dir.mkdir()
    (config_dir / "integration-catalogs.yml").write_text(
        """
catalogs:
  - name: one
    url: https://example.com/one.json
    priority: 1
  - name: two
    url: https://example.com/two.json
    priority: 1
""",
        encoding="utf-8",
    )
    with pytest.raises(IntegrationValidationError, match="duplicate priority"):
        IntegrationCatalog(tmp_path).get_active_catalogs()

    (config_dir / "integration-catalogs.yml").write_text("catalogs: [", encoding="utf-8")
    with pytest.raises(IntegrationValidationError, match="Failed to read catalog config"):
        IntegrationCatalog(tmp_path).get_active_catalogs()


def test_optional_bug_workflow_templates_are_label_gated_and_pr_first():
    bug_fix = read_text(".github/workflows/bug-fix.md")
    bug_test = read_text(".github/workflows/bug-test.md")

    assert "names: [bug-fix]" in bug_fix
    assert "draft: true" in bug_fix
    assert "not explicitly labeled `bug-fix`" in bug_fix
    assert "do not open a pr" in bug_fix.lower()

    assert "names: [bug-test]" in bug_test
    assert "add-comment" in bug_test
    assert "pull-requests: read" in bug_test
    assert "Never check out, fetch, or execute code referenced by a non-`origin` URL or remote" in bug_test


def test_workflow_cli_commands_are_split_from_root_entrypoint():
    root_cli = read_text("src/specify_cli/__init__.py")
    workflow_commands = read_text("src/specify_cli/workflows/commands.py")

    assert "register_workflow_commands" in root_cli
    assert "def workflow_run(" not in root_cli
    assert "def workflow_resume(" not in root_cli
    assert "def workflow_status(" not in root_cli
    assert "def workflow_run(" in workflow_commands
    assert "def register_workflow_commands(" in workflow_commands
