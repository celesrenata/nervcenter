# Plan: Celestium SSO + Mobile Auth Integration

**Feature:** sso-integration · **Spec:** [`spec.md`](./spec.md) · **Tasks:** [`tasks.md`](./tasks.md)

## Ground Truth (2026-09-30)

| Area | State | Evidence |
|------|-------|----------|
| SSO host | Authentik at `sso.celestium.life` (`GET /` → 302 `/admin/`, authentik JSON 404 style, per-app OIDC discovery); **no `nervecenter` provider exists** (discovery 404 for candidate slugs) | `curl -D - https://sso.celestium.life/`, `/application/o/nervecenter/.well-known/openid-configuration` |
| Backend auth | Toy: in-memory `token_store`, hardcoded `admin/password` (`backend/api/auth.py:27-28`), opaque tokens (not JWT), state wiped on restart | file inspection |
| Web auth | `AuthContext` fake-decodes any `authToken` to `admin`; no Authorization header on API fetches; `LoginView` advertises default creds | `web/src/auth/AuthContext.tsx`, `web/src/views/LoginView.tsx` |
| Apple auth | `NerveAuth` has biometric primitives only; no OIDC RP, no pairing, no Keychain credential flow | `apple/Shared/Sources/NerveAuth/**` |
| Deploy | `nervecenter.celestium.life` live on LAN (TLS Let's Encrypt); public DNS NXDOMAIN (T207 open) | tasks.md verification log (nervecenter-deploy) |

## Architecture Decisions

1. **Identity provider:** Authentik (authoritative at `sso.celestium.life`).
   NerveCenter is an OIDC **RP** (relying party). Provider slug `nervecenter`.
   PKCE (S256) authorization-code flow for both web and Apple; no implicit flow.
2. **Backend token strategy:** RS256 verification against Authentik JWKS when
   the provider is live; HS256 (`NERVE_JWT_SECRET`) fallback so the backend,
   web e2e, and CLI/MCP work without the provider. Access tokens carry
   `sub`, `iat`, `exp`, `typ=access` (or `device`), `roles`.
3. **Session/device persistence:** PostgreSQL via alembic migration
   (`auth_sessions`, `auth_devices` tables). Tokens are stateless-JWT; the
   device registry and pairing challenges are persisted, so restarts never
   invalidate a valid JWT.
4. **Break-glass:** local admin login exists only when `NERVE_LOCAL_ADMIN`
   env is set; logs a warning; grep-verified no `admin/password` default.
5. **Web:** redirect-based SSO (`/auth/callback` route, PKCE in sessionStorage),
   `Authorization: Bearer` on every fetch via a shared `apiFetch` helper,
   401 → redirect to `/login`. Mock mode (`VITE_API_BASE` unset) keeps the
   local login so the e2e harness stays green.
6. **Apple:** `NerveAuth` gains `NerveSSOClient` (PKCE RP), `NerveCredentialStore`
   (Keychain), and a biometric gate guarding approval submission (§72).
   `NerveModels` regenerated from live OpenAPI after backend changes.
7. **Deploy:** app-level SSO (backend 401/redirect + web callback) rather than
   traefik forwardAuth — the ingress stays simple and the same flow works for
   all clients; TLS unchanged.

## Dependency Graph

```
S101 backend-auth ─────┐
S102 web-sso ───────────┼──► S201 deploy ──► S202 audit-fix-loop
S103 apple-auth ────────┤
S104 provider-config ───┘
```

- S101, S102, S103, S104 have disjoint file ownership and can start in one
  wave; live integration checks (S201/S202) wait for S101+deploy.
- S104 is partly external (Authentik admin) — it proceeds with the config
  endpoint + manual-provider doc and unblocks S202 once the provider exists.

## File Ownership (single owner per path)

| Owner task | Paths |
|-----------|-------|
| S101 | `backend/api/auth.py`, `backend/api/endpoints/**` (auth-adjacent), `backend/persistence/models/**` (auth tables), `migrations/**`, `tests/**` (auth tests), `pyproject.toml` (jwt deps) |
| S102 | `web/src/**`, `web/index.html`, web build config (not `web/Dockerfile`) |
| S103 | `apple/Shared/**` |
| S104 | `docs/**` (SSO provider doc), `deployments/**` (env vars, secrets), `specs/sso-integration/**` |
| S201/S202 | k8s objects via kubectl, `deployments/**` patches, `web/**` + `backend/**` defect fixes filed back to owning tasks |

Cross-boundary rule: S102 may *read* `backend/` contract (OpenAPI) but not
modify it; defects found go back as S101 follow-ups. Same for S103 vs S101.

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Authentik admin credentials unknown | S104 documents manual provider creation; backend ships OIDC-client-first so it works the moment the provider exists |
| Public DNS NXDOMAIN (T207) | SSO verified on LAN + local dev; public reachability remains T207's blocker |
| Web e2e depends on mock mode | SSO code paths degrade to local login in mock mode; e2e keeps passing |
| Apple Keychain/biometric not device-testable | Unit tests + xcodebuild gate; device testing stays out of scope (spec constraint) |
| JWT secret management | HS256 secret via k8s Secret (`nervecenter-auth`); RS256 path uses Authentik JWKS (no secret) |

## Exit Criteria (from spec)

AC-S01–AC-S09 in [`spec.md`](./spec.md) — each maps to a task's verification section.
