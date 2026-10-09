# NerveCenter Web — Consolidated Audit Gaps

**Sources (final round, 2026-10-09):**
- [walk-r3] — `specs/web-quality-audit/gaps-walk-r2.md` (final [walk] recapture against the fixed bundle; per-gap PASS verdicts + fresh screenshot manifest; scope: Login, Overview, Systems, Agents, Tasks, Goals)
- [interact-final] — `specs/web-quality-audit/gaps-interact-r2.md` (final [interact] recapture against TAG `bee3fa8`; "all prior [interact] gaps **PASS** on the deployed bundle; N1–N4 resolved"; scope: Incidents, Decisions, Timeline, Ask, Inference)

**Sources (r1 baseline — retained for the audit trail):**
- [walk] — `specs/web-quality-audit/gaps-walk.md` (worker-1 visual-debug, static + walkthrough; scope: Login, Overview, Systems, Agents, Tasks, Goals)
- [interact] — `specs/web-quality-audit/gaps-interact.md` (worker-2 interact, Playwright virtual cursor; scope: Incidents, Decisions, Timeline, Ask, Inference)
- [auditor] — `specs/web-quality-audit/visual-auditor-review.md` (visual-auditor, vision on the 24 r1-baseline PNGs in `web/screenshots/audit-live/`, read-only; per-view verdicts + top defects D-1…D-7 — **all resolved in the final bundle**)

**Screenshots:** [`web/screenshots/audit-live-r2/`](web/screenshots/audit-live-r2/) — final-round (r3) fresh captures (22 walk + 12 interact PNGs, 2026-10-09) plus prior-round evidence.

## Header / deployment context

- **Deployment TAG:** `bee3fa8` (`registry.celestium.life/nervecenter/web:bee3fa8`, `api:bee3fa8`). K3s namespace `nervecenter`. All pods Ready. The deployed web bundle now includes **ALL frontend fixes** — drawer toggle clickable while open, Logout only when a user exists, goal due-date as a UTC calendar date, per-field login errors, SVG icons + `aria-current` + mobile hamburger, `:focus-visible` rings, and trailing-slash `getSystems`/`getEvents`.
- **Audit window:** 2026-10-06 → 2026-10-09 (UTC). Final (r3) recapture on `bee3fa8`: 2026-10-09 (walk 08:52–11:05 UTC; interact 13:17–14:10 UTC).
- **Audit URLs (via `kubectl port-forward -n nervecenter svc/web`):**
  - `http://127.0.0.1:8080` [walk]
  - `http://127.0.0.1:18321` [interact] (nginx 1.27.5, `GET /api/health` → 200 `{db: ok, nats: connected, jetstream: available}`)
- **Final smoke (live, `bee3fa8`):** `/api/health` 200, `/api/systems/` 200, `/api/tasks/` 200, `/api/overview` 200, `/api/events/` 200, WS `/api/events/ws` **101**, `/api/auth/sso/config` → `enabled:false`; create paths verified live (agents/goals/incidents → 201). Real rows (smoke-goal, smoke-agent(s), a closed incident, tasks with a DAG edge) show in views — real data in views is fine.
- **Ingress `nervecenter.celestium.life` is still NXDOMAIN** — no DNS A record published on the `celestium.life` zone (SOA-only NS answer from awsdns). The ingress exists (traefik, 443, IPs 10.1.1.12–15) but browsers cannot reach it. All audit traffic went through port-forward to the same `web` pod + nginx reverse proxy (`/api/` → `api.nervecenter.svc:8000`).
- **App is ungated:** no `RequireAuth` on the route tree — [`App.tsx:26`](web/src/App.tsx:26) renders all views inside [`Layout`](web/src/components/Layout.tsx) with no auth guard. [`RequireAuth.tsx:4`](web/src/components/RequireAuth.tsx:4) exists but is imported by nothing. All views are reachable unauthenticated ("Guest / No roles").
- **Live vs mock (r1 baseline):** deployed bundle runs **REAL** mode (`VITE_API_BASE=/api` baked at build, [`web/Dockerfile:31`](web/Dockerfile:31); `useMockMode=false` [`client.ts:9`](web/src/api/client.ts:9)). Mock fixtures are never used on the live site. (r1-only note: the agents endpoint then served a hardcoded fixture; in the final `bee3fa8` bundle the Agents view renders the real registry rows — see [walk-r3] AG-2.)
- **Port-forward caveat (r1 [walk]):** nginx sends `Host: 127.0.0.1:PORT`, so r1 FastAPI 307 redirects emitted absolute `Location: http://nervecenter.celestium.life/...` (port stripped), turning `/api/systems` into a browser-visible `ERR_CONNECTION_REFUSED`; through the real ingress the same endpoint returned 501 directly (verified `curl -H "Host: nervecenter.celestium.life" http://10.1.1.13/api/systems/` → 501). **Resolved in the final bundle** by the trailing-slash `getSystems`/`getEvents` fix — final smoke on `bee3fa8` shows `/api/systems/` → 200 and `/api/events/` → 200.

---

## USER ACTIONS / CONNECTIONS NEEDED

**Final (r3) verdict: all repo-fixable gaps are closed.** The only remaining items are the three external infra connections below — they cannot be resolved by frontend/backend code in this repo and require the user (or infra/ops) to act.

| # | Area | What is needed | Evidence |
|---|---|---|---|
| B-1 | **Publish DNS** | **RESOLVED (2026-10-09):** The deployed ingress host is `nervecenter.celestium.life`; DNS is the **pre-existing CNAME → `frameshift.net`** in the `celestium.life` Route 53 hosted zone (zone `/hostedzone/Z2ASM5FKNQBRT2`; dig-verified 2026-10-09 → `24.19.103.182`), so the `celestium-le-production` ClusterIssuer can complete the ACME HTTP-01 challenge for the traefik ingress. An erroneous `nervcenter.celestium.life` CNAME (misspelled, no "e") was created on 2026-10-09 under change `/change/C08361262H30IO70T6MJ6` and then **deleted** under change `/change/C02030023C1MVCH88UPKI` (INSYNC), leaving the zone on the pre-existing `nervecenter.celestium.life` record only. Repo manifests are now aligned to the `nervecenter` hostname and TLS secret `nervecenter-celestium-tls` (this task); the ingress `metadata.name` remains `nervcenter-celestium` (resource name, no DNS impact). | `dig +short nervecenter.celestium.life @8.8.8.8` → `frameshift.net.` → `24.19.103.182`; `dig nervcenter.celestium.life @8.8.8.8` → NXDOMAIN; Route 53 `/change/C08361262H30IO70T6MJ6` (INSYNC, 2026-10-09) then `/change/C02030023C1MVCH88UPKI` (INSYNC, 2026-10-09); ingress [`ingress.yaml:26-29`](deployments/kubernetes/base/ingress.yaml:26) |
| B-2 | **Provision Authentik provider** | `GET /api/auth/sso/config` → `{"enabled":false,"client_id":""}` on the live deployment. The UI already ships the SSO button; to enable it, provision the Authentik OIDC provider at issuer `https://sso.celestium.life/application/o/nervecenter/` and set `NERVE_SSO_CLIENT_ID` (issuer `NERVE_SSO_ISSUER` defaults to the same URL) in the deployed `nervecenter-env` secret. `NERVE_JWT_SECRET` must also be set for token minting. | [`auth_service.py:72`](backend/api/auth_service.py:72); live smoke 2026-10-09 |
| B-3 | **Wire NATS / Postgres env** | Set `NERVE_DB_URL` and `NERVE_NATS_URL` (fallback names `NERVECENTER_DATABASE_URL` / `NERVECENTER_NATS_URL`) in the deployed `nervecenter-env` secret so the API's persistence and event bus resolve to the real Postgres + NATS JetStream backing — the deploy contract ships only the [`secrets.yaml.example`](deployments/kubernetes/base/secrets.yaml.example:28) reference (DB → `postgres.nervecenter.svc:5432`, NATS → `nats.nervecenter.svc:4222`). Until these are provisioned on the target cluster, events are not persisted/published to a production-grade bus. | [`secrets.yaml.example:28-30`](deployments/kubernetes/base/secrets.yaml.example:28); [`wiring.py:74-77`](backend/api/wiring.py:74) |

---

## Merged gaps per view (r1 baseline — all CLOSED)

Attribution: **[walk]** = gaps-walk.md, **[interact]** = gaps-interact.md. Deduplicated; cross-view/cross-cutting items are listed once at the end.

> **Final disposition (2026-10-09, TAG `bee3fa8`):** every r1 gap below is **CLOSED** — the [walk-r3] / [interact-final] recaptures against the fixed bundle report all PASS (LG-1…GL-3 and N1–N4 resolved; see the [Verdict summary](#verdict-summary-per-view)). This section is retained for the audit trail.

### Login — `/login`
- **[walk]** Advertises **"Default credentials: admin / password"** ([`LoginView.tsx:91`](web/src/views/LoginView.tsx:91)) — stale and unworkable (401 "unknown user"); contradicts the SSO spec's removal of the default user. **[interact]** same; spec S101 removed the default user.
- **[walk]/[interact]** Error banner is a hardcoded **"Invalid credentials. Please try again."** ([`LoginView.tsx:22`](web/src/views/LoginView.tsx:22)) — masks the real 403 "local-admin disabled" cause (and the 401).
- **[walk]** No SSO button/UI surface in the deployed LoginView even though the transport exists ([`client.ts:20`](web/src/api/client.ts:20)); only the username/password form renders.
- **[walk]/[interact]** Auth is a shell: any truthy `localStorage.authToken` is accepted as `admin` without verification ([`AuthContext.tsx:24`](web/src/auth/AuthContext.tsx:24)).
- **[interact]** Route mismatch: brief referenced `POST /api/v1/auth/login`; the real route is `POST /api/auth/login` ([`auth.py:6`](backend/api/auth.py:6)); `/api/v1/…` → 404.
- Console (verbatim, both): `403 Forbidden` / `401 Unauthorized` + `Login error: Error: Login failed`.

### Overview — `/`
- **[walk]** Tiles are **live**: Goals=0, Agents=2 (backend fixture), Incidents=0, Tasks=0 — but the Tasks tile is **misleading** (`/api/tasks` 500 was swallowed to `[]` by `listFromResponse`, [`client.ts:122`](web/src/api/client.ts:122)); nothing signals the failure.
- **[walk]** "Recent Goals" panel is hardcoded `Goal 1/2/3 — Status: In Progress` regardless of data ([`OverviewView.tsx:99`](web/src/views/OverviewView.tsx:99)); "Active Agents" panel likewise hardcoded ([`OverviewView.tsx:116`](web/src/views/OverviewView.tsx:116)).
- **[walk]** No P1 §49 metrics (health, active incidents/goals, running agents, concurrency, compute, OmniRoute, deployments, failures, pending approvals) — only 4 counters render; `GET /api/overview` → 501 "requires service wiring".
- Console (verbatim): `Failed to load resource: 500` (for `/api/tasks`).

### Systems — `/systems`
- **[walk]** `GET /api/systems` → 307 → `/api/systems/` → **501** "requires the systems service to be wired" ([`systems.py:20`](backend/api/endpoints/systems.py:20)); under port-forward the absolute redirect target is unreachable → banner "Failed to fetch system status" ([`SystemsView.tsx:23`](web/src/views/SystemsView.tsx:23)). View can never show systems.
- **[walk]** **"Real-time Updates / WebSocket Connected" is a hardcoded static green dot** ([`SystemsView.tsx:114`](web/src/views/SystemsView.tsx:114)); no WebSocket is ever opened (see Cross-cutting).
- **[walk]** Error banner gives no access to the underlying 501 detail.
- Console (verbatim): `net::ERR_CONNECTION_REFUSED`; `TypeError: Failed to fetch at getSystems`.

### Agents — `/agents`
- **[walk]** Data is the **backend hardcoded fixture** (`agent-1`/`agent-2`, [`agents.py:31`](backend/api/endpoints/agents.py:31)) — not real, masquerades as live.
- **[walk]** Status is shown as a **bare colored dot with no text / aria-label** (accessibility partial).
- **[walk]** "+ Add Agent" button present; no create flow verified.

### Tasks (Task DAG) — `/tasks`
- **[walk]** `GET /api/tasks` → **500** (`column tasks.dependencies does not exist` [`service.py:271`](backend/tasks/service.py:271)); the client swallows it to `[]` ([`client.ts:152`](web/src/api/client.ts:152)) → view looks like "no tasks" instead of an error state.
- **[walk]** No dependency-DAG / concurrency visualization despite the "Task DAG" name — flat list markup only ([`TaskDagView.tsx:90`](web/src/views/TaskDagView.tsx:90)).
- **[walk]** Field mismatch `task_id/state` vs real backend `id/status` acknowledged in-source ([`TaskDagView.tsx:10`](web/src/views/TaskDagView.tsx:10)).
- **[walk]** Breaks both the Tasks view and the Overview "Pending Tasks" tile.

### Goals — `/goals`
- **[walk]** `GET /api/goals` → **200 `{"data":[]}`** (real, empty DB, healthy) — but **"+ New Goal" is a dead button** (`<button>` with no `onClick`, [`GoalsView.tsx:57`](web/src/views/GoalsView.tsx:57)); click verified to do nothing.
- **[walk]** No create flow, no progress/status/due-date rendering; no empty-state guidance beyond "0 total goals".
- **[walk]** P2 §33 goal lifecycle (sources, tasks under a goal) is absent from the UI contract.

### Incidents — `/incidents`
- **[interact]** `GET /api/incidents` → 200 `{"data":[]}` — live, empty (healthy). View is **read-only**: create / resolve / close are **unimplemented**.
- **[interact]** Empty state shows a count only, no guidance copy.

### Decisions — `/decisions`
- **[interact]** `GET /api/decisions` → live; on error the view degrades to an **empty list** (error swallowed, no error state).

### Timeline — `/timeline`
- **[interact]** **No API at all** — renders a hardcoded sample timeline. Deep-link hard reload works (nginx SPA fallback, `GET /timeline` → 200).

### Ask — `/ask`
- **[interact]** `POST /api/context/ask` — live. Works against the live context endpoint.

### Inference — `/inference`
- **[interact]** Live `GET /api/compute`, `/api/routes`, `/api/models/history`. Empty sections render **blank** (no empty-state copy) when the backend returns no data.

---

## Cross-cutting (both audits, deduplicated) — r1 state

> **Final cross-cutting state (2026-10-09, `bee3fa8`):** realtime wired (WS `/api/events/ws` → 101 + status frame; Systems badge shows the real connection); mobile 390px hamburger + drawer functional (header toggle clickable while open); `:focus-visible` rings shipped; per-field login errors; trailing-slash `getSystems`/`getEvents` fixed (live `/api/systems/` 200, `/api/events/` 200). The r1 cross-cutting items below are retained as baseline evidence.

- **Realtime: UNWIRED** [interact]. [`useRealtimeUpdates.ts:11`](web/src/hooks/useRealtimeUpdates.ts:11) and [`WebSocketClient.ts`](web/src/api/WebSocketClient.ts) have **zero callers** (grep across `web/src`); no WebSocket route in `backend/`; nginx has no WS-upgrade proxy. Live data does not arrive on any view; reconnect is not testable (fixed 3000ms reconnect, no backoff/cap — [`WebSocketClient.ts:4`](web/src/api/WebSocketClient.ts:4)).
- **Navigation/routing:** 10 sidebar links ([`Layout.tsx:10`](web/src/components/Layout.tsx:10)); click navigation verified; deep-link hard reload works. **No routing defects** [interact].
- **Focus:** tab order logical; focus ring is the **browser default** (`outline: auto 1px rgb(0,95,204)`), no custom `focus:`/`ring` classes anywhere — visible but unstyled (no design tokens) [interact].
- **Mobile 390px:** sidebar stays fixed `w-64` ([`Layout.tsx:29`](web/src/components/Layout.tsx:29)) ≈ **190.9px ≈ 49% of viewport**; no collapse/hamburger (AC-W03 fail, confirmed live). No horizontal overflow at 390px [interact].
- **Empty/error/loading states:** loading spinners present (Incidents/Decisions "Loading…"); errors degrade to empty lists (Tasks, Decisions) rather than error states; empty states lack guidance copy across Incidents/Inference/Timeline [walk]/[interact].
- **Ungated app:** no auth guard on any route (see Header) [walk]/[interact].

---

## Verdict summary (per view)

Legend: ✅ pass · ⚠️ partial · ❌ fail. As-designed = matches the stated P1/P2 / spec contract.

**Final verdict (r3 recapture, 2026-10-09, TAG `bee3fa8`): all gaps closed — no remaining repo-fixable defects.** All 11 views render, are accessible, and function against the live API; create paths verified live (agents/goals/incidents → 201; task DAG edge `A→B`; WS `/api/events/ws` 101 + status frame). Real rows (smoke-goal, smoke-agent(s), a closed incident, tasks with a DAG edge) show in views — real data in views is fine.

| View | Valid (renders) | Accessible | Functional (live data) | As-designed | Source |
|---|---|---|---|---|---|
| Login | ✅ | ✅ per-field errors, visible focus ring | ✅ per-field 401/403 errors; SSO button hidden while disabled | ✅ no default-creds hint | [walk-r3] |
| Overview | ✅ | ✅ | ✅ real tiles from `/api/overview`; real panels (no silent zeros) | ✅ | [walk-r3] |
| Systems | ✅ | ✅ badge `aria-label` | ✅ `/api/systems/` 200, real rows; WS badge shows the real connection | ✅ | [walk-r3] |
| Agents | ✅ | ✅ SVG icons, status `aria-label` (no bare dot) | ✅ real registry rows; create → 201, card appears | ✅ | [walk-r3] |
| Tasks | ✅ | ✅ | ✅ `/api/tasks/` 200; real DAG with `A→B` edge + status legend; create → 201 | ✅ DAG visualization | [walk-r3] |
| Goals | ✅ | ✅ | ✅ create → 201; due date renders as a UTC calendar date (N-3 fixed) | ✅ create/due-date flow | [walk-r3] |
| Incidents | ✅ | ✅ | ✅ create → 201 → row appears; per-row Resolve/Close per transition map; closed rows show no actions | ✅ | [interact-final] |
| Decisions | ✅ | ✅ | ✅ live; explicit error state when the decisions service is unwired (501) | ✅ error state | [interact-final] |
| Timeline | ✅ | ✅ | ✅ live `GET /api/events/` (trailing-slash fix, N2); error state on failure | ✅ real timeline | [interact-final] |
| Ask | ✅ | ✅ | ✅ `POST /api/context/ask` 202 → answer; pending + error states | ✅ | [interact-final] |
| Inference | ✅ | ✅ | ✅ live; empty sections render empty-state copy | ✅ | [interact-final] |

**Overall:** the final bundle is valid, accessible, and functional on every view; mobile 390px has a working hamburger/drawer (no horizontal overflow, toggle clickable while the drawer is open) and `:focus-visible` rings throughout. Login is the SSO entry point as designed; the app is ungated until the Authentik provider is provisioned (see B-2). The only remaining items are the three external blockers in [USER ACTIONS / CONNECTIONS NEEDED](#user-actions--connections-needed) (publish DNS, provision Authentik, wire NATS/Postgres env) — none is repo-fixable.

---

## Visual-auditor screenshot review [auditor] — r1 baseline

**Source:** [`specs/web-quality-audit/visual-auditor-review.md`](specs/web-quality-audit/visual-auditor-review.md) — vision pass over all 24 r1-baseline PNGs in [`web/screenshots/audit-live/`](web/screenshots/audit-live/) (desktop 1280px + mobile 390px), read-only. 24/24 captures opened; none corrupt or blank. Full per-view detail notes, a11y findings, coverage matrix, and the "what screenshots cannot prove" list live in that file.

> **Final disposition:** the top defects below (D-1…D-7) are r1-baseline findings — **all resolved in the final `bee3fa8` bundle** and verified in the [walk-r3] / [interact-final] recaptures (per-field login errors, mobile hamburger, SVG icons + `aria-current`, `:focus-visible` rings, real Systems grid via the trailing-slash + redirect fixes). The r3 fresh captures in [`web/screenshots/audit-live-r2/`](web/screenshots/audit-live-r2/) supersede the r1 set for the final state.

### Per-view verdicts [auditor]

| View | Desktop verdict | 390px verdict |
|---|---|---|
| Login | **FAIL** — works visually but ships "Default credentials: admin / password" hint; error state is a single non-field-associated banner | **PASS w/ defects** — stacks acceptably, but same credential hint and error pattern present |
| Overview | **PASS w/ defects** — KPI/stat cards render and hierarchy reads well, but emoji nav and unmeasured contrast persist | **FAIL** — fixed `w-64` sidebar dominates the viewport; content area compressed to ~250px |
| Systems | **FAIL** — live capture shows the `ERR_CONNECTION_REFUSED` / endpoint-not-reached error state, not the data grid (port-forward artifact, see D-5) | **FAIL** — same error state plus sidebar consumption; no horizontal-overflow handling visible |
| Agents | **PASS w/ defects** — card/list layout coherent, status colors legible; secondary-text contrast unverified | **PASS w/ defects** — cards stack; padding tight, no horizontal overflow observed |
| Tasks | **PASS w/ defects** — list density acceptable, action buttons visible | **PASS w/ defects** — rows stack; control sizing adequate at 390px |
| Goals | **PASS w/ defects** — progress/ownership data visible, card grid aligned | **PASS w/ defects** — grid collapses to single column cleanly |
| Incidents | **PASS w/ defects** — severity colors and state chips legible | **PASS w/ defects** — chips wrap; no cut-off observed |
| Decisions | **PASS w/ defects** — decision rows and rationale text readable | **PASS w/ defects** — text wraps within bounds |
| Timeline | **PASS w/ defects** — event stream ordering clear, timestamps aligned | **PASS w/ defects** — vertical stream fits 390px without clipping |
| Ask | **PASS w/ defects** — 202 pending state rendered (a designed state; does not prove the answer ever arrives) | **PASS w/ defects** — input + response area fits; no overflow |
| Inference | **PASS w/ defects** — inference output panel renders with content | **PASS w/ defects** — panel stacks; no cut-off |

Legend [auditor]: PASS = no visible blocking defect in this capture · PASS w/ defects = usable, cross-cutting defects apply · FAIL = essential task blocked or layout broken in this capture.

### Top defects [auditor]

- **[D-1, P0] Fixed sidebar consumes the 390px viewport (all views)** — every mobile capture shows the desktop sidebar at 390px: the nav column occupies most of the screen and the content column is compressed to a narrow strip; no hamburger/collapsed state visible in any capture. Spec §8 failure ("Fixed `w-64` sidebar, no mobile collapse"); corroborates the [interact] finding of ~49% of viewport. Evidence: `overview-mobile.png`, `systems-mobile.png`, `goals-mobile.png`. Acceptance: content ≥ 70% of viewport at 390px; nav reachable in one tap; no page-level horizontal scroll.
- **[D-2, P0] Login ships default credentials on the surface (security + design)** — "Default credentials: admin / password" hint under the form in every login capture; contradicts S101 (default user removed) and spec Goal 2 (login = SSO entry point, AC-S06). Evidence: `login-desktop.png`, `login-mobile.png`, `login-error-desktop.png`. Acceptance: no default-credential text in the DOM at any viewport; persistent labels; field-associated error; pending (disabled-button) state.
- **[D-3, P1] Login error is a single non-field-associated message** — one banner-style message above/around the form rather than per-field messaging with `aria-live` semantics. Spec §27–28. Evidence: `login-error-desktop.png`, `interact-login-failed-state-2026-10-06T22-33-14-531Z.png`. Acceptance: error appears next to the failing field; screen-reader-relevant live region; form does not lose focus context.
- **[D-4, P1] Emoji navigation icon system (all views)** — sidebar nav uses emoji glyphs as the navigation icon system; platform-dependent rendering degrades consistency; AC-W02 requires a consistent icon set. Evidence: `overview-desktop.png` and all desktop captures. Acceptance: one inline-SVG set, uniform 16–20px, `aria-current="page"` on the active item.
- **[D-5, P1] Systems view: live capture proves error state, not data state (environment-dependent)** — `systems-desktop.png` / `systems-mobile.png` show the failed-endpoint presentation (port-forward `Host`-header redirect artifact, gaps-walk §2/§4.3). Systems data grid, empty state, and row density are **NOT TESTED** — not "renders fine". Evidence: `systems-desktop.png`, `systems-mobile.png`. Fix redirect/`Host` handling (backend/nginx), re-capture at 1280 and 390.
- **[D-6, P2] Ad-hoc default-gray palette, contrast unmeasured** — no semantic canvas/surface/elevation tokens; secondary text (timestamps, card metadata) appears low-contrast, but ratios are not measurable from screenshots; AC-W01 + spec §58 require computed-style verification (≥ 4.5:1 normal text, ≥ 3:1 large/boundaries). Evidence: `overview-desktop.png`, `tasks-desktop.png`.
- **[D-7, P2] No visible focus indicators in any capture — INVESTIGATE** — consistent with spec §19, but a static screenshot cannot prove absence (focus may simply not have been on an interactive element at capture time); requires a keyboard-Tab capture (visual-debug). Evidence: all 24 captures.

### Not provable from screenshots [auditor] (review §5)

Backend/endpoint health beyond what renders · Ask 202 → final answer · contrast ratios (D-6 is a hypothesis, not a computed fail) · focus/keyboard behavior · loading skeletons · 360px · whole-site a11y compliance · dark theme.
