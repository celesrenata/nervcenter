# Live Site Walkthrough Audit — gaps-walk.md

**Worker:** visual-debug (parallel worker-1, task 01a112c3)
**Date:** 2026-10-06 (21:50–23:55 UTC)
**Scope (6 views only):** Login, Overview, Systems, Agents, Tasks, Goals
**Deployed revision:** TAG `50e4c83` (registry.celestium.life/nervecenter/web:50e4c83, api:50e4c83), K3s ns `nervecenter`; all pods Running/Ready, migrate-job Completed. Deployed `web/src` is byte-identical to this worktree snapshot (`git diff 34f946d 50e4c83 -- web/src/` = empty).

---

## 1. URL used

| Candidate | Result |
|---|---|
| `https://nervcenter.celestium.life/` (ingress `nervcenter-celestium`, traefik, 443; IPs 10.1.1.12–15) | TLS 200 when addressed via `--resolve` to each ingress IP; **but NXDOMAIN from the user's browser context** (local resolver, dns.google/1.1.1.1, 8.8.8.8 all return NXDOMAIN — the A record is not published on `celestium.life`; SOA-only NS answer from awsdns). Browser cannot navigate it. |
| **AUDIT URL: `http://127.0.0.1:8080`** | `kubectl port-forward -n nervecenter svc/web 8080:80` → the same `web-ddd6f8f99-vjqt8` pod + its nginx reverse proxy (`web/nginx.conf.template:37-49` proxies `/api/` → `api.nervecenter.svc:8000`), i.e. the exact upstream the ingress fronts. Used for the entire walkthrough. |

Caveat: under port-forward, nginx `proxy_set_header Host $host` sends `Host: 127.0.0.1:8080`, so FastAPI 307 redirects emit absolute `Location: http://nervcenter.celestium.life/...` URLs (port stripped) — this is what turns `/api/systems` into a browser-visible `ERR_CONNECTION_REFUSED` (see §4.3). Through the real ingress host the same endpoint returns 501 directly (verified via `curl -H "Host: nervcenter.celestium.life" http://10.1.1.13/api/systems/` → 501).

## 2. Login outcome — **FAIL (no working auth path exists live)**

- UI posts to `POST /api/auth/login` ([AuthContext.tsx:34](web/src/auth/AuthContext.tsx#L34)); the live backend route is `POST /api/auth/login` ([backend/api/auth.py:205](backend/api/auth.py#L205), break-glass `local-admin`).
- Credentials were discoverable from the repo (key names only, no values): `secrets.yaml.example` defines `NERVE_LOCAL_ADMIN` / `NERVE_LOCAL_ADMIN_PASSWORD` — **neither key is present** in the deployed `nervecenter-env` secret (keys: `NERVE_DB_URL, NERVE_NATS_URL, NERVE_OMNIROUTE_URL, NERVE_MOCK_INFER, NERVECENTER_*` only). No password value exists anywhere in-repo (by design: "no default password").
- Probes (verbatim responses, sensitive values redacted — only probe strings used):
  - `POST /api/auth/login {"username":"local-admin","password":"<probe>"}` → **403** `{"detail":"local-admin login is disabled (set NERVE_LOCAL_ADMIN)"}`
  - `POST /api/auth/login {"username":"admin","password":"password"}` → **401** `{"detail":"unknown user"}`
  - `GET /api/auth/sso/config` → **200** `{"enabled":false,"issuer":"https://sso.celestium.life/application/o/nervecenter/","client_id":""}` — SSO is off.
  - `GET /api/auth/me` (no token) → **401** `{"detail":"missing bearer token"}`
- **UI console (verbatim):**
  - `[error] Failed to load resource: the server responded with a status of 403 (Forbidden)`
  - `[error] Login error: Error: Login failed at i (http://127.0.0.1:8080/assets/index-BoWc-G3Z.js:67:3045) at async f (http://127.0.0.1:8080/assets/index-BoWc-G3Z.js:67:45307)`
  - (2nd attempt, admin/password) `[error] Failed to load resource: the server responded with a status of 401 (Unauthorized)`
- **How the audit proceeded:** after failed logins the app is browsable **unauthenticated** — `RequireAuth` ([web/src/components/RequireAuth.tsx](web/src/components/RequireAuth.tsx)) exists but is **not used by any route** (grep: zero usages; [App.tsx:24-42](web/src/App.tsx#L24) mounts views directly). Layout shows `Guest / No roles` ([Layout.tsx:56-59](web/src/components/Layout.tsx#L56)). All 6 views were walked in this state.
- Gap: the login page advertises **"Default credentials: admin / password"** ([LoginView.tsx:91-94](web/src/views/LoginView.tsx#L91)) — stale and unworkable (401 unknown user); also contradicts the SSO spec's removal of the default user. The error banner always shows the same hardcoded "Invalid credentials. Please try again." ([LoginView.tsx:22](web/src/views/LoginView.tsx#L22)), which masks the actual 403 "disabled" reason.

## 3. LIVE vs MOCK determination (global)

- The deployed bundle runs in **REAL mode**: `VITE_API_BASE=/api` is baked at build ([web/Dockerfile:31-35](web/Dockerfile#L31)); `useMockMode = API_BASE === undefined || API_BASE === ''` → false ([web/src/api/client.ts:9-11](web/src/api/client.ts#L9)). Bundle grep for mock fixture markers (`mock-jwt-token`, `goal-1`, `task-1`) = 0 hits.
- **No mock fallback ever occurred in any view.** Every data panel is either live API data or the consequence of a live API error.
- Important nuance: the only "fixture-like" data shown anywhere is the **backend's** hardcoded agents fixture — `{"id":"agent-1","name":"Agent 1","status":"active"}, {"id":"agent-2",...}` ([backend/api/endpoints/agents.py:31-33](backend/api/endpoints/agents.py#L31)) — which masquerades as live data in the Agents view and the Overview tile.

## 4. Per-view findings

### 4.1 Login — `/login`
| Check | Verdict | Evidence |
|---|---|---|
| Valid (renders) | ✅ PASS | Card, title, subtitle, 2 fields, button, default-creds hint; screenshots `login-desktop.png`, `login-mobile.png` |
| Accessible | ✅ PASS | Labels `htmlFor` username/password ([LoginView.tsx:46-54, 64-72](web/src/views/LoginView.tsx#L46)); `required` set; Tab order username→password verified; visible focus outline `rgb(0,95,204) auto 1px` (computed) on both inputs |
| Functional | ❌ FAIL | No credential set can succeed live (break-glass disabled 403; SSO disabled; no default user). Error banner renders on failure (verified) |
| As-designed (P1 §71 / sso-integration AC-S03) | ❌ FAIL | Break-glass path disabled at deploy (missing secret keys); stale "admin / password" hint; generic error hides 403-vs-401 distinction |

**Gaps:** L-1 unworkable advertised credentials; L-2 generic error masks "disabled" cause; L-3 no SSO button/UI surface even though `client.ts` has full SSO/PKCE transport ([web/src/api/client.ts:20-105](web/src/api/client.ts#L20)) — the deployed LoginView only has the username/password form.

### 4.2 Overview — `/`
| Check | Verdict | Evidence |
|---|---|---|
| Valid (renders) | ✅ PASS | h1 "Overview", 4 stat tiles, 2 panels; `overview-desktop.png`, `overview-mobile.png` |
| Accessible | ✅ PASS | h1 present; stat tiles are plain text (no bad contrast observed); nav links focusable (first Tab lands on "Overview" link, outline `auto 1px`) |
| Functional | ⚠️ PARTIAL | Tiles are **live**: Goals=0 (`GET /api/goals` 200 `[]`), Agents=2 (backend fixture), Incidents=0 (`/api/incidents` 200 `[]`), Tasks=0 — **misleading**: `/api/tasks` returned 500 and was swallowed by `listFromResponse` → `[]` ([client.ts:122-138](web/src/api/client.ts#L122)); nothing signals the failure |
| As-designed (P1 §49: health, active incidents, active goals, running agents, task concurrency, compute utilization, OmniRoute activity, recent deployments, recent failures, pending approvals) | ❌ FAIL | Only 4 counters render; 8 of 10 required items absent. `GET /api/overview` is **501** "requires service wiring" so the backend can't even serve the aggregate |

**Live data:** goals 0 / agents 2 / incidents 0 (real API); tasks 0 (real API **error** masked).
**Gaps:** O-1 "Recent Goals" panel is hardcoded `Goal 1/2/3 — Status: In Progress` regardless of data ([OverviewView.tsx:99-113](web/src/views/OverviewView.tsx#L99)); O-2 "Active Agents" panel likewise hardcoded ([OverviewView.tsx:116-126](web/src/views/OverviewView.tsx#L116)); O-3 no §49 metrics at all; O-4 500 on `/api/tasks` silently zeroed.
**Console (verbatim):** `[error] Failed to load resource: the server responded with a status of 500 (Internal Server Error)` (for `/api/tasks`).

### 4.3 Systems — `/systems`
| Check | Verdict | Evidence |
|---|---|---|
| Valid (renders) | ✅ PASS | h1 + error banner + realtime panel render; `systems-desktop.png`, `systems-mobile.png` |
| Accessible | ✅ PASS | Error text is real text content; no ARIA misuse observed |
| Functional | ❌ FAIL | `GET /api/systems` → 307 → `/api/systems/` → **501** "Systems list endpoint requires the systems service to be wired via app.state.services" ([backend/api/endpoints/systems.py:20-22](backend/api/endpoints/systems.py#L20)). Under port-forward the absolute redirect target is unreachable → banner "Failed to fetch system status" ([SystemsView.tsx:23,54-57](web/src/views/SystemsView.tsx#L23)). Even through the real ingress the endpoint is 501, so the view can never show systems |
| As-designed (FEATURES.md §2: health status, metrics/version, realtime WebSocket updates) | ❌ FAIL | Zero system cards render in any reachable state |

**Live data:** none (endpoint 501). **Mock:** none.
**Gaps:** S-1 no system data path exists in the deployed backend; S-2 **"Real-time Updates / WebSocket Connected"** is a **hardcoded static green dot** ([SystemsView.tsx:114-126](web/src/views/SystemsView.tsx#L114)) — no WebSocket is ever opened: `web/src/api/WebSocketClient.ts` is an **empty file (0 bytes)**, `useRealtimeUpdates`/`RequireAuth` are used by no view; S-3 error banner shows "Failed to fetch system status" with no way to see the underlying 501 detail.
**Console (verbatim):** `[error] Failed to load resource: net::ERR_CONNECTION_REFUSED`; `[error] TypeError: Failed to fetch at Object.getSystems (http://127.0.0.1:8080/assets/index-BoWc-G3Z.js:67:7999) at Object.health (http://127.0.0.1:8080/assets/index-BoWc-G3Z.js:67:9578)`.

### 4.4 Goals — `/goals`
| Check | Verdict | Evidence |
|---|---|---|
| Valid (renders) | ✅ PASS | h1 "Goals", "0 total goals", "+ New Goal" button; `goals-desktop.png`, `goals-mobile.png` |
| Accessible | ✅ PASS | h1; button has text content (no aria-label needed) |
| Functional | ❌ FAIL | `GET /api/goals` → **200 `{"data":[]}`** (real, empty DB — healthy). But "+ New Goal" is a **dead button**: `<button>` with **no onClick** ([GoalsView.tsx:57-59](web/src/views/GoalsView.tsx#L57)) — clicked (virtual cursor): no dialog, no state change, no navigation (verified via DOM after click) |
| As-designed (P2 §33 Personal Goals; FEATURES.md §4: create/track, progress bars, status indicators, due dates) | ❌ FAIL | No create flow, no progress/status/due-date rendering, no empty-state guidance beyond "0 total goals" |

**Live data:** 0 goals (real API, healthy 200). **Mock:** none.
**Gaps:** G-1 dead "+ New Goal" CTA; G-2 no empty-state copy; G-3 P2 §33 goal lifecycle (sources, tasks under a goal) entirely absent from the UI contract.

### 4.5 Tasks (Task DAG) — `/tasks`
| Check | Verdict | Evidence |
|---|---|---|
| Valid (renders) | ✅ PASS | h1 "Task DAG" + 8-state legend render; zero task rows (no empty-state message); `tasks-desktop.png`, `tasks-mobile.png` |
| Accessible | ✅ PASS | Legend is real text; page reachable |
| Functional | ❌ FAIL | `GET /api/tasks` → **500 Internal Server Error**. Backend traceback (sanitized, from api pod logs): `sqlalchemy.exc.ProgrammingError … column tasks.dependencies does not exist` at `list_tasks` ([backend/tasks/service.py:271](backend/tasks/service.py#L271)) — **schema/migration drift**: the tasks table lacks the `dependencies` column the query selects. Client swallows it → `[]` via `listFromResponse` ([client.ts:152-155](web/src/api/client.ts#L152)) |
| As-designed (P1 §50: must visibly distinguish PENDING/READY/RUNNING/BLOCKED/VERIFYING/SUCCEEDED/FAILED; concurrent execution visibly obvious) | ❌ FAIL | Legend exists but no task is ever renderable; dependency graph / concurrency display does not exist in the view (flat list markup only, [TaskDagView.tsx:90-133](web/src/views/TaskDagView.tsx#L90)); field mismatch `task_id/state` vs real backend `id/status` acknowledged in-source ([TaskDagView.tsx:10-12](web/src/views/TaskDagView.tsx#L10)) |

**Live data:** none (500). **Mock:** none.
**Gaps:** T-1 backend 500 (missing `tasks.dependencies` column) breaks both the Tasks view and the Overview "Pending Tasks" tile; T-2 500 swallowed → view looks like "no tasks" instead of an error state (contrast with Systems, which at least shows a banner); T-3 no dependency-DAG visualization despite "Task DAG" name.

### 4.6 Agents — `/agents`
| Check | Verdict | Evidence |
|---|---|---|
| Valid (renders) | ✅ PASS | h1 "Agents", "2 total agents", 2 cards, "+ Add Agent" button; `agents-desktop.png`, `agents-mobile.png` |
| Accessible | ⚠️ PARTIAL | Status shown as a **bare colored dot with no text/aria-label** ([AgentsView.tsx:89-94](web/src/views/AgentsView.tsx#L89)) — screen-reader users get no status; rest of page fine |
| Functional | ❌ FAIL | `GET /api/agents` → **200** with the backend's hardcoded 2-record fixture ([agents.py:31-33](backend/api/endpoints/agents.py#L31)) — **not** DB data, **not** the frontend mockClient. Cards render `CPU Usage %` / `Memory Usage %` / `Tasks Completed` / `Tasks Failed` / `Last Heartbeat` as **blank** because the fixture has only `{id,name,status}` — all other fields are `undefined` (verbatim DOM: "CPU Usage\n%\nMemory Usage\n%\nTasks Completed\n\nTasks Failed\n\nLast Heartbeat"). "+ Add Agent" is another **dead button** (no onClick, [AgentsView.tsx:66-68](web/src/views/AgentsView.tsx#L66)) — clicked: no effect |
| As-designed (FEATURES.md §6: health/status, CPU+memory viz, task completion stats, last heartbeat) | ❌ FAIL | Every metric row renders empty; no agent detail; no type shown (empty `type` field → blank line under name) |

**Live data:** 2 fixture agents (backend-side fixture — indistinguishable in-UI from real agents; this is the only "mock-like" content in the app). **Frontend mockClient fallback:** never used.
**Gaps:** A-1 backend fixture masquerading as live fleet; A-2 five undefined metric fields render as blank labels; A-3 dead "+ Add Agent"; A-4 status dot not labeled.

## 5. Cross-cutting defects

| ID | Defect | Evidence |
|---|---|---|
| X-1 | **No auth gate on any view** — `RequireAuth` exists but is wired to zero routes; the entire app is readable unauthenticated as "Guest" | [App.tsx:24-42](web/src/App.tsx#L24); `grep RequireAuth web/src --include=*.tsx` → definition only |
| X-2 | **Backend endpoints that the UI depends on are 501/500**: `/api/tasks` 500 (schema drift), `/api/overview` 501, `/api/systems` 501, `/api/metrics` 501 — Overview §49 contract is unsatisfiable at the deployed revision | [wiring context: backend/api/app.py:106-109](backend/api/app.py#L106); pod log traceback |
| X-3 | **Silent data masking**: `listFromResponse` maps any error/non-list body to `[]` ([client.ts:122-138](web/src/api/client.ts#L122)); Overview/Tasks render "0"/blank with no error surface, unlike Systems which shows a banner | in-page fetch probes: `/api/tasks`=500 yet tile shows 0 |
| X-4 | **Mobile layout (390px)**: fixed `w-64` sidebar never collapses ([Layout.tsx:29](web/src/components/Layout.tsx#L29)); measured at 390px: sidebar 191px, main content column **199px** (no horizontal overflow, `scrollWidth=390`, but content is squeezed to ~half width; no hamburger/ARIA-expanded nav) — matches prior-audit spec item ([specs/web-quality-audit/spec.md:17-18](specs/web-quality-audit/spec.md#L17)) | `overview-mobile.png` + geometry probe |
| X-5 | **Emoji icon system in nav** (`📊🖥️⏱️🎯📋🤖🧠⚠️📜💬`) — no `aria-label` on nav links (text content carries the name, so functionally OK, but fails prior-audit rule §5) | [Layout.tsx:10-21](web/src/components/Layout.tsx#L10) |
| X-6 | **Dead CTA pattern**: both create buttons ("+ New Goal", "+ Add Agent") are visually enabled but do nothing | §4.4, §4.6 |
| X-7 | **No empty-state copy** on Goals/Tasks/Agents lists ("0 total goals" / blank) — users cannot tell "no data yet" from "feature broken" | screenshots |
| X-8 | **Versioned alias gap**: `GET /api/v1/tasks` → 404 `{"detail":"Not Found"}` while unversioned `/api/tasks` exists (500) — inconsistent with the `/api/v1` base advertised by [backend/api/versioning.py:15-16](backend/api/versioning.py#L15); UI uses unversioned paths so no functional impact today | probe |

## 6. Console/network error ledger (verbatim, per view)

| View | Console error(s) verbatim | Network |
|---|---|---|
| Login | `Failed to load resource: the server responded with a status of 403 (Forbidden)` · `Login error: Error: Login failed at i (http://127.0.0.1:8080/assets/index-BoWc-G3Z.js:67:3045) at async f (http://127.0.0.1:8080/assets/index-BoWc-G3Z.js:67:45307)` · (2nd attempt) `Failed to load resource: the server responded with a status of 401 (Unauthorized)` | `POST /api/auth/login` → 403 / 401 |
| Overview | `Failed to load resource: the server responded with a status of 500 (Internal Server Error)` | `GET /api/goals` 200 · `GET /api/agents` 200 · `GET /api/incidents` 200 · `GET /api/tasks` **500** |
| Systems | `Failed to load resource: net::ERR_CONNECTION_REFUSED` · `TypeError: Failed to fetch at Object.getSystems (http://127.0.0.1:8080/assets/index-BoWc-G3Z.js:67:7999) at Object.health (http://127.0.0.1:8080/assets/index-BoWc-G3Z.js:67:9578)` · page banner: "Failed to fetch system status" | `GET /api/systems` → 307 → `/api/systems/` → **501** |
| Goals | — (clean) | `GET /api/goals` 200 |
| Tasks | `Failed to load resource: the server responded with a status of 500 (Internal Server Error)` | `GET /api/tasks` **500** |
| Agents | — (clean) | `GET /api/agents` 200 |

Note: console capture was done per-navigation (cleared between views); entries above are from the dedicated capture for each view.

## 7. Live-vs-mock summary per view

| View | Real API data shown? | Mock fallback? | Backend state |
|---|---|---|---|
| Login | n/a (auth exchange only) | No | 403 disabled / 401 unknown; SSO off |
| Overview | Yes (goals/agents/incidents counters) | No | tasks 500 masked as 0; overview 501 unused by view |
| Systems | No — never reaches data | No | 501 unwired |
| Goals | Yes (empty list, healthy) | No | 200 `[]` |
| Tasks | No | No | 500 schema drift |
| Agents | Partial — backend **fixture** (2 records), not DB; fields undefined in UI | No (frontend mockClient never engaged) | 200 fixture |

**Global:** the app is in real-API mode (`VITE_API_BASE=/api` baked, [Dockerfile:31-35](web/Dockerfile#L31)); `useMockMode` is false; zero mock-client code paths executed.

## 8. Screenshot inventory (`web/screenshots/audit-live/`)

Desktop 1280×800: `login-desktop.png`, `login-error-desktop.png`, `overview-desktop.png`, `systems-desktop.png`, `goals-desktop.png`, `tasks-desktop.png`, `agents-desktop.png`
Mobile 390×844: `login-mobile.png`, `overview-mobile.png`, `systems-mobile.png`, `goals-mobile.png`, `tasks-mobile.png`, `agents-mobile.png`
(13 files total; error-state shot included for Login.)

## 9. Verification limits (NOT TESTED / inconclusive)

- Screenshots captured via headless Chromium driven by Playwright MCP; **screenshot content itself was not visually re-inspected by a vision auditor** (this worker is a text-capable gatherer) — handoff to visual-auditor recommended for layout/contrast sign-off.
- Audit ran through the port-forwarded upstream, not the public TLS ingress (host NXDOMAIN from this machine); port-80 ingress behavior verified with `Host:` probes against 10.1.1.12–15.
- Dark mode, focus-trap inside dialogs (none exist), and reduced-motion behavior were not exercised.
- No login success path could be exercised (no credentials exist by design; break-glass disabled), so authenticated-only UI states (role badges, token-authorized fetches, 401-redirect flow in [client.ts:101-103](web/src/api/client.ts#L101)) remain unverified — recorded as gap, not failure.
- Backend 500 traceback read from pod logs (sanitized of credentials); the missing column name is from the SQLAlchemy exception text in the api container log.
