# Plan: Mobile (iPhone/Watch) Quality Bar + SSO Pairing

**Feature:** mobile-quality-audit · **Spec:** [`spec.md`](./spec.md) · **Tasks:** [`tasks.md`](./tasks.md)

## Ground Truth (2026-10-01)

| Area | State | Evidence |
|------|-------|----------|
| SDK | `NerveAuth` has Approval/Biometrics/CredentialStore/DevicePairing/PlannedChange primitives ([NerveAuth](../../apple/Shared/Sources/NerveAuth/CredentialStore.swift)); only `InMemoryCredentialStore` — no Keychain impl | file inspection |
| SSO | No OIDC RP: no PKCE client, no JWKS validation, no `/api/auth/sso/config` consumer | file inspection |
| Pairing | [DevicePairing.swift](../../apple/Shared/Sources/NerveAuth/DevicePairing.swift) has primitives but no initiate/confirm helpers against S101 endpoints, no ≤5-min expiry enforcement | file inspection |
| Approval | [Biometrics.swift](../../apple/Shared/Sources/NerveAuth/Biometrics.swift) gate guards any operation; not bound to exact `PlannedChange` (§72) | file inspection |
| Staleness | [SynchronizedState.swift](../../apple/Shared/Sources/NerveModels/SynchronizedState.swift) carries data; no `updatedAt`/`isStale(after:)`/freshness contract | file inspection |
| Tests | [NerveSharedTests](../../apple/Tests/NerveSharedTests) cover cache/events/transport only | file inspection |
| App targets | `iOS/` contains only `.gitkeep`; no `Watch/` directory — the iPhone and Watch apps are **not built at all** | `apple/**` tree |

## Architecture Decisions

1. SDK stays dependency-free: protocols + injectable seams (`SecItem` behind a
   `KeychainStore` protocol, `LAContext` behind `BiometricAuthenticator`).
2. OIDC RP: PKCE (S256) authorization-code + token exchange against the issuer
   from `/api/auth/sso/config`; no network in unit tests (request builders +
   response parsers tested, transport mocked).
3. Pairing helpers mirror S101 endpoints exactly: `POST
   /api/auth/pairing/initiate` → `POST /api/auth/pairing/confirm`; client-side
   expiry enforcement ≤ 5 min (§71).
4. Biometric gate binds to the exact `PlannedChange`: `ApprovalRequest` carries
   `planned_change_id` + `device_id` + `nonce` + `expires_at`; the gate refuses
   submission when the bound change's hash differs from the one presented at
   authorization time (§72: any modification invalidates approval).
5. Staleness contract on `CachedState`/`SynchronizedState`: `updatedAt`,
   `isStale(after:)` with configurable threshold, `freshness` descriptor;
   §69 `updated_at` always populated.
6. App targets (iPhone + Watch) are a separate feature: see
   [specs/mobile-apps/spec.md](../mobile-apps/spec.md) (M201–M206) — not part
   of this SDK audit.

## Dependency Graph

```text
S101 backend auth contract ─────┐  (read-only reference)
M101 SSO client (PKCE) ─────────┤
M102 Keychain store ────────────┼──► M104 xcodebuild + swift test evidence
M103 pairing + bound approval ──┘
M105 staleness contract ──────── (independent)
M106 app targets ─────────────── (separate feature, mobile-apps)
```

M101–M103 and M105 share `apple/Shared/**` with one Apple worker; M104 waits
for all.

## File Ownership

| Owner task | Paths |
|-----------|-------|
| M101–M105 (one Apple worker) | `apple/Shared/**` (Sources + Tests) |
| M106 | `apple/iOS/**`, `apple/Watch/**`, `apple/Package.swift` (targets) |
| S101 (cross-ref) | `backend/api/auth.py` contract — read-only for M101–M103 |

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Authentik provider not yet provisioned | SDK compiles and tests against the contract; live round-trip stays pending until S104 lands |
| Keychain/biometric not device-testable | Unit tests + `xcodebuild` gate; gaps stated explicitly in evidence |
| OpenAPI drift after S101 | `NerveModels` regenerated from live OpenAPI once S101 is deployed; contract notes updated |
