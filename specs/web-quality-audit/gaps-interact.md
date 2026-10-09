# Live Interaction Audit — Incidents / Decisions / Timeline / Ask / Inference

**Worker:** interact (visual-debug, Playwright virtual cursor)
**Date:** 2026-10-06T22:17–22:35Z
**Target:** live deployment, K3s ns `nervecenter`, deployed image `registry.celestium.life/nervecenter/web:50e4c83` (pod `web-ddd6f8f99-vjqt8`, imageID sha256:6adbc402…), matches TAG 50e4c83. api/mcp/nats/postgres Running/Ready; migrate-job Completed.
**Companion file:** this is the interaction/live-evidence half; `gaps-walk.md` (sibling worker) covers the static walk.

## URL used

- Ingress `nervcenter-celestium` → host `nervecenter.celestium.life` (traefik, 80/443): **NXDOMAIN from this host** (`curl: (6) Could not resolve host`).
- Fallback used: `kubectl port-forward -n nervecenter svc/web 18321:80` → **`http://127.0.0.1:18321`** (nginx 1.27.5, HTTP 200, `GET /api/health` → 200 `{db: ok, nats: connected, jetstream: available}`).

## Login outcome (recorded verbatim)

- The app is **ungated**: [`App.tsx`](../../web/src/App.tsx:26) wraps routes in `Layout` with **no `RequireAuth`** ([`RequireAuth.tsx`](../../web/src/components/RequireAuth.tsx:4) exists but is never used in [`App.tsx`](../../web/src/App.tsx:1)). All 5 views are reachable unauthenticated ("Guest / No roles").
- [`LoginView.tsx`](../../web/src/views/LoginView.tsx:91) still advertises **"Default credentials: admin / password"** (spec: S101 removed the default user).
- Submitting `admin`/`password` live: `POST /api/auth/login` → **401** `{"detail":"unknown user"}` (confirmed by curl and in-browser). UI error (verbatim): **"Invalid credentials. Please try again."** ([`LoginView.tsx:22`](../../web/src/views/LoginView.tsx:22)). Console (verbatim):
  ```
  [error] Failed to load resource: the server responded with a status of 401 (Unauthorized)
  [error] Login error: Error: Login failed
      at i (http://127.0.0.1:18321/assets/index-BoWc-G3Z.js:67:3045)
      at async f (http://127.0.0.1:18321/assets/index-BoWc-G3Z.js:67:45307)
  ```
- `GET /api/auth/sso/config` → `{"enabled":false, "local_admin_enabled":false, "client_id":""}` → **no valid credential path exists on live**; login = GAP (cannot reach authenticated state; no secrets were printed).
- [`AuthContext.tsx:24`](../../web/src/auth/AuthContext.tsx:24): any truthy `localStorage.authToken` is accepted as `admin` **without verification** (comment: "In a real implementation, decode and verify the token"). Auth is a shell.
- Note: task brief referenced `POST /api/v1/auth/login`; the real route is `POST /api/auth/login` ([`backend/api/auth.py:6`](../../backend/api/auth.py:6)) — `/api/v1/…` returns 404.

## Live vs mock (per view)

Deployed bundle is in **LIVE mode**: `VITE_API_BASE=/api` is baked in at build ([`web/Dockerfile:29`](../../web/Dockerfile:29)); the deployed JS contains the literal `"/api"`; `useMockMode=false` ([`client.ts:11`](../../web/src/api/client.ts:11)). **Mock fixtures are never used on the live site.** Per view: Incidents → live `GET /api/incidents`; Decisions → live `GET /api/decisions`; Timeline → **no API at all** (hardcoded sample); Ask → live `POST /api/context/ask`; Inference → live `GET /api/compute`, `/api/routes`, `/api/models/history`.

## View verdicts

### Incidents — READ-ONLY, create/resolve/close UNIMPLEMENTED
- `GET /api/incidents` → 200 `{"data":[]}` — **live, empty** (no incidents in DB). Renders "0 active incidents"; no empty-state guidance copy.
- **"+ Report Incident" is a dead button** ([`IncidentsView.tsx:75`](../../web/src/views/IncidentsView.tsx:75)): no `onClick`. Live click → no dialog, no input, no API call, no navigation (verified via DOM + resource timing).
- No edit/resolve/close flows; no filters; no severity/status filtering controls. No mutation endpoints exist backend-side (list-only).
- Console: **0 errors** on load. Loading state present ([`IncidentsView.tsx:73`](../../web/src/views/IncidentsView.tsx:73)).
- Verdict vs contract (P1 §48 view set + P2 incident severity semantics [`prompt2.md:789`](../../prompt2.md:789)): **FAIL as-designed** — display-only, all actions fake.

### Decisions — BACKEND 501, GRACEFUL DEGRADE, create UNIMPLEMENTED
- `GET /api/decisions` → **501** (verbatim body): `{"detail":"Decisions list endpoint requires the decisions service to be wired via app.state.services."}` — console error on load: `Failed to load resource: … 501 (Not Implemented)`.
- View does **not** crash: `listFromResponse` degrades to `[]` ([`client.ts:125`](../../web/src/api/client.ts:125)); renders "0 total decisions". Backend defines the route but the service is unwired ([`backend/api/app.py:112`](../../backend/api/app.py:112)).
- **"+ New Decision" is a dead button** ([`DecisionsView.tsx:62`](../../web/src/views/DecisionsView.tsx:62)) — click → no dialog, no request.
- No decision detail/edit/revoke flows.
- Verdict: **FAIL** — 501 backend defect + create unimplemented; error state handled gracefully (no user-facing error copy; only console + empty list).

### Timeline — HARDCODED SAMPLE DATA, NO LIVE FEED, NO CONTROLS
- **Zero API requests** (verified via `performance.getEntriesByType('resource')`). Renders exactly the 5 `sampleEvents` hardcoded in `useEffect` ([`TimelineView.tsx:16`](../../web/src/views/TimelineView.tsx:16), `setEvents(sampleEvents)` at [`TimelineView.tsx:53`](../../web/src/views/TimelineView.tsx:53)) — dated 2026-09-28, fakes like `Agent "data-processor" started successfully`.
- This is **not** the `mockClient` fixture — it's inline sample data presented with no "sample/demo" labeling, so it reads as live history. It is neither live data nor the declared mock mode.
- **No filtering, no scrubbing, no date range, no controls** (only focusable control on the page: Logout). No link to `/api/events`.
- Console: **0 errors**.
- Verdict: **FAIL** — non-functional view; static sample; no interaction to exercise.

### Ask — WORKS AS-DESIGNED (ACK PATH); answer path unreachable; label gap
- Live submit "What is the status of the deploy?" → `POST /api/context/ask` → **202** (verbatim body): `{"accepted":true,"executed":false,"service":"context","detail":"No 'context' service is configured; mutation accepted but not executed.",…}`.
- UI renders the ack correctly: **"Request accepted (execution: pending). No 'context' service is configured; mutation accepted but not executed."** ([`AskView.tsx:75`](../../web/src/views/AskView.tsx:75)–[`78`](../../web/src/views/AskView.tsx:78)). No crash, no console errors.
- Validation: **Send is disabled when input empty** (verified `disabled:true` after submit + when empty); empty submit is a no-op ([`AskView.tsx:49`](../../web/src/views/AskView.tsx:49)).
- 4 "Quick Questions" chips present (functional shortcuts to the same path).
- Gaps: message input has **placeholder only, no `aria-label`/label association** (AC-W05 form-rule gap); no provenance/evidence rendering possible because the 202 ack carries none; the 200 answer path (answer + facts/hypotheses per [`AskView.tsx:11`](../../web/src/views/AskView.tsx:11)) is **unreachable on live** (context service unwired) — NOT TESTED end-to-end.
- Verdict: **PASS (ack path, live)**; answer+evidence path blocked by backend config.

### Inference — LIVE BUT EMPTY, NO EMPTY-STATE COPY, NO ACTIONS
- Live calls: `GET /api/compute` → 200 `{"data":[]}`; `GET /api/routes` → 200 `{"data":[]}`; `GET /api/models/history` → 200 **`{"id":"history","resource":"models"}`** (single-resource object, not a list — handled by `listFromResponse`).
- Renders the 3 section headers "Physical Nodes / OmniRoute Routes / Historical Model Performance" with **zero items and no empty-state text** — sections look blank. All three use `.map` with no `length===0` branch ([`InferenceView.tsx:100`](../../web/src/views/InferenceView.tsx:100), [`164`](../../web/src/views/InferenceView.tsx:164), [`203`](../../web/src/views/InferenceView.tsx:203)).
- **No interaction controls** (only Logout); no "run inference"/submit action exists in the view.
- Console: **0 errors**.
- Verdict: **PARTIAL** — live wiring correct, graceful empty; missing empty-state copy per P1 §51 (Inference UI) and any submission surface.

## Cross-cutting findings

- **Realtime: UNWIRED.** [`useRealtimeUpdates.ts:11`](../../web/src/hooks/useRealtimeUpdates.ts:11) and [`WebSocketClient.ts:1`](../../web/src/api/WebSocketClient.ts:1) exist but have **zero callers** (grep across `web/src`). No WebSocket route exists in `backend/` and nginx has no WS upgrade proxy (`web/nginx.conf.template` has no `proxy_set_header Upgrade`). **Live data does not arrive on any view; reconnect behavior is not testable** (code: fixed 3000ms reconnect, no backoff/cap — [`WebSocketClient.ts:4`](../../web/src/api/WebSocketClient.ts:4), [`44`](../../web/src/api/WebSocketClient.ts:44)).
- **Global navigation/routing:** 10 sidebar links ([`Layout.tsx:10`](../../web/src/components/Layout.tsx:10)); click navigation verified (Inference→Incidents etc.); deep-link hard reload works (nginx SPA fallback, `GET /timeline` → 200). No routing defects observed.
- **Keyboard/focus:** tab order is logical (10 nav links → Logout → content controls, 12 focusable on Incidents). Focus ring = **browser default** (`outline: auto 1px rgb(0,95,204)` on nav links; no custom `focus:`/`ring` classes anywhere) — visible but unstyled (AC-W04: no design tokens). No focus traps observed.
- **Mobile 390px:** sidebar remains fixed `w-64` ([`Layout.tsx:29`](../../web/src/components/Layout.tsx:29)) = computed **190.9px ≈ 49% of viewport**; no collapse/hamburger (AC-W03 fail, confirmed live). No horizontal overflow at 390px (`scrollWidth === clientWidth`).
- **Empty/error/loading states:** loading spinner text present (Incidents/Decisions "Loading…"); error → empty list (Decisions); empty states lack guidance copy (Incidents count only, Inference blank sections, Timeline shows sample data instead).
- **Console/network errors (verbatim, live):**
  | View | Console error | Network |
  |---|---|---|
  | Incidents | none | `/api/incidents` 200 |
  | Decisions | `Failed to load resource: … 501 (Not Implemented)` | `/api/decisions` 501 |
  | Timeline | none | **no API calls** |
  | Ask | none | `/context/ask` 202 |
  | Inference | none | `/compute` 200, `/routes` 200, `/models/history` 200 |
  | Login | `Login error: Error: Login failed` (stack above) | `/auth/login` 401 |
  | Overview (adjacent, out of scope) | `Failed to load resource: … 500 (Internal Server Error)` | `GET /api/tasks` → **500** `Internal Server Error` (backend defect on live) |

## Gap/defect register

1. **G1 Incidents create/resolve/close unimplemented** — dead button [`IncidentsView.tsx:75`](../../web/src/views/IncidentsView.tsx:75); no backend mutation route. (backend+web)
2. **G2 Decisions list 501 on live** — decisions service not wired (`backend/api/app.py:112`); user-visible only as empty list, no error copy. (backend)
3. **G3 Decisions create unimplemented** — dead button [`DecisionsView.tsx:62`](../../web/src/views/DecisionsView.tsx:62). (web)
4. **G4 Timeline renders hardcoded sample events** as if live, no `/api/events` wiring, no filters/scrubbing ([`TimelineView.tsx:16`](../../web/src/views/TimelineView.tsx:16)). (web)
5. **G5 Ask: context service unconfigured** — only 202 ack possible; answer+evidence path NOT TESTED (backend config).
6. **G6 Ask input lacks accessible label** (placeholder-only; AC-W05 form rule). [`AskView.tsx`](../../web/src/views/AskView.tsx) input `placeholder="Type your message..."`, no `aria-label`.
7. **G7 Inference blank sections, no empty-state copy**; `/api/models/history` returns non-list shape (cosmetic for the client, but backend contract inconsistency).
8. **G8 Realtime not wired end-to-end** — zero `useRealtimeUpdates` callers; no backend WS route; no nginx WS proxy; fixed-interval reconnect untested. (web+backend+nginx)
9. **G9 Auth is a shell on live** — login impossible (SSO `enabled:false`, `local_admin_enabled:false`, 401 "unknown user") while all routes are ungated (no `RequireAuth` in [`App.tsx:26`](../../web/src/App.tsx:26)); any `localStorage.authToken` = admin ([`AuthContext.tsx:24`](../../web/src/auth/AuthContext.tsx:24)); dead default-credentials copy [`LoginView.tsx:91`](../../web/src/views/LoginView.tsx:91). (web+backend config)
10. **G10 Mobile sidebar consumes 49% of 390px viewport, no collapse** — AC-W03 fail (live). [`Layout.tsx:29`](../../web/src/components/Layout.tsx:29).
11. **G11 `GET /api/tasks` → 500 on live** (adjacent view; breaks Overview "Pending Tasks").
12. **G12 Emoji navigation icons live** (AC-W02) — confirmed on all views ([`Layout.tsx:11`](../../web/src/components/Layout.tsx:11)).
13. **G13 Focus rings are UA defaults only** — no semantic focus tokens (AC-W01/W04).

## Screenshot list (`web/screenshots/audit-live/`, prefix `interact-`)

Desktop 1280px:
- `interact-incidents-desktop-2026-10-06T22-20-36-243Z.png`
- `interact-decisions-desktop-2026-10-06T22-21-33-058Z.png`
- `interact-timeline-desktop-2026-10-06T22-23-30-219Z.png`
- `interact-ask-desktop-202ack-2026-10-06T22-24-51-011Z.png` (post-submit, 202 ack rendered)
- `interact-inference-desktop-2026-10-06T22-26-03-588Z.png`
- `interact-login-failed-state-2026-10-06T22-33-14-531Z.png`

Mobile 390px (844):
- `interact-incidents-mobile-390-2026-10-06T22-29-55-278Z.png`
- `interact-decisions-mobile-390-2026-10-06T22-30-13-354Z.png`
- `interact-timeline-mobile-390-2026-10-06T22-30-29-431Z.png`
- `interact-ask-mobile-390-2026-10-06T22-30-45-388Z.png`
- `interact-inference-mobile-390-2026-10-06T22-31-04-446Z.png`

## NOT TESTED / limitations

- Authenticated-only flows (approval binding, role-gated mutations) — no valid credentials exist on live (G9).
- Ask 200-answer + provenance rendering — blocked by unwired context service (G5).
- Realtime reconnect under drop — no WS endpoint to attach to (G8).
- Ingress TLS/host path (`nervecenter.celestium.life`) — unresolvable from this host; cluster-internal path only.
- Screenshot *content* interpretation was done via DOM text extraction, not vision review (no visual-auditor handoff performed in this worker; screenshots are provided for the auditor pass).
