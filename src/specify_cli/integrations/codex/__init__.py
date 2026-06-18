"""Codex CLI integration — skills-based agent.

Codex discovers only the entry skill under ``.agents/skills``. Full Spec Kit
stage skills live under ``.agents/spec-kit/skills`` and are loaded on demand.
"""

from __future__ import annotations

from pathlib import Path

from ..base import IntegrationOption, SkillsIntegration


class CodexIntegration(SkillsIntegration):
    """Integration for OpenAI Codex CLI."""

    key = "codex"
    config = {
        "name": "Codex CLI",
        "folder": ".agents/",
        "commands_subdir": "skills",
        "internal_skills_subdir": "spec-kit/skills",
        "exposed_skill_names": ["speckit-specify"],
        "install_url": "https://github.com/openai/codex",
        "requires_cli": True,
    }
    registrar_config = {
        "dir": ".agents/skills",
        "format": "markdown",
        "args": "$ARGUMENTS",
        "extension": "/SKILL.md",
    }
    context_file = "AGENTS.md"
    multi_install_safe = True

    def build_exec_args(
        self,
        prompt: str,
        *,
        model: str | None = None,
        output_json: bool = True,
    ) -> list[str] | None:
        # Codex uses ``codex exec "prompt"`` for non-interactive mode.
        # Workflow automation must also work in freshly initialized
        # ``--no-git`` projects and must be able to write Spec Kit artifacts.
        args: list[str] = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
        ]
        if model:
            args.extend(["--model", model])
        if output_json:
            args.append("--json")
        args.append(prompt)
        return args

    def build_command_invocation(self, command_name: str, args: str = "") -> str:
        """Build a workflow-runner prompt for a Spec Kit stage.

        Only ``speckit-specify`` is exposed for native Codex discovery. The
        workflow runner still needs to execute hidden stage skills one at a
        time, so it asks Codex to read the exact SKILL.md file for the selected
        stage instead of relying on slash-command discovery.
        """
        stem = command_name
        if stem.startswith("speckit."):
            stem = stem[len("speckit."):]
        if "." in stem:
            return super().build_command_invocation(command_name, args)

        skill_name = f"speckit-{stem.replace('_', '-')}"
        folder = self.config.get("folder", ".agents/") if self.config else ".agents/"
        internal_subdir = (
            self.config.get("internal_skills_subdir", "spec-kit/skills")
            if self.config
            else "spec-kit/skills"
        )
        if skill_name in self.exposed_skill_names():
            skill_path = Path(str(folder)) / "skills" / skill_name / "SKILL.md"
        else:
            skill_path = Path(str(folder)) / str(internal_subdir) / skill_name / "SKILL.md"

        stage_args = " ".join(args.split())
        if not stage_args:
            stage_args = "(none)"

        return (
            f"Run Spec Kit workflow stage `{skill_name}` under `specify workflow run`. "
            f"Read `{skill_path.as_posix()}` and follow that stage contract exactly. "
            "This invocation is scoped to the current YAML workflow step: complete "
            "this stage and any on-demand capability skills it requires, then return. "
            "Do not ask the human to type the next Spec Kit command, and do not run "
            "unrelated later workflow stages; the workflow runner will invoke the "
            "next YAML step. Stop only for blockers, required human decisions, "
            "high-risk confirmations, validation failures, or unavailable external "
            "dependencies. If you stop, report `blockers` and "
            f"`next_required_human_action`. Stage arguments: {stage_args}"
        )

    @classmethod
    def options(cls) -> list[IntegrationOption]:
        return [
            IntegrationOption(
                "--skills",
                is_flag=True,
                default=True,
                help="Install as agent skills (default for Codex)",
            ),
        ]
