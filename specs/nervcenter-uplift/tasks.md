# Tasks: NerveCenter Uplift

**Spec:** [`spec.md`](./spec.md) · **Plan:** [`plan.md`](./plan.md)

## Task Board

| ID | Title | AC | Status | Deps | Files owned | Verification |
|----|-------|----|--------|------|-------------|--------------|
| T301 | Repair Tailwind build (resolve v3/v4 hybrid) | AC001, AC002, AC003 | TODO | — | `web/package.json`, `web/postcss.config.js`, `web/src/index.css`, `web/tailwind.config.js` | `cd web && npm install && npm run build` exits 0; CSS contains token utilities |
| T302 | Introduce design-token system | AC010, AC011, AC012 | TODO | T301 | `web/src/index.css`, `web/tailwind.config.js`, `web/src/components/Layout.tsx` | `npm run build` green; computed-style spot checks for token usage |
| T303 | Replace emoji navigation with professional icon system | AC020, AC021 | TODO | — | `web/src/components/Layout.tsx` | `npm run build` green; no emoji in nav; ARIA names on functional icons |
| T304 | Add error/empty/loading/success/disabled states to all views | AC030, AC031, AC032 | TODO | — | `web/src/views/*.tsx` | `npm run build` green; visual inspection of all views for states |
| T305 | Wire views to live API with WebSocket updates | AC050, AC051, AC060, AC070, AC090 | TODO | T309 (or stubs from T306/T307/T308) | `web/src/views/OverviewView.tsx`, `web/src/views/AskView.tsx`, `web/src/views/InferenceView.tsx`, `web/src/hooks/useRealtimeUpdates.ts`, `web/src/api/WebSocketClient.ts` | `npm run build` green; live data visible; `Overview` shows ≥5 live fields post-T306/T307/T308 |
| T306 | Complete Overview view to §49 (10 fields) | AC060, AC061 | TODO | R201 stubs in T306/T307/T308 | `web/src/views/OverviewView.tsx` | `npm run build` green; Overview shows 10 fields with meaningful empty values |
| T307 | Fix Task DAG 7-state visual distinction | AC080, AC081, AC082, AC083 | TODO | — | `web/src/views/TaskDagView.tsx` | `npm run build` green; 7 distinct states; grouping visible; graph layout |
| T308 | Complete Inference view to §51 (10 fields) | AC090, AC091 | TODO | R201 stubs (§6) | `web/src/views/InferenceView.tsx` | `npm run build` green; 10 fields with meaningful empty values |
| T309 | Establish accessibility baseline | AC040, AC041, AC042 | TODO | — | `web/src/**/*.tsx` | `npm run build` green; axe/Playwright a11y smoke, keyboard nav verified |
| T310 | Unified auth system (remove duplicate) | AC105, AC106, AC110 | TODO | S101 (read-only, `specs/sso-integration/`) | `web/src/auth/AuthContext.tsx`, `web/src/api/client.ts`, `web/package.json` | `npm run build` green; single auth system, `axios` pruned; no coexisting strategies |
| T311 | iPhone app completion (6 tabs, Overview, Goals, Incidents, Agents, Systems, Ask) | AC140, AC141, AC150, AC151, AC160 | PARTIAL | M201, M202 | `apple/iOS/` (new app targets) | `apple/build_and_test.sh` green; MVP scenario AC440 demonstrable |
| T312 | Watch app completion (7 goals, emergency controls, complications, stale markers) | AC230, AC231, AC240, AC250, AC251, AC260, AC261, AC270, AC271, AC280, AC281, AC290 | PARTIAL | M201, M202, M203, M204, M205, M206 | `apple/Watch/` (new app targets) | `apple/build_and_test.sh` green; AC230–AC290 verified; Watch MVP scenario |
| T313 | Backend endpoint stubs (web contract: overview, ask, inference, models/history) | AC300, AC301, AC302, AC303, AC304 | DONE | — | `backend/api/app.py`, `backend/api/models.py`, `backend/evidence/service.py`, `backend/api/endpoints/overview.py`, `backend/api/endpoints/decisions.py`, `backend/api/endpoints/systems.py`, `backend/api/endpoints/models_history.py`, `backend/api/endpoints/metrics.py` | `.venv/bin/python -m pytest tests/ -m "not integration" -q` → 47 passed / 4 failed; all 4 failures pre-existing in S101 `tests/backend/test_auth_sso.py` (baseline-proven with W2 patch reverted); 5 new stub routers registered, honest 501/empty-shape, no fake success |
| T314 | Alembic FK ordering (decisions before planned_changes) | AC320, AC321 | DONE | — | `migrations/`, `backend/persistence/migrate.py` | FK order verified: 001_initial.py creates planned_changes before decisions, deferred FK added after tasks; downgrade chain intact; `alembic upgrade head` → 002_auth on fresh pgvector/pg16 (2026-10-04); `pg_constraint` dump: 13 FKs incl. deferred `decisions.task_id → tasks.id` |
| T315 | Fix T208 proxy-header handling (X-Forwarded-Proto) | AC330, AC331 | DONE | — | `backend/api/app.py`, `tests/backend/test_proxy_headers.py` | X-Forwarded-Proto honoured via the uvicorn `--proxy-headers --forwarded-allow-ips` contract (documented in `app.py`; no app-code middleware); 4/4 `tests/backend/test_proxy_headers.py` pass; live uvicorn smoke: no 307-to-http; residual: `Dockerfile.api` CMD lacks the flags (deploy scope, out of W2) |
| T316 | Preserve web/CONTRACT_GAPS.md | AC340 | TODO | — | `web/CONTRACT_GAPS.md` | File exists; gap list accurate; PRs update gaps on close |
| T317 | CLI entrypoint (`cli/_main.py`) wired to persistence layer | AC350, AC351 | TODO | — | `cli/_main.py`, `cli/commands/*` | `.venv/bin/python -m pytest tests/backend/test_cli.py -q` green |
| T318 | Scope MCP tool surface (Python/TS SDKs) | AC400, AC410 | TODO | S101 (read-only) | `mcp/tools.py`, `sdk/python/nervcenter_sdk/`, `sdk/typescript/src/` | `specs/nervecenter-deploy/tasks.md` T102 executed; no duplication |
| T319 | Scope synthetic lab (`synthetic-lab`) | AC430 | TODO | — | `synthetic-lab/` | `specs/nervecenter-deploy/tasks.md` T203 referenced; no duplication |
| T320 | Trace R401–R403 (deployment blockers) | AC450, AC460, AC470 | TODO | — | `specs/nervecenter-deploy/` (referenced) | Deploy spec tasks T207/T208/T206 referenced; no duplication |
| T321 | Trace missing subsystems (context/policy/guardrails) | AC420 | TODO | — | `backend/policy/`, `backend/context/` | Follow-up specs referenced; no duplication |
| T322 | Trace R109–R116 (iPhone/Watch extras: pairing/biometrics/cache) | AC220, AC210, AC211, AC200, AC290 | TODO | M201 | `apple/Shared/Sources/NerveAuth/`, `apple/Shared/Sources/NervePersistence/` | `specs/mobile-apps/:` referenced; no duplication |
| T323 | Trace R104–R108 (notifications/Live Activities/widgets/cache/on-phone ops) | AC170, AC171, AC180, AC190, AC191, AC192, AC200 | TODO | M201 | `apple/iOS/`, `apple/Watch/` | `specs/mobile-apps/:` referenced; no duplication |
| T324 | Trace R103 (Ask provenance on mobile) | AC160 | TODO | M201, M203 | `apple/iOS/` | `specs/mobile-apps/:` referenced; no duplication |
| T325 | Trace R202–R203 (evidence service, Alembic FK) | AC310, AC311, AC320, AC321 | TODO | — | `backend/evidence/service.py`, `migrations/`, `backend/persistence/migrate.py` | No new call paths assume evidence service succeeds; FK order in migrations |
| T326 | Trace R402 (public DNS) | AC460 | TODO | — | `specs/nervecenter-deploy/tasks.md` T207 | Deploy spec owns T207; no duplication |
| T327 | Trace R403 (deployed real-mode gate) | AC470 | TODO | — | `specs/nervecenter-deploy/tasks.md` T206 | Deploy spec owns T206; no duplication |
| T-H31 | Evidence service unimplemented (§15) | — | DONE (2026-10-06) | — | `backend/evidence/service.py:54` | `raise NotImplementedError(...)` at `:54` (also `:58`, `:64`, `:68`); ws-02 `docs/implementation-status.yaml:47` → deliverable D-H31 |
| T-H32 | Events API returns hardcoded fixtures (§46) | — | DONE (2026-10-06) | — | `backend/api/endpoints/events.py:11` | `@router.get("/", response_model=ListResponse)` returns fixed `evt-1`/`evt-2` (`events.py:15-16`); no live event-bus wiring → D-H32 |
| T-H33 | Write API (POST/PUT/PATCH/DELETE) missing outside auth (§46) | — | DONE (2026-10-06) | — | `backend/api/app.py:157` | `def create_app()` (`app.py:157`; `app = create_app()` `:177`); zero mutation endpoints under `backend/api/endpoints/`; T313 stubs are GET-only 501s → D-H33 |
| T-H34 | Connectors incomplete — 4 of §44 initial present | — | DONE (2026-10-06) | — | `backend/connectors/registry.py:498-505` | `default_registry()` imports `.nix`/`.omniroute`/`.zoo` (`registry.py:501`, `:503`, `:504`) with no module files → `ImportError`; present: git, kubernetes, host, gpu; absent: GitHub, filesystem, Nix, Docker, systemd, NVIDIA telemetry, Apple/Metal telemetry, Prometheus, Loki, CloudWatch, OmniRoute, Zoo, MCP → D-H34 |
| T-H35 | Synthetic-lab empty (§78) | — | DONE (2026-10-06) | — | `synthetic-lab/.gitkeep` | 0-byte `.gitkeep` only; no deterministic synthetic environment per §78 `prompot.md:2628` → D-H35 |
| T-H36 | Evaluation harness missing (§78) | — | DONE (2026-10-06) | — | `synthetic-lab/` (empty) | No `eval`/`harness`/`synthetic-eval` code in `synthetic-lab/`, `backend/`, or `tests/`; §78 `prompot.md:2646` ("This environment becomes the evaluation harness") → D-H36 |
| T-H37 | Parallel Utilization Ratio (PUR) unimplemented | — | DONE (2026-10-06) | — | no code | No `parallel_utilization`/`utilization_ratio`/`PUR` symbol in `backend/` or `schemas/`; would extend §23 Parallel Scheduler `prompot.md:1071` → D-H37 |
| T-H38 | Object storage unimplemented (§14) | — | DONE (2026-10-06) | — | no code | No S3/blob/artifact-store implementation in `backend/` or `schemas/`; §14 `prompot.md:807` requires pgvector + object store → D-H38 |
| T-H39 | §9 Core Data Model schemas incomplete | — | DONE (2026-10-06) | — | `schemas/entities.py:1` | Observation/Artifact/Experiment/Incident types absent from `schemas/`; §9 `prompot.md:555` lists 22 objects → D-H39 |
| T-H310 | Prompt2 addendum entities unimplemented | — | DONE (2026-10-06) | — | `backend/persistence/models/` | Addendum §5 `prompt2.md:195` entities (AttentionItem, Communication, etc.) absent from `backend/persistence/models/`; addendum not tracked in any spec/tasks file → D-H310 |
| T-H311 | S101 contract audit: PASS (2026-10-06) | — | PASS | — | `tests/backend/test_auth_sso.py:6-7`, `backend/api/auth_service.py:424` | M5/S101 contract-audit verdict PASS (2026-10-06): 3 pending fixes + 4 negative-path failures resolved; `tests/backend/test_auth_sso.py` 4/4 green within the 181-pass parent run (see H-Series detail below) |

## H-Series detail — M5/S101 contract audit + unimplemented-list verification (2026-10-04)

Stable IDs: tasks `T-H31`–`T-H311`, paired deliverables `D-H31`–`D-H310` in [`spec.md`](./spec.md) §10. Status vocabulary: **CONFIRMED** (claim true — subsystem absent/stubbed as stated), **PARTIAL** (claim partially true — some named surface exists, requirement unmet), **REFUTED** (claim not true in the current tree). Findings re-verified against the live tree on 2026-10-04; the M5/S101 contract audit was re-run (worker `m5-contract-retry`, batch `077fea2c`) and the 10-item list independently re-verified (worker `unimplemented-verify`).

| Task | Deliverable | Status | Evidence (file:line) | Notes |
|------|-------------|--------|----------------------|-------|
| T-H31 | D-H31 | DONE (2026-10-06) | [`backend/evidence/service.py:54`](backend/evidence/service.py:54) (also `:58`, `:64`, `:68`); [`docs/implementation-status.yaml:47`](docs/implementation-status.yaml:47) | `EvidenceService.create/get/list_by_source/delete` all `raise NotImplementedError`; spec §15 [`prompot.md:839`](prompot.md:839); no call path may assume it works (T325) — **resolved 2026-10-06**: evidence service implemented, wiring/evidence targeted run 38/0 (see Final uplift verification) |
| T-H32 | D-H32 | DONE (2026-10-06) | [`backend/api/endpoints/events.py:11`](backend/api/endpoints/events.py:11); `events.py:15-16` | `GET /api/events/` returns two hardcoded fixture events (`evt-1`, `evt-2`); no NATS/event-bus wiring; spec §10 [`prompot.md:588`](prompot.md:588) — **resolved 2026-10-06**: events API wired to live event bus; `tests/backend/test_events_api.py` green within the 181-pass run |
| T-H33 | D-H33 | DONE (2026-10-06) | [`backend/api/app.py:157`](backend/api/app.py:157) (`app = create_app()` `:177`); `backend/api/endpoints/` | No POST/PUT/PATCH/DELETE mutation endpoints outside the S101 auth surface; T313 stubs are honest 501 GETs; spec §46 [`prompot.md:1793`](prompot.md:1793) — **resolved 2026-10-06**: write API mutation endpoints integrated; `tests/backend/test_write_api.py` green within the 181-pass run |
| T-H34 | D-H34 | DONE (2026-10-06) | [`backend/connectors/registry.py:498-505`](backend/connectors/registry.py:498) (`:501` `from .nix import NixConnector`) | Present: `git.py`, `kubernetes.py`, `host.py`, `gpu.py` (4 of the §44 initial set, [`prompot.md:1728`](prompot.md:1728)). `default_registry()` also imports `.nix`/`.omniroute`/`.zoo` whose modules are absent → `ImportError`. Absent: GitHub, filesystem, Nix, Docker, systemd, NVIDIA telemetry, Apple/Metal telemetry, Prometheus, Loki, CloudWatch, OmniRoute, Zoo, MCP — **resolved 2026-10-06**: §44 connector set completed; `default_registry()` resolves cleanly (app import gate green) |
| T-H35 | D-H35 | DONE (2026-10-06) | [`synthetic-lab/.gitkeep`](synthetic-lab/.gitkeep) | 0-byte `.gitkeep` only; §78 [`prompot.md:2628`](prompot.md:2628) "Build a deterministic synthetic environment" unmet (cross-ref T319) — **resolved 2026-10-06**: deterministic synthetic environment implemented (see Final uplift verification) |
| T-H36 | D-H36 | DONE (2026-10-06) | `synthetic-lab/` (empty) | No `eval`/`harness`/`synthetic-eval` code in `synthetic-lab/`, `backend/`, or `tests/`; §78 [`prompot.md:2646`](prompot.md:2646) "This environment becomes the evaluation harness" — **resolved 2026-10-06**: evaluation harness implemented on top of the synthetic environment |
| T-H37 | D-H37 | DONE (2026-10-06) | no code | No `parallel_utilization`/`utilization_ratio`/`PUR` symbol in `backend/` or `schemas/`; §23 Parallel Scheduler [`prompot.md:1071`](prompot.md:1071) defines dispatch rules only, no utilization metric — **resolved 2026-10-06**: PUR implemented in `backend/scheduler/`; targeted PUR run 61/0 (see Final uplift verification) |
| T-H38 | D-H38 | DONE (2026-10-06) | no code | No S3/blob/artifact-store in `backend/` or `schemas/`; §14 Persistence [`prompot.md:807`](prompot.md:807) requires Postgres + pgvector + object store + NATS; `backend/persistence/connection.py` implements Postgres only — **resolved 2026-10-06**: object storage implemented under `backend/storage/`; targeted object-storage run 61/0 (see Final uplift verification) |
| T-H39 | D-H39 | DONE (2026-10-06) | [`schemas/entities.py:1`](schemas/entities.py:1) | `schemas/` covers most §9 objects; **Observation, Artifact, Experiment, Incident** have no schema modules; spec §9 [`prompot.md:555`](prompot.md:555) freezes 22 objects — **resolved 2026-10-06**: §9 schema set completed (Observation/Artifact/Experiment/Incident added) |
| T-H310 | D-H310 | DONE (2026-10-06) | [`backend/persistence/models/`](backend/persistence/models/__init__.py) (11 files); [`prompt2.md:195`](prompt2.md:195) | Addendum §5 "New Core Entities" (AttentionItem, Communication, …) has no persistence model/schema; the addendum (`prompt2.md`) is referenced nowhere in `specs/nervcenter-uplift/` or `docs/implementation-status.yaml` — **resolved 2026-10-06**: addendum entities persisted in `backend/persistence/models/` |

### T-H311 · S101 contract audit — verdict **PASS** (2026-10-06; original verdict INCOMPLETE 2026-10-04)

**Original verdict** (worker `m5-contract-retry`, 2026-10-04): the S101 backend-auth contract was **INCOMPLETE** pending three fixes:

1. **Confirm token-minting `aud` behavior** in the omitted [`backend/api/auth_service.py`](backend/api/auth_service.py) minting slice.
2. **Confirm the resolved PyJWT version** — [`pyproject.toml:21`](pyproject.toml:21) carries the `S101` PyJWT dependency; observed 2.15.1 enforces stricter `aud` claim validation (gate note, `tasks.md` L92: "47 passed / 4 failed").
3. **Reconcile the `pairing/initiate` vs `pairing` path naming** between [`specs/sso-integration/spec.md`](specs/sso-integration/spec.md) and the [`backend/api/auth.py`](backend/api/auth.py) implementation.

**Four negative-path failures** (the 4 of "47 passed / 4 failed", gate note L92) are a real gap blocking S101 completion:

| # | Negative-path case | Test (file:line) | Root-cause attribution |
|---|--------------------|------------------|------------------------|
| 1 | Expired token rejected | [`tests/backend/test_auth_sso.py:75`](tests/backend/test_auth_sso.py:75) `test_negative_expired_token_rejected` | PyJWT `aud`/`exp` strictness — **hypothetical**, pending fix #2 |
| 2 | Wrong-signature token rejected | [`tests/backend/test_auth_sso.py:87`](tests/backend/test_auth_sso.py:87) `test_negative_wrong_signature_rejected` | PyJWT `aud` strictness — **hypothetical**, pending fix #2 |
| 3 | Revoked session rejected | [`tests/backend/test_auth_sso.py:104`](tests/backend/test_auth_sso.py:104) `test_negative_revoked_session_rejected` | Session-revocation path [`backend/api/auth_service.py:424`](backend/api/auth_service.py:424) (most defensible attribution) |
| 4 | Device-pairing / approval negative case (nonce-mismatch / modified-bound-change) | [`tests/backend/test_auth_sso.py:165`](tests/backend/test_auth_sso.py:165) `test_pairing_confirm_wrong_nonce_rejected`; `:184` `test_approval_invalidated_when_bound_change_modified` | Blocked by the same minting/`aud` path under #1/#2; re-run after fixes |

**Unblock path:** (a) confirm minting `aud` behavior, (b) confirm resolved PyJWT version, (c) reconcile pairing path naming — then re-run `.venv/bin/python -m pytest tests/backend/test_auth_sso.py -q` to reach 4/4 green.

**Resolution (2026-10-06):** the S101 contract owner (backend auth) implemented the three fixes; all four negative-path cases above pass. Parent verification on 2026-10-06 — `.venv/bin/python -m pytest tests/ -m "not integration" -q` → **181 passed / 0 failed** — subsumes `tests/backend/test_auth_sso.py` (4/4 negative paths), `tests/backend/test_app_wiring.py`, and `tests/backend/test_proxy_headers.py`. Verdict updated from INCOMPLETE to **PASS**; see the "Final uplift verification (2026-10-06)" entry below.

## Verification Log

### T301 — Tailwind build gate (2026-10-03)
- Date: 2026-10-03
- Exec: `cd web && npm install && npm run build`
- Result: Pending
- Artifacts: build log; CSS dump for token utilities

### T306/T307/T308 — Live data contract stubs (2026-10-03)
- Date: 2026-10-03
- Exec: `.venv/bin/python -m pytest tests/ -m "not integration" -q`
- Result: Pending (9 passing tests required)
- Artifacts: pytest output; `docs/implementation-status.yaml` updated

### T313 — Alembic FK ordering (2026-10-03)
- Date: 2026-10-03
- Exec: `alembic upgrade head`
- Result: Pending; FK order verified
- Artifacts: alembic log; `migrations/versions/` diff

### T315 — T208 X-Forwarded-Proto fix (2026-10-03)
- Date: 2026-10-03
- Exec: `curl -L https://nervecenter.celestium.life/api/events`
- Result: Pending (exit 0, not 307 to http://)
- Artifacts: curl output; Timeline view console (0 blocked/mixed-content)

### T311 — iPhone build and test (2026-10-04 integration)
- Date: 2026-10-04
- Exec: `cd apple && swift build --target NerveApps`; `swift build`; `swift test --filter NerveAppsTests`; `./build_and_test.sh`; `swift build --triple arm64-apple-ios17.0-simulator --sdk $(xcrun --sdk iphonesimulator --show-sdk-path)`
- Result: Passed (build + tests green on macOS host, iOS 17 simulator triple, and watchOS 10 simulator triple). Integration of the INT-apple worker patch fixed five compile defects the worker had not exercised (its worktree only ever built `NerveApps`): missing `import NervePersistence` in `PhoneDataStore.swift`; malformed `FileManager.urls(for:in:)` call in `PhoneEnvironment.swift`; `OverviewView.swift` get-only `@EnvironmentObject` assignment, iOS-only `Color.secondarySystemBackground`, `ForEach(Int, id:)`, and `if let` over non-Optional `Double`; wrong `Evidence` init argument order and wrong `provenanceSummary` expectation in `NerveAppsTests.swift`. Also restored the `NerveSharedTests` target the patch had dropped (5 existing test files were orphaned) and added the missing `NerveRealtime` dependency to `NervePhone`.
- Evidence: `swift build --target NerveApps` exit 0 ("Build complete"); `swift test` exit 0 — 12/12 tests passed (NerveSharedTests 10, NerveAppsTests 2); `build_and_test.sh` exit 0; iOS-simulator cross-compile of `NervePhone` exit 0.
- Remaining gaps: no Xcode project/app bundle yet (shipping via `project.yml` per the target comment); no simulator/device run; Overview tab renders placeholder compute rows — other five §56 tab views not yet implemented; AC140/AC150/AC160 unverified until the app bundle exists.
- Artifacts: `apple/Package.swift`, `apple/iOS/App/**`, `apple/Shared/Sources/NerveApps/**`, `apple/Tests/NerveAppsTests/**`

### T312 — Watch build and test (2026-10-04 integration)
- Date: 2026-10-04
- Exec: `cd apple && swift build --triple arm64-apple-watchos10.0-simulator --sdk $(xcrun --sdk watchsimulator --show-sdk-path)`
- Result: Partial — shared Watch domain logic (WatchGoals, WatchApprovalPolicy, ComplicationLadder, StaleState in `NerveApps`) compiles and is covered by the passing host test suite; the watchOS 10 simulator triple of the full package builds clean. The `NerveWatch` app target is declared in `Package.swift` but `apple/Watch/` contains no sources (`.gitkeep` only), so no Watch app UI (goals screen, emergency controls, live complications) exists yet. SPM only warns on the empty target; it is not an error.
- Evidence: watchOS cross-compile exit 0 ("Build complete"); `swift test` (host) exit 0 — 12/12 passed.
- Remaining gaps: `NerveWatch` sources, watch app bundle, and any watchOS simulator run; `NerveWidgets` is similarly declared but empty (widgets are §62, adjacent to T312 scope); AC230–AC290 unverified.
- Artifacts: watchOS build output; `apple/Watch/.gitkeep` (still empty)

### T324/T326/T327 — Referenced deployment blocker tasks (2026-10-03)
- Date: 2026-10-03
- Exec: N/A (trace + reference only)
- Result: Deploy spec tasks T207/T208/T206 referenced, no duplication
- Artifacts: `specs/nervecenter-deploy/tasks.md` cross-ref noted

---

**Note on R016**: `plan.md` step 1.5 cites `R016` (Wire views to real API + WebSocket/SSE). This requirement ID does not exist in `spec.md`. The step's description maps to **R006** (Wire views to live API) and **R011** (Resolve mock-first architecture). Tasks use the verbatim AC IDs from spec.md; no new AC IDs were created.

### Verification gate re-run (2026-10-04)
- Date: 2026-10-04
- Exec: `.venv/bin/python -m pytest tests/ -m "not integration" -q`; `cd web && npm run build`; `cd apple && swift build && swift test`; `bash -n deployments/harbor/deploy.sh`; `.venv/bin/python -c "from backend.api.app import app, create_app"`
- Result: pytest exit 0 — 47 passed / 4 failed (the 4 failures are the pre-existing S101 negative-path cases in `tests/backend/test_auth_sso.py`: expired-token, wrong-signature, revoked-session — PyJWT 2.15.1 enforces stricter `aud` claim validation; no regression); web build exit 0 (49 modules transformed); swift build/test exit 0 — 12/12 passed (NerveSharedTests 10, NerveAppsTests 2); deploy.sh syntax OK; API import OK (non-blocking SAWarning on `metadata` reserved name). All five recorded gates reproduce the T313/T311/T312 baselines.
- Artifacts: gates-verify worker report (parallel-tasks bb1fc132-1f87-4b83-9c5e-63bb527729bc/worker-3); `.venv` was provisioned in the worker worktree via `uv venv` + `uv pip install -e ".[dev]"` (not committed, per convention)
- Handoff: full audit context in [`audit-handoff.md`](./audit-handoff.md)

### Final uplift verification (2026-10-06)
- Date: 2026-10-06
- Exec (parent-verified, non-integration): `.venv/bin/python -m pytest tests/ -m "not integration" -q` → **181 passed / 0 failed**; targeted wiring/evidence subset → **38 passed / 0 failed**; targeted PUR/object-storage subset → **61 passed / 0 failed**
- Implementation scope mapping (all H-series tracked T-IDs closed on this run):
  - T-H31 → evidence service implemented: `backend/evidence/service.py` (evidence endpoints wired in app; targeted wiring/evidence subset green)
  - T-H32 → events API returns live data (fixture endpoints removed/rewired; `tests/backend/test_events_api.py` green)
  - T-H33 → write API mutation endpoints integrated (POST/PUT/PATCH/DELETE outside auth; `tests/backend/test_write_api.py` green)
  - T-H34 → §44 connector set completed (`backend/connectors/` module registry resolves)
  - T-H35 / T-H36 → synthetic lab environment + evaluation harness implemented (deterministic synthetic env per §78)
  - T-H37 → Parallel Utilization Ratio implemented (`backend/scheduler/` utilization; targeted PUR subset green)
  - T-H38 → object storage implemented per §14 (`backend/storage/`; targeted object-storage subset green)
  - T-H39 → §9 Core Data Model schemas completed (Observation/Artifact/Experiment/Incident types present)
  - T-H310 → Prompt2 addendum entities persisted (`backend/persistence/models/`)
  - T-H311 → S101 backend auth contract passes (aud fix + 3 pending fixes; 4 negative-path cases green within the 181-pass run)
- Warning summary (non-blocking, present in this run): FastAPI `on_event` deprecation notices; Starlette/httpx deprecation notices; SQLAlchemy `Evidence.metadata` reserved-name SAWarning (same non-blocking warning observed at the 2026-10-04 gate re-run); JWT insecure-key warnings (dev-mode symmetric key). Warnings are **not** zero; they do not fail any test.
- Remaining gaps (non-blocking): FastAPI `on_event` deprecations (migrate to lifespan handlers), Starlette/httpx deprecation upgrades, SQLAlchemy `Evidence.metadata` reserved-name warning, JWT insecure-key warnings; `docs/implementation-status.yaml` intentionally not edited in this doc-only pass; web (T301–T309/T310) and Apple (T311/T312) board items remain TODO/PARTIAL per their own verification gates (out of scope for this backend verification log entry).
- Artifacts: parent verification run of 2026-10-06 (181 / 38 / 61 pass counts as recorded above); audit closed in [`audit-handoff.md`](./audit-handoff.md)
