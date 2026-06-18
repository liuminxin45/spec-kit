"""
Agent Command Registrar for Spec Kit

Shared infrastructure for registering Spec Kit commands as Codex skills.
Used by both the extension system and the preset system to write command files
into the Codex skill directory in the correct format.
"""

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

import yaml


def _build_agent_configs() -> dict[str, Any]:
    """Derive CommandRegistrar.AGENT_CONFIGS from INTEGRATION_REGISTRY."""
    from specify_cli.integrations import INTEGRATION_REGISTRY

    configs: dict[str, dict[str, Any]] = {}
    for key, integration in INTEGRATION_REGISTRY.items():
        if integration.registrar_config:
            config = dict(integration.registrar_config)
            # Propagate invoke_separator from the integration class when the
            # registrar_config dict doesn't already declare it explicitly.
            # Codex sets invoke_separator="-" as a class attribute but omits
            # it from registrar_config, so without this it would fall back to "."
            # when register_commands() resolves __SPECKIT_COMMAND_*__ tokens.
            if "invoke_separator" not in config:
                config["invoke_separator"] = integration.invoke_separator
            configs[key] = config
    return configs


class CommandRegistrar:
    """Handles registration of commands with Codex.

    Supports writing command files in the Codex SKILL.md layout with correct
    argument placeholders.
    """

    # Derived from INTEGRATION_REGISTRY — single source of truth.
    # Populated lazily via _ensure_configs() on first use.
    AGENT_CONFIGS: dict[str, dict[str, Any]] = {}
    _configs_loaded: bool = False

    def __init__(self) -> None:
        self._ensure_configs()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._ensure_configs()

    @classmethod
    def _ensure_configs(cls) -> None:
        if not cls._configs_loaded:
            try:
                cls.AGENT_CONFIGS = _build_agent_configs()
                cls._configs_loaded = True
            except ImportError:
                pass  # Circular import during module init; retry on next access

    @staticmethod
    def parse_frontmatter(content: str) -> tuple[dict, str]:
        """Parse YAML frontmatter from Markdown content.

        Args:
            content: Markdown content with YAML frontmatter

        Returns:
            Tuple of (frontmatter_dict, body_content)
        """
        if not content.startswith("---"):
            return {}, content

        # Find second ---
        end_marker = content.find("---", 3)
        if end_marker == -1:
            return {}, content

        frontmatter_str = content[3:end_marker].strip()
        body = content[end_marker + 3 :].strip()

        try:
            frontmatter = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError:
            frontmatter = {}

        if not isinstance(frontmatter, dict):
            frontmatter = {}

        return frontmatter, body

    @staticmethod
    def render_frontmatter(fm: dict) -> str:
        """Render frontmatter dictionary as YAML.

        Args:
            fm: Frontmatter dictionary

        Returns:
            YAML-formatted frontmatter with delimiters
        """
        if not fm:
            return ""

        yaml_str = yaml.dump(
            fm, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        return f"---\n{yaml_str}---\n"

    def _adjust_script_paths(self, frontmatter: dict) -> dict:
        """Normalize script paths in frontmatter to generated project locations.

        Rewrites known repo-relative and top-level script paths under the
        ``scripts`` key (for example ``../../scripts/``,
        ``../../templates/``, ``../../memory/``, ``scripts/``, ``templates/``, and
        ``memory/``) to the ``.specify/...`` paths used in generated projects.

        Args:
            frontmatter: Frontmatter dictionary

        Returns:
            Modified frontmatter with normalized project paths
        """
        frontmatter = deepcopy(frontmatter)

        scripts = frontmatter.get("scripts")
        if isinstance(scripts, dict):
            for key, script_path in scripts.items():
                if isinstance(script_path, str):
                    scripts[key] = self.rewrite_project_relative_paths(script_path)
        return frontmatter

    @staticmethod
    def rewrite_project_relative_paths(text: str) -> str:
        """Rewrite repo-relative paths to their generated project locations."""
        if not isinstance(text, str) or not text:
            return text

        for old, new in (
            ("../../memory/", ".specify/memory/"),
            ("../../scripts/", ".specify/scripts/"),
            ("../../templates/", ".specify/templates/"),
        ):
            text = text.replace(old, new)

        # Only rewrite top-level style references so extension-local paths like
        # ".specify/extensions/<ext>/scripts/..." remain intact.
        text = re.sub(r'(^|[\s`"\'(])(?:\.?/)?memory/', r"\1.specify/memory/", text)
        text = re.sub(r'(^|[\s`"\'(])(?:\.?/)?scripts/', r"\1.specify/scripts/", text)
        text = re.sub(
            r'(^|[\s`"\'(])(?:\.?/)?templates/', r"\1.specify/templates/", text
        )

        return text.replace(".specify/.specify/", ".specify/").replace(
            ".specify.specify/", ".specify/"
        )

    def render_skill_command(
        self,
        agent_name: str,
        skill_name: str,
        frontmatter: dict,
        body: str,
        source_id: str,
        source_file: str,
        project_root: Path,
    ) -> str:
        """Render a command override as a SKILL.md file.

        SKILL-target agents should receive the same skills-oriented
        frontmatter shape used elsewhere in the project instead of the
        original command frontmatter.

        Technical debt note:
        Spec-kit currently has multiple SKILL.md generators (template packaging,
        init-time conversion, and extension/preset overrides). Keep the skill
        frontmatter keys aligned (name/description/compatibility/metadata, with
        metadata.author and metadata.source subkeys) to avoid drift across agents.
        """
        if not isinstance(frontmatter, dict):
            frontmatter = {}

        agent_config = self.AGENT_CONFIGS.get(agent_name, {})
        if agent_config.get("extension") == "/SKILL.md":
            body = self.resolve_skill_placeholders(
                agent_name, frontmatter, body, project_root
            )

        description = frontmatter.get(
            "description", f"Spec-kit workflow command: {skill_name}"
        )
        skill_frontmatter = self.build_skill_frontmatter(
            agent_name,
            skill_name,
            description,
            f"{source_id}:{source_file}",
        )
        return self.render_frontmatter(skill_frontmatter) + "\n" + body

    @staticmethod
    def build_skill_frontmatter(
        agent_name: str,
        skill_name: str,
        description: str,
        source: str,
    ) -> dict:
        """Build consistent SKILL.md frontmatter across all skill generators."""
        skill_frontmatter = {
            "name": skill_name,
            "description": description,
            "compatibility": "Requires spec-kit project structure with .specify/ directory",
            "metadata": {
                "author": "spec-kit",
                "source": source,
            },
        }
        return skill_frontmatter

    @staticmethod
    def resolve_skill_placeholders(
        agent_name: str, frontmatter: dict, body: str, project_root: Path
    ) -> str:
        """Resolve script placeholders for skills-backed agents."""
        try:
            from . import load_init_options
        except ImportError:
            return body

        if not isinstance(frontmatter, dict):
            frontmatter = {}

        scripts = frontmatter.get("scripts", {}) or {}
        if not isinstance(scripts, dict):
            scripts = {}

        init_opts = load_init_options(project_root)
        if not isinstance(init_opts, dict):
            init_opts = {}

        script_variant = init_opts.get("script")
        if script_variant != "ps":
            script_variant = "ps" if "ps" in scripts else None

        script_command = scripts.get(script_variant) if script_variant else None
        if script_command:
            script_command = script_command.replace("{ARGS}", "$ARGUMENTS")
            body = body.replace("{SCRIPT}", script_command)

        body = body.replace("{ARGS}", "$ARGUMENTS").replace("__AGENT__", agent_name)

        # Resolve __CONTEXT_FILE__ from init-options
        context_file = init_opts.get("context_file") or ""
        body = body.replace("__CONTEXT_FILE__", context_file)

        return CommandRegistrar.rewrite_project_relative_paths(body)

    def _convert_argument_placeholder(
        self, content: str, from_placeholder: str, to_placeholder: str
    ) -> str:
        """Convert argument placeholder format.

        Args:
            content: Command content
            from_placeholder: Source placeholder (e.g., "$ARGUMENTS")
            to_placeholder: Target placeholder (e.g., "{{args}}")

        Returns:
            Content with converted placeholders
        """
        return content.replace(from_placeholder, to_placeholder)

    @staticmethod
    def _compute_output_name(
        agent_name: str, cmd_name: str, agent_config: Dict[str, Any]
    ) -> str:
        """Compute the on-disk command or skill name for an agent."""
        if agent_config["extension"] != "/SKILL.md":
            return cmd_name

        short_name = cmd_name
        if short_name.startswith("speckit."):
            short_name = short_name[len("speckit.") :]
        short_name = short_name.replace(".", "-")

        return f"speckit-{short_name}"

    @staticmethod
    def _ensure_inside(candidate: Path, base: Path) -> None:
        """Validate that a write target stays within the expected base directory.

        Uses lexical normalization so traversal via ``..`` or absolute paths is
        rejected while intentionally symlinked sub-directories remain
        supported.

        Args:
            candidate: Path that will be written.
            base: Directory the write must remain within.

        Raises:
            ValueError: If the normalized candidate path escapes ``base``.
        """
        normalized = Path(os.path.normpath(candidate))
        base_normalized = Path(os.path.normpath(base))
        if not normalized.is_relative_to(base_normalized):
            raise ValueError(f"Output path {candidate!r} escapes directory {base!r}")

    def register_commands(
        self,
        agent_name: str,
        commands: List[Dict[str, Any]],
        source_id: str,
        source_dir: Path,
        project_root: Path,
        context_note: str = None,
        _resolved_dir: Path = None,
    ) -> List[str]:
        """Register commands for a specific agent.

        Args:
            agent_name: Agent name. Only ``codex`` is supported.
            commands: List of command info dicts with 'name', 'file', and optional 'aliases'
            source_id: Identifier of the source (extension or preset ID)
            source_dir: Directory containing command source files
            project_root: Path to project root
            context_note: Custom context comment for markdown output
            _resolved_dir: Pre-resolved command directory (internal use
                only — avoids a second ``_resolve_agent_dir`` call and
                duplicate deprecation warnings when invoked from
                ``register_commands_for_all_agents``).

        Returns:
            List of registered command names

        Raises:
            ValueError: If agent is not supported
        """
        self._ensure_configs()
        if agent_name not in self.AGENT_CONFIGS:
            raise ValueError(f"Unsupported agent: {agent_name}")

        agent_config = self.AGENT_CONFIGS[agent_name]
        if agent_config.get("extension") != "/SKILL.md":
            raise ValueError(
                f"Unsupported command target for Codex-only Spec Kit: {agent_name}"
            )

        commands_dir = _resolved_dir or self._resolve_agent_dir(
            agent_name, agent_config, project_root,
        )
        commands_dir.mkdir(parents=True, exist_ok=True)

        registered = []

        for cmd_info in commands:
            cmd_name = cmd_info["name"]
            cmd_file = cmd_info["file"]

            source_file = source_dir / cmd_file
            if not source_file.exists():
                continue

            content = source_file.read_text(encoding="utf-8")
            frontmatter, body = self.parse_frontmatter(content)

            if frontmatter.get("strategy") == "wrap":
                raise ValueError(
                    "Preset-style wrap strategy is not supported in the Codex-only Spec Kit build."
                )

            frontmatter = self._adjust_script_paths(frontmatter)

            for key in agent_config.get("strip_frontmatter_keys", []):
                frontmatter.pop(key, None)

            if agent_config.get("inject_name") and not frontmatter.get("name"):
                format_name = agent_config.get("format_name")
                frontmatter["name"] = format_name(cmd_name) if format_name else cmd_name

            body = self._convert_argument_placeholder(
                body, "$ARGUMENTS", agent_config["args"]
            )

            # Resolve __SPECKIT_COMMAND_*__ tokens using the agent's invoke separator.
            # The separator is sourced from agent_config (populated by _build_agent_configs,
            # which propagates each integration's invoke_separator class attribute).
            # Deferred import of IntegrationBase avoids a circular import at module load
            # (base.py itself imports CommandRegistrar lazily).
            from specify_cli.integrations.base import IntegrationBase  # noqa: PLC0415

            _sep = agent_config.get("invoke_separator", ".")
            body = IntegrationBase.resolve_command_refs(body, _sep)

            output_name = self._compute_output_name(agent_name, cmd_name, agent_config)

            output = self.render_skill_command(
                agent_name,
                output_name,
                frontmatter,
                body,
                source_id,
                cmd_file,
                project_root,
            )

            dest_file = commands_dir / f"{output_name}{agent_config['extension']}"
            self._ensure_inside(dest_file, commands_dir)
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            dest_file.write_text(output, encoding="utf-8")

            registered.append(cmd_name)

            for alias in cmd_info.get("aliases", []):
                alias_output_name = self._compute_output_name(
                    agent_name, alias, agent_config
                )

                if agent_config.get("inject_name"):
                    alias_frontmatter = deepcopy(frontmatter)
                    format_name = agent_config.get("format_name")
                    alias_frontmatter["name"] = (
                        format_name(alias) if format_name else alias
                    )
                    alias_output = self.render_skill_command(
                        agent_name,
                        alias_output_name,
                        alias_frontmatter,
                        body,
                        source_id,
                        cmd_file,
                        project_root,
                    )
                else:
                    alias_output = self.render_skill_command(
                        agent_name,
                        alias_output_name,
                        frontmatter,
                        body,
                        source_id,
                        cmd_file,
                        project_root,
                    )

                alias_file = (
                    commands_dir / f"{alias_output_name}{agent_config['extension']}"
                )
                self._ensure_inside(alias_file, commands_dir)
                alias_file.parent.mkdir(parents=True, exist_ok=True)
                alias_file.write_text(alias_output, encoding="utf-8")
                registered.append(alias)

        return registered

    @staticmethod
    def _resolve_agent_dir(
        agent_name: str,
        agent_config: dict[str, Any],
        project_root: Path,
    ) -> Path:
        """Return the agent command directory, falling back to legacy_dir.

        When the canonical directory (``agent_config["dir"]``) does not
        exist but a ``legacy_dir`` is configured and present on disk,
        returns the legacy path and emits a deprecation warning advising
        the user to upgrade.

        Integrations that do not declare ``legacy_dir`` get the canonical
        path unconditionally — no fallback, no warning.
        """
        agent_dir = project_root / agent_config["dir"]
        if not agent_dir.exists():
            legacy = agent_config.get("legacy_dir")
            if legacy:
                legacy_dir = project_root / legacy
                if legacy_dir.exists():
                    import warnings

                    warnings.warn(
                        f"Found legacy '{legacy}' directory for "
                        f"{agent_name}. Run 'specify integration "
                        f"upgrade {agent_name}' to migrate to "
                        f"'{agent_config['dir']}'.",
                        stacklevel=3,
                    )
                    return legacy_dir
        return agent_dir

    def register_commands_for_all_agents(
        self,
        commands: List[Dict[str, Any]],
        source_id: str,
        source_dir: Path,
        project_root: Path,
        context_note: str = None,
    ) -> Dict[str, List[str]]:
        """Register commands for all detected Codex skill targets in the project.

        Args:
            commands: List of command info dicts
            source_id: Identifier of the source (extension or preset ID)
            source_dir: Directory containing command source files
            project_root: Path to project root
            context_note: Custom context comment for markdown output

        Returns:
            Dictionary mapping target names to list of registered commands
        """
        results = {}

        self._ensure_configs()
        for agent_name, agent_config in self.AGENT_CONFIGS.items():
            agent_dir = self._resolve_agent_dir(
                agent_name, agent_config, project_root,
            )

            if agent_dir.exists():
                try:
                    registered = self.register_commands(
                        agent_name,
                        commands,
                        source_id,
                        source_dir,
                        project_root,
                        context_note=context_note,
                        _resolved_dir=agent_dir,
                    )
                    if registered:
                        results[agent_name] = registered
                except ValueError:
                    continue

        return results

    def unregister_commands(
        self, registered_commands: Dict[str, List[str]], project_root: Path
    ) -> None:
        """Remove previously registered command files from Codex directories.

        When a ``legacy_dir`` is configured, files are removed from
        *both* the canonical and the legacy directory so that orphaned
        commands left behind after an ``integration upgrade`` are
        cleaned up as well.

        Args:
            registered_commands: Dict mapping target names to command name lists
            project_root: Path to project root
        """
        self._ensure_configs()
        for agent_name, cmd_names in registered_commands.items():
            if agent_name not in self.AGENT_CONFIGS:
                continue

            agent_config = self.AGENT_CONFIGS[agent_name]
            commands_dir = self._resolve_agent_dir(
                agent_name, agent_config, project_root,
            )

            # Collect all directories to clean: canonical (or resolved
            # legacy) plus the legacy dir if it exists separately.
            dirs_to_clean = [commands_dir]
            legacy = agent_config.get("legacy_dir")
            if legacy:
                legacy_dir = project_root / legacy
                if legacy_dir.exists() and legacy_dir != commands_dir:
                    dirs_to_clean.append(legacy_dir)

            for cmd_name in cmd_names:
                output_name = self._compute_output_name(
                    agent_name, cmd_name, agent_config
                )
                for target_dir in dirs_to_clean:
                    cmd_file = (
                        target_dir / f"{output_name}{agent_config['extension']}"
                    )
                    if cmd_file.exists():
                        cmd_file.unlink()
                        # For SKILL.md targets each command lives in its own
                        # subdirectory (e.g. .agents/skills/speckit-ext-cmd/
                        # SKILL.md).  Remove the parent dir when it becomes
                        # empty to avoid orphaned directories.
                        parent = cmd_file.parent
                        if parent != target_dir and parent.exists():
                            try:
                                parent.rmdir()
                            except OSError:
                                pass

# Populate AGENT_CONFIGS after class definition.
# Catches ImportError from circular imports during module loading;
# _configs_loaded stays False so the next explicit access retries.
try:
    CommandRegistrar._ensure_configs()
except ImportError:
    pass
