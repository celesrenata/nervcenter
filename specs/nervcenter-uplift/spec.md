# NerveCenter Uplift — Specification

**Status:** draft · **Created:** 2026-10-03
**Standard:** `prompot.md` (3565 lines, 114 sections) is the authoritative product standard. Section citations below (`§49`, `§52`, …) refer to it.
**Companion docs:** [plan.md](./plan.md) · [tasks.md](./tasks.md)

---

## 1. Problem Statement

A first draft of the NerveCenter application exists and partially works, but four independent read audits found it materially incomplete against the product standard:

1. **Web frontend** — 11 verified defects (below), the head of which is a hybrid Tailwind v3/v4 configuration that likely breaks stylesheet generation at build, plus emoji navigation, zero accessibility, no error/empty states, mock-first data, and dual coexisting auth systems.
2. **Mobile** — `apple/` contains only the shared `NerveShared` Swift SDK (compiles per T204). The iPhone app, Watch app, and Widget targets are empty shells.
3. **Backend contract** — view-facing endpoints are only partially implemented (`web/CONTRACT_GAPS.md`; `docs/implementation-status.yaml`), the evidence service intentionally raises `NotImplementedError`, and two deployment blockers (T207, T208) are open.
4. **Missing subsystems** — CLI, MCP server, SDKs, and several inference-plane subsystems are tracked in other specs but not integrated here.

This specification drives a single, traceable uplift: (a) bring the web UI to the project's web-quality bar and to its §48–§51 data requirements, (b) complete the iPhone and Watch applications, (c) close the backend contract gaps that block live views, and (d) scope the remaining subsystems — most as follow-up spec references rather than new scope.

### Scope

**In scope**

- Web frontend (`web/`) UX uplift, design-token system, and data wiring (mock → real API, realtime).
- iPhone + Watch application completion on the existing shared SDK (`apple/`).
- Backend endpoint/contract stubs required by the web views and the MVP scenario, plus the T208 proxy fix.
- Deployment close-out tasks for T207/T208 (execution lives in the deploy spec; this spec traces them).
- Follow-up-spec scoping for the missing subsystems (CLI/MCP/SDKs/inference planes/synthetic-lab).

**Out of scope**

- Full implementation of subsystems deferred to follow-up specs (see §7): `T102` (CLI/MCP/SDK), inference context/policy/guardrail planes, synthetic-lab. These are *scoped*, not *done*, here.
- Any change to canonical data contracts already frozen per §85.
- Treating `cmap-topology-26.json` (12,809-line unconsumed ARP-discovery artifact) as a contract — no code consumes it; it is explicitly **not** a contract.
- Redesign of the backend stack (§83: Python/FastAPI/PostgreSQL is correct and preserved).
- Replacing the web framework (§83 L2764-2770: TypeScript/React/WebSocket-SSE — the existing React 18 + Vite + Tailwind + React Router v6 choice is confirmed correct and is kept).

### Non-goals

- No new cloud dependencies; the system must remain useful without Internet (§82).
- No monospace-everything interface text (design rule; monospace is reserved for data values).
- No simulated backend success in the UI (web-quality rule 7).

---

## 2. Reference Documents (do not duplicate)

The following existing specs are **referenced, not re-authored**. This spec adds only the uplift delta and points at them.

| Document | Role |
|----------|------|
| `specs/sso-integration/` (spec/plan/tasks) | SSO / PKCE design of record for web auth (R101–R103). |
| `specs/web-quality-audit/` (spec/plan/tasks) | Prior web audit; source of the design-guidance bar. |
| `specs/mobile-apps/` (spec/plan/tasks) | Apple app architecture; shared-SDK target. |
| `specs/mobile-quality-audit/` (spec/plan/tasks) | Mobile quality baseline. |
| `specs/nervecenter-deploy/` (spec/plan/tasks) | Deploy + K8s + Harbor; owns T205–T208 execution and the verification log. |
| `web/CONTRACT_GAPS.md` | Live list of known backend gaps — **preserve and keep current** (R205). |
| `docs/implementation-status.yaml` | §95 workstream status; canonical T101–T104/T204 state. |
| `docs/nervcenter-spec.md` | Architecture reference (Executive Summary → Core Data Model). Note the spelling: **nervcenter**, not nervecenter. |

### ID-collision rule

Task IDs in `tasks.md` use the **T3xx** prefix (T301+) specifically to avoid colliding with the T1xx–T2xx IDs already assigned in `specs/nervecenter-deploy/tasks.md` and `docs/implementation-status.yaml`. Requirement (R) and acceptance (AC) IDs are local to this spec and are stable — never reassigned.

---

## 3. Requirements — Web Frontend

> Each requirement lists its acceptance criteria. All AC are stable IDs.

### R001 · Repair the Tailwind build (web conflict #1)
- **AC001** — `web/postcss.config.js` and `web/src/index.css` use a single coherent Tailwind version. Either (a) fully on v3 (`tailwindcss: ^3.4.7`, standard `tailwindcss` postcss plugin, `@tailwind base/components/utilities`), or (b) fully on v4 (`tailwindcss: ^4`, `@tailwindcss/postcss`, no v3 directives). The choice must be deliberate and consistent across `package.json`, `postcss.config.js`, and `index.css`.
- **AC002** — `cd web && npm install && npm run build` exits 0 and the produced CSS contains the token utilities from R002.
- **AC003** — No dead dependency remaining from the hybrid (e.g. `autoprefixer` if v4 is chosen, per R013).

### R002 · Introduce a design-token system (web conflict #3)
Prescribed token table (from web-quality guidance): body/UI ~14–16px, section heading 18–24px, spacing scale `4,8,12,16,24,32,48,64`, gutters 16–20px mobile / 24–40px desktop, reading measure 55–75ch, sidebar 14–17rem, control height 40–44px, radii family ~6/10/16px, rem units, unitless line-heights, system font stack, `tabular-nums` for comparable numbers.

- **AC010** — Tokens are declared once (in `tailwind.config.js` `theme.extend` or v4 `@theme`) and reused across components; no per-component ad-hoc color/spacing literals for the system-level values.
- **AC011** — Radii come from a small family (≈6/10/16px); fully-rounded pills are used only where meaningful.
- **AC012** — Interface text uses the system font; comparable numeric columns use `tabular-nums`; monospace is not applied to all interface text.

### R003 · Replace emoji navigation with a professional icon system (web conflict #2)
- **AC020** — `web/src/components/Layout.tsx` no longer uses emoji as nav icons; a consistent single-family icon set (coherent size/stroke) is used.
- **AC021** — Decorative icons are hidden from assistive technology; functional icons/controls carry an accessible name.

### R004 · Add error, empty, loading, success, and disabled states to every view (web conflict #4)
- **AC030** — Every view (Overview, Systems, Timeline, Goals, Task DAG, Agents, Inference, Incidents, Decisions, Ask) renders distinct loading, empty, and error states; errors are shown to the user, not logged to console only.
- **AC031** — Ask loading surfaces a visible pending indicator rather than an in-flight flag.
- **AC032** — No UI simulates a successful backend action that did not occur; success is shown only after a confirmed response.

### R005 · Establish accessibility baseline (web conflict #5)
- **AC040** — `web/src/**/*.tsx` uses `aria-*`/`role`/`tabIndex` where needed; color-only encoding is not the sole status cue (Task DAG states carry text/shape, per R009).
- **AC041** — Visible focus indicators exist; keyboard navigation has logical order and no traps.
- **AC042** — `prefers-reduced-motion` is respected; motion is short (≈120–220ms) and non-essential motion is suppressed.

### R006 · Wire views to live API with realtime updates (web conflict #6)
- **AC050** — Views fetch from the real API in deployed builds (not silent fixtures) and consume `/ws` or SSE. `web/src/hooks/useRealtimeUpdates.ts` and `web/src/api/WebSocketClient.ts` are imported by the views that need live data.
- **AC051** — `VITE_API_BASE` is baked into the deployed build (see R210 / T206 in deploy spec) so `useMockMode` is false in production.

### R007 · Complete the Overview view to §49 (web conflict #7)
§49 (L1885-1909) requires these 10 fields; current Overview shows 4 counters:

1. overall health · 2. active incidents · 3. active goals · 4. running agents · 5. task concurrency · 6. compute utilization · 7. OmniRoute activity · 8. recent deployments · 9. recent failures · 10. pending approvals.

- **AC060** — Overview renders all 10 §49 fields with truthful data (zero/missing distinguished from absent).
- **AC061** — Each metric has a clear label and, where available, a comparison/scope; no invented trends.

### R008 · Fix the Ask provenance/UX gap (web conflict #4 data facet)
- **AC070** — Ask shows provenance with evidence inspectable, matching §58 ("Answers retain provenance. Evidence is inspectable.") and Phase 2 Ask Reality (evidence-backed answers).
- **AC071** — Pending/success/error states are visible in Ask (overlaps R004).

### R009 · Fix Task DAG state visual distinction (web conflict #8, per §50)
- **AC080** — All seven §50 states (PENDING READY RUNNING BLOCKED VERIFYING SUCCEEDED FAILED) are rendered with distinct, non-color-only styles. `SUCCEEDED` and `RUNNING` must not share `bg-green-500`.
- **AC081** — Concurrent execution is visibly obvious (per §50 "Concurrent execution must be visually obvious").
- **AC082** — The non-standard `CANCELLED` state is reconciled: either dropped if the backend has no such state, or explicitly documented as a superset with consistent rendering.
- **AC083** — A graph/dependency layout (not a bare list) renders the DAG.

### R010 · Complete the Inference view to §51 (web data requirement)
§51 (L1931-1946) requires: physical nodes, loaded models, OmniRoute routes, active inference calls, tokens/sec, context usage, latency, failures, fallbacks, historical model performance.

- **AC090** — Inference renders all 10 §51 fields; missing values show a meaningful empty value (e.g. "Not recorded"), not a bare gap.
- **AC091** — Historical model performance surfaces depend on the `/models/history` backend endpoint (see R201 / CONTRACT_GAPS).

### R011 · Resolve mock-first architecture (web conflict #9)
- **AC100** — Default development mode may still use fixtures for offline work, but the *deployed* build fetches from `/api` (per T206 in deploy spec) and the UI clearly does not silently fall back to fixtures when a live call fails (errors surface via R004).

### R012 · Unify auth to a single system (web conflict #10)
- **AC105** — Exactly one auth system remains in `web/`: PKCE-SSO with sessionStorage (the SSO spec's security model), per `specs/sso-integration/`. The localStorage-token simple login is removed or superseded and no longer coexisting.
- **AC106** — `prompot.md` prescribes no specific web auth/SSO, so the SSO spec is the design of record; this requirement only de-duplicates, it does not invent a new auth scheme.

### R013 · Remove dead dependencies (web conflict #12)
- **AC110** — `axios` removed from `web/package.json` (client uses `fetch`); any other unused dependency is pruned; `npm audit`/install is clean.

### R014 · Tokenize the dark-mode surface hierarchy (web conflict #11)
- **AC120** — Dark theme uses distinguishable surface layers (canvas / surface / elevated) and visible control boundaries — not several near-identical gray-800/700 fills (design guidance anti-pattern).
- **AC121** — `web/CONTRACT_GAPS.md` is preserved and kept current (R205).

### R015 · Preserve the correct web stack (web conflict #13)
- **AC130** — React 18 + TypeScript + Vite + Tailwind + React Router v6 are retained (§83 L2764-2770); no framework swap.

---

## 4. Requirements — iPhone Application

> Shared `NerveShared` SDK already compiles (T204). These requirements complete the `iPhone` app target against the standard.

### R101 · Six primary tabs (§56, L2057-2068)
- **AC140** — iPhone presents the six primary tabs: Overview, Goals, Incidents, Agents, Systems, Ask.
- **AC141** — iPhone Overview matches the §57 layout (system health, agents running/waiting, compute table with device name + model + utilization, incidents, goals, pending approvals).

### R102 · Incident view contract (§59, L2131-2147)
- **AC150** — Incident detail shows: summary, timeline, affected entities, facts, hypotheses, confidence, supporting evidence, agents investigating, recommended actions, planned changes, and verification.
- **AC151** — Facts and hypotheses are visually distinguished (§82: "Claims require provenance. Facts require evidence.").

### R103 · Ask with provenance (§58, L2103-2127)
- **AC160** — Ask answers retain provenance and evidence is inspectable on iPhone (mirrors R008/R010).

### R104 · Notifications (§60, L2151-2174)
- **AC170** — Notification classes INFORMATIONAL / ACTION_REQUIRED / URGENT are implemented.
- **AC171** — Notifications fire only for the listed events (incident detected, critical task failed, goal blocked, approval required, investigation completed, deployment failure, benchmark completed, goal completed); **no** notification for routine system events.

### R105 · Live Activities (§61, L2178-2205)
- **AC180** — Live Activities shown for suitable operations (incident investigation, deployment, benchmark campaign, migration, large goal operation) with progress (e.g. investigation steps + percentage).

### R106 · iPhone widgets (§62, L2209-2237)
- **AC190** — Small widget: health + agents + incidents.
- **AC191** — Medium widget: GPU table + agents + incidents.
- **AC192** — Large widget: goal progress + compute state + incidents + agent activity.

### R107 · iPhone local cache (§73, L2500-2512)
- **AC200** — iPhone caches: systems, recent incidents, goals, agent activity, compute state, pending approvals, recent responses; app remains useful offline.

### R108 · Sensitive approval on iPhone (§72, L2478-2496)
- **AC210** — Biometric authorization (LocalAuthentication) required for sensitive operations.
- **AC211** — Authorization binds to an exact `PlannedChange` (approval_id/change_id/device_id/expires_at/nonce); any modification to the `PlannedChange` invalidates the approval.

### R109 · Device pairing / Keychain auth (§71, L2458-2474)
- **AC220** — Pairing flow iPhone → pairing challenge → NerveCenter server → device credential → Keychain; the user does not repeatedly copy API tokens.

---

## 5. Requirements — Apple Watch Application

### R110 · Seven Watch goals (§63, L2241-2259)
- **AC230** — The Watch app serves exactly: glance, alert, query, acknowledge, approve, reject, stop. It is **not** a miniature dashboard.
- **AC231** — The primary question "Does something need me?" is answered on the main surface.

### R111 · Watch home states (§64, L2263-2292)
- **AC240** — Watch home shows healthy and problem states (compact).

### R112 · Watch approval policy (§66, L2318-2355)
- **AC250** — Watch may approve LOW-RISK REVERSIBLE changes.
- **AC251** — Watch must **not** authorize: persistent storage deletion, credential mutation, production DB destructive changes, high-blast-radius infrastructure mutation, security-policy changes. Those deep-link to the iPhone.

### R113 · Emergency controls (§67, L2359-2382)
- **AC260** — STOP AGENTS: stop dispatching, cancel cancellable jobs, revoke unused mutation authorization, keep monitoring.
- **AC261** — STOP MUTATIONS: preserve read-only investigation.

### R114 · Watch complications (§68, L2386-2413)
- **AC270** — Complications for: system health, incident count, agent count, GPU state, goal progress, approval count.
- **AC271** — Priority ladder honored: urgent incident → approval required → active incident → active investigation → goal progress → general status.

### R115 · Watch synced state + stale markers (§69, L2417-2434)
- **AC280** — Watch receives the compact synchronized state JSON: `system_health`, `active_incidents`, `running_agents`, `pending_approvals`, `primary_goal_progress`, `updated_at`.
- **AC281** — Watch remains useful from cached state; **stale information is marked clearly**.

### R116 · Watch local cache (§73, L2514-2522)
- **AC290** — Watch caches: health, incidents, approvals, goal summary, compute summary.

---

## 6. Requirements — Backend Contract Gaps

> `web/CONTRACT_GAPS.md` is the running list (R205). Contracts from `docs/implementation-status.yaml` §95 apply.

### R201 · Implement/keep the documented endpoint stubs (CONTRACT_GAPS)
- **AC300** — `GET /api/models/history` returns historical model performance (feeds §51 / Inference).
- **AC301** — `GET /api/compute` response includes `fallbacks24h`.
- **AC302** — `GET /api/tasks` response includes `estimatedDuration` (feeds Task DAG).
- **AC303** — `POST /api/ask` response includes provenance (feeds Ask §58).
- **AC304** — Each stub returns well-formed typed data matching OpenAPI; no view renders an undefined field silently.

### R202 · Evidence service contract (docs §95 / ws-02)
- **AC310** — `backend/evidence/service.py` raising `NotImplementedError` for ORM integration is **intentional and preserved**; every caller catches it.
- **AC311** — No new call path is added that assumes the evidence service succeeds without handling the `NotImplementedError`.

### R203 · Alembic FK ordering (docs §95)
- **AC320** — Migrations maintain FK order: the `decisions` table is created **before** its `planned_changes` FK targets.
- **AC321** — No direct DB writes outside `backend/persistence/migrate.py`.

### R204 · Fix T208 — X-Forwarded-Proto → 307 / mixed content
- **AC330** — The API respects `X-Forwarded-Proto` so the API does not 307-redirect to `http://`. Fix owner is the deploy spec (T208); `backend/**` route/`ProxyHeaders` or `web/nginx.conf.template`.
- **AC331** — `curl -L https://nervecenter.celestium.life/api/events` → 200; web Timeline view: 0 blocked/mixed-content console errors (the deploy spec's verbatim acceptance command).

### R205 · Preserve and keep current the contract-gap doc
- **AC340** — `web/CONTRACT_GAPS.md` is never deleted; its gap list stays accurate as gaps close.

### R206 · Contract test gate (docs §95)
- **AC350** — `.venv/bin/python -m pytest tests/ -m "not integration" -q` passes (9 passing unit tests post-migration).
- **AC351** — CLI commands remain wired under `cli/commands/*` with entrypoint `cli/_main.py` calling the migrated persistence layer (frozen contract; do not disturb).

---

## 7. Requirements — Missing Subsystems (scoped; mostly follow-up specs)

These are **coverage gaps** from the specs audit. Most are already owned by other specs; this section scopes the reference so the uplift is complete-by-reference rather than duplicated.

### R301 · CLI (§47, L1831-1862)
- **AC400** — CLI target is scoped to `specs/nervecenter-deploy` `T102` (commands `nerve status/ask/entity/changes/goal/task/agents/compute/routes/incident/pause-agents/stop-mutations`; all commands support JSON output). Traced here, executed there.

### R302 · MCP server + SDKs (Python/TypeScript)
- **AC410** — MCP server and Python/TypeScript SDKs are scoped to follow-up under the API contract (`T102` lineage, §85 frozen contracts). Traced here, not implemented in this uplift.

### R303 · Inference subsystems — context plane, policy plane, guardrails
- **AC420** — Context plane, policy plane, and guardrails are scoped as follow-up specs (Phase 4 "Inference Intelligence", §90). Traced here; dependency of the Inference view's *policy explanation* (not its basic rendering).

### R304 · Synthetic lab (`synthetic-lab`)
- **AC430** — `synthetic-lab` (deterministic incident demo) is scoped to deploy spec `T203`. Traced here.

### R305 · MVP end-to-end scenario (§100-§101, L3388-3448)
- **AC440** — The final MVP scenario is satisfiable: user sees an incident on iPhone/Watch, asks what happened, a reversible remediation is proposed and approved, NerveCenter executes + verifies, and a reversible planned change **can be approved from Watch**. This is the cross-cutting acceptance the uplift must enable.
- **AC441** — MVP-complete checklist (§101 L3395-3453, including "the web UI works / CLI works / iPhone app works / Watch app works / MCP access works / a deterministic fault can be diagnosed and remediated end-to-end") is the final trace target.

---

## 8. Requirements — Deployment Blockers

### R401 · T208 — API respects `X-Forwarded-Proto`
- **AC450** — As R204: API no longer 307-redirects to `http://` behind the TLS terminating proxy. (Traces `specs/nervecenter-deploy/tasks.md` T208.)

### R402 · T207 — public DNS reachability
- **AC460** — `nervcenter.celestium.life` resolves on the public internet (currently NXDOMAIN / authoritatively private-only). Chosen access path (public tunnel / public DNS) loads the UI. (Traces `specs/nervecenter-deploy/tasks.md` T207.)

### R403 · Deployed-bundle real-mode gate (deploy D2)
- **AC470** — The deployed web bundle runs in real mode: `VITE_API_BASE` baked into the image, `Overview` shows live data (not fixtures), per deploy spec T206 acceptance.

---

## 9. Traceability Matrix

| Web conflict | Requirement | Key ACs |
|---|---|---|
| #1 Tailwind hybrid break | R001 | AC001, AC002, AC003 |
| #2 Emoji navigation | R003 | AC020, AC021 |
| #3 No design tokens | R002 | AC010, AC011, AC012 |
| #4 Error/empty states | R004 (+R008) | AC030, AC031, AC032, AC070, AC071 |
| #5 Zero accessibility | R005 | AC040, AC041, AC042 |
| #6 Static/single-fetch | R006 | AC050, AC051 |
| #7 Overview 4-of-10 | R007 | AC060, AC061 |
| #8 Task DAG states | R009 | AC080, AC081, AC082, AC083 |
| #9 Mock-first | R011 (+R006) | AC100, AC051, AC470 |
| #10 Dual auth | R012 | AC105, AC106 |
| #11 Dark mode + gaps doc | R014 (+R205) | AC120, AC121, AC340 |
| #12 Dead axios | R013 | AC110 |
| #13 Correct stack kept | R015 | AC130 |

Mobile/Watch requirement set → R101–R116 (§4, §5). Backend contract gaps → R201–R206 (§6). Deployment blockers → R401–R403 (§8). Missing subsystems → R301–R305 (§7).

---

## 10. Deliverables — M5/S101 contract audit & unimplemented-list verification (2026-10-04)

This register captures the **unimplemented-subsystem verification** performed on 2026-10-04 (worker `unimplemented-verify`, re-run of the M5 contract audit via worker `m5-contract-retry`). Each deliverable `D-H3x` pairs 1:1 with a task `T-H3x` in [`tasks.md`](./tasks.md) §"H-Series detail". Status vocabulary: **CONFIRMED** (the named subsystem is absent/stubbed as claimed — real finishing work), **PARTIAL** (part of the named surface exists, the requirement is still unmet), **REFUTED** (the claim does not hold in the current tree). Findings were re-verified against the live tree on 2026-10-04; file:line references are the audit's evidence anchors.

| Deliverable | Status | Evidence (file:line) | What remains to finish |
|-------------|--------|----------------------|------------------------|
| **D-H31** — Evidence service (§15) | CONFIRMED | [`backend/evidence/service.py:54`](backend/evidence/service.py:54) (also `:58`, `:64`, `:68`); [`docs/implementation-status.yaml:47`](docs/implementation-status.yaml:47) | `EvidenceService.create/get/list_by_source/delete` are `raise NotImplementedError` stubs; the §15 [`prompot.md:839`](prompot.md:839) evidence system (capture + provenance + citation) is unwired to the ORM in `backend/persistence/models/evidence.py` |
| **D-H32** — Events API live (§46) | CONFIRMED | [`backend/api/endpoints/events.py:11`](backend/api/endpoints/events.py:11); `events.py:15-16` | `GET /api/events/` returns two hardcoded fixture events; the §10 [`prompot.md:588`](prompot.md:588) immutable event schema + event-bus-backed listing (NATS) is unimplemented |
| **D-H33** — Write/mutation API (§46) | PARTIAL | [`backend/api/app.py:157`](backend/api/app.py:157) (`app = create_app()` `:177`); `backend/api/endpoints/` | No POST/PUT/PATCH/DELETE mutation endpoints exist outside the S101 auth surface; T313's stubs are honest 501 GETs; §46 [`prompot.md:1793`](prompot.md:1793) full HTTP API (ask/plan/execute/incidents) is the gap |
| **D-H34** — Connectors (§44) | PARTIAL | [`backend/connectors/registry.py:498-505`](backend/connectors/registry.py:498) (`:501` `from .nix import NixConnector`) | Present: `git.py`, `kubernetes.py`, `host.py`, `gpu.py` (4 of the §44 initial set, [`prompot.md:1728`](prompot.md:1728)). `default_registry()` imports `.nix`/`.omniroute`/`.zoo` whose modules are missing → `ImportError`. Absent: GitHub, filesystem, Nix, Docker, systemd, NVIDIA telemetry, Apple/Metal telemetry, Prometheus, Loki, CloudWatch, OmniRoute, Zoo, MCP |
| **D-H35** — Synthetic-lab (§78) | CONFIRMED | [`synthetic-lab/.gitkeep`](synthetic-lab/.gitkeep) | 0-byte `.gitkeep` only; the §78 [`prompot.md:2628`](prompot.md:2628) deterministic synthetic environment (fault injection: commits, pod failures, model failures, OmniRoute fallbacks, …) is unimplemented. Cross-ref T319 |
| **D-H36** — Evaluation harness (§78/§79) | CONFIRMED | `synthetic-lab/` (empty) | No `eval`/`harness`/`synthetic-eval` code in `synthetic-lab/`, `backend/`, or `tests/`; §78 [`prompot.md:2646`](prompot.md:2646) "This environment becomes the evaluation harness" + §79 Agent Evaluation [`prompot.md:2662`](prompot.md:2662) unmet |
| **D-H37** — Parallel Utilization Ratio (§23) | CONFIRMED | no code | No `parallel_utilization`/`utilization_ratio`/`PUR` symbol in `backend/` or `schemas/`; the §23 Parallel Scheduler [`prompot.md:1071`](prompot.md:1071) defines dispatch/runnable rules only — the utilization metric is absent (would attach to task-DAG state, §22 [`prompot.md:1028`](prompot.md:1028)) |
| **D-H38** — Object storage (§14) | CONFIRMED | no code | No S3/blob/artifact-store implementation in `backend/` or `schemas/`; §14 Persistence [`prompot.md:807`](prompot.md:807) requires Postgres + pgvector + **object store** + NATS; `backend/persistence/connection.py` implements Postgres only |
| **D-H39** — §9 Core Data Model schemas | PARTIAL | [`schemas/entities.py:1`](schemas/entities.py:1) | `schemas/` covers most §9 objects (Event/Entity/Relationship/Evidence/Claim/Decision/Task/TaskRun/Goal/Agent/Model/ModelInstance/InferenceRoute/ComputeNode/ContextPackage/PlannedChange/Approval); the §9 objects **Observation, Artifact, Experiment, Incident** have no schema modules. §9 [`prompot.md:555`](prompot.md:555) freezes 22 objects ("These interfaces should be frozen early") |
| **D-H310** — Prompt2 addendum entities (§5) | CONFIRMED | [`backend/persistence/models/`](backend/persistence/models/__init__.py) (11 files); [`prompt2.md:195`](prompt2.md:195) | The addendum's "New Core Entities" ([`prompt2.md:195-219`](prompt2.md:195): AttentionItem, Communication, …) has no persistence model or schema; the addendum (`prompt2.md`, 2580 lines) is referenced nowhere in `specs/nervcenter-uplift/` or `docs/implementation-status.yaml` |

**Verification note:** the M5/S101 **contract audit** verdict (**INCOMPLETE**, pending three fixes, with four negative-path failures) is tracked as task **T-H311** in [`tasks.md`](./tasks.md) §"H-Series detail"; it is not itself one of the ten deliverables above.
