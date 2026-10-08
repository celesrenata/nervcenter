# Spec: Mobile (iPhone/Watch) Quality Bar + SSO Pairing

**Feature ID:** mobile-quality-audit
**Created:** 2026-09-30
**Status:** Active
**Branch target:** main (repo root: nervcenter)
**Upstream:** [prompot.md](../../prompot.md) §65–73 (Phone/Watch surfaces, complications, synchronized state, local connectivity, authentication, sensitive approval, local cache)
**Companion:** [specs/sso-integration/spec.md](../sso-integration/spec.md) (AC-S04 pairing, AC-S05 approval binding, AC-S07 Apple RP)

## Problem

The shared Apple SDK compiles (AC009 green) but its mobile-facing contracts are
incomplete against the new rules and prompot §65–73:

- **No OIDC RP:** `NerveAuth` has pairing/approval/biometric primitives but no
  SSO client — an iPhone cannot obtain a device credential from
  `sso.celestium.life` (Authentik) or exchange the §71 pairing challenge
  against the real backend endpoints (S101).
- **No Keychain:** `CredentialStore` has only `InMemoryCredentialStore`;
  prompot §71 requires the device credential to land in **Keychain**.
- **No staleness marking:** §69/§73 require "stale information must be marked
  clearly" and cached state (systems, incidents, goals, approvals…) to stay
  usable offline; `NervePersistence` `CachedState`/`SynchronizedState` carry
  data but no age/freshness contract exposed to the UI.
- **Biometric gate exists but is unbound:** `BiometricApprovalGate` guards
  any operation; §72 requires the gate to bind to an **exact**
  `PlannedChange` (approval bound to `planned_change_id` + `device_id` +
  `nonce` + `expires_at`, invalidated by any modification of the change —
  mirrored in S101's backend binding; the SDK must submit that binding).
- **No Watch/iPhone compact-state contract:** §69's synchronized state
  (`system_health`, `active_incidents`, `running_agents`, `pending_approvals`,
  `primary_goal_progress`, `updated_at`) exists in `NerveModels` but has no
  consumer-side freshness contract or complication mapping (§68 priority
  order: urgent incident → approval → active incident → investigation →
  goal → general status).

## Goals

1. `NerveAuth` implements the full mobile SSO path: OIDC RP (PKCE) against
   the Authentik provider, pairing challenge initiation/confirm against the
   real backend endpoints, Keychain-backed credential store.
2. The approval submission path binds biometric authorization to an exact
   `PlannedChange` per §72 and the S101 backend contract.
3. Cached/synchronized state carries a clear staleness contract (age,
   freshness flag, "stale" marking) usable by iPhone/Watch UIs.
4. Everything compiles green via `xcodebuild -scheme NerveShared build` on
   the M5 Max (AC009 gate), with unit tests for PKCE/biometric/pairing paths.

## Scope

**In scope:** `apple/Shared/**` (NerveAuth SSO client + Keychain store +
approval binding, NervePersistence staleness contract, NerveModels additions
if OpenAPI regeneration requires them), `apple/Shared/Tests/**` unit tests.

**Out of scope:** real device testing (spec constraint from
nervecenter-deploy), app targets (iPhone/Watch UIs live outside the shared
SDK), backend changes (S101), web changes (S102).

## Constraints

- `xcodebuild -scheme NerveShared -destination 'generic/platform=iOS Simulator' build`
  green on the M5 Max after every change (AC009 gate).
- SDK stays dependency-free (existing pattern: protocols + in-memory test
  impls; app targets map to `LocalAuthentication`/`Security`).
- OpenAPI regeneration after S101 lands: `NerveModels` must match the live
  contract, not a guessed one.
- §71 constraint honored: challenge expiry ≤ 5 min, credential bound to
  `device_id`; §72: any modification of the bound change invalidates approval.

## Acceptance Criteria

- AC-M01: `NerveSSOClient` implements PKCE (S256) authorization-code +
  token exchange against the issuer from `/api/auth/sso/config`; unit tests
  cover code-verifier/challenge generation and token-request construction
  (no network in tests).
- AC-M02: `KeychainCredentialStore` implements the `CredentialStore`
  protocol via `Security.framework` with an injectable seam for tests
  (`InMemoryCredentialStore` remains the test default); credential expiry
  checks preserved.
- AC-M03: Pairing flow helpers initiate/confirm against the S101 endpoints
  (`POST /api/auth/pairing/initiate`, `/confirm`) with the challenge nonce
  and ≤5-min expiry enforced client-side too.
- AC-M04: Approval submission binds biometric authorization to an exact
  `PlannedChange`: `ApprovalRequest` carries `planned_change_id`,
  `device_id`, `nonce`, `expires_at`; the gate refuses to submit when the
  bound change's hash differs from the one presented at authorization time
  (§72: any modification invalidates approval); unit-tested.
- AC-M05: Staleness contract: `CachedState`/`SynchronizedState` expose
  `updatedAt`, `isStale(after:)` (configurable threshold), and a
  `freshness` descriptor; §69 `updated_at` is always populated; unit-tested.
- AC-M06: `xcodebuild -scheme NerveShared build` green on M5 Max; all SDK
  unit tests pass; evidence logged in `docs/implementation-status.yaml`
  and the [tasks.md](../sso-integration/tasks.md) verification log.

## Verification

Each AC maps to a task in [tasks.md](../sso-integration/tasks.md) (S103)
with exact commands (`xcodebuild`, `swift test`) and evidence; gaps (no
device testing) stated explicitly.
