# Tasks: Celestium SSO + Mobile Auth Integration

**Spec:** [`spec.md`](./spec.md) · **Plan:** [`plan.md`](./plan.md)

## Task Board

| ID | Title | AC | Deps | Files owned | Verification |
|----|-------|----|------|-------------|--------------|
| S101 | Backend auth: signed JWT + pairing + approval binding | AC-S01, AC-S02, AC-S03, AC-S04, AC-S05 | — | `backend/api/auth.py`, `backend/persistence/models/**` (auth tables), `migrations/**`, `tests/**` (auth), `pyproject.toml` | pytest auth suite green; `/api/auth/sso/config` 200; pairing + approval negative paths tested |
| S102 | Web SSO login + authorized fetches | AC-S06 | — | `web/src/**`, `web/index.html`, web build config (not `web/Dockerfile`) | Playwright: login → authorized fetch → view data; 0 console errors; mock-mode e2e stays green |
| S103 | Apple: NerveAuth OIDC RP + Keychain + biometric gate | AC-S07 | — | `apple/Shared/**` | `xcodebuild -scheme NerveShared build` green on M5 Max; unit tests for PKCE/biometric paths |
| S104 | Authentik provider + config doc + deploy env | AC-S01, AC-S09 | — | `docs/sso/**`, `deployments/**` (auth env/secrets), `specs/sso-integration/**` | `/api/auth/sso/config` reflects provider when live; manual-provision doc reviewed; secrets wired |
| S201 | Deploy auth stack to K3s | AC-S03, AC-S09 | S101, S102 | k8s objects in `nervecenter` ns | pods Running; `/api/auth/sso/config` live 200; TLS chain valid for both hosts |
| S202 | Audit: curl + Playwright + mobile evidence | AC-S01–AC-S09 | S201 | patches via defect follow-ups | curl matrix + Playwright matrix incl. SSO round-trip all green; defects filed & fixed; evidence in `docs/implementation-status.yaml` |

S101, S102, S103, S104 have disjoint initial file ownership and can start in
one dispatch wave (per [plan.md](./plan.md) dependency graph). Live
integration checks (S201/S202) wait for S101 and deployment.

## S101 — Backend auth: signed JWT + pairing + approval binding

Scope:
- Rewrite `backend/api/auth.py`: signed JWT (RS256 via Authentik JWKS when
  `NERVE_SSO_ISSUER` set + provider live; HS256 with `NERVE_JWT_SECRET`
  fallback), claims `sub`/`iat`/`exp`/`typ`/`roles`; opaque-token store gone.
- Add `auth_sessions` + `auth_devices` + `pairing_challenges` tables
  (alembic migration), so restarts never invalidate a valid JWT.
- Endpoints per spec §46 groups + §71/§72: `GET /api/auth/sso/config`,
  `POST /api/auth/pairing/initiate`, `POST /api/auth/pairing/confirm`,
  approval binding on existing approvals group (`device_id` + `nonce` +
  `expires_at` + exact `planned_change_id`; any modification of the bound
  change invalidates the approval).
- Break-glass: local admin login only when `NERVE_LOCAL_ADMIN` env set;
  logs warning; grep-verified no `admin/password` default remains.
- Tests: ≥3 negative-path token tests (expired, wrong-type, tampered),
  ≥2 pairing tests, ≥1 approval-invalidation test.

## S102 — Web SSO login + authorized fetches

Scope:
- `/auth/callback` route + PKCE (S256) code flow against `/api/auth/sso/config`
  issuer; tokens in sessionStorage; `Authorization: Bearer` on every fetch via
  shared `apiFetch`; 401 → redirect `/login`.
- Login surface: "Sign in with Celestium SSO" primary; break-glass form
  demoted (visible only when `NERVE_LOCAL_ADMIN` enabled, i.e. config
  endpoint says so); visible labels, actionable errors, pending state.
- Mock mode (`VITE_API_BASE` unset) keeps local login path so e2e stays green.
- Playwright: login → authorized fetch → view data; 0 console errors.

## S103 — Apple: NerveAuth OIDC RP + Keychain + biometric gate

Scope:
- `NerveAuth`: `NerveSSOClient` (PKCE authorization-code, token exchange,
  JWKS validation), `NerveCredentialStore` (Keychain device credential),
  biometric gate guarding approval submission (§72), pairing challenge
  initiation/confirm helpers (§71).
- `NerveModels` regenerated from live OpenAPI after S101 contract changes.
- `xcodebuild -scheme NerveShared build` green on M5 Max (AC009-style gate).

## S104 — Authentik provider + config doc + deploy env

Scope:
- Authentik admin: create `nervecenter` OIDC provider (slug `nervecenter`,
  redirect `https://nervcenter.celestium.life/auth/callback` + dev
  `http://localhost:3000/auth/callback`, PKCE required) when credentials are
  available; otherwise document the exact manual steps in `docs/sso/`.
- `deployments/kubernetes/**`: `NERVE_SSO_ISSUER`, `NERVE_JWT_SECRET` (Secret
  `nervecenter-auth`), `NERVE_LOCAL_ADMIN` unset in prod.
- Verification: `/api/auth/sso/config` `enabled=true` + real endpoints once
  provider live; TLS valid for `sso.celestium.life` and
  `nervcenter.celestium.life` (curl `-D -`).

## S201 — Deploy auth stack to K3s

Steps:
1. Build+push api image with new auth (tag = git sha).
2. Apply kustomize (auth Secret, api Deployment env, web Deployment).
3. Verify: pods Running; `/api/auth/sso/config` live 200; TLS chain valid
   for both hosts; unauthenticated request redirected to SSO or login.

## S202 — Audit: curl + Playwright + mobile evidence

Matrix:
- API: `/api/auth/sso/config`, pairing endpoints, approval binding — live
  curl matrix with `-D -` for headers/status.
- Web: Playwright script across 10 views + login + SSO round-trip
  (or break-glass when provider absent) + authorized fetch; 0 console errors.
- Mobile: `xcodebuild -scheme NerveShared build` output captured; unit tests
  for PKCE/biometric paths.
- Defects → fix → S201 redeploy → re-run until green. Evidence into
  `docs/implementation-status.yaml` + this file's Verification Log.

## Verification Log

*(updated per task completion — commands, results, gaps)*
