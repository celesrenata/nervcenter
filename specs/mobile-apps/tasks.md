# Tasks: iPhone & Watch App Targets

**Spec:** [`spec.md`](./spec.md) · **Plan:** [`plan.md`](./plan.md)

## Task Board

| ID | Title | AC | Deps | Files owned | Verification |
|----|-------|----|------|-------------|--------------|
| M201 | Package targets + app entry points | AC-MP01 | — | `apple/Package.swift`, `apple/iOS/**`, `apple/Watch/**` | `xcodebuild -scheme NervePhone … build` + `xcodebuild -scheme NerveWatch … build` green on M5 Max |
| M202 | iPhone status surfaces (§65–66) | AC-MP02 | M201 | `apple/iOS/**` views + view models | Simulator build green; loading/empty/error/stale states exercised in unit tests |
| M203 | iPhone approval inbox + biometric gate (§72) | AC-MP03 | M201, M103 | `apple/iOS/**` approvals screens | Unit tests: gate refusal on hash mismatch, denial/expiry paths |
| M204 | iPhone pairing + server config (§70/§71) | AC-MP04 | M201, M102, M103 | `apple/iOS/**` settings screens | Unit tests: pairing confirm flow, Keychain store, connection test |
| M205 | Watch complication + cached state (§68/§69/§73) | AC-MP05 | M201, M105 | `apple/Watch/**` | `xcodebuild -scheme NerveWatch … build` green; complication priority order unit-tested |
| M206 | Build + test evidence | AC-MP06 | M201–M205 | evidence only | `xcodebuild` outputs + test results logged in `docs/implementation-status.yaml` + this file's verification log |

M201 first (targets must exist before screens), then M202–M205 as one Apple
worker's internal sequence (single owner of `apple/**`), M206 last. SDK
contracts come from [specs/mobile-quality-audit/tasks.md](../mobile-quality-audit/tasks.md)
(M101–M105) — read-only here; defects found go back as M101–M105 follow-ups.

## M201 — Package targets + app entry points

Scope:
- Add `NervePhone` (iOS) and `NerveWatch` (watchOS) executable targets to
  [apple/Package.swift](../../apple/Package.swift); create `apple/iOS/**` and
  `apple/Watch/**` source trees with app entry points and root navigation.
- Keep assets minimal; if SwiftPM app targets fight bundle resources, split to
  `apple/iOS/NervePhone.xcodeproj` and document the deviation in the
  verification log.

## M202 — iPhone status surfaces

Scope:
- Systems health list, incidents (active/resolved, severity), agents
  (running/paused), goals (progress) per §65–66, fed from `NerveAPI` +
  `NervePersistence` cache with the M105 staleness contract (AC-MP02);
  loading/empty/error/stale states; no hardcoded fixture rows; preview data
  only inside `#Preview` closures and tests.

## M203 — iPhone approval inbox

Scope:
- Pending approvals list; submission runs the §72 biometric gate bound to the
  exact `PlannedChange` (AC-MP03); denial and expiry paths visible; LAContext
  implementation of `BiometricAuthenticator` lives in this target.

## M204 — iPhone pairing + server config

Scope:
- Pairing initiated/confirmed against S101 endpoints (AC-MP04, AC-M03 SDK
  contract); credential stored via `KeychainCredentialStore` (AC-M02); manual
  server entry (§70) with connection test; break-glass absent on phone.

## M205 — Watch complication + cached state

Scope:
- Complication renders the §69 compact state in the §68 fixed priority order
  (urgent incident → approval → active incident → investigation → goal →
  general status); cached-state view marks stale data clearly (§73) and stays
  usable offline (AC-MP05).

## M206 — Build + test evidence

Scope:
- Run both `xcodebuild` builds and `swift test` on the M5 Max; capture output;
  log evidence into [docs/implementation-status.yaml](../../docs/implementation-status.yaml)
  and this file's verification log; state explicit gaps (no device testing,
  no live SSO until S104 lands).

## Verification Log

*(updated per task completion — commands, results, gaps)*
