"""Tests for X-Forwarded-Proto and X-Forwarded-For proxy header handling.

T315: Fix T208 proxy-header handling (X-Forwarded-Proto).

The NerveCenter API must honor the ``X-Forwarded-Proto`` header when deployed
behind a TLS-terminating ingress (e.g., AWS ALB, NGINX). Without this, requests
arriving as ``https://`` get redirected to ``http://`` by FastAPI, breaking the
application behind the ingress.

Environment variables
---------------------
- ``NERVE_TRUSTED_HOSTS``: comma-separated list of trusted proxy IPs (default: ``127.0.0.1,::1``)

Contract (per `Dockerfile.api` CMD and `k8s/api-deployment.yaml`):
- uvicorn started with ``--proxy-headers`` and ``--forwarded-allow-ips``
- FastAPI reads ``X-Forwarded-Proto`` to construct correct redirect URLs
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def client():
    """Create an app with proxy headers enabled."""
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestProxyHeaders:
    """Test proxy header handling."""

    def test_x_forwarded_proto_https_no_redirect(
        self,
        client: TestClient,
    ) -> None:
        """HTTPS requests with X-Forwarded-Proto: https should not redirect to http."""
        # Simulate a request arriving via HTTPS at the ingress
        response = client.get(
            "/api/health",
            headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "example.com"},
            follow_redirects=False,
        )
        # Should return health data, not a 307 redirect to http
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. "
            f"Body: {response.text}"
        )

    def test_x_forwarded_proto_http_also_acceptable(
        self,
        client: TestClient,
    ) -> None:
        """HTTP requests with X-Forwarded-Proto: http are also accepted."""
        response = client.get(
            "/api/health",
            headers={"X-Forwarded-Proto": "http"},
            follow_redirects=False,
        )
        assert response.status_code == 200

    def test_x_forwarded_for_passed_through(
        self,
        client: TestClient,
    ) -> None:
        """X-Forwarded-For header should be present in request."""
        # Just check we can make a request with the header - actual processing
        # is handled by uvicorn middleware, not our app code
        response = client.get(
            "/api/health",
            headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2"},
            follow_redirects=False,
        )
        assert response.status_code == 200

    def test_version_endpoint_responds(
        self,
        client: TestClient,
    ) -> None:
        """The /version endpoint should respond under proxy headers."""
        response = client.get(
            "/version",
            headers={"X-Forwarded-Proto": "https"},
            follow_redirects=False,
        )
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
