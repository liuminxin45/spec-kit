import subprocess
from pathlib import Path

from specify_cli.shared_infra import install_shared_infra


class NullConsole:
    def print(self, *args, **kwargs):
        pass


def test_shared_infra_installs_checklist_rules_and_validator(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]

    install_shared_infra(
        tmp_path,
        "ps",
        version="test",
        core_pack=None,
        repo_root=repo_root,
        console=NullConsole(),
    )

    rules_dir = tmp_path / ".specify" / "checklist-rules"
    assert (rules_dir / "common.yml").is_file()
    assert (rules_dir / "new-feature.yml").is_file()
    assert (rules_dir / "migration.yml").is_file()
    assert (rules_dir / "bugfix.yml").is_file()
    assert (rules_dir / "tooling.yml").is_file()

    validator = tmp_path / ".specify" / "scripts" / "powershell" / "validate-checklist.ps1"
    assert validator.is_file()

    manifest = tmp_path / ".specify" / "integrations" / "speckit.manifest.json"
    manifest_text = manifest.read_text(encoding="utf-8")
    assert ".specify/checklist-rules/common.yml" in manifest_text
    assert ".specify/scripts/powershell/validate-checklist.ps1" in manifest_text


def test_shared_infra_skips_generated_python_bytecode(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    project = tmp_path / "project"
    project.mkdir()
    core_pack = tmp_path / "core_pack"
    python_scripts = core_pack / "scripts" / "python"
    pycache = python_scripts / "__pycache__"
    pycache.mkdir(parents=True)
    (python_scripts / "check_prerequisites.py").write_text("# script\n", encoding="utf-8")
    (pycache / "check_prerequisites.cpython-313.pyc").write_bytes(b"bytecode")

    install_shared_infra(
        project,
        "ps",
        version="test",
        core_pack=core_pack,
        repo_root=repo_root,
        console=NullConsole(),
    )

    installed_python = project / ".specify" / "scripts" / "python"
    assert (installed_python / "check_prerequisites.py").is_file()
    assert not list(installed_python.rglob("*.pyc"))
    assert not any(path.name == "__pycache__" for path in installed_python.rglob("*"))


def test_checklist_validator_counts_only_checkbox_prefix_ids(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    feature_dir = tmp_path / "specs" / "001-demo"
    checklist_dir = feature_dir / "checklists"
    checklist_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    checklist = checklist_dir / "requirements.md"
    checklist.write_text(
        "# Checklist\n\n"
        "Reference: spec.md. CHK001 is discussed here as source context.\n\n"
        "- [x] CHK001 First executable item.\n"
        "- [x] CHK002 Mentions CHK001 in prose without becoming a duplicate.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(repo_root / "scripts" / "powershell" / "validate-checklist.ps1"),
            "-FeatureDir",
            str(feature_dir),
            "-ChecklistPath",
            str(checklist),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    assert "Checklist validation passed" in result.stdout
