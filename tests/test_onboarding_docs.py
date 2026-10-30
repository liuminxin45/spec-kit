"""Keep first-run documentation aligned with executable mode contracts."""
from pathlib import Path
import json
import re
import shlex

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from specify_cli import app, get_speckit_version
from specify_cli.codex_runtime import packs

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ("docs/agent-setup.md", "docs/codex-skill-mode.md", "docs/releases/v2.0.0.md")
DOCS = ("README.md", "README.en.md", "docs/README.md", *GUIDES,
        "docs/local-install-and-knowledge-mount.md")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def cli_lines(text):
    return [line for block in re.findall(r"```powershell\n(.*?)```", text, re.S)
            for line in block.splitlines() if line.startswith("specify ")]


def invoke(line, project):
    args = [str(project) if v == "$projectPath" else v for v in shlex.split(line)[1:]]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("guide", GUIDES)
def test_documented_first_install_runs_with_one_entry(guide, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# User rules\nKeep my rules.\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("# User source\n", encoding="utf-8")
    lines = cli_lines(read(guide))
    init = next(line for line in lines if line.startswith("specify init "))
    assert "--mode codex-skill" in init and "--no-git" in init and "--json" in init
    assert invoke(init, tmp_path)["status"] == "ok"
    assert packs.config(tmp_path)["mode"] == "codex-skill"
    assert (tmp_path / ".specify/packs.lock.json").is_file()
    assert (tmp_path / ".agents/skills/speckit/SKILL.md").is_file()
    assert not (tmp_path / ".agents/skills/speckit-specify").exists()
    assert not (tmp_path / ".agents/spec-kit").exists()
    assert not (tmp_path / "ai").exists()
    assert not (tmp_path / ".git").exists()
    assert "Keep my rules." in (tmp_path / "AGENTS.md").read_text()
    assert (tmp_path / "app.py").read_text() == "# User source\n"
    doctor = invoke(next(v for v in lines if v == "specify pack doctor --json"), tmp_path)
    assert doctor["status"] == "ok" and doctor["mode"] == "codex-skill"
    assert doctor["runtime_version"] == get_speckit_version()
    context = invoke(next(v for v in lines if v == "specify context --json"), tmp_path)
    assert context["status"] == "ok" and context["resources"]
    assert "$speckit 修复登录失败" in read(guide)


def test_documented_skill_upgrade_and_customization_protection(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    packs.initialize(tmp_path)
    text = read("docs/agent-setup.md").split("### 已有 2.0 项目：", 1)[1].split("## 4.", 1)[0]
    lines = cli_lines(text)
    assert len(lines) == 2 and all("--source" not in v and "--force" not in v for v in lines)
    before = snapshot(tmp_path)
    assert invoke(lines[0], tmp_path)["status"] == "planned"
    assert snapshot(tmp_path) == before
    assert invoke(lines[1], tmp_path)["status"] == "ok"
    skill = tmp_path / ".agents/skills/speckit/SKILL.md"
    skill.write_text("User customized skill\n", encoding="utf-8")
    before = snapshot(tmp_path)
    result = CliRunner().invoke(app, shlex.split(lines[0].replace("$projectPath", "."))[1:])
    assert result.exit_code != 0 and json.loads(result.output)["status"] == "blocked"
    assert snapshot(tmp_path) == before


def test_legacy_contract_and_documented_readonly_migration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Protect the CLI default while docs explicitly select the recommended mode.
    mode = next(p for p in get_command(app).commands["init"].params if p.name == "mode")
    assert mode.default == "legacy"
    (tmp_path / ".specify").mkdir()
    (tmp_path / ".specify/workspace.yml").write_text("custom: true\n")
    (tmp_path / "AGENTS.md").write_text("<!-- SPECKIT START -->\nUser legacy rules\n")
    before = snapshot(tmp_path)
    line = next(v for v in cli_lines(read("docs/agent-setup.md")) if v.startswith("specify pack migration-plan"))
    plan = invoke(line, tmp_path)
    assert plan["writes"] == [] and snapshot(tmp_path) == before
    result = CliRunner().invoke(app, ["init", "--here", "--mode", "codex-skill", "--no-git", "--json"])
    assert result.exit_code != 0 and json.loads(result.output)["status"] == "blocked"
    assert snapshot(tmp_path) == before
    primary, compatibility = read("docs/agent-setup.md").split("## 6. legacy 兼容与迁移")
    assert "$speckit-specify" not in primary
    assert "--mode legacy" in compatibility and "$speckit-specify" in compatibility
    for name in ("README.md", "README.en.md"):
        assert "$speckit-specify" not in read(name)
        assert "--mode codex-skill" in read(name)
        assert "$speckit " in read(name)
    # The maintained guide may change; the selected CLI must remain a stable tag.
    assert "spec-kit/v2.0.0/docs/agent-setup.md" not in read("docs/releases/v2.0.0.md")


@pytest.mark.parametrize("name", DOCS)
def test_onboarding_relative_links_and_anchors(name):
    for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", read(name)):
        if "://" in target or target.startswith("mailto:"):
            continue
        path, _, anchor = target.partition("#")
        resolved = (ROOT / name).parent / path if path else ROOT / name
        assert resolved.exists(), (name, target)
        if anchor:
            headings = re.findall(r"^#+ (.+)$", resolved.read_text(encoding="utf-8"), re.M)
            slugs = [re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings]
            assert anchor in slugs, (name, target, slugs)
