"""Source-backed authoring packs, explicit legacy import and reviewed local releases."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from .common import (RuntimeBlocked, digest, inside, json_bytes, mutex, now,
                     read_json, read_yaml, transaction, tree_digest, tree_files, yaml_bytes)
from . import packs


SKIP = {".git", ".specify", ".agents", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache"}
MANIFESTS = {"package.json", "pyproject.toml", "Cargo.toml", "go.mod", "CMakeLists.txt", "Makefile", "pom.xml"}


def _scan(root: Path) -> list[str]:
    found = []
    for folder, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(d for d in directories if d not in SKIP and not (Path(folder) / d).is_symlink())
        for name in sorted(files):
            path = Path(folder) / name
            if path.is_symlink() or name.startswith(".env") or any(s in name.lower() for s in ["credential", "private-key"]):
                continue
            found.append(path.relative_to(root).as_posix())
            if len(found) > 10000:
                raise RuntimeBlocked("Repository map scan exceeds 10000 files; choose a component root")
    return found


def _publish_new(root: Path, output: str, files: dict[str, bytes]) -> Path:
    destination = inside(root, output)
    if destination.exists():
        raise RuntimeBlocked("Authoring output exists and was preserved: " + output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".speckit-author-", dir=destination.parent))
    try:
        for name, data in files.items():
            path = inside(temporary, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        packs.validate_pack(temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists() and temporary.resolve().is_relative_to(destination.parent.resolve()) and temporary.name.startswith(".speckit-author-"):
            shutil.rmtree(temporary)
    return destination


def _manifest(identity: str, description: str, contents: list[dict]) -> dict:
    if not packs.PACK_ID.fullmatch(identity):
        raise RuntimeBlocked("Use a namespaced owner/name identity")
    return {"schema_version": "2.0", "id": identity, "version": "0.1.0", "layer": "project",
            "description": description, "contents": contents}


def bootstrap(root: Path, identity: str, output: str) -> dict:
    names = _scan(root)
    output_path = inside(root, output)
    names = [name for name in names if not (root / name).is_relative_to(output_path)]
    manifests = [name for name in names if Path(name).name in MANIFESTS or Path(name).suffix in {".sln", ".csproj"}]
    sources = [{"path": name, "sha256": digest(inside(root, name).read_bytes())} for name in manifests]
    commands = []
    for name in manifests:
        if Path(name).name == "package.json":
            package = read_json(inside(root, name))
            for key, value in package.get("scripts", {}).items():
                commands.append({"manifest": name, "script": key, "declared_command": value,
                                 "verification": "declared-only; not executed"})
    top = sorted({name.split("/")[0] for name in names})
    map_text = "# Repository map (generated candidate)\n\n" + "\n".join("- " + name for name in top)
    map_text += "\n\n## Build and dependency manifests\n\n" + "\n".join("- " + name for name in manifests)
    map_text += ("\n\n## Unknowns requiring project review\n\n"
                 "- Component ownership and runtime/process boundaries\n- Verified run/debug commands and prerequisites\n"
                 "- UI/UX design sources and approved interaction contracts\n- Device/external-system availability\n"
                 "- Mandatory project requirements and their owners\n\n"
                 "This map reports files, not inferred architecture. Provenance is in provenance.json.\n")
    files = {
        "repository-map.md": map_text.encode(),
        "run-debug.json": json_bytes({"status": "candidate", "commands": commands, "unknowns": ["Verified invocation, environment and debug target"]}),
        "pitfalls.md": ("# Pitfall candidates\n\nNo proven pitfalls were inferred from filenames.\n\n"
                        "For each candidate record: symptom, applicable versions/scope, evidence, root cause, resolution, verification, review status.\n").encode(),
        "provenance.json": json_bytes({"generated_at": now(), "files_scanned": len(names), "sources": sources,
                                       "review_status": "candidate", "private_paths_excluded": True}),
    }
    contents = [{"id": "map", "type": "reference", "path": "repository-map.md", "description": "Source-backed repository map candidate"},
                {"id": "run-debug", "type": "reference", "path": "run-debug.json", "description": "Declared commands; runtime verification pending"},
                {"id": "pitfalls", "type": "reference", "path": "pitfalls.md", "description": "Reviewed lesson candidates"}]
    files["pack.yml"] = yaml_bytes(_manifest(identity, "Project knowledge generated from repository evidence; review before promotion.", contents))
    path = _publish_new(root, output, files)
    return {"status": "candidate", "path": output, "id": identity, "version": "0.1.0", "sha256": tree_digest(path),
            "files_scanned": len(names), "unknowns_require_review": True, "automatically_installed": False}


def import_legacy(root: Path, source: str, identity: str, output: str) -> dict:
    directory = inside(root, source)
    if not directory.is_dir():
        raise RuntimeBlocked("Legacy knowledge directory is missing")
    copied, contents, provenance = {}, [], []
    for name, data in tree_files(directory).items():
        if Path(name).suffix.lower() not in {".md", ".txt", ".yml", ".yaml", ".json"}:
            continue
        if sum(map(len, copied.values())) + len(data) > 8 * 1024 * 1024:
            raise RuntimeBlocked("Legacy import exceeds 8 MiB; choose a smaller source")
        destination = "legacy/" + name
        copied[destination] = data
        rid = "ref-" + digest(name.encode())[:16]
        contents.append({"id": rid, "type": "reference", "path": destination,
                         "description": "Imported legacy reference; review scope, paths and freshness"})
        provenance.append({"source": f"{source}/{name}", "path": destination, "sha256": digest(data)})
    if not contents:
        raise RuntimeBlocked("No supported legacy reference files found")
    copied["pack.yml"] = yaml_bytes(_manifest(identity, "Imported legacy knowledge; not automatically promoted to policies.", contents))
    copied["provenance.json"] = json_bytes({"imported_at": now(), "sources": provenance, "review_status": "needs-review"})
    copied["review.md"] = ("# Import review\n\nCheck outdated paths, credentials, project scope, run/debug commands and conflicting requirements.\n"
                           "All imported material remains reference data. Select policies/checks explicitly after review.\n").encode()
    path = _publish_new(root, output, copied)
    return {"status": "candidate", "id": identity, "path": output, "references": len(contents), "sha256": tree_digest(path), "source_unchanged": True}


def release(root: Path, directory: str, bump: str, reason: str, review: dict) -> dict:
    path = inside(root, directory)
    if bump not in {"patch", "minor", "major"} or not reason.strip():
        raise RuntimeBlocked("Release needs patch/minor/major and a concrete reason")
    with mutex(root, "knowledge-release"):
        manifest = packs.validate_pack(path)
        before = tree_digest(path)
        if (review.get("status") != "passed" or review.get("origin") != "human" or
            not review.get("source_ref") or not review.get("quote") or review.get("content_sha256") != before):
            raise RuntimeBlocked("Release needs actual referenced human review of the current content fingerprint")
        base = re.sub(r"-.*$", "", manifest["version"])
        numbers = list(map(int, base.split(".")))
        position = {"major": 0, "minor": 1, "patch": 2}[bump]
        numbers[position] += 1
        for i in range(position + 1, 3):
            numbers[i] = 0
        version = ".".join(map(str, numbers))
        updated = deepcopy(manifest)
        updated["version"] = version
        # Derived gate/dependency metadata belongs in the lock, not the source manifest.
        for item in updated["contents"]:
            item.pop("gates", None)
        files = tree_files(path)
        files["pack.yml"] = yaml_bytes(updated)
        for item in updated["contents"]:
            if item["type"] == "workflow":
                definition = read_yaml(inside(path, item["path"]))
                definition["version"] = version
                files[item["path"]] = yaml_bytes(definition)
        history = files.get("CHANGELOG.md", b"# Changelog\n").decode("utf-8")
        files["CHANGELOG.md"] = (history.rstrip() + f"\n\n## {version}\n\n{reason}\n\nReviewed source: {before}\n").encode()
        fingerprint = digest({name: digest(data) for name, data in files.items()})
        marker = {"id": manifest["id"], "version": version, "sha256": fingerprint,
                  "reviewed_source_sha256": before, "review": review, "reason": reason, "released_at": now(),
                  "provenance_verification": "referenced human message; not independently attested"}
        relative = path.relative_to(root).as_posix()
        changes = {f"{relative}/{name}": data for name, data in files.items()}
        changes[f"{relative}/.speckit-release.json"] = json_bytes(marker)
        txid = transaction(root, changes)
        return {"status": "ok", **marker, "transaction": txid, "published_remote": False}
