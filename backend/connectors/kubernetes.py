from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from .base import (
    ConnectError,
    Connector,
    ConnectorEvent,
    HTTPPool,
)

log = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class KubernetesConnector(Connector):
    """Connector to Kubernetes API server.

    Parameters
    ----------
    endpoint:
        Kubernetes API server URL (e.g. ``https://k8s.example.com``).
    token:
        Bearer token for authentication.
    namespace:
        Namespace to watch. Defaults to ``default``.
    max_connections:
        Maximum concurrent HTTP connections to the API server.
    timeout:
        Default timeout for API requests.
    """

    connector_type = "kubernetes"
    capabilities = ["pull", "subscribe"]
    transport = "http"
    auth_scheme = "bearer"

    def __init__(
        self,
        *,
        endpoint: str,
        token: str,
        namespace: str = "default",
        max_connections: int = 10,
        timeout: float = 5.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(name=f"k8s:{namespace}", endpoint=endpoint, **kwargs)
        self._token = token
        self._namespace = namespace
        self._timeout = timeout
        self._http_pool = HTTPPool(
            base_url=endpoint,
            max_connections=max_connections,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
        self._last_resource_versions: dict[str, str] = {}

    async def _connect_internal(self) -> None:
        """Verify the API server is reachable."""
        try:
            await self._http_pool.get("/version")
        except httpx.HTTPError as exc:
            raise ConnectError(f"Kubernetes API unreachable: {exc}", retryable=True) from exc

    async def _disconnect_internal(self) -> None:
        """Close the HTTP pool."""
        await self._http_pool.aclose()

    async def _snapshot_internal(self) -> dict[str, Any]:
        """Capture current state of pods and deployments."""
        pods = await self._list_pods()
        deployments = await self._list_deployments()
        return {
            "namespace": self._namespace,
            "pods": pods,
            "deployments": deployments,
            "snapshot_at": _utcnow().isoformat(),
        }

    async def _subscribe_internal(self, *, interval: float) -> AsyncIterator[ConnectorEvent]:
        """Poll for changes in pods and deployments."""
        while self._sub_running:
            await asyncio.sleep(max(0.05, interval))
            try:
                pods = await self._list_pods()
                deployments = await self._list_deployments()
                async for event in self._diff(pods, deployments):
                    yield event
            except httpx.HTTPError as exc:
                log.error(
                    "k8s.poll_failed",
                    namespace=self._namespace,
                    error=str(exc),
                )
                continue

    async def _diff(
        self, pods: dict[str, Any], deployments: dict[str, Any]
    ) -> AsyncIterator[ConnectorEvent]:
        """Yield events for changes since last poll."""
        # Implementation would compare with previous state
        # and yield appropriate events
        pass

    async def _list_pods(self) -> dict[str, Any]:
        """List all pods in the namespace."""
        resp = await self._http_pool.get(
            f"/api/v1/namespaces/{self._namespace}/pods",
            params={
                "watch": "false",
                "resourceVersion": self._last_resource_versions.get("pods", "0"),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._last_resource_versions["pods"] = data.get("metadata", {}).get("resourceVersion", "0")
        return {p["metadata"]["name"]: p for p in data.get("items", [])}

    async def _list_deployments(self) -> dict[str, Any]:
        """List all deployments in the namespace."""
        resp = await self._http_pool.get(
            f"/apis/apps/v1/namespaces/{self._namespace}/deployments",
            params={
                "watch": "false",
                "resourceVersion": self._last_resource_versions.get("deployments", "0"),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._last_resource_versions["deployments"] = data.get("metadata", {}).get("resourceVersion", "0")
        return {d["metadata"]["name"]: d for d in data.get("items", [])}

    def emitted_event_types(self) -> list[str]:
        return [
            "k8s.pod.created",
            "k8s.pod.deleted",
            "k8s.pod.updated",
            "k8s.deployment.created",
            "k8s.deployment.deleted",
            "k8s.deployment.updated",
        ]


__all__ = ["KubernetesConnector"]
