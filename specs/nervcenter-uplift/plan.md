# NerveCenter Uplift — Phased Plan

**Spec:** [spec.md](./spec.md) · **Tasks:** [tasks.md](./tasks.md)

Phases are ordered by **user-visible impact**: users see the web first, then mobile, then the contract/deployment underneath, and finally the subsystems that widen access. Each phase lists the existing specs it reuses (reference, not duplication).

Phase 1 and Phase 3 can proceed in parallel (different file owners: `web/src/**` vs `backend/**` + contract tests), but Phase 1's *live-mode* acceptance (T311) depends on Phase 3 stubs closing, so the plan orders them 1 → 3.

---

## Phase 1 — Web UI Completeness *(highest user-visible impact)*

Goal: the 10 §48 views render on **real data**, all §49/§50/§51 fields present, with a coherent tokenized design system, professional icons, full error/empty/loading states, baseline accessibility, and a working build.

| Step | Requirements | Notes |
|---|---|---|
| 1.1 Repair Tailwind build (resolve the v3/v4 hybrid) | R001 | Unblocks CSS; must land before tokens are meaningful |
| 1.2 Design-token system + dark surface hierarchy | R002, R014 | One place to define; reused everywhere |
| 1.3 Professional icon system replacing emoji nav | R003 | Small change, high polish payoff |
| 1.4 Error/empty/loading/success/disabled states in all views | R004, R008 | Includes Ask pending indicator + provenance |
| 1.5 Wire views to real API + WebSocket/SSE | R006, R011, R016 | Uses existing `useRealtimeUpdates.ts`/`WebSocketClient.ts` |
| 1.6 Overview to full §49 (10 fields) | R007 | Depends on R201 stubs (Phase 3) for live values |
| 1.7 Task DAG 7-state distinction + graph layout | R009 | Per §50 |
| 1.8 Inference to full §51 (10 fields) | R010 | Depends on `/models/history` + `fallbacks24h` |
| 1.9 Accessibility baseline (ARIA/focus/reduced-motion) | R005 | Cross-cutting; land states first |
| 1.10 Unify auth to SSO only; prune dead deps | R012, R013 | Removes localStorage-token path; drops `axios` |
| 1.11 Keep the §83 web stack (no framework swap) | R015 | Guardrail, verified at build |

**Reused specs:** `specs/web-quality-audit` (design bar), `specs/sso-integration` (auth design of record).
**Exit gate (Phase 1):** task T308 gate (`npm run build` clean) + live-data checks T309/T311.

## Phase 2 — Mobile Apps *(iPhone + Watch completion)*

Goal: the iPhone and Watch targets — currently empty shells on top of the compiling `NerveShared` SDK — become the core supported clients of §52.

| Step | Requirements | Notes |
|---|---|---|
| 2.1 iPhone six tabs + Overview | R101 | §56 |
| 2.2 iPhone incident view contract | R102 | §59, full detail set |
| 2.3 iPhone Ask (provenance) | R103 | mirrors web Ask |
| 2.4 Notifications (3 classes) + Live Activities | R104, R105 | §60–§61 |
| 2.5 iPhone widgets (S/M/L) | R106 | §62 |
| 2.6 iPhone cache (offline usefulness) | R107 | §73 |
| 2.7 Watch: 7 goals + home states + emergency controls | R110, R111, R113 | §63/§64/§67 |
| 2.8 Watch approval policy + biometric deep-link | R112, R108 | §66; reversible-low-risk only |
| 2.9 Watch complications + synced state + stale markers | R114, R115 | §68/§69; Watch cache §73 (R116) |
| 2.10 Device pairing → Keychain (no manual token copy) | R109 | §71 |

**Reused specs:** `specs/mobile-apps` (app architecture + shared SDK), `specs/mobile-quality-audit` (quality baseline).
**Exit gate (Phase 2):** apps build on M5 Max (existing T204 pattern), MVP scenario AC440 demonstrable end-to-end.

## Phase 3 — Backend Contract Gaps *(unblocks real data)*

Goal: close the endpoints/fields the web views and MVP scenario require, and fix the redirect blocker.

| Step | Requirements | Notes |
|---|---|---|
| 3.1 Implement the 4 CONTRACT_GAPS stubs | R201 | `/models/history`, `fallbacks24h`, `estimatedDuration`, ask provenance |
| 3.2 Evidence service stays intentional-raise | R202 | no caller assumes success |
| 3.3 Alembic FK order preserved; no direct DB writes outside migrate.py | R203 | decisions before planned_changes FK targets |
| 3.4 T208 — API honors X-Forwarded-Proto (no http 307) | R204, R401 | unblocks live `/api/*` over https |

**Reused specs:** `specs/nervecenter-deploy` (owns T208 execution + K8s/ingress), plus `web/CONTRACT_GAPS.md` (living gap list, preserved per R205).
**Exit gate (Phase 3):** `.venv/bin/python -m pytest tests/ -m "not integration" -q` green (9 unit tests) + `curl -L …/api/events` → 200.

## Phase 4 — Missing Subsystems *(scoped; mostly follow-up specs)*

Goal: scope (and where cheap, trace) the subsystems the specs audit flags as absent, so the uplift is complete-by-reference.

| Step | Requirements | Notes |
|---|---|---|
| 4.1 CLI (§47) | R301 | → `specs/nervecenter-deploy` T102 |
| 4.2 MCP server + Python/TS SDKs | R302 | follow-up under frozen §85 contracts |
| 4.3 Inference planes: context, policy, guardrails | R303 | follow-up spec (Phase-4 "Inference Intelligence") |
| 4.4 Synthetic lab (deterministic demo) | R304 | → deploy T203 |
| 4.5 Record MVP end-to-end scenario as the trace target | R305 | §100–§101 |

**Reused specs:** `specs/nervecenter-deploy` (T102, T203), plus references to `docs/nervcenter-spec.md` (note spelling **nervcenter**).
**Exit gate (Phase 4):** references resolved and recorded in tasks.md; no un-owned coverage gap.

## Phase 5 — Deployment *(close T207/T208 + real-mode bundle)*

Goal: the deployed system is reachable publicly and serves real data over https.

| Step | Requirements | Notes |
|---|---|---|
| 5.1 T207 — public DNS/tunnel for nervous domain | R402 | `nervecenter.celestium.life` NXDOMAIN today |
| 5.2 T208 verified live (redirects fixed) | R401, R204 | deploy spec owns, this spec traces |
| 5.3 Deployed bundle in real mode, live Overview | R403, R011 | `VITE_API_BASE` baked into image (deploy T206) |

**Reused specs:** `specs/nervecenter-deploy` (deployment + verification log).
**Exit gate (Phase 5):** T207 chosen access path loads the UI; T208 curl → 200; deployed Overview shows live (non-fixture) data.

---

## Cross-cutting contracts (unchanged, verified at gate)

- `.venv/bin/python -m pytest tests/ -m "not integration" -q` — 9 passing unit tests post-migration (R206).
- Alembic FK order: `decisions` before `planned_changes` FK targets (R203).
- No direct DB writes outside `backend/persistence/migrate.py` (R203).
- CLI entrypoint `cli/_main.py` wiring preserved (R206).
- `web/CONTRACT_GAPS.md` preserved and kept current (R205).
- `cmap-topology-26.json` is **not** a contract (unconsumed ARP artifact).

## Phase ordering rationale

- **1 before 2**: web is the surface users see first; mobile reuses the same real APIs, so Phase 1's contract wiring validates against the Phase 3 stubs before mobile is built on top.
- **3 parallel-safe with 1**: different owners (`backend/**` vs `web/src/**`); merge after stubs land so web live-mode steps (T309/T311) can run.
- **4 is scoping, not build**: it does not gate 1–3 or 5; it runs concurrently as reference work.
- **5 last**: deployment is only meaningful once web is real-mode (Phase 1) and T208/contract are fixed (Phase 3).
