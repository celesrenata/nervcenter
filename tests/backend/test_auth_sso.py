"""S101 tests: signed-JWT auth core + SSO endpoints (spec sso-integration).

Covers the acceptance-criteria evidence named in ``specs/sso-integration/
tasks.md`` S101:

- three *negative* token-validation cases (expired / wrong signature /
  revoked session) — AC-S02 / AC-S03;
- two device-pairing cases (successful confirm, nonce-mismatch reject) —
  AC-S04 / prompot §71;
- one approval-invalidation case (bound change modified) — AC-S05 / prompot §72.

Plus contract tests: the AC-S01 ``GET /api/auth/sso/config`` shape and the
AC-S03 break-glass login (no default credential; disabled unless
``NERVE_LOCAL_ADMIN`` is set).

No live database or SSO provider is used: the service runs against its
in-process session store (``session_factory=None``) and the SSO probe is
allowed to report "not live" (the issuer is an unroutable test host).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import backend.api.auth_service as auth_service
from backend.api.app import create_app
from backend.api.auth_service import (
    ACCESS_TOKEN_TTL,
    LOCAL_ADMIN_SUB,
    TYP_ACCESS,
    AuthContext,
    TokenError,
)

TEST_ISSUER = "https://sso.test.example/application/o/nervecenter/"
# Keep test fixtures at the RFC 7518-recommended minimum for HS256 keys.
SECRET_A = "unit-secret-a-" + "a" * 56
SECRET_B = "unit-secret-b-" + "b" * 56


def _ctx(secret: str = SECRET_A, **kwargs) -> AuthContext:
    return AuthContext(
        secret=secret,
        issuer=TEST_ISSUER,
        client_id="nervecenter-test-client",
        local_admin_enabled=kwargs.pop("local_admin_enabled", False),
        local_admin_password=kwargs.pop("local_admin_password", None),
        session_factory=None,  # in-process store
        **kwargs,
    )


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "NERVE_JWT_SECRET",
        "NERVE_SSO_ISSUER",
        "NERVE_SSO_CLIENT_ID",
        "NERVE_LOCAL_ADMIN",
        "NERVE_LOCAL_ADMIN_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    auth_service.reset_memory_store()
    auth_service.reset_discovery_cache()
    yield


def _client():
    return TestClient(create_app())


# ─── AC-S02 / AC-S03: three negative token-validation cases ───────────────────


async def test_negative_expired_token_rejected(monkeypatch: pytest.MonkeyPatch):
    """A past-its-expiry token is rejected, not just signature-checked."""
    ctx = _ctx()
    monkeypatch.setattr(auth_service, "ACCESS_TOKEN_TTL", type(ACCESS_TOKEN_TTL)())
    try:
        token, _exp = ctx.issue_access_token(LOCAL_ADMIN_SUB, ["admin"])
    finally:
        monkeypatch.undo()
    with pytest.raises(TokenError, match="expired"):
        await ctx.verify_token(token, expected_typ=TYP_ACCESS)


async def test_negative_wrong_signature_rejected():
    """A token signed with a foreign secret is rejected by verify_token."""
    ctx_a = _ctx(secret=SECRET_A)
    ctx_b = _ctx(secret=SECRET_B)
    token, _exp = ctx_a.issue_access_token(LOCAL_ADMIN_SUB, ["admin"])
    await auth_service.record_session(
        ctx_a,
        jti=auth_service._jti_of(token, ctx_a),
        sub=LOCAL_ADMIN_SUB,
        typ=TYP_ACCESS,
        expires_at=_exp,
        source="unit",
    )
    with pytest.raises(TokenError, match="rejected"):
        await ctx_b.verify_token(token, expected_typ=TYP_ACCESS)


async def test_negative_revoked_session_rejected():
    """A still-expired signature is not enough: a revoked session 401s."""
    ctx = _ctx()
    token, exp = ctx.issue_access_token(LOCAL_ADMIN_SUB, ["admin"])
    jti = auth_service._jti_of(token, ctx)
    await auth_service.record_session(
        ctx, jti=jti, sub=LOCAL_ADMIN_SUB, typ=TYP_ACCESS, expires_at=exp,
        source="unit",
    )
    # Positive control: the live session is accepted.
    claims = await ctx.verify_token(token, expected_typ=TYP_ACCESS)
    assert claims["sub"] == LOCAL_ADMIN_SUB
    assert await auth_service.revoke_session(ctx, jti) is True
    with pytest.raises(TokenError, match="revoked|unknown"):
        await ctx.verify_token(token, expected_typ=TYP_ACCESS)


# ─── AC-S04 / prompot §71: two device-pairing cases ───────────────────────────


async def test_pairing_confirm_success_mints_device_credential():
    """Challenge → confirm(nonce) yields a ``device:<id>``-subject credential."""
    ctx = _ctx()
    challenge = await auth_service.initiate_pairing(ctx, by_sub=LOCAL_ADMIN_SUB)
    from datetime import UTC, datetime

    assert (
        challenge["expires_at"]
        and datetime.fromisoformat(challenge["expires_at"])
        >= datetime.now(UTC)
    )
    token, exp = ctx.issue_access_token(LOCAL_ADMIN_SUB, ["admin"])
    await auth_service.record_session(
        ctx,
        jti=auth_service._jti_of(token, ctx),
        sub=LOCAL_ADMIN_SUB,
        typ=TYP_ACCESS,
        expires_at=exp,
        source="unit",
    )
    result = await auth_service.confirm_pairing(
        ctx,
        challenge_id=challenge["challenge_id"],
        nonce=challenge["nonce"],
        device_name="Unit iPhone",
        platform="ios",
        attestation={"secure_enclave": "ok"},
        device_id="unit-device-1",
    )
    device_token = result["device_credential"]
    claims = await ctx.verify_token(device_token, expected_typ="device")
    assert claims["sub"] == "device:unit-device-1"
    assert claims["device_id"] == "unit-device-1"
    assert result["device"]["status"] == "active"
    # Single-use: the same challenge cannot be confirmed twice.
    with pytest.raises(TokenError, match="single-use"):
        await auth_service.confirm_pairing(
            ctx,
            challenge_id=challenge["challenge_id"],
            nonce=challenge["nonce"],
            device_name="Unit iPhone",
            device_id="unit-device-2",
        )


async def test_pairing_confirm_wrong_nonce_rejected():
    """A mismatched nonce fails confirmation and the challenge is marked failed."""
    ctx = _ctx()
    challenge = await auth_service.initiate_pairing(ctx, by_sub=LOCAL_ADMIN_SUB)
    with pytest.raises(TokenError, match="nonce"):
        await auth_service.confirm_pairing(
            ctx,
            challenge_id=challenge["challenge_id"],
            nonce="wrong-nonce",
            device_name="Unit iPhone",
            device_id="unit-device-3",
        )
    row = await auth_service._load_challenge(ctx, challenge["challenge_id"])
    assert row.status == "failed"


# ─── AC-S05 / prompot §72: approval invalidation on change modification ──────


async def test_approval_invalidated_when_bound_change_modified():
    """Any modification of the bound planned change invalidates the approval."""
    ctx = _ctx()
    change = {
        "id": "0" * 32,
        "change_type": "update",
        "title": "Rotate API key",
        "description": "rotate",
        "status": "proposed",
        "risk_level": 2,
        "subject_ids": ["entity-1"],
        "diff": {"before": "a", "after": "b"},
        "rollback": {},
        "proposed_at": "2026-10-02T00:00:00Z",
        "expires_at": None,
    }
    approval = await auth_service.create_approval(
        ctx,
        planned_change_id=change["id"],
        change=change,
        nonce="nonce-1",
        approver_sub="device:unit-device-1",
        device_id="unit-device-1",
    )
    check = await auth_service.verify_approval(
        ctx, approval_id=approval["approval_id"], change=change,
        device_id="unit-device-1",
    )
    assert check["valid"] is True

    modified = dict(change, title="Rotate API key (v2)")  # any field change
    check = await auth_service.verify_approval(
        ctx, approval_id=approval["approval_id"], change=modified,
        device_id="unit-device-1",
    )
    assert check["valid"] is False
    assert check["reason"] == "change_modified"
    assert check["approval"]["decision"] == "invalidated"


# ─── AC-S01: SSO config contract ──────────────────────────────────────────────


def test_sso_config_shape_and_default_issuer():
    client = _client()
    response = client.get("/api/auth/sso/config")
    assert response.status_code == 200
    body = response.json()
    assert body["issuer"] == auth_service.DEFAULT_SSO_ISSUER
    for key in (
        "issuer",
        "client_id",
        "authorization_endpoint",
        "token_endpoint",
        "userinfo_endpoint",
        "jwks_uri",
        "enabled",
    ):
        assert key in body, f"missing {key}"
    # Provider not live in the test environment → enabled is False.
    assert body["enabled"] is False


# ─── AC-S03: break-glass local admin (no default credential) ─────────────────


def test_login_disabled_by_default_and_wrong_password_401(monkeypatch: pytest.MonkeyPatch):
    client = _client()
    # No NERVE_LOCAL_ADMIN → disabled (403), never 200.
    response = client.post(
        "/api/auth/login",
        json={"username": LOCAL_ADMIN_SUB, "password": "anything"},
    )
    assert response.status_code == 403

    # Enabled, but wrong password → 401.
    monkeypatch.setenv("NERVE_LOCAL_ADMIN", "1")
    monkeypatch.setenv("NERVE_LOCAL_ADMIN_PASSWORD", "correct-horse")
    # Fresh app so the AuthContext is rebuilt from the now-enabled env
    # (the per-app context is cached on app.state at first use).
    client = _client()
    response = client.post(
        "/api/auth/login",
        json={"username": LOCAL_ADMIN_SUB, "password": "wrong"},
    )
    assert response.status_code == 401

    # Enabled + correct password → tokens, and /me round-trips.
    response = client.post(
        "/api/auth/login",
        json={"username": LOCAL_ADMIN_SUB, "password": "correct-horse"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"] and body["refresh_token"]
    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["sub"] == LOCAL_ADMIN_SUB
    assert me.json()["roles"] == ["admin"]


def test_login_unknown_user_401():
    client = _client()
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "password"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "unknown user"
