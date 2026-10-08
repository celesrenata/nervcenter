# NerveCenter Web — Consolidated Audit Gaps

**Sources:**
- [walk] — `specs/web-quality-audit/gaps-walk.md` (worker-1 visual-debug, static + walkthrough; scope: Login, Overview, Systems, Agents, Tasks, Goals)
- [interact] — `specs/web-quality-audit/gaps-interact.md` (worker-2 interact, Playwright virtual cursor; scope: Incidents, Decisions, Timeline, Ask, Inference)
- [auditor] — `specs/web-quality-audit/visual-auditor-review.md` (visual-auditor, vision on all 24 PNGs in `web/screenshots/audit-live/`, read-only; per-view verdicts + top defects with screenshot evidence)

**Screenshots:** [`web/screenshots/audit-live/`](web/screenshots/audit-live/) (12 walk + 11 interact PNGs). All 24 reviewed in the [auditor] pass.

## Header / deployment context

- **Deployment TAG:** `50e4c83` (`registry.celestium.life/nervecenter/web:50e4c83`, `api:50e4c83`). K3s namespace `nervecenter`. All pods Running/Ready; `migrate-job` Completed. Deployed `web/src` is byte-identical to this worktree snapshot.
- **Audit date:** 2026-10-06 → 2026-10-07 (UTC).
- **Audit URLs (via `kubectl port-forward -n nervecenter svc/web`):**
  - `http://127.0.0.1:8080` [walk]
  - `http://127.0.0.1:18321` [interact] (nginx 1.27.5, `GET /api/health` → 200 `{db: ok, nats: connected, jetstream: available}`)
- **Ingress `nervcenter.celestium.life` is NXDOMAIN** — no DNS A record published on the `celestium.life` zone (SOA-only NS answer from awsdns; 1.1.1.1/8.8.8.8 all NXDOMAIN). The ingress exists (traefik, 443, IPs 10.1.1.12–15; TLS 200 via `--resolve`) but browsers cannot reach it. All audit traffic went through port-forward to the same `web` pod + nginx reverse proxy (`/api/` → `api.nervecenter.svc:8000`).
- **App is ungated:** no `RequireAuth` on the route tree — [`App.tsx:26`](web/src/App.tsx:26) renders all views inside [`Layout`](web/src/components/Layout.tsx) with no auth guard. [`RequireAuth.tsx:4`](web/src/components/RequireAuth.tsx:4) exists but is imported by nothing. All views are reachable unauthenticated ("Guest / No roles").
- **Live vs mock:** deployed bundle runs **REAL** mode (`VITE_API_BASE=/api` baked at build, [`web/Dockerfile:31`](web/Dockerfile:31); `useMockMode=false` [`client.ts:9`](web/src/api/client.ts:9)). Mock fixtures are never used on the live site. The only "fixture-like" data anywhere is the **backend's** hardcoded agents fixture ([`backend/api/endpoints/agents.py:31`](backend/api/endpoints/agents.py:31)), which masquerades as live in the Agents view + Overview tile.
- **Port-forward caveat [walk]:** nginx sends `Host: 127.0.0.1:PORT`, so FastAPI 307 redirects emit absolute `Location: http://nervcenter.celestium.life/...` (port stripped). This turns `/api/systems` into a browser-visible `ERR_CONNECTION_REFUSED`; through the real ingress the same endpoint returns 501 directly (verified `curl -H "Host: nervcenter.celestium.life" http://10.1.1.13/api/systems/` → 501).

---

## USER ACTIONS / CONNECTIONS NEEDED

Gaps that cannot be resolved by frontend/backend code alone and require the user (or infra/ops) to act:

| # | Area | What is needed | Evidence |
|---|---|---|---|
| U-1 | **DNS record** | Publish an A (or AAAA) record for `nervcenter.celestium.life` → ingress LB (10.1.1.12–15) in the `celestium.life` zone. Currently NXDOMAIN; browser cannot navigate the ingress URL. | [walk §1] ingress `nervcenter-celestium`, traefik, 443 |
| U-2 | **Credentials / backend data** | No working auth path exists live. `local-admin` disabled (`NERVE_LOCAL_ADMIN` not set in the deployed `nervecenter-env` secret); `admin/password` → 401 "unknown user". Need valid credentials OR a seeded user. | [walk §2] [`auth.py:205`](backend/api/auth.py:205); [interact §Login] |
| U-3 | **SSO / API keys** | SSO is off (`/api/auth/sso/config` → `{"enabled":false,"client_id":""}`; issuer `https://sso.celestium.life/application/o/nervecenter/`). To enable the SSO button the UI already ships, an SSO issuer + client_id + API keys must be provisioned. | [walk §2/L-3]; [interact §Login] |
| U-4 | **Backend service wiring** | `/api/systems` → 501 ("requires the systems service to be wired via `app.state.services`"); `/api/overview` → 501 ("requires service wiring"). These are backend wiring gaps, not frontend bugs — the views can never render data until wired. | [walk §4.3] [`systems.py:20`](backend/api/endpoints/systems.py:20); [walk §4.2] |
| U-5 | **DB migration / schema** | `GET /api/tasks` → 500 `sqlalchemy.exc.ProgrammingError: column tasks.dependencies does not exist` (schema/migration drift). Requires an Alembic migration to add the column + a redeploy. | [walk §4.5] [`service.py:271`](backend/tasks/service.py:271) |
| U-6 | **WebSocket backend route** | Realtime is unwired: no WebSocket route exists in `backend/` and nginx has no WS-upgrade proxy (`web/nginx.conf.template` lacks `proxy_set_header Upgrade`). Live data will not push to any view until a backend WS route + nginx config are added. | [interact §Cross-cutting] |
| U-7 | **Default-credentials hint on login** | Remove the "Default credentials: admin / password" hint from the production login surface: spec S101 removed the default user and spec Goal 2 makes login the SSO entry point (AC-S06) — shipping the hint is both a security and a design defect; product/security decision. | [auditor D-2] `login-desktop.png`, `login-mobile.png`, `login-error-desktop.png` |
| U-8 | **Field-associated login error** | Replace the single banner-style login error with per-field messaging adjacent to the failing field (`aria-live`, focus preserved) plus a pending/disabled Sign-in state while the request is in flight. | [auditor D-3] `login-error-desktop.png`, `interact-login-failed-state-2026-10-06T22-33-14-531Z.png` |
| U-9 | **Re-capture Systems data grid** | After fixing the redirect/`Host`-header handling and systems service wiring (see U-1, U-4), re-capture `/systems` at 1280px and 390px: the data-grid verdict is **NOT TESTED** (only the endpoint-unreached error state was captured). | [auditor D-5] `systems-desktop.png`, `systems-mobile.png` |

---

## Merged gaps per view

Attribution: **[walk]** = gaps-walk.md, **[interact]** = gaps-interact.md. Deduplicated; cross-view/cross-cutting items are listed once at the end.

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

## Cross-cutting (both audits, deduplicated)

- **Realtime: UNWIRED** [interact]. [`useRealtimeUpdates.ts:11`](web/src/hooks/useRealtimeUpdates.ts:11) and [`WebSocketClient.ts`](web/src/api/WebSocketClient.ts) have **zero callers** (grep across `web/src`); no WebSocket route in `backend/`; nginx has no WS-upgrade proxy. Live data does not arrive on any view; reconnect is not testable (fixed 3000ms reconnect, no backoff/cap — [`WebSocketClient.ts:4`](web/src/api/WebSocketClient.ts:4)).
- **Navigation/routing:** 10 sidebar links ([`Layout.tsx:10`](web/src/components/Layout.tsx:10)); click navigation verified; deep-link hard reload works. **No routing defects** [interact].
- **Focus:** tab order logical; focus ring is the **browser default** (`outline: auto 1px rgb(0,95,204)`), no custom `focus:`/`ring` classes anywhere — visible but unstyled (no design tokens) [interact].
- **Mobile 390px:** sidebar stays fixed `w-64` ([`Layout.tsx:29`](web/src/components/Layout.tsx:29)) ≈ **190.9px ≈ 49% of viewport**; no collapse/hamburger (AC-W03 fail, confirmed live). No horizontal overflow at 390px [interact].
- **Empty/error/loading states:** loading spinners present (Incidents/Decisions "Loading…"); errors degrade to empty lists (Tasks, Decisions) rather than error states; empty states lack guidance copy across Incidents/Inference/Timeline [walk]/[interact].
- **Ungated app:** no auth guard on any route (see Header) [walk]/[interact].

---

## Verdict summary (per view)

Legend: ✅ pass · ⚠️ partial · ❌ fail. As-designed = matches the stated P1/P2 / spec contract.

| View | Valid (renders) | Accessible | Functional (live data) | As-designed | Source |
|---|---|---|---|---|---|
| Login | ✅ | ✅ | ❌ no working auth path (403/401) | ❌ default creds advertised, no SSO surface | [walk][interact] |
| Overview | ✅ | ✅ | ⚠️ live tiles but Tasks 500 masked; agents = fixture | ❌ 8/10 §49 items missing; panels hardcoded | [walk] |
| Systems | ✅ | ✅ | ❌ 501 unwired; WS dot is fake | ❌ no systems data path | [walk] |
| Agents | ✅ | ⚠️ status = bare dot, no aria | ⚠️ fixture data only | ⚠️ fixture, not real registry | [walk] |
| Tasks | ✅ | ✅ | ❌ 500 (missing `dependencies` col), swallowed to `[]` | ❌ no DAG / concurrency viz | [walk] |
| Goals | ✅ | ✅ | ❌ dead "+ New Goal" (no onClick) | ❌ no create/progress/due-date flow | [walk] |
| Incidents | ✅ | ✅ | ⚠️ live read-only; create/resolve/close unimpl. | ⚠️ read-only, empty-state = count only | [interact] |
| Decisions | ✅ | ✅ | ⚠️ live; error → empty list (swallowed) | ⚠️ no error state | [interact] |
| Timeline | ✅ | ✅ | ❌ no API, hardcoded sample | ❌ sample data, not real timeline | [interact] |
| Ask | ✅ | ✅ | ✅ live `POST /api/context/ask` | ✅ | [interact] |
| Inference | ✅ | ✅ | ⚠️ live; blank sections when empty | ⚠️ no empty-state copy | [interact] |

**Overall:** the shell is valid, navigable, and responsive (no 390px overflow, no routing defects), but it is **ungated** and **functionally hollow**: 4 of 11 views never display real data (Systems 501, Tasks 500, Timeline sample, Agents fixture), login has no working credential path, realtime is unwired, and the mobile nav eats half the viewport.

---

## Visual-auditor screenshot review [auditor]

**Source:** [`specs/web-quality-audit/visual-auditor-review.md`](specs/web-quality-audit/visual-auditor-review.md) — vision pass over all 24 PNGs in [`web/screenshots/audit-live/`](web/screenshots/audit-live/) (desktop 1280px + mobile 390px), read-only. 24/24 captures opened; none corrupt or blank. Full per-view detail notes, a11y findings, coverage matrix, and the "what screenshots cannot prove" list live in that file.

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
