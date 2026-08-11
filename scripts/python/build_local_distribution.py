#!/usr/bin/env python3
"""Build a local Spec Kit wheel with optional, caller-selected knowledge packs."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import shutil
import sys
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def wheel_hash(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return "sha256=" + digest.decode("ascii")


def zip_write(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name.replace("\\", "/"), ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


def collect_tree(root: Path, destination: str) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    if root.is_file():
        result[destination.replace("\\", "/")] = root.read_bytes()
        return result
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(root).as_posix()
        result[f"{destination.rstrip('/')}/{relative}"] = path.read_bytes()
    return result


def build_wheel(repo_root: Path, wheel_dir: Path) -> tuple[Path, dict[str, object]]:
    config = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = config["project"]
    name = str(project["name"])
    version = str(project["version"])
    normalized = name.replace("-", "_")
    dist_info = f"{normalized}-{version}.dist-info"
    wheel_path = wheel_dir / f"{normalized}-{version}-py3-none-any.whl"

    files: dict[str, bytes] = collect_tree(repo_root / "src" / "specify_cli", "specify_cli")
    force_include = config["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    for source, destination in force_include.items():
        files.update(collect_tree(repo_root / source, str(destination)))

    metadata = [
        "Metadata-Version: 2.3",
        f"Name: {name}",
        f"Version: {version}",
        f"Summary: {project.get('description', '')}",
        f"Requires-Python: {project.get('requires-python', '')}",
    ]
    metadata.extend(f"Requires-Dist: {dependency}" for dependency in project.get("dependencies", []))
    metadata.append("")
    files[f"{dist_info}/METADATA"] = "\n".join(metadata).encode("utf-8")
    files[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\n"
        "Generator: spec-kit-local-distribution\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    ).encode("utf-8")
    entry_points = project.get("scripts", {})
    files[f"{dist_info}/entry_points.txt"] = (
        "[console_scripts]\n" + "".join(f"{key} = {value}\n" for key, value in entry_points.items())
    ).encode("utf-8")
    license_path = repo_root / "LICENSE"
    if license_path.is_file():
        files[f"{dist_info}/licenses/LICENSE"] = license_path.read_bytes()

    record_path = f"{dist_info}/RECORD"
    record_buffer = io.StringIO(newline="")
    writer = csv.writer(record_buffer, lineterminator="\n")
    for path, data in sorted(files.items()):
        writer.writerow([path, wheel_hash(data), len(data)])
    writer.writerow([record_path, "", ""])
    files[record_path] = record_buffer.getvalue().encode("utf-8")

    wheel_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel_path, "w") as archive:
        for path, data in sorted(files.items()):
            zip_write(archive, path, data)
    return wheel_path, {"name": name, "version": version, "file_count": len(files)}


def read_pack_info(pack_root: Path) -> dict[str, str]:
    manifest = pack_root / "knowledge-pack.yml"
    if not manifest.is_file():
        raise ValueError(f"knowledge-pack.yml not found: {pack_root}")
    values: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.startswith(("id:", "version:", "title:", "kind:", "description:")):
            key, value = line.split(":", 1)
            values[key] = value.strip().strip('"').strip("'")
    if not values.get("id") or not values.get("version"):
        raise ValueError(f"knowledge pack id/version missing: {pack_root}")
    return values


def archive_directory(source: Path, destination: Path, top_level: str) -> None:
    with zipfile.ZipFile(destination, "w") as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                zip_write(archive, f"{top_level}/{path.relative_to(source).as_posix()}", path.read_bytes())


def file_checksums(root: Path) -> list[dict[str, object]]:
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.json":
            data = path.read_bytes()
            entries.append(
                {"path": path.relative_to(root).as_posix(), "sha256": sha256_bytes(data), "size": len(data)}
            )
    return entries


def build_bundle(args: argparse.Namespace) -> dict[str, object]:
    repo_root = Path(args.repo_root).resolve()
    workspace_root = Path(args.workspace_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    wheel_path, spec_info = build_wheel(repo_root, output_dir / "spec-kit")
    pack_dir = output_dir / "knowledge-packs"
    archive_dir = output_dir / "knowledge-pack-archives"
    pack_dir.mkdir()
    archive_dir.mkdir()
    packs = []
    for pack_name in args.knowledge_pack:
        source = workspace_root / ".specify" / "knowledge" / "exports" / pack_name
        info = read_pack_info(source)
        destination = pack_dir / info["id"]
        shutil.copytree(source, destination)
        archive = archive_dir / f"{info['id']}-{info['version']}.zip"
        archive_directory(destination, archive, info["id"])
        packs.append(
            {
                "id": info["id"],
                "version": info["version"],
                "title": info.get("title", info["id"]),
                "kind": info.get("kind", "knowledge-pack"),
                "description": info.get("description", ""),
                "directory": destination.relative_to(output_dir).as_posix(),
                "archive": archive.relative_to(output_dir).as_posix(),
            }
        )

    shutil.copy2(repo_root / "docs" / "local-install-and-knowledge-mount.md", output_dir / "INSTALL-AI.md")
    shutil.copy2(repo_root / "scripts" / "powershell" / "install-local-bundle.ps1", output_dir / "Install-Local.ps1")
    manifest = {
        "schema_version": "1.0",
        "artifact_kind": "spec-kit-local-install-bundle",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "spec_kit": {
            **spec_info,
            "wheel": wheel_path.relative_to(output_dir).as_posix(),
        },
        "knowledge_packs": packs,
        "default_compose_order": [pack["id"] for pack in packs],
        "promotion_performed": False,
    }
    (output_dir / "bundle-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    checksums = file_checksums(output_dir)
    (output_dir / "SHA256SUMS.json").write_text(
        json.dumps(checksums, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    bundle_zip = output_dir.parent / f"{output_dir.name}.zip"
    archive_directory(output_dir, bundle_zip, output_dir.name)
    return {
        "status": "ok",
        "facts": {
            "output_dir": str(output_dir),
            "bundle_zip": str(bundle_zip),
            "bundle_zip_sha256": sha256_bytes(bundle_zip.read_bytes()),
            "wheel": str(wheel_path),
            "wheel_sha256": sha256_bytes(wheel_path.read_bytes()),
            "knowledge_packs": packs,
            "checksum_count": len(checksums),
        },
        "blockers": [],
        "unknowns": [],
        "hints": ["Extract the bundle and read INSTALL-AI.md before installation."],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--knowledge-pack", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return args


def main() -> int:
    args = parse_args()
    try:
        result = build_bundle(args)
    except Exception as exc:
        result = {
            "status": "blocked",
            "facts": {},
            "blockers": [str(exc)],
            "unknowns": [],
            "hints": [],
        }
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
