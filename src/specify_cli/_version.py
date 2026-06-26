"""Version checking and self-update commands for specify_cli.

The default build keeps self-check local and non-networked. The
``self_app`` Typer sub-command group is co-located here so all version-related
logic lives in one place.

Dependencies: stdlib + packaging + ._console only (no other internal imports
at module level, keeping this layer thin and circular-import-safe).
"""
from __future__ import annotations

import typer
from packaging.version import InvalidVersion, Version

from ._console import console

def _get_installed_version() -> str:
    """Return the installed specify-cli distribution version or 'unknown'.

    Uses importlib.metadata so the value reflects what was actually installed
    by pip/uv/pipx — not a value read from pyproject.toml. This is
    intentional for `specify self check`, which should reason about the
    installed distribution rather than a source-tree fallback. Callers must
    treat the sentinel string 'unknown' as an indeterminate value (see FR-020).
    """
    import importlib.metadata

    metadata_errors = [importlib.metadata.PackageNotFoundError]
    invalid_metadata_error = getattr(importlib.metadata, "InvalidMetadataError", None)
    if invalid_metadata_error is not None:
        metadata_errors.append(invalid_metadata_error)

    try:
        return importlib.metadata.version("specify-cli")
    except tuple(metadata_errors):
        return "unknown"


def _normalize_tag(tag: str) -> str:
    """Strip exactly one leading 'v' from a release tag.

    Returns the rest of the string unchanged. This handles the common
    'vX.Y.Z' tag convention in this repo; it MUST NOT strip more
    aggressively (e.g., two leading 'v's keeps one).
    """
    return tag[1:] if tag.startswith("v") else tag


def _is_newer(latest: str, current: str) -> bool:
    """Return True iff `latest` is strictly greater than `current` under PEP 440.

    Returns False whenever either side is 'unknown' or fails to parse; this
    keeps the comparison indeterminate (rather than crashing or falsely
    recommending a downgrade) on edge inputs.
    """
    if latest == "unknown" or current == "unknown":
        return False
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        return False


def _fetch_latest_release_tag() -> tuple[str | None, str | None]:
    """Return (tag, failure_category) without outbound network access."""
    return None, "remote version check disabled in this local build"


# ===== Self Commands =====

self_app = typer.Typer(
    name="self",
    help="Manage the specify CLI itself (read-only check and reserved upgrade command).",
    add_completion=False,
)


@self_app.command("check")
def self_check() -> None:
    """Report the installed specify-cli version. Read-only.

    This command does not modify your installation or contact remote services.
    The reserved (and currently non-destructive) `specify self upgrade` command
    is the name that a future release will use for actual self-upgrade — its
    behavior is not implemented in this release and is intentionally out of
    scope here. See `specify self upgrade --help` for its current status.
    """
    installed = _get_installed_version()
    tag, failure_reason = _fetch_latest_release_tag()

    if tag is None:
        assert failure_reason is not None
        console.print(f"Installed: {installed}")
        console.print(f"[yellow]Remote update check skipped:[/yellow] {failure_reason}")
        console.print("To reinstall from the team source, run from the workspace root:")
        console.print(r"  .\spec-kit\scripts\powershell\install.ps1")
        return

    latest_normalized = _normalize_tag(tag)

    if installed == "unknown":
        # FR-020: surface the latest release and the recovery action even
        # when the local distribution metadata is unavailable.
        console.print("Current version could not be determined.")
        console.print(f"Latest release: {latest_normalized}")
        console.print("\nTo reinstall:")
        console.print(r"  .\spec-kit\scripts\powershell\install.ps1")
        return

    if _is_newer(latest_normalized, installed):
        console.print(f"[green]Update available:[/green] {installed} → {latest_normalized}")
        console.print("\nTo upgrade:")
        console.print(r"  .\spec-kit\scripts\powershell\install.ps1")
        return

    # Installed is parseable AND is >= latest → "up to date" (FR-006).
    # Also reached when the tag is unparseable (InvalidVersion) → _is_newer
    # returns False, and the up-to-date branch is the safer default per
    # FR-004 / test T016.
    console.print(f"[green]Up to date:[/green] {installed}")


@self_app.command("upgrade")
def self_upgrade() -> None:
    """Reserved command surface for self-upgrade; not implemented in this release.

    This command is a documented non-destructive stub in this release: it
    performs no outbound network request, no install-method detection, and
    invokes no installer. It prints a three-line guidance message and exits 0.
    Actual self-upgrade is planned as follow-up work.

    Use `specify self check` today to see whether a newer release is available
    and to get a copy-pasteable reinstall command.
    """
    console.print("specify self upgrade is not implemented yet.")
    console.print("Run 'specify self check' to see whether a newer release is available.")
    console.print("Actual self-upgrade is planned as follow-up work.")
