"""Per-group §46 method groups for the NerveCenter SDK.

Each group exposes the canonical paths currently served by the backend
(see ``backend/api/app.py`` and ``backend/api/endpoints/``):

- collections: ``GET /api/<group>`` (list) and ``GET /api/<group>/<id>``
- plus the group-specific POST paths defined by the §46/§47 contract
  (``POST /api/context/ask``, ``POST /api/incidents/investigate``,
  ``POST /api/agents/pause``, ``POST /api/changes/stop-mutations``) —
  the backend does not implement those POST routes yet; see
  ``cli/CONTRACT_GAP_NOTES.md``.
"""
from __future__ import annotations

from typing import Any

__all__ = [
    "Agents",
    "Approvals",
    "Changes",
    "Claims",
    "Clients",
    "Compute",
    "Context",
    "Entities",
    "Events",
    "Evidence",
    "Goals",
    "Incidents",
    "Models",
    "Relationships",
    "Routes",
    "Runs",
    "Search",
    "Tasks",
]


class _Group:
    """Base class for a §46 API group."""

    prefix: str = ""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def list(self, **params: Any) -> Any:
        """GET /api/<prefix> (optionally with query params).

        Returns the unwrapped ``data`` list for the standard ``ListResponse``
        envelope (``{"data": [...], "meta": {...}}``), or the raw body when
        the endpoint does not use the envelope.
        """
        clean = {k: v for k, v in params.items() if v is not None}
        raw = await self._client.get(f"/api/{self.prefix}", params=clean or None)
        if isinstance(raw, dict) and "data" in raw and "meta" in raw:
            return raw["data"]
        return raw

    async def get(self, item_id: str) -> Any:
        """GET /api/<prefix>/<id>."""
        return await self._client.get(f"/api/{self.prefix}/{item_id}")


class Events(_Group):
    prefix = "events"


class Entities(_Group):
    prefix = "entities"


class Relationships(_Group):
    prefix = "relationships"


class Evidence(_Group):
    prefix = "evidence"


class Claims(_Group):
    prefix = "claims"


class Search(_Group):
    prefix = "search"


class Goals(_Group):
    prefix = "goals"


class Tasks(_Group):
    prefix = "tasks"


class Agents(_Group):
    prefix = "agents"

    async def pause(self) -> Any:
        """POST /api/agents/pause (pause all running agents; §47)."""
        return await self._client.post("/api/agents/pause", json_body={})


class Runs(_Group):
    prefix = "runs"


class Incidents(_Group):
    prefix = "incidents"

    async def investigate(self, entity: str) -> Any:
        """POST /api/incidents/investigate (start an investigation; §47)."""
        return await self._client.post(
            "/api/incidents/investigate", json_body={"entity": entity}
        )


class Models(_Group):
    prefix = "models"


class Compute(_Group):
    prefix = "compute"


class Routes(_Group):
    prefix = "routes"


class Changes(_Group):
    prefix = "changes"

    async def stop_mutations(self) -> Any:
        """POST /api/changes/stop-mutations (stop mutations; §47)."""
        return await self._client.post("/api/changes/stop-mutations", json_body={})


class Approvals(_Group):
    prefix = "approvals"


class Clients(_Group):
    prefix = "clients"


class Context(_Group):
    prefix = "context"

    async def ask(self, question: str, **params: Any) -> Any:
        """POST /api/context/ask (ask the system; §47)."""
        clean = {k: v for k, v in params.items() if v is not None}
        return await self._client.post(
            "/api/context/ask", json_body={"question": question, **clean}
        )
