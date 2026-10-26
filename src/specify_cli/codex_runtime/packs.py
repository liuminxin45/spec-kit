"""Versioned, namespaced resources; no package installation executes its code."""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

from packaging.version import Version, InvalidVersion

from .common import (
    RuntimeBlocked, atomic_write, digest, inside, json_bytes, mutex, now,
    read_json, read_yaml, transaction, tree_digest, tree_files, yaml_bytes,
)
from .._assets import _locate_core_pack, _repo_root, get_speckit_version


PACK_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*$")
RESOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TYPES = {"reference", "policy", "asset", "skill", "tool", "action", "mcp", "check", "workflow", "hook"}
FLAGS = {"changes_code", "changes_visible_ui", "changes_runtime", "publishes_remote"}
BUILTINS = {"builtin/request-contract", "builtin/validation-receipts", "builtin/ui-evidence",
            "builtin/criteria-review", "builtin/runtime-evidence"}
CONFIG = ".specify/config.yml"
LOCK = ".specify/packs.lock.json"
START, END = "<!-- SPECKIT CODEX START -->", "<!-- SPECKIT CODEX END -->"


def assets_root() -> Path:
    source = _repo_root() / "templates/codex-skill"
    if source.is_dir():
        return source
    core = _locate_core_pack()
    if core and (core / "codex-skill").is_dir():
        return core / "codex-skill"
    raise RuntimeBlocked("Codex Skill assets are missing; reinstall the CLI")


def semver(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?", value):
        raise RuntimeBlocked(f"Expected semantic version, got {value!r}")
    try:
        Version(value)
    except InvalidVersion as exc:
        raise RuntimeBlocked(str(exc)) from exc
    return value


def validate_workflow(data: dict, qualified: str, version: str) -> dict:
    if data.get("schema_version") != "2.0" or data.get("id") != qualified:
        raise RuntimeBlocked(f"Workflow identity/schema mismatch: {qualified}")
    if data.get("version", version) != version:
        raise RuntimeBlocked(f"Workflow version must match its release pack: {qualified}")
    phases = data.get("phases")
    if not isinstance(phases, list) or not phases or not all(isinstance(v, str) for v in phases):
        raise RuntimeBlocked(f"Workflow needs phases: {qualified}")
    if len(phases) != len(set(phases)) or not {"contract", "ai_accept"} <= set(phases):
        raise RuntimeBlocked("Workflow phases need distinct contract and ai_accept entries")
    if phases[0] != "contract" or phases[-1] != "ai_accept":
        raise RuntimeBlocked("Workflow phases must start at contract and finish at ai_accept; human acceptance is separate")
    seen = set()
    gates = data.get("gates", [])
    if not isinstance(gates, list):
        raise RuntimeBlocked("Workflow gates must be a list")
    for gate in gates:
        if not isinstance(gate, dict) or not RESOURCE_ID.fullmatch(str(gate.get("id", ""))):
            raise RuntimeBlocked(f"Invalid workflow gate: {qualified}")
        if gate["id"] in seen or gate.get("phase") not in phases:
            raise RuntimeBlocked(f"Duplicate gate or unknown phase: {qualified}")
        seen.add(gate["id"])
        if gate.get("kind") not in {"machine", "judgment"}:
            raise RuntimeBlocked("Gate kind must be machine or judgment")
        if not isinstance(gate.get("required", True), bool):
            raise RuntimeBlocked("Gate required must be boolean")
        if gate.get("when", "always") not in FLAGS | {"always"}:
            raise RuntimeBlocked(f"Unknown gate condition: {gate.get('when')}")
        check = gate.get("check", "")
        if not isinstance(check, str):
            raise RuntimeBlocked("Gate check must be a qualified resource ID")
        if check.startswith("builtin/") and check not in BUILTINS:
            raise RuntimeBlocked(f"Unknown builtin check: {check}")
        if check not in BUILTINS and "::" not in check:
            raise RuntimeBlocked(f"Expected qualified check resource: {check}")
    acceptance = data.get("human_acceptance", {})
    if not isinstance(acceptance, dict):
        raise RuntimeBlocked("human_acceptance must be an object")
    if not isinstance(data.get("read_only", False), bool):
        raise RuntimeBlocked("Workflow read_only must be boolean")
    if not isinstance(acceptance.get("required_for_close", True), bool):
        raise RuntimeBlocked("human_acceptance.required_for_close must be boolean")
    return {**data, "version": version}


def validate_pack(root: Path) -> dict:
    root = root.resolve()
    data = read_yaml(inside(root, "pack.yml"))
    if data.get("schema_version") != "2.0":
        raise RuntimeBlocked("Use a schema 2.0 pack, or import the legacy pack first")
    if not PACK_ID.fullmatch(str(data.get("id", ""))):
        raise RuntimeBlocked("Pack id must be a namespaced lowercase owner/name")
    if not isinstance(data.get("description"), str) or not data["description"].strip():
        raise RuntimeBlocked("Pack description is required")
    semver(data.get("version"))
    requirements = data.get("requires", [])
    contents = data.get("contents", [])
    if not isinstance(requirements, list) or not isinstance(contents, list) or not (contents or requirements):
        raise RuntimeBlocked("A pack needs contents or exact dependencies")
    for dep in requirements:
        if not isinstance(dep, dict) or not PACK_ID.fullmatch(str(dep.get("id", ""))):
            raise RuntimeBlocked("Invalid dependency identity")
        semver(dep.get("version"))
    seen = set()
    for item in contents:
        if not isinstance(item, dict) or not RESOURCE_ID.fullmatch(str(item.get("id", ""))):
            raise RuntimeBlocked("Invalid resource id")
        if item["id"] in seen or item.get("type") not in TYPES:
            raise RuntimeBlocked(f"Duplicate resource or unsupported type: {item['id']}")
        seen.add(item["id"])
        path = inside(root, item.get("path"))
        if not path.exists():
            raise RuntimeBlocked(f"Missing resource: {item['path']}")
        if item["type"] == "workflow":
            definition = validate_workflow(read_yaml(path), f"{data['id']}::{item['id']}", data["version"])
            item["gates"] = definition.get("gates", [])
        if item["type"] == "skill":
            text = path.read_text(encoding="utf-8-sig")
            match = re.match(r"\A---\s*\n(.*?)\n---", text, re.S)
            metadata = __import__("yaml").safe_load(match[1]) if match else None
            if not isinstance(metadata, dict) or not metadata.get("name") or not metadata.get("description"):
                raise RuntimeBlocked(f"Invalid Skill frontmatter: {item['path']}")
        if not isinstance(item.get("requires", []), list):
            raise RuntimeBlocked("Resource requires must be a list of qualified IDs")
        if item["type"] == "workflow":
            item["requires"] = list(dict.fromkeys([*item.get("requires", []),
                *(gate["check"] for gate in item["gates"] if gate["check"] not in BUILTINS)]))
        if item["type"] in {"check", "action"}:
            descriptor = read_yaml(path)
            if not isinstance(descriptor.get("argv"), list) or not descriptor["argv"] or not all(isinstance(v, str) for v in descriptor["argv"]):
                raise RuntimeBlocked(f"Executable resource needs an argv descriptor: {item['id']}")
        if item.get("scope") and not isinstance(item["scope"], list):
            raise RuntimeBlocked("Resource scope must be a list of relative glob patterns")
    tree_files(root)  # Also reject links and unsafe paths outside declared resources.
    return data


def config(root: Path) -> dict:
    path = inside(root, CONFIG)
    if not path.is_file():
        raise RuntimeBlocked("Initialize this project with specify init --mode codex-skill")
    result = read_yaml(path)
    if result.get("mode") != "codex-skill":
        raise RuntimeBlocked("This is not a Codex Skill mode project")
    return result


def is_project(root: Path | None) -> bool:
    if root is None or not (root / CONFIG).is_file():
        return False
    try:
        return read_yaml(root / CONFIG).get("mode") == "codex-skill"
    except RuntimeBlocked:
        return False


def locked(root: Path, *, verify: bool = True) -> dict:
    config(root)
    data = read_json(inside(root, LOCK))
    if not data or data.get("schema_version") != "2.0":
        raise RuntimeBlocked("Pack lock is missing or invalid")
    if verify:
        for journal in (root / ".specify/transactions").glob("*/transaction.json"):
            if read_json(journal, {}).get("status") in {"prepared", "recovery-required"}:
                raise RuntimeBlocked("Recover unfinished transaction before using this project: " + journal.parent.name)
        for entry in data.get("packs", []):
            path = inside(root, entry["path"])
            if not path.is_dir() or tree_digest(path) != entry["sha256"]:
                raise RuntimeBlocked(f"Installed pack content changed: {entry['id']}")
    return data


def resolve(entries: list[dict]) -> list[dict]:
    by_id = {}
    for entry in entries:
        if entry["id"] in by_id:
            raise RuntimeBlocked(f"Duplicate pack identity: {entry['id']}")
        by_id[entry["id"]] = entry
    done, visiting, result = set(), set(), []
    def visit(key):
        if key in visiting:
            raise RuntimeBlocked(f"Dependency cycle at {key}")
        if key in done:
            return
        visiting.add(key)
        for dep in by_id[key]["manifest"].get("requires", []):
            if dep["id"] not in by_id:
                raise RuntimeBlocked(f"Missing dependency {dep['id']}@{dep['version']}; supply its source explicitly")
            if by_id[dep["id"]]["version"] != dep["version"]:
                raise RuntimeBlocked(f"Dependency version conflict: {dep['id']}")
            if not by_id[dep["id"]].get("enabled", True):
                raise RuntimeBlocked(f"Required dependency is disabled: {dep['id']}")
            visit(dep["id"])
        visiting.remove(key)
        done.add(key)
        result.append(by_id[key])
    for key in sorted(by_id):
        visit(key)
    return result


def catalog(root: Path, lock: dict | None = None) -> dict[str, dict]:
    lock = locked(root) if lock is None else lock
    result = {}
    for entry in resolve(lock["packs"]):
        if not entry.get("enabled", True):
            continue
        for resource in entry["manifest"].get("contents", []):
            identity = f"{entry['id']}::{resource['id']}"
            result[identity] = {
                **resource, "id": identity, "pack_id": entry["id"], "version": entry["version"],
                "path": f"{entry['path']}/{resource['path']}", "pack_sha256": entry["sha256"],
                "pack_path": entry["path"],
                "description": resource.get("description", entry["manifest"]["description"]),
                "scope": resource.get("scope") or entry.get("scope", []),
                "layer": entry.get("layer", entry["manifest"].get("layer", "project")),
            }
    for item in result.values():
        for dep in item.get("requires", []):
            if dep not in result:
                raise RuntimeBlocked(f"Missing resource dependency {dep} for {item['id']}")
        if item["type"] == "workflow":
            # Cross-resource gate validation is deferred until the whole batch exists.
            # The definition is already validated at its source, before installation.
            for gate in item.get("gates", []):
                if gate["check"] not in BUILTINS and (gate["check"] not in result or result[gate["check"]]["type"] != "check"):
                    raise RuntimeBlocked(f"Unknown workflow check: {gate['check']}")
    return result


def compatibility(item: dict) -> dict:
    requirements = item.get("compatibility", {})
    system = platform.system().lower()
    problems = []
    if requirements.get("os") and system not in requirements["os"]:
        problems.append(f"Requires platform {requirements['os']}; current {system}")
    for executable in requirements.get("tools", []):
        if not shutil.which(executable):
            problems.append(f"Missing executable: {executable}")
    return {"status": "unsupported" if problems else "needs-connection-verification"
            if item["type"] in {"mcp", "hook"} else "supported", "reasons": problems}


def knowledge_status(root: Path, item: dict) -> dict:
    provenance = inside(root, item["pack_path"] + "/provenance.json")
    if not provenance.is_file():
        return {"status": "not-declared"}
    record = read_json(provenance, {})
    changed = []
    for source in record.get("sources", []):
        name = source.get("source", source.get("path"))
        try:
            path = inside(root, name)
            if not path.is_file() or digest(path.read_bytes()) != source.get("sha256"):
                changed.append(name)
        except RuntimeBlocked:
            changed.append(name)
    return {"status": "needs-revalidation" if changed else record.get("review_status", "unknown"),
            "changed_sources": changed}


def context(root: Path, *, selected: list[str] | None = None,
            files: list[str] | None = None, capabilities: list[str] | None = None) -> dict:
    resources = catalog(root)
    cfg = config(root)
    policies = cfg.get("required_resources", [])
    for policy in policies:
        if policy not in resources or resources[policy]["type"] != "policy":
            raise RuntimeBlocked(f"Required project policy is unavailable: {policy}")
    if selected is None:
        candidates, excluded = [], []
        for identity, item in resources.items():
            paths = item.get("scope", [])
            relevant = not paths or not files or any(fnmatch.fnmatch(f, pattern) for f in files for pattern in paths)
            tags = item.get("tags", [])
            matches = not capabilities or not tags or bool(set(capabilities) & set(tags))
            if identity in policies or (relevant and matches):
                candidates.append({**item, "compatibility_status": compatibility(item),
                                   "knowledge_status": knowledge_status(root, item),
                                   "required": identity in policies,
                                   "selection_reason": "project-policy" if identity in policies else "scope-and-capability-candidate"})
            else:
                excluded.append({"id": identity, "reason": "outside-requested-scope-or-capability"})
        return {"status": "ok", "mode": "discovery", "resources": candidates, "excluded": excluded,
                "note": "These are candidates; the agent chooses a workflow from project facts, not keyword routing."}
    order, visiting, done = [], set(), set()
    def load(identity):
        if identity in visiting:
            raise RuntimeBlocked(f"Resource dependency cycle: {identity}")
        if identity not in resources:
            raise RuntimeBlocked(f"Unknown resource: {identity}")
        if identity in done:
            return
        visiting.add(identity)
        for dep in resources[identity].get("requires", []):
            load(dep)
        visiting.remove(identity)
        done.add(identity)
        item = resources[identity]
        path = inside(root, item["path"])
        content = None
        if path.is_file() and item["type"] not in {"asset"}:
            try:
                content = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError as exc:
                raise RuntimeBlocked(f"Non-text resource must use asset type: {identity}") from exc
        order.append({**item, "content": content, "compatibility_status": compatibility(item),
                      "knowledge_status": knowledge_status(root, item),
                      "required": identity in policies})
    for identity in [*policies, *selected]:
        load(identity)
    return {"status": "ok", "mode": "selected", "resources": order}


def _agent_block() -> str:
    return (START + "\nFor AI Coding in this project, use the native $speckit entry Skill.\n"
            "Discover the relevant project resources with `specify context --json`; load only selected resources.\n"
            "Keep clarification provenance, workflow checks and source-bound evidence.\n"
            "Human feedback remains pending until the user actually supplies it.\n" + END + "\n")


def _outputs(root: Path, lock: dict, previous: dict) -> dict[str, bytes | None]:
    generated = {f".agents/skills/speckit/{name}": data
                 for name, data in tree_files(assets_root() / "skill").items()}
    generated[".specify/generated/catalog.json"] = json_bytes(list(catalog(root, lock).values()))
    old_managed = previous.get("managed", {})
    for relative, expected in old_managed.items():
        path = inside(root, relative)
        if path.exists() and digest(path.read_bytes()) != expected:
            raise RuntimeBlocked(f"Customized managed file preserved; resolve its diff first: {relative}")
    for relative in generated:
        path = inside(root, relative)
        if path.exists() and relative not in old_managed and path.read_bytes() != generated[relative]:
            raise RuntimeBlocked(f"Existing unowned file preserved: {relative}")
    lock["managed"] = {name: digest(data) for name, data in generated.items()}
    changes: dict[str, bytes | None] = {**generated}
    for relative in old_managed.keys() - generated.keys():
        changes[relative] = None
    agents = inside(root, "AGENTS.md")
    text = agents.read_text(encoding="utf-8-sig") if agents.exists() else ""
    if (START in text) != (END in text):
        raise RuntimeBlocked("Malformed Spec Kit managed region; preserve and repair AGENTS.md first")
    if START in text:
        start, end = text.index(START), text.index(END) + len(END)
        old_block = text[start:end] + "\n"
        if previous.get("agents_block_hash") and digest(old_block.encode()) != previous["agents_block_hash"]:
            raise RuntimeBlocked("Customized Spec Kit AGENTS region preserved")
        text = text[:start] + _agent_block().rstrip("\n") + text[end:]
    else:
        if "<!-- SPECKIT START -->" in text:
            raise RuntimeBlocked("Legacy managed instructions detected; inspect pack migration-plan before changing the project mode")
        text = text.rstrip() + ("\n\n" if text.strip() else "") + _agent_block()
    lock["agents_block_hash"] = digest(_agent_block().encode())
    changes["AGENTS.md"] = text.encode("utf-8")
    return changes


def _source(source: str, temporary: Path) -> tuple[Path, str]:
    if source.startswith("git+"):
        url, separator, revision = source[4:].rpartition("@")
        if not separator or not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
            raise RuntimeBlocked("Git pack sources must end in @<full-40-character-commit>")
        clone = temporary / digest(source.encode())[:16]
        empty = temporary / "empty-git-template"
        empty.mkdir(exist_ok=True)
        commands = [["git", "clone", "--no-checkout", f"--template={empty}", "--", url, str(clone)],
                    ["git", "-C", str(clone), "-c", f"core.hooksPath={empty}", "checkout", "--detach", revision]]
        for argv in commands:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=120)
            if result.returncode:
                raise RuntimeBlocked(f"Pinned Git source unavailable: {result.stderr.strip()}")
        return clone, source
    if source.startswith("builtin:"):
        name = source.removeprefix("builtin:")
        if name not in {"workflows", "knowledge"}:
            raise RuntimeBlocked("Unknown builtin pack")
        return assets_root() / "packs" / name, source
    path = Path(source).expanduser().resolve()
    if not path.is_dir():
        raise RuntimeBlocked(f"Pack directory is missing: {path}")
    return path, str(path)


def install(root: Path, sources: list[str], *, replace: bool = False,
            dry_run: bool = False, initial: bool = False) -> dict:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with mutex(root, "packs"):
        previous = read_json(inside(root, LOCK), {})
        if not initial:
            locked(root)
        elif previous:
            locked(root)
        cfg = read_yaml(inside(root, CONFIG)) if inside(root, CONFIG).exists() else {
            "schema_version": "2.0", "mode": "codex-skill", "required_resources": [], "bindings": {}}
        if cfg.get("mode") != "codex-skill":
            raise RuntimeBlocked("Existing project mode is preserved; inspect migration-plan")
        entries = {entry["id"]: entry for entry in previous.get("packs", [])}
        changes: dict[str, bytes | None] = {}
        seen = set()
        with tempfile.TemporaryDirectory(prefix="speckit-pack-source-") as temp:
            for source in sources:
                source_root, normalized = _source(source, Path(temp))
                manifest = validate_pack(source_root)
                release_marker = source_root / ".speckit-release.json"
                if release_marker.is_file() and read_json(release_marker).get("sha256") != tree_digest(source_root):
                    raise RuntimeBlocked("Released pack was modified; review and create a new version before installation")
                identity = manifest["id"]
                if identity in seen:
                    raise RuntimeBlocked(f"Duplicate install source for {identity}")
                seen.add(identity)
                sha = tree_digest(source_root)
                old = entries.get(identity)
                if old and old["sha256"] != sha:
                    if not replace:
                        raise RuntimeBlocked(f"Pack already installed; use pack update: {identity}")
                    if old["version"] == manifest["version"]:
                        raise RuntimeBlocked("Published pack identity/version is immutable; bump the version before update")
                    if Version(manifest["version"]) <= Version(old["version"]):
                        raise RuntimeBlocked("Pack updates must increase the version")
                destination = f".specify/packs/p-{digest(identity.encode())[:20]}/{manifest['version']}-{sha[:16]}"
                for name, data in tree_files(source_root).items():
                    changes[f"{destination}/{name}"] = data
                entries[identity] = {"id": identity, "version": manifest["version"], "sha256": sha,
                                     "source": normalized, "path": destination, "enabled": True,
                                     "scope": old.get("scope", []) if old else [], "manifest": manifest}
            ordered = resolve(list(entries.values()))
            lock = {"schema_version": "2.0", "runtime_version": get_speckit_version(),
                    "packs": ordered, "updated_at": now()}
            # Catalog construction uses only validated manifests, not copied content.
            changes.update(_outputs(root, lock, previous))
            cfg["schema_version"] = "2.0"
            changes[CONFIG] = yaml_bytes(cfg)
            changes[LOCK] = json_bytes(lock)
            ignore = inside(root, ".gitignore")
            existing = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
            additions = [v for v in [".specify/packs/", ".specify/transactions/", ".specify/locks/",
                                    ".specify.local.yml"] if v not in existing.splitlines()]
            if additions:
                changes[".gitignore"] = (existing.rstrip() + "\n" + "\n".join(additions) + "\n").encode()
            result = {"status": "planned" if dry_run else "ok", "packs": [e["id"] for e in ordered],
                      "changed_files": sorted(changes), "auto_run_scripts": False}
            if not dry_run:
                result["transaction"] = transaction(root, changes)
            return result


def initialize(root: Path, *, dry_run: bool = False) -> dict:
    if any((root / name).exists() for name in [".specify/spec-kit.lock.yml", ".specify/feature.json", ".specify/workspace.yml"]) and not (root / CONFIG).exists():
        raise RuntimeBlocked("Existing legacy project preserved; use pack migration-plan and an isolated trial first")
    return install(root, ["builtin:workflows", "builtin:knowledge"], initial=True, dry_run=dry_run)


def remove(root: Path, identity: str, *, dry_run: bool = False) -> dict:
    with mutex(root, "packs"):
        old = locked(root)
        if identity.startswith("speckit/"):
            raise RuntimeBlocked("Keep the bundled entry workflows; disable specific capabilities through project bindings")
        if any(value.startswith(identity + "::") for value in config(root).get("required_resources", [])):
            raise RuntimeBlocked("Unbind required policies before removing this pack")
        remaining = [entry for entry in old["packs"] if entry["id"] != identity]
        if len(remaining) == len(old["packs"]):
            raise RuntimeBlocked(f"Pack is not installed: {identity}")
        resolve(remaining)
        lock = {**old, "packs": remaining, "updated_at": now()}
        changes = _outputs(root, lock, old)
        changes[LOCK] = json_bytes(lock)
        if not dry_run:
            txid = transaction(root, changes)
        else:
            txid = None
        return {"status": "planned" if dry_run else "ok", "removed": identity,
                "retained_cached_content": True, "transaction": txid}


def doctor(root: Path) -> dict:
    blockers, warnings = [], []
    resources = []
    try:
        lock = locked(root)
        for relative, expected in lock.get("managed", {}).items():
            path = inside(root, relative)
            if not path.is_file() or digest(path.read_bytes()) != expected:
                warnings.append(f"Customized or missing managed file: {relative}")
        for item in catalog(root, lock).values():
            result = compatibility(item)
            resources.append({"id": item["id"], **result})
            if result["status"] != "supported":
                warnings.append(f"{item['id']}: {result['status']}")
            if knowledge_status(root, item)["status"] == "needs-revalidation":
                warnings.append(f"{item['id']}: knowledge source changed; review and release an updated pack")
        context(root, selected=[])
    except (RuntimeBlocked, OSError) as exc:
        blockers.append(str(exc))
    for path in (root / ".specify/transactions").glob("*/transaction.json"):
        if read_json(path, {}).get("status") in {"prepared", "recovery-required"}:
            blockers.append(f"Unfinished package transaction: {path.parent.name}")
    return {"status": "blocked" if blockers else "warning" if warnings else "ok",
            "mode": "codex-skill", "runtime_version": get_speckit_version(),
            "blockers": blockers, "warnings": warnings, "resources": resources}


def migration_plan(root: Path) -> dict:
    legacy_lock = root / ".specify/spec-kit.lock.yml"
    return {"status": "planned", "root": str(root),
            "legacy_version": read_yaml(legacy_lock).get("spec_kit", {}).get("version") if legacy_lock.exists() else None,
            "knowledge_root": "ai/knowledge" if (root / "ai/knowledge").exists() else None,
            "active_feature": (root / ".specify/feature.json").exists(),
            "preserve": ["AGENTS.md", "ai/knowledge", ".specify/feature.json", "specs", ".agents/skills"],
            "next": "Import legacy knowledge into a schema 2.0 pack, validate in an isolated project, then explicitly review project instruction migration.",
            "writes": []}


def bind(root: Path, identity: str, scopes: list[str], required: list[str], layer: str) -> dict:
    if layer not in {"personal", "organization", "project", "component", "task"}:
        raise RuntimeBlocked("Unsupported package layer")
    if any(not pattern or pattern.startswith(("/", "\\")) or ":" in pattern or ".." in pattern.replace("\\", "/").split("/") for pattern in scopes):
        raise RuntimeBlocked("Scopes must be relative glob patterns")
    with mutex(root, "packs"):
        old = locked(root)
        cfg = config(root)
        resources = catalog(root, old)
        if any(v not in resources or resources[v]["type"] != "policy" or resources[v]["pack_id"] != identity for v in required):
            raise RuntimeBlocked("Required bindings must name policies from this pack")
        lock = __import__("copy").deepcopy(old)
        entry = next((v for v in lock["packs"] if v["id"] == identity), None)
        if not entry:
            raise RuntimeBlocked("Pack is not installed")
        entry.update(scope=scopes, layer=layer)
        previous_required = set(cfg.setdefault("bindings", {}).get(identity, {}).get("required", []))
        cfg["bindings"][identity] = {"scope": scopes, "required": required, "layer": layer}
        cfg["required_resources"] = sorted((set(cfg.get("required_resources", [])) - previous_required) |
            {v for binding in cfg["bindings"].values() for v in binding.get("required", [])})
        changes = _outputs(root, lock, old)
        changes.update({CONFIG: yaml_bytes(cfg), LOCK: json_bytes(lock)})
        return {"status": "ok", "transaction": transaction(root, changes), "binding": cfg["bindings"][identity]}


def restore(root: Path, *, dry_run: bool = False) -> dict:
    """Rehydrate an absent cache without resolving a newer dependency or source."""
    with mutex(root, "packs"):
        lock = locked(root, verify=False)
        changes = {}
        with tempfile.TemporaryDirectory(prefix="speckit-restore-") as temporary:
            for entry in lock["packs"]:
                path = inside(root, entry["path"])
                if path.exists():
                    if tree_digest(path) != entry["sha256"]:
                        raise RuntimeBlocked("Modified cache preserved; inspect before restoring " + entry["id"])
                    continue
                source, _ = _source(entry["source"], Path(temporary))
                validate_pack(source)
                if tree_digest(source) != entry["sha256"]:
                    raise RuntimeBlocked("Locked source no longer matches " + entry["id"])
                changes.update({f"{entry['path']}/{name}": data for name, data in tree_files(source).items()})
        return {"status": "planned" if dry_run else "ok", "changed_files": sorted(changes),
                "transaction": transaction(root, changes) if changes and not dry_run else None}
