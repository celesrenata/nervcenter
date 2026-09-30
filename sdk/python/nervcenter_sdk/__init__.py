"""NerveCenter Python SDK (spec §29 correlation, §46 API surface).

A small async ``httpx`` client with one method per §46 group, a timeout,
exactly one retry on 5xx, and a ``Nerve-Trace-Id`` correlation header on
every request (auto-generated UUID unless the caller supplies one).

Usage (async)::

    import asyncio
    from nervcenter_sdk import NerveClient

    async def main() -> None:
        async with NerveClient(base_url="http://localhost:8310") as client:
            health = await client.get("/api/health")
            goals = await client.goals.list()
            print(health, goals)

    asyncio.run(main())

Usage (sync convenience wrapper)::

    from nervcenter_sdk import NerveSync

    with NerveSync() as client:
        print(client.health())
"""
from __future__ import annotations

from .client import (
    ApiError,
    ContractError,
    NerveClient,
    NerveSync,
    UnreachableError,
)
from .groups import (
    Agents,
    Approvals,
    Changes,
    Claims,
    Clients,
    Compute,
    Context,
    Entities,
    Events,
    Evidence,
    Goals,
    Incidents,
    Models,
    Relationships,
    Routes,
    Runs,
    Search,
    Tasks,
)

__all__ = [
    "NerveClient",
    "NerveSync",
    "ApiError",
    "ContractError",
    "UnreachableError",
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
