"""Canonical resource registry (NC-SPEC-2026-010 Phase 2, C2).

This package owns the registry *service* over the C1 canonical-platform ORM
rows and frozen contracts:

- :class:`RegistryService` — the async service layer (connector instance
  registration, at-least-once reconciliation, explicit-deletion tombstones,
  aliases, relations, sync health). See :mod:`backend.registry.service`.
- DTOs — :class:`Sighting`, :class:`ReconcileOutcome`,
  :class:`RegistryInstanceView`.
- Errors — :class:`RegistryError` and its subclasses.
- :func:`mint_resource_id` — deterministic ``res_`` + Crockford platform id
  derivation from a canonical ``nc://`` URI.

A later router (outside this package) maps the public async methods 1:1 onto
``/api/registry/*`` endpoints.
"""

from .service import (
    RegistryConnectorNotFound,
    RegistryError,
    RegistryInstanceView,
    RegistryResourceNotFound,
    RegistryService,
    RegistryUriError,
    ReconcileOutcome,
    Sighting,
    mint_resource_id,
)

__all__ = [
    "RegistryService",
    "RegistryError",
    "RegistryUriError",
    "RegistryResourceNotFound",
    "RegistryConnectorNotFound",
    "Sighting",
    "ReconcileOutcome",
    "RegistryInstanceView",
    "mint_resource_id",
]
