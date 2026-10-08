# Plan: iPhone & Watch App Targets

**Feature:** mobile-apps · **Spec:** [`spec.md`](./spec.md) · **Tasks:** [`tasks.md`](./tasks.md)

## Ground Truth (2026-10-01)

| Area | State | Evidence |
|------|-------|----------|
| App targets | None: [apple/iOS](../../apple/iOS) contains only `.gitkeep`; `apple/Watch/.gitkeep` exists but no watchOS target; `apple/Widgets/.gitkeep` dormant | `apple/**` tree |
| Shared SDK | Compiles green (AC009-style gate); NerveAPI/NerveAuth/NervePersistence/NerveDesign/NerveModels/NerveRealtime all present ([apple/Shared/Sources](../../apple/Shared/Sources)) | file inspection |
| Auth primitives | Pairing/biometric/credential primitives exist; SSO client (M101), Keychain store (M102), bound approval (M103) owned by [specs/mobile-quality-audit](../mobile-quality-audit/tasks.md) | file inspection |
| State contract | Staleness contract (M105) owned by mobile-quality-audit; targets consume it | file inspection |
| Build host | M5 Max macOS; `xcodebuild` available (AC009 gate precedent) | repo docs |

## Architecture Decisions

1. **Targets live in the Swift package:** `apple/Package.swift` gains
   executable targets `NervePhone` (iOS) and `NerveWatch` (watchOS); the
   package is the single build unit so the AC009-style gate covers everything.
2. **SwiftUI only**, no third-party UI deps; design tokens come from
   [NerveDesign/Tokens.swift](../../apple/Shared/Sources/NerveDesign/Tokens.swift).
3. **Data flow:** views → `NerveAPI` client (transport injectable,
   `MockTransport` for previews/tests) → `NervePersistence` cache with the
   M105 staleness contract → `NerveAuth` for SSO/pairing/Keychain/biometric.
   No fabricated data in shipped views; preview data stays in `#Preview`
   closures and tests.
4. **LAContext implementation** of `BiometricAuthenticator` lives in the iOS
   target (LocalAuthentication is not available on the watch); the watch uses
   pairing-confirmed authorization only.
5. **Complication** renders the §69 compact state in the §68 fixed priority
   order; the watch cached-state view marks staleness per §73.
6. **Server configuration** (§70): manual entry with connection test always
   available; Bonjour discovery best-effort and optional.

## Dependency Graph

```text
M101/M102/M103/M105 SDK contracts (mobile-quality-audit) ──┐
M201 package targets + entry points ────────────────────────┼──► M206 build + evidence
M202 iPhone status surfaces ────────────────────────────────┤
M203 approval inbox + biometric gate ───────────────────────┤
M204 pairing + server config ───────────────────────────────┤
M205 watch complication + cached state ─────────────────────┘
```

M201 first (targets must exist), then M202–M205 in one Apple worker sequence
(single owner of `apple/**`), M206 last. SDK contracts come from
mobile-quality-audit tasks (M101–M105) — read-only here.

## File Ownership

| Owner task | Paths |
|-----------|-------|
| M201–M205 (one Apple worker) | `apple/Package.swift`, `apple/iOS/**`, `apple/Watch/**` |
| M206 | evidence only: `apple/e2e-artifacts/**`, `docs/implementation-status.yaml`, `specs/mobile-apps/tasks.md` |
| M101–M105 (cross-ref) | `apple/Shared/**` — read-only for app targets |

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| watchOS simulator destination naming varies | Use `generic/platform=watchOS Simulator`; fall back to a listed destination if needed; state gaps |
| SDK contracts (M101–M105) not yet merged | Targets compile against protocols; `MockTransport`/`InMemory` implementations keep tests green; live SSO stays pending until S104 |
| No device testing | Simulator builds + unit tests only; gaps stated explicitly in evidence |
| SwiftPM iOS/watchOS executable targets need bundle resources | Keep assets minimal; if the package layout fights app targets, split to `apple/iOS/NervePhone.xcodeproj` and document the deviation |
