# Live Site Walkthrough Audit — gaps-walk-r2.md

**Worker:** visual-debug (gap-closure round re-run, [walk] pass)
**Date:** 2026-10-08 (17:33–19:20 UTC)
**Scope (6 views only):** Login, Overview, Systems, Agents, Tasks (Task DAG), Goals
**Deployed revision:** TAG `85a9e1a` (registry.celestium.life/nervecenter/web:85a9e1a, api:85a9e1a), K3s ns `nervecenter`, all pods Ready.
**Audit URL:** `http://127.0.0.1:8080` via `kubectl -n nervecenter port-forward svc/web 8080:80` (same pod + nginx reverse proxy the ingress fronts; `nginx.conf.template:37-49` proxies `/api/` → `api.nervecenter.svc:8000`).
**Pre-walk API smoke (live):** `/api/health` 200, `/api/systems/` 200 (3 rows: nervecenter-api, postgres, nats), `/api/tasks` 200 (empty), `/api/goals` 200 (empty), `/api/agents` 200 (14 rows), `/api/overview` 200, `/api/incidents` 200, WS `/api/events/ws` 101 (verified OPEN via in-browser `new WebSocket` probe), `/api/auth/sso/config` → `{"enabled":false,...}`.
**Auth state:** all 6 views walked **unauthenticated** (Guest / No roles), same as the r1 pass — see §2.

---

## 1. Old-gap disposition summary (vs `gaps-walk.md`)

| Gap | r1 state | r2 result | Evidence |
|---|---|---|---|
| LG-1 no default-creds text | FAIL | **PASS** — DOM text scan `/default credentials/i` = no match, desktop + mobile | [login-desktop.png](web/screenshots/audit-live-r2/login-desktop.png), [login-mobile.png](web/screenshots/audit-live-r2/login-mobile.png) |
| LG-3 401 → field-associated error | FAIL (hardcoded banner) | **PASS** — 401 renders `role="alert"` `#login-credential-error` "Invalid credentials." between the fields; both inputs get `aria-describedby="login-credential-error"` + `aria-invalid="true"`. 403 renders the backend detail verbatim: "local-admin login is disabled (set NERVE_LOCAL_ADMIN)" | [login-error-desktop.png](web/screenshots/audit-live-r2/login-error-desktop.png), [login-403-detail-desktop.png](web/screenshots/audit-live-r2/login-403-detail-desktop.png) |
| LG-4 SSO surface hidden when disabled | FAIL (dead button) | **PASS (by design)** — button absent from DOM (`GET /api/auth/sso/config` → `enabled:false`); absence is correct, not a defect | `LoginView.tsx:72-81` |
| OV-1 tasks tile reflects real fetch | FAIL (silent zero on 5xx) | **PASS** — tiles show live counts (Goals 0, Agents 14, Tasks 0, Incidents 0) matching `GET /api/overview`; `assertOk` guard converts non-2xx to a visible banner ([OverviewView.tsx:83-99](web/src/views/OverviewView.tsx#L83)) | [overview-desktop.png](web/screenshots/audit-live-r2/overview-desktop.png) |
| OV-2 no fake Goal 1/2/3 or fake agents | FAIL (hardcoded fixture) | **PASS** — Goals panel shows honest empty state ("No goals yet…"); Agents panel renders the 14 real backend rows (Planner, Repository Inspector, …) | [overview-desktop.png](web/screenshots/audit-live-r2/overview-desktop.png) |
| SY-2 WS badge reflects REAL state | FAIL (fake green) | **PARTIAL** — badge is now honest (real `WebSocketClient` state machine, visible text "Real-time: Reconnecting", `role="status"` + `aria-label`), but it subscribed to a **non-existent `/ws/systems`** while the only live socket is `/api/events/ws` (verified OPEN) → can never reach "Connected". **Fixed in `web/src` (see §6, D-10)** | [systems-desktop.png](web/screenshots/audit-live-r2/systems-desktop.png), [systems-badge-mobile.png](web/screenshots/audit-live-r2/systems-badge-mobile.png) |
| SY-3 error banner shows detail on failure | FAIL (generic banner) | **CODE PASS / LIVE FAIL** — banner renders `status — detail` (`formatApiError`), but the live fetch never returns an error body because the request dies on the 307 redirect before any FastAPI response (see D-9) | [systems-desktop.png](web/screenshots/audit-live-r2/systems-desktop.png) |
| TA-3 table/nodes use id/name/status | FAIL (UUID-only) | **PASS** — DAG nodes render title + status badge + priority/level ("Collect GPU evidence · COMPLETED · P50 · L0"); `data-testid="task-node-*"`; real `/api/tasks` empty → honest empty state | [tasks-dag-edges-desktop.png](web/screenshots/audit-live-r2/tasks-dag-edges-desktop.png) (stubbed), [tasks-desktop.png](web/screenshots/audit-live-r2/tasks-desktop.png) (real empty) |
| TA-2 DAG edges render | UNVERIFIED (empty list) | **PASS (verified on deployed bundle)** — since `POST /api/tasks` 500s (D-4), seeded 4 tasks via an in-page `fetch` stub (SPA navigation preserved the stub); all 4 edges rendered: `task-edge-task-a-task-b`, `task-edge-task-a-task-c`, `task-edge-task-b-task-d`, `task-edge-task-c-task-d` + 5 SVG shapes. Real-create path NOT TESTED (blocked by D-4) | [tasks-dag-edges-desktop.png](web/screenshots/audit-live-r2/tasks-dag-edges-desktop.png) |
| GL-1 New Goal works end-to-end | FAIL | **BLOCKER (backend)** — form opens, submits, and surfaces the exact failure: `500 — HTTP 500` in a `role="alert"` banner; form stays open for retry. `POST /api/goals` does **exist** and is **unauthenticated** (no 401/403) but returns **HTTP 500** — see D-4 | [goals-create-error-desktop.png](web/screenshots/audit-live-r2/goals-create-error-desktop.png) |
| GL-2 progress/status/due-date render | FAIL | **NOT TESTED live** — no goals can exist while D-4 blocks creation; normalizer handles `title/progress(0..1)/deadline` (`GoalsView.tsx:35-45`), `formatDate` → "No due date" fallback at `GoalsView.tsx:47-52` | code inspection |
| AG-2 status dot has text+aria | FAIL (bare dot) | **PASS** — each card: `<span role="img" aria-label="Planner status: active">` + visible "active" text (`data-testid="agent-status"`) | [agents-desktop.png](web/screenshots/audit-live-r2/agents-desktop.png) |
| AG-3 Add Agent enabled → 201 → card | FAIL (disabled) | **PARTIAL** — "+ Add Agent" enabled; form (Name required, Type select, Description) submits; **`POST /api/agents` returns HTTP 500** and the banner shows "500 — Internal Server Error". The write *partially persisted* (probe agent appears in `GET /api/agents` at 16) but no new card appears because the refresh path 500s — see D-4/D-5 | [agents-add-error-desktop.png](web/screenshots/audit-live-r2/agents-add-error-desktop.png) |
| CC-4 mobile ≥70% content, hamburger one-tap, no h-scroll | FAIL | **PASS** — at 390px: `documentElement.scrollWidth == innerWidth` on **all 6 views** (no horizontal scroll); login form width 326px = **83.6%** of viewport; hamburger `aria-label="Open navigation"`, one tap → `aria-expanded=true` + all 10 nav links visible | [overview-mobile.png](web/screenshots/audit-live-r2/overview-mobile.png), [overview-mobile-nav-open.png](web/screenshots/audit-live-r2/overview-mobile-nav-open.png) |
| CC-3/D-7 visible focus ring on Tab | FAIL | **PASS** — Tab on login focuses input with `outline: rgb(37,99,235) solid 2px` + `box-shadow … 0 0 0 2px rgb(59,130,246)` (visible ring) | [login-focus-mobile.png](web/screenshots/audit-live-r2/login-focus-mobile.png) |
| D-4 SVG icons + aria-current | FAIL (emoji/unicode) | **PASS** — Layout nav uses `icons.tsx` SVG components (grep: 11 icon imports, 0 emoji in nav); active item carries `aria-current="page"` (`Layout.tsx:157`), observed live on Overview/Systems/Goals/Tasks/Agents | [overview-mobile-nav-open.png](web/screenshots/audit-live-r2/overview-mobile-nav-open.png) |
| D-2/D-3 login acceptance | FAIL | **PASS** — labeled Username/Password fields, visible "Sign in", no hints, error states verified above | — |
| D-6 secondary-text contrast | FAIL (measured <3:1 in r1) | **PASS** — measured computed colors: tagline `rgb(107,114,128)` on `rgb(243,244,246)` = **4.39:1** (AA for 14px); nav-active `rgb(29,78,216)` on `rgb(239,246,255)` = **6.16:1**; login tagline on white = **4.83:1** | in-browser `getComputedStyle` + WCAG luminance calc |

## 2. Login outcome — **FAIL (no working auth path exists live; unchanged from r1)**

- UI posts `POST /api/auth/login`. Backend only accepts the username `local-admin` ([`auth.py:205-222`](backend/api/auth.py#L205)) and requires `NERVE_LOCAL_ADMIN` enabled + `NERVE_LOCAL_ADMIN_PASSWORD`. Live config: `local_admin_enabled: false` (from `/api/auth/sso/config`).
- 401 path exercised: `admin` / `password` → `401 {"detail":"unknown user"}` → field-associated "Invalid credentials."
- 403 path exercised: `local-admin` / (any) → `403 {"detail":"local-admin login is disabled (set NERVE_LOCAL_ADMIN)"}` → detail shown verbatim in submit-error banner.
- User-provided SSO credentials (`/tmp/key`) were **not usable** against this deployment: SSO `enabled:false` (no SSO button in DOM, correctly), and the same username/password via `POST /api/auth/login` → `401 unknown user`. The ingress domain `nervecenter.celestium.life` is also unresolvable from this machine (NXDOMAIN) but reachable via `--resolve` to ingress IPs (10.1.1.12–15) — SSO config there is identically `enabled:false`.
- **Views are browsable unauthenticated** (`RequireAuth` is not mounted on any route — same as r1). This is a pre-existing architectural fact, not a new defect.

## 3. Per-view findings

### 3.1 Login — `/login` — **PASS**
- No "Default credentials" text anywhere in DOM (LG-1 ✓). SSO button absent when disabled (LG-4 ✓, correct behavior).
- 401 → field-associated `role="alert"` error + `aria-describedby`/`aria-invalid` on both inputs (LG-3 ✓). 403 → backend detail shown verbatim (LG-3 ✓).
- Pending state: submit is awaited (button disabled while in-flight — verified by code [LoginView.tsx:83-110](web/src/views/LoginView.tsx#L83) + observed no double-post).
- Mobile 390px: no horizontal scroll; form 83.6% viewport width (CC-4 ✓). Tab → visible blue focus ring (CC-3/D-7 ✓).
- Console: exactly 1 expected error per failed attempt (`Failed to load resource … 401/403`); no other errors.

### 3.2 Overview — `/` — **PASS**
- Tiles reflect real `GET /api/overview` (Agents 14; Tasks 0; Goals 0; Incidents 0) — honest zeros, no silent-failure masking (OV-1 ✓).
- Goals panel: honest empty state, no hardcoded Goal 1/2/3 (OV-2 ✓). Agents panel: 14 real backend rows with name + "Active" (OV-2 ✓).
- No error banners (all fetches 200). Console clean apart from r1-era login 401/403 remnants cleared before walk.
- Mobile: tiles stack cleanly, no horizontal scroll.

### 3.3 Systems — `/systems` — **FAIL (two live defects, both fixed in web/src; see §6 D-9/D-10)**
- **Live (as deployed, TAG 85a9e1a):** badge = "Real-time: Reconnecting" (red, `role="status"`); panel = error banner "System status unavailable / Failed to fetch / The /api/systems endpoint is not wired yet…". **The panel is empty even though `GET /api/systems/` returns 200 with 3 healthy rows.**
- Root cause A (REST): the client fetches **slashless** `/api/systems` ([client.ts:432](web/src/api/client.ts#L432), pre-fix) while the route is `@router.get("/")` on prefix `/api/systems` ([systems.py:29](backend/api/endpoints/systems.py#L29)) → FastAPI 307 with absolute `Location: http://127.0.0.1/api/systems/` (port stripped under port-forward) **and** `Location: http://nervcenter.celestium.life/api/systems/` (**scheme downgraded to http via the real ingress** too — verified via `--resolve` curl) → browser follow fails cross-origin/cross-scheme → `Failed to fetch`. Reproduced in-page: `fetch('/api/systems', {redirect:'manual'})` → opaque redirect; `fetch('/api/systems/')` → 200 with 3 rows.
- Root cause B (WS): badge socket pointed at **`/ws/systems`** ([SystemsView.tsx:106](web/src/views/SystemsView.tsx#L106), pre-fix) which does not exist — it serves the SPA `index.html` (HTTP 200), so every handshake fails. Console (verbatim, 15+ occurrences): `WebSocket connection to 'ws://127.0.0.1:8080/ws/systems' failed: Error during WebSocket handshake: Unexpected response code: 200`. The real endpoint `/api/events/ws` was probed in-page and returned `OPEN` — so the transport works; only the URL was wrong. The badge was *honest* (never fake-green) but could never show "Connected" (SY-2).
- **Fixes applied in `web/src`** (pending redeploy): `getSystems` → `/systems/` (`client.ts`); `useRealtimeUpdates('/api/events/ws', …)` + shape-guard so event frames never clobber the list (`SystemsView.tsx`). `tsc --noEmit` clean.
- Mobile: badge + banner render without overflow; no horizontal scroll.

### 3.4 Agents — `/agents` — **PASS (AG-2, AG-3 front half) / BLOCKED (AG-3 back half, backend D-4/D-5)**
- 14 real agent cards (name, type-id, status text). Status indicator: `role="img" aria-label="Planner status: active"` + visible "active" + green dot `aria-hidden` (AG-2 ✓, `data-testid="agent-status"`).
- "+ Add Agent" enabled (AG-3 ✓ front). Form: Name (required), Type (select, native types), Description. Submit → `POST /api/agents` → **HTTP 500** → banner "500 — Internal Server Error", form stays open (honest error handling ✓).
- **Side effect observed:** the 500'd POST **persisted** the agent anyway (`GET /api/agents` → 16 rows incl. `audit-r2-probe`, `audit-r2 probe agent`; Overview tile went 14→16). So the write succeeds in a partial step and a later step 500s — see D-5. Probe rows were **not deleted** (no authed/working delete path to test); noted for cleanup.
- Mobile: 16 cards stack cleanly, Add Agent reachable, no horizontal scroll.

### 3.5 Tasks (Task DAG) — `/tasks` — **PASS (empty state + edge renderer) / NOT TESTED (real create, blocked D-4)**
- Real `GET /api/tasks` → 200 empty → honest empty state: "No tasks scheduled. Tasks appear here when goals or decisions are decomposed into work; the dependency graph renders as each task lands." + status legend. No silent errors (TA-1/OV-1 discipline ✓).
- TA-2 edge renderer verified on the **deployed bundle** with an in-page `fetch` stub (4 tasks, 2-level dependency tree; SPA navigation preserved the stub): all 4 `data-testid="task-edge-*"` elements rendered with correct cubic-bezier paths, 4 `task-node-*` nodes showing title + status badge + `P<priority> · L<level>`. [tasks-dag-edges-desktop.png](web/screenshots/audit-live-r2/tasks-dag-edges-desktop.png).
- TA-3: nodes use title/name + status (real backend shape `id/title/status` normalized at [TaskDagView.tsx:82-95](web/src/views/TaskDagView.tsx#L82)) ✓.
- Real end-to-end create-with-dependencies **NOT TESTED** — `POST /api/tasks` 500s (D-4).

### 3.6 Goals — `/goals` — **PASS (form + error surfacing) / BLOCKER (GL-1, backend D-4)**
- Empty state honest ("0 total goals", "+ New Goal" enabled). Create form: Name (required), Description, Priority (0–10), Due date (date input) (GL-2 inputs ✓).
- Submit "Audit R2 live-goal" + due 2026-11-01 → `POST /api/goals` → **HTTP 500** → `role="alert"` banner **"500 — HTTP 500"**, form remains open for retry. UI is correct end-to-end; the route exists, is unauthenticated, and fails server-side. **This is the GL-1 blocker.**
- GL-2 (progress/status/due-date rendering on a created row) **NOT TESTED live** — no goal can exist while D-4 blocks create. Normalizer + `formatDate` verified by code.
- Mobile: form opens/renders without overflow; no horizontal scroll.

## 4. Cross-cutting defects

### D-4 (BLOCKER, backend) — every mutation endpoint 500s on datetime serialization
`POST /api/goals`, `POST /api/agents`, `POST /api/tasks` (title-only payload) **all** return HTTP 500. API pod logs (verbatim):
```
sqlalchemy.exc.ProgrammingError: … column "deadline" is of type timestamp with time zone
but expression is of type character varying
[SQL: INSERT INTO goals (id, created_at, …) VALUES ($1::UUID, $2::TIMESTAMP …, $12::VARCHAR, …)]
```
and the same for `due_at` on `tasks`. Root cause: services build the ORM via the schema with `model_dump(mode="json")`-style projection, serializing `datetime` fields (`created_at`, `deadline`, `due_at`, `scheduled_at`) to ISO strings, then INSERT into `DateTime(timezone=True)` columns — asyncpg rejects str→timestamptz. Affects every write path (goals, tasks, and anything else stamping `created_at`), so GL-1/AG-3/TA-2-real are all blocked on it.

### D-5 (backend, related) — partial-persistence on the agents 500
The 500'd `POST /api/agents` **persisted** the row (16 total agents after 2 probe posts). The failure happens after the INSERT (likely a post-write service/metric step), so the deployment both errors the client and leaves orphan rows. Probe rows `audit-r2-probe` / `audit-r2 probe agent` remain in the live DB (not deleted — no verified safe delete path exercised; user action or cleanup commit recommended).

### D-6 (web, fixed in-repo) — Systems REST fetch uses slashless URL (was the SY-3 "Failed to fetch")
`systemsApi.getSystems` fetched `/systems` while the route is `/api/systems/`. FastAPI's 307 emits an absolute `Location` that strips the port (port-forward) **and** downgrades `https`→`http` (ingress, because nginx forwards `X-Forwarded-Proto: http` and FastAPI doesn't trust it), so the browser follow always fails. Fixed: [`web/src/api/client.ts`](web/src/api/client.ts) `getSystems` → `apiFetch('/systems/')`. (Alternative backend-side fix: `use_redirect_slashes` off or registering `""` — noted for the API round.)

### D-7 (web, fixed in-repo) — SystemsView subscribed to non-existent `/ws/systems`
The WS badge could never be "Connected" against the real deployment because the URL didn't exist (SPA HTML → handshake 200 → error state, 15+ console errors/min). Fixed: [`web/src/views/SystemsView.tsx`](web/src/views/SystemsView.tsx) now subscribes to `/api/events/ws` (verified OPEN) with a comment that the socket drives the badge only.

### D-8 (web, fixed in-repo, safety) — event frames must not clobber the systems list
With D-7 the socket now delivers *event objects* (`{type, payload}` single objects). The old fold effect's `length === 0` guard is `false` for objects (`length === undefined`) and would have run `setSystems(eventObject)`. Added a shape guard: only fold in when `Array.isArray(rows) && rows[0]` has string `name` + `status` (a system row).

### D-9 (minor, web copy) — SystemsView fallback error text is stale
The banner tail "The /api/systems endpoint is not wired yet; check the backend service for details." is a hardcoded fallback ([SystemsView.tsx](web/src/views/SystemsView.tsx)) that misdescribes the failure (the endpoint IS wired; the fetch itself failed). The `status — detail` prefix is honest; the suffix is misleading. Left as-is this round (copy nit, not user-blocking); candidate for the final round.

### D-10 (observation, web) — Goals create error banner degrades to "500 — HTTP 500"
`GoalsView` surfaces `formatApiError(err)` = "500 — HTTP 500" (no `detail` available because the server returns a plain "Internal Server Error" body, not FastAPI's `{detail}`). Correct behavior, but once D-4 is fixed the API should return a structured `detail` (or a 500 handler) so the banner can show the real reason.

## 5. Console/network error ledger (verbatim)

| View | Console errors | Network errors |
|---|---|---|
| Login | `Failed to load resource: … 401 (Unauthorized)` ×1 per bad attempt (expected, test data) | POST /api/auth/login → 401 / 403 (expected) |
| Overview | none (after clear) | all GET 200 |
| Systems | `WebSocket connection to 'ws://127.0.0.1:8080/ws/systems' failed: Error during WebSocket handshake: Unexpected response code: 200` (repeating every ~3s reconnect) | GET /api/systems → 307 → redirect-target fail ("Failed to fetch") |
| Agents | none (list fetch 200) | POST /api/agents → 500 (on submit) |
| Tasks | none | GET /api/tasks → 200 |
| Goals | none | POST /api/goals → 500 (on submit) |

## 6. Repro snippets (for the fixer round)

```bash
# D-4 (all three fail identically):
curl -s -X POST http://127.0.0.1:8080/api/goals  -H 'Content-Type: application/json' -d '{"title":"probe"}' -w "\n%{http_code}\n"   # 500
curl -s -X POST http://127.0.0.1:8080/api/tasks  -H 'Content-Type: application/json' -d '{"title":"probe"}' -w "\n%{http_code}\n"   # 500
curl -s -X POST http://127.0.0.1:8080/api/agents -H 'Content-Type: application/json' -d '{"name":"probe","type":"custom"}' -w "\n%{http_code}\n"  # 500 (row persists)
# D-6:
curl -sI  http://127.0.0.1:8080/api/systems   # 307, Location: http://127.0.0.1/api/systems/  (port stripped)
curl -s   http://127.0.0.1:8080/api/systems/  # 200, 3 rows
curl -sI --resolve nervcenter.celestium.life:443:10.1.1.13 https://nervcenter.celestium.life/api/systems
   # 307, Location: http://nervcenter.celestium.life/api/systems/   (scheme downgraded — breaks ingress too)
```

## 7. In-repo fixes applied this round (NOT redeployed — final round must rebuild web image and recapture)

1. [`web/src/api/client.ts`](web/src/api/client.ts) — `getSystems` now fetches `/systems/` (trailing slash) with a comment explaining the 307/Location trap.
2. [`web/src/views/SystemsView.tsx`](web/src/views/SystemsView.tsx) — `useRealtimeUpdates('/api/events/ws', …)` (real endpoint, verified OPEN) + updated comment; realtime fold effect now shape-guards (array-of-rows only) so event frames cannot clobber the REST-derived list.
- Verified: `npx tsc --noEmit` → exit 0 (no type errors).
- **Not fixed (backend, out of web/src scope):** D-4 (datetime→str INSERT), D-5 (agents partial persistence), D-9 (stale banner copy — minor).

## 8. Screenshot inventory (`web/screenshots/audit-live-r2/` — 23 files, all verified non-blank)

| File | State captured |
|---|---|
| login-desktop.png | baseline, empty form |
| login-error-desktop.png | 401 field-associated error |
| login-403-detail-desktop.png | 403 backend detail banner |
| login-mobile.png | 390px baseline (no h-scroll, form 83.6%) |
| login-focus-mobile.png | Tab focus ring on password input |
| overview-desktop.png | tiles + real goals/agents panels |
| overview-mobile.png | 390px, nav collapsed |
| overview-mobile-hamburger-closed.png | header, burger closed |
| overview-mobile-nav-open.png | one-tap hamburger, 10 links, aria-current |
| systems-desktop.png | badge "Reconnecting" + Failed-to-fetch banner |
| systems-badge-mobile.png | 390px badge + banner, no overflow |
| agents-desktop.png | 14 cards, status dot + text + aria |
| agents-add-open-desktop.png | Add Agent form open |
| agents-add-error-desktop.png | "500 — Internal Server Error" banner |
| agents-mobile.png | 390px cards |
| tasks-desktop.png | honest empty state + legend |
| tasks-mobile.png | 390px empty state |
| tasks-dag-edges-desktop.png | 4 nodes + 4 edges (fetch-stub seeded, deployed bundle) |
| goals-empty-desktop.png | 0 goals empty state |
| goals-create-open-desktop.png | create form (name/desc/priority/due) |
| goals-create-error-desktop.png | "500 — HTTP 500" banner, form open |
| goals-mobile.png | 390px empty state |
| goals-create-mobile.png | 390px create form |

## 9. Verification limits (NOT TESTED / inconclusive)

- **GL-1 / AG-3 / TA-2-real:** end-to-end create flows cannot complete live — all `POST /api/{goals,agents,tasks}` return 500 (D-4). UI error handling for each was verified (banner + open form + correct HTTP status reported).
- **GL-2:** progress/status/due-date *rendering* on a real row untested (no creatable row); normalizer verified by code + mock fixtures.
- **Authenticated views:** no working login path live (SSO disabled, local-admin disabled) — all views walked as Guest, same as r1. `/tmp/key` SSO credentials unusable against this deployment.
- **D-5 cleanup:** the two probe agents remain in the live DB; no safe/verified delete path was exercised to remove them.
- **Post-fix verification:** D-6/D-7/D-8 fixes are in `web/src` only — the *deployed* bundle (85a9e1a) still exhibits D-6/D-7. Rebuild + redeploy + recapture required to confirm (final round).
