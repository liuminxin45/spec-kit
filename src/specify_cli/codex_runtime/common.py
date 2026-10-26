"""Small deterministic primitives shared by the pack and task runtimes."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

import yaml


class RuntimeBlocked(ValueError):
    """An operation could not satisfy its declared contract."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: bytes | object) -> str:
    data = value if isinstance(value, bytes) else json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        raise RuntimeBlocked(f"Cannot read JSON {path}: {exc}") from exc


def read_object(path: Path) -> dict:
    value = read_json(path)
    if not isinstance(value, dict):
        raise RuntimeBlocked(f"Expected a JSON object: {path}")
    return value


def read_yaml(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError, yaml.YAMLError) as exc:
        raise RuntimeBlocked(f"Cannot read YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeBlocked(f"Expected an object: {path}")
    return value


def yaml_bytes(value: dict) -> bytes:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")


def inside(root: Path, relative: str, *, allow_root: bool = False) -> Path:
    root = root.resolve()
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise RuntimeBlocked("Expected a nonempty project-relative path")
    # Backslashes are separators even when validating a Windows pack on Unix.
    normalized = relative.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
        raise RuntimeBlocked(f"Unsafe relative path: {relative}")
    path = (root / normalized).resolve()
    if not path.is_relative_to(root) or (path == root and not allow_root):
        raise RuntimeBlocked(f"Path escapes its owner: {relative}")
    current = root
    for part in Path(normalized).parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise RuntimeBlocked(f"Linked paths are not managed: {relative}")
    return path


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if os.name != "nt" or attempt == 4:
                    raise
                time.sleep(0.025 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def mutex(root: Path, name: str = "runtime", timeout: float = 5):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", name):
        raise RuntimeBlocked("Invalid operation lock name")
    folder = inside(root, ".specify/locks")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.lock"
    token = uuid.uuid4().hex
    end = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"token": token, "pid": os.getpid(), "created_at": now()}, handle)
            break
        except FileExistsError:
            if time.monotonic() >= end:
                raise RuntimeBlocked(f"Operation is locked; inspect the owner before recovery: {path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if read_json(path, {}).get("token") == token:
            path.unlink(missing_ok=True)


def transaction(root: Path, changes: dict[str, bytes | None]) -> str:
    """Publish a preflighted write set; restore written files on failure."""
    txid = uuid.uuid4().hex
    txroot = inside(root, f".specify/transactions/{txid}")
    txroot.mkdir(parents=True)
    before: dict[str, bytes | None] = {}
    paths: dict[str, Path] = {}
    effective = {}
    for relative, data in changes.items():
        path = inside(root, relative)
        if path.exists() and not path.is_file():
            raise RuntimeBlocked(f"Managed destination is not a file: {relative}")
        old = path.read_bytes() if path.exists() else None
        if data == old:
            continue
        i = len(before)
        paths[relative] = path
        before[relative] = old
        effective[relative] = data
        if before[relative] is not None:
            atomic_write(txroot / f"{i}.before", before[relative])
    changes = effective
    journal = {"id": txid, "status": "prepared", "files": list(changes),
               "existed": [before[key] is not None for key in changes],
               "before": {key: digest(data) if data is not None else None for key, data in before.items()},
               "after": {key: digest(data) if data is not None else None for key, data in changes.items()}}
    atomic_write(txroot / "transaction.json", json_bytes(journal))
    written: list[str] = []
    try:
        for relative, data in changes.items():
            written.append(relative)
            if data is None:
                paths[relative].unlink(missing_ok=True)
            else:
                atomic_write(paths[relative], data)
        journal["status"] = "committed"
        atomic_write(txroot / "transaction.json", json_bytes(journal))
    except BaseException:
        errors = []
        for relative in reversed(written):
            try:
                data = before[relative]
                if data is None:
                    paths[relative].unlink(missing_ok=True)
                else:
                    atomic_write(paths[relative], data)
            except OSError as exc:
                errors.append(f"{relative}: {exc}")
        journal.update(status="recovery-required" if errors else "rolled-back", errors=errors)
        atomic_write(txroot / "transaction.json", json_bytes(journal))
        raise
    return txid


def recover_transaction(root: Path, identity: str, *, apply: bool = False) -> dict:
    if not re.fullmatch(r"[a-f0-9]{32}", identity):
        raise RuntimeBlocked("Invalid transaction id")
    with mutex(root, "packs"):
        folder = inside(root, ".specify/transactions/" + identity)
        journal = read_json(folder / "transaction.json", {})
        if journal.get("status") not in {"prepared", "recovery-required"}:
            raise RuntimeBlocked("Only an unfinished transaction can be recovered")
        restores = {}
        for i, relative in enumerate(journal["files"]):
            path = inside(root, relative)
            current = digest(path.read_bytes()) if path.is_file() else None
            before = journal.get("before", {}).get(relative)
            after = journal.get("after", {}).get(relative)
            if current not in {before, after} or (path.exists() and not path.is_file()):
                raise RuntimeBlocked("Subsequent user change preserved: " + relative)
            backup = (folder / f"{i}.before").read_bytes() if journal["existed"][i] else None
            if (digest(backup) if backup is not None else None) != before:
                raise RuntimeBlocked("Transaction backup integrity mismatch")
            restores[relative] = backup
        if apply:
            for relative, data in restores.items():
                if data is None:
                    inside(root, relative).unlink(missing_ok=True)
                else:
                    atomic_write(inside(root, relative), data)
            journal.update(status="rolled-back", recovered_at=now())
            atomic_write(folder / "transaction.json", json_bytes(journal))
        return {"status": "ok" if apply else "planned", "transaction": identity, "restored_files": list(restores)}


IGNORED = {".git", "__pycache__", ".pytest_cache", "node_modules", ".speckit-release.json"}


def tree_files(root: Path) -> dict[str, bytes]:
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in IGNORED for part in relative.parts):
            continue
        safe = inside(root, relative.as_posix())
        if safe.is_file():
            result[relative.as_posix()] = safe.read_bytes()
    return result


def tree_digest(root: Path) -> str:
    return digest({name: digest(data) for name, data in tree_files(root).items()})
