"""Integration registry for the supported Spec Kit coding assistant.

This Spec Kit distribution is intentionally Codex-only. Keeping the registry small
prevents init/install flows, generated context, and tests from drifting back
toward multi-agent compatibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import IntegrationBase

# Maps integration key → IntegrationBase instance.
# Populated by later stages as integrations are migrated.
INTEGRATION_REGISTRY: dict[str, IntegrationBase] = {}


def _register(integration: IntegrationBase) -> None:
    """Register an integration instance in the global registry.

    Raises ``ValueError`` for falsy keys and ``KeyError`` for duplicates.
    """
    key = integration.key
    if not key:
        raise ValueError("Cannot register integration with an empty key.")
    if key in INTEGRATION_REGISTRY:
        raise KeyError(f"Integration with key {key!r} is already registered.")
    INTEGRATION_REGISTRY[key] = integration


def get_integration(key: str) -> IntegrationBase | None:
    """Return the integration for *key*, or ``None`` if not registered."""
    return INTEGRATION_REGISTRY.get(key)


# -- Register built-in integrations --------------------------------------


def _register_builtins() -> None:
    """Register the only built-in integration."""
    from .codex import CodexIntegration

    _register(CodexIntegration())


_register_builtins()
