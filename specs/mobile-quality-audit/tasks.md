# Tasks: Mobile (iPhone/Watch) Quality Bar + SSO Pairing

**Spec:** [`spec.md`](./spec.md) · **Plan:** [`plan.md`](./plan.md)

## Task Board

| ID | Title | AC | Deps | Files owned | Verification |
|----|-------|----|------|-------------|--------------|
| M101 | NerveSSOClient: PKCE OIDC RP | AC-M01 | S101 contract (read-only) | `apple/Shared/Sources/NerveAuth/NerveSSOClient.swift` | Unit tests: verifier/challenge + token-request construction; `xcodebuild` green |
| M102 | KeychainCredentialStore | AC-M02 | — | `apple/Shared/Sources/NerveAuth/KeychainCredentialStore.swift` | Unit tests with injectable seam; expiry checks preserved |
| M103 | Pairing helpers + §72-bound approval | AC-M03, AC-M04 | S101 contract (read-only) | `apple/Shared/Sources/NerveAuth/DevicePairing.swift`, `apple/Shared/Sources/NerveAuth/Approval.swift`, `apple/Shared/Sources/NerveAuth/Biometrics.swift` | Unit tests: ≤5-min expiry, hash-mismatch refusal, binding payload |
| M105 | Staleness contract | AC-M05 | — | `apple/Shared/Sources/NerveModels/SynchronizedState.swift`, `apple/Shared/Sources/NervePersistence/CachedState.swift` | Unit tests: `isStale(after:)`, freshness descriptor, §69 `updated_at` |
| M104 | Compile + test evidence | AC-M06 | M101–M103, M105 | evidence only | `xcodebuild -scheme NerveShared build` + `swift test` green on M5 Max; logged |

M101–M103 and M105 are one Apple worker's internal sequence (single owner of
`apple/Shared/**`); M104 waits for all. App targets (iPhone/Watch) are out of
scope here — see [specs/mobile-apps/spec.md](../mobile-apps/spec.md) (M201–M206).

## M101 — NerveSSOClient

Scope:
- `NerveSSOClient` implementing PKCE (S256) authorization-code + token
  exchange against the issuer from `/api/auth/sso/config` (AC-M01); JWKS
  validation hook; no network in tests (transport mocked).
- Unit tests: code-verifier/challenge generation (RFC 7636 shapes), token
  request construction.

## M102 — KeychainCredentialStore

Scope:
- `KeychainCredentialStore` implementing the `CredentialStore` protocol via
  `Security.framework` behind an injectable `KeychainStore` seam (AC-M02);
  `InMemoryCredentialStore` remains the test default; expiry checks preserved.

## M103 — Pairing + bound approval

Scope:
- Pairing helpers initiate/confirm against S101 endpoints (`POST
  /api/auth/pairing/initiate`, `/confirm`) with challenge nonce and ≤5-min
  expiry enforced client-side (AC-M03).
- `ApprovalRequest` carrying `planned_change_id`, `device_id`, `nonce`,
  `expires_at`; the biometric gate refuses submission when the bound change's
  hash differs from the one presented at authorization time (AC-M04, §72).

## M105 — Staleness contract

Scope:
- `CachedState`/`SynchronizedState` expose `updatedAt`, `isStale(after:)`
  (configurable threshold), and a `freshness` descriptor; §69 `updated_at`
  always populated (AC-M05).

## M104 — Compile + test evidence

Scope:
- Run `xcodebuild -scheme NerveShared -destination 'generic/platform=iOS
  Simulator' build` and `swift test` on the M5 Max; capture output; log
  evidence into [docs/implementation-status.yaml](../../docs/implementation-status.yaml)
  and this file's verification log; state explicit gaps (no device testing).

## Verification Log

*(updated per task completion — commands, results, gaps)*
