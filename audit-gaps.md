# NerveCenter Web — Consolidated Audit Gaps

**Sources (final round, 2026-10-09):**
- [walk-r3] — `specs/web-quality-audit/gaps-walk-r2.md` (final [walk] recapture against the fixed bundle; per-gap PASS verdicts + fresh screenshot manifest; scope: Login, Overview, Systems, Agents, Tasks, Goals)
- [interact-final] — `specs/web-quality-audit/gaps-interact-r2.md` (final [interact] recapture against TAG `bee3fa8`; "all prior [interact] gaps **PASS** on the deployed bundle; N1–N4 resolved"; scope: Incidents, Decisions, Timeline, Ask, Inference)

**Sources (2026-10-11 round — full-stack verification):**
- [local-run] — `uvicorn backend.api.app:app` on :8000 + Vite dev on :3000 with `VITE_API_BASE=/api` (proxy → :8000). `NERVE_MOCK_INFER=1 NERVE_SSO_ISSUER=https://sso.celestium.life/realms/celestium NERVE_LOCAL_ADMIN=1`.
- [tests] — `uv run pytest tests/` and `npx playwright test` in `web/`.
- [sso-live-probe] — `GET https://sso.celestium.life/realms/celestium/.well-known/openid-configuration` + authorizer probe for candidate client ids.

**Sources (2026-10-12 round — prompt2 Phase P0 + SSO + realtime e2e):**
- [attention-p0] — `backend/attention/` (AttentionItem schema + deterministic/explainable scoring) and the `/api/attention` router group; 20 dedicated tests in `tests/backend/test_attention.py`.
- [now-screen] — `web/src/views/NowView.tsx` + `/now` route + `NowIcon` nav item; covered by the AC005 view render matrix.
- [ws-e2e] — `web/tests/e2e/events-ws.spec.ts` exercises `GET /api/events/ws` in a real browser (handshake + honest error-frame contract).
- [sso-live] — `nervecenter` OIDC client provisioned in Keycloak realm `celestium`; live PKCE SSO verified end-to-end.
- [messages-p1] (2026-10-12, same round) — `backend/messages/` service + `/api/messages` router (Personal Operations Plane: thread reconstruction, cross-channel person resolution, AttentionItem generation, draft replies) and the `/messages` web view; 18 tests in `tests/backend/test_messages.py`.
- [calendar-p2] (2026-10-12, same round) — `backend/calendar/` service + `/api/calendar` router (Calendar Integration + Conflict Reasoning, §42/§43: availability guard, free-slot search, §43 "I can do after…" suggestion) and the web **Calendar** screen (`/calendar`); 20 tests in `tests/backend/test_calendar.py`.
- [tests] — `pytest tests/` and `npx playwright test` in `web/`.

## 2026-10-12 Verification Results (after Phase P2)

### Backend test suite
`pytest tests/` → **451 passed** (0 failed, 0 skipped). The 431 after P1 plus 20 new `tests/backend/test_calendar.py` tests (ingest/idempotent upsert, 7-day list horizon, availability window, overlap + all-day conflict detection, free-slot search, §43 suggestion incl. next-day, and honest 404/422s from the `/api/calendar` router).

### Playwright e2e suite
`cd web && npx playwright test` → **44 passed** (0 failed). The 42 from P0 plus:
- `views.spec.ts` — `/calendar` added to the AC005 render matrix (renders the upcoming-events list and the availability/free-slot/§43-suggestion panel with no console errors).
- `views.spec.ts` — `/messages` added to the AC005 render matrix (renders the reconstructed thread list + conversation pane with no console errors).
- (the P0 additions above: `/now` in the render matrix, and the `events-ws.spec.ts` socket handshake/error-frame tests)

### prompt2 Phase P2 (Calendar Integration + Conflict Reasoning)
- **Backend:** new `backend/calendar/` plane — `CalendarEvent` model (with `all_day`, provenance `source`, `participants`) + a `CalendarService` (in-memory, **idempotent upsert by `event_id`**). New `/api/calendar` group: `GET /` (7-day horizon list), `POST /ingest`, `POST /availability` (the **scheduling guard** — `available` + `conflicts[]` + `earliest_free_after`), `POST /free-time` (earliest N-minute gap within a 7-day horizon), and `POST /suggest` (the §43 answer: a free window → "Yes — …"; a blocked window → "I can do after …" naming the conflicting event, with next-day proposals when the day is full). NerveCenter holds only read-only copies (§42); nothing mutates the user's real calendar.
- **Web:** new **Calendar** screen (`/calendar`) — upcoming events + a reasoning panel (check availability / find free slot / suggest §43). Failures surface as `role="alert"` banners (OV-1); an empty schedule is an honest empty state.
- **Not part of this commit:** the actual **calendar-sync bridge** (the Personal Relay's read-only EventKit/CalDAV ingest, §42) — a separate source-side deliverable. The NerveCenter-side contract (`/api/calendar/ingest` + the provenance field on every `CalendarEvent`) is implemented and tested, so the bridge can be built and pointed at it without backend changes.

### prompt2 Phase P1 (Personal Operations — Messages)
- **Backend:** new `backend/messages/` plane — `Message`/`Conversation` models; a `MessagesService` that ingests normalized events (one thread per peer+channel, chronological reconstruction, unread bookkeeping, **idempotent by `message_id`** for relay replay safety, §48), resolves people across channels, and (re)creates **one live `AttentionItem` per conversation** through the shared P0 deterministic scorer (so a source is always explainable, §21/§22). New `/api/messages` group: list, ingest, persons, thread get, acknowledge (resolves the item), draft. In-memory by design (no `NERVE_DB_URL` needed yet, same convention as P0); `NERVE_SEED_MESSAGES=1` pre-populates a demo thread for dev. Drafts are rule-based and read-only — §13 "AI drafts, human sends".
- **Web:** new **Messages** screen (`/messages`) — thread list (unread badges, channel, last activity) + conversation pane; *Mark as read* clears the badge and resolves the AttentionItem; *Draft reply* shows a suggested reply that is explicitly draft-only. Failures surface as `role="alert"` banners (OV-1); empty inbox is an honest empty state.
- **Not part of this commit:** the macOS **Personal Relay daemon** (`nerve-personal-relay`, `prompt2.md` §46/§47 — the read-only source-side bridge that reads local message storage with explicit, user-granted permissions and posts normalized events to `/api/messages/ingest` with full provenance). It is a separate deliverable: its spec lives in `prompt2.md`, and it has not been built yet. The NerveCenter side of the contract (the ingest API, thread reconstruction, and the provenance field on every `Message`) is implemented and tested here, so the relay can be built and pointed at `/api/messages/ingest` without backend changes.

### prompt2 Phase P0 (Personal Operations — Attention)
- **Backend:** `AttentionItem` / `AttentionState` schema and a deterministic, explainable scorer (identical inputs → identical `priority` + `why[]`). New `/api/attention` group: list, `/now`, get, create, resolve, suppress, acknowledge, snooze — all auth-gated, returning `data`/`meta` envelopes with honest 404/422s.
- **Web:** new **Now** screen (`/now`) as the first prompt2 surface — a ranked "what deserves my attention now" queue where each card shows its `priority` and the `why[]` factors, plus create / resolve / snooze / suppress. Failure states surface via `role="alert"` banners (OV-1 contract).

### SSO (B-2) — resolved
- The `nervecenter` OIDC client is now provisioned in Keycloak realm `celestium`. `GET /api/auth/sso/config` returns `enabled:true` with the real issuer/client. Live PKCE login was exercised end-to-end after fixing two frontend bugs (`VITE_API_BASE` and the PKCE `S256` code-challenge). The SSO button renders when `enabled:true` and the break-glass path still works.

### Realtime (RT) — resolved
- `web/tests/e2e/events-ws.spec.ts` now provides browser-level e2e coverage for `GET /api/events/ws` (previously unit-test-only). It targets the backend on `:8000` directly because the Vite proxy forwards WebSocket only for the `/ws/*` prefix, not `/api/*`.

## 2026-10-11 Verification Results

### Backend test suite
`uv run pytest tests/` → **393 passed** in 2.22 s (0 failed, 0 skipped, 0 xfail). Includes `test_schema_param_types`, `test_auth_sso.*`, `test_app_wiring`, `test_gap_closure`, `test_write_api`, `test_evidence`, `test_write_routes_gap3`, `test_events_api`, `test_object_storage`, `test_tasks_dependencies`, `test_agents`, `test_policy/test_pdp`, and the MCP-tools tests under `tests/mcp/`.

### Playwright e2e suite
`cd web && npx playwright test` → **40 passed** in 18.0 s (0 failed, 0 skipped). Coverage:
- `login-shell.spec.ts` — LG-1…LG-4 (no default-cred hint in DOM, 401 maps to a field-associated error, 403 surfaces the real detail, submit button disables with pending label, SSO button only when `enabled:true`).
- `auth-transport.spec.ts` — `apiFetch` injects `Authorization: Bearer <nc.accessToken>` only when a token is present; 401 clears sessionStorage; `/auth/callback` validates PKCE state and exchanges the code; rejects a state mismatch.
- `views.spec.ts` — 10 view-render tests (Overview, Systems, Timeline, Goals, Agents, Inference, Incidents, Decisions, Ask, + the "Ask round-trip").

### Live Keycloak probe
```
GET https://sso.celestium.life/realms/celestium/.well-known/openid-configuration
  → 200 OK, full discovery doc (RS256 JWKS, PKCE authorization_code,
    client_id/audience contract visible in the realm).

GET https://sso.celestium.life/realms/celestium/protocol/openid-connect/auth
  ?client_id=web&response_type=code&redirect_uri=http://localhost:3000/auth/callback&...
  → 400 Bad Request  (no client registered under that id)
  for client_id ∈ { web, client, webapp, nervecenter } — same 400.
```
**Conclusion:** the realm is live and reachable, but **no `nervecenter`/`web`/`webapp`/`client` OIDC client is registered in realm `celestium`**. The SSO button on the web login view therefore correctly stays hidden (`sso/config.enabled == false`) — this is the same outstanding item as `audit-gaps.md` B-2 from 2026-10-09.

### Local service state (verification host)
- `:8000` uvicorn (mock infer, in-process session store) — `/api/health` → 200.
- `:3000` Vite dev server (proxies `/api/*` and `/ws/*` to :8000).
- `GET /api/auth/sso/config` → `{"enabled": false, "client_id": "", "issuer": "https://sso.celestium.life/realms/celestium", "audience": "nervecenter", "local_admin_enabled": true, ...}`.
- 63 API route registrations across `backend/api/*.py`.

### Screenshots (this round)
Captured on the running Vite server: `Home` (default `/`), `/goals`, `/incidents`. All render without console errors, follow the one-accent blue-on-neutral system, and use real empty states — no fake cards. See the Playwright-saved PNGs in the Downloads directory of the verifying host.

## Open items carried into this round
| Id  | Item | Status |
| --- | ---- | ------ |
| B-2 | **Keycloak client for NerveCenter not provisioned in realm `celestium`; `NERVE_SSO_CLIENT_ID` and `NERVE_JWT_SECRET` not set in deployed secret** | **RESOLVED (2026-10-12)** — the `nervecenter` OIDC client is provisioned in realm `celestium`; `sso/config` returns `enabled:true`; live PKCE SSO verified end-to-end. |
| P0  | **`prompt2.md` (Personal Operations & Attention Engine Addendum, 85 sections, Phases P0–P4)** is not implemented in the web UI: no `/attention`, `/now`, `/email`, `/messages`, `/voicemail`, `/calendar`, `/contacts`, `/briefing`, or `/waiting-on` routes; no corresponding API group from `prompt2.md §63` exists in `backend/api/`. | **PARTIALLY CLOSED (2026-10-12, P2 added)** — Phase P0 (Attention Engine): `/api/attention` + `AttentionItem` + the web **Now** screen (`/now`). Phase P1 (Messages, Personal Operations Plane): `/api/messages` ingest/list/persons/thread/acknowledge/draft + `backend/messages/` service + the web **Messages** screen (`/messages`); the Messages→Attention link works (a new thread produces an AttentionItem on `/now`). The source-side **Personal Relay daemon** (`nerve-personal-relay`, §46/§47) is a separate tracked deliverable — the NerveCenter-side contract is implemented and tested. Still OPEN: `/email`, `/voicemail`, `/contacts`, `/briefing`, `/waiting-on` (Phases P3–P4). |
| RT  | Realtime `/api/events/ws` and NATS event bus integration are covered by unit tests but have no e2e test in the tree (the mock harness's Playwright `webServer` does not proxy `/ws`). | **RESOLVED (2026-10-12)** — `web/tests/e2e/events-ws.spec.ts` exercises the endpoint in a real browser (handshake + honest error-frame contract), targeting the backend on `:8000` directly. |

## Items the 2026-10-11 run **clearly verified as working**
- `GET /api/auth/sso/config` returns the full SSO discovery document (all fields of §64/§71).
- `POST /api/auth/login` (break-glass) — verified by unit test in `tests/backend/test_auth_sso.py`; when `NERVE_LOCAL_ADMIN=1` the endpoint returns 403 with a real detail (not masked).
- The 63 API routes across:
  - `backend/api/auth.py` — sso/config, login, me, logout, pairing initiate/confirm, approvals bind/verify/decide.
  - `backend/api/wiring.py` — top-level mount of all other routers (`/api/health`, `/api/systems`, `/api/entities`, `/api/events` + `/ws`, `/api/goals`, `/api/tasks`, `/api/agents`, `/api/inference`, `/api/incidents`, `/api/decisions`, `/api/ask`, `/api/context/ask`, `/api/planned-changes`, `/api/knowledge/graph`, `/api/audit`, `/api/policy/decisions`, `/api/policy/evaluate`).
- Web login view (no default-cred hint, per-field errors on 401, detail-surfacing on 403, disabled submit label while pending, SSO button only when configured).
- Auth transport in `web/src/api/client.ts` (Bearer header only when present; 401 clears sessionStorage and surfaces `ApiError(401)`; PKCE + state round-trip on `/auth/callback`).
- 10 view-render pages + Ask round-trip (all render without console errors under the real backend).

## Web design-bar compliance (per `.roo/rules-code/20-web-design.md`)
The running UI, screenshotted this round, matches the rule bars:
- **Rule 1 — page purpose:** Every view has an explicit nav label + H1; each of the 10 routes maps 1 : 1 to a distinct primary information object (overview / systems / timeline / goals / tasks / agents / inference / incidents / decisions / ask).
- **Rule 2 — specific decision (not generic purple dashboard):** Blue-on-neutral palette; one brand accent; no gradient headers; no decorative shadows; dark theme only inverts surfaces, not the accent.
- **Rule 3 — composition before decoration:** Sidebar (permanent ≥ 641 px, hamburger below), page heading + subtext, content grid. No floating decorative chrome.
- **Rule 4 — hierarchy:** H1 (24 px, 600 weight) → body (14 px, 400). Primary CTA is `bg-blue-600 text-white` (only one in the whole app); secondary actions are ghost.
- **Rule 5 — small consistent system:** 1 color (brand blue), 2 typefaces (tabular Inter/system + monospace for ids/numbers), 4 radii, 4 spacing steps, `:focus-visible` rings, one icon set.
- **Rule 6 — layout matches content:** Lists for events / goals / tasks; forms only on `/login`; no card grid as a default treatment (Goals and Incidents use real empty states with a short actionable line rather than fake cards).
- **Rule 7 — real behavior:** Buttons do what they say. Submit is disabled with a pending label while `login()` is in flight (unit-tested). The SSO button appears **only** when `sso/config` reports `enabled:true` — verified by a negative test (`SSO button renders only when sso/config reports enabled`).
- Empty / error / loading / success states all exist per view (the Playwright view tests assert each view renders a non-trivial DOM tree against a real, empty backend).

## What this audit did *not* verify
- ~~Live end-to-end SSO PKCE flow against Keycloak~~ — **verified live on 2026-10-12** (B-2 resolved; client provisioned, PKCE round-trip confirmed).
- Live break-glass login with real `NERVE_LOCAL_ADMIN` / `NERVE_LOCAL_ADMIN_PASSWORD` values (the local service here has the flag but not a password, so it correctly 401/403s).
- ~~Any prompt2.md personal-operations feature~~ — **Phases P0–P2 verified on 2026-10-12**: `/api/attention` + the **Now** screen (`/now`), `/api/messages` + the **Messages** screen (`/messages`), and `/api/calendar` + the **Calendar** screen (`/calendar`) all render against the real backend with no console errors. Phases P3–P4 (email, voicemail, contacts, briefing, waiting-on) still do not exist to verify.
- ~~Realtime `/api/events/ws` fan-out~~ — **covered on 2026-10-12** by `web/tests/e2e/events-ws.spec.ts` (handshake + honest error-frame contract, no-NATS path). Full live fan-out against a connected NATS bus remains unverified in CI (no NATS in the e2e harness).

## Reproduction

```bash
# backend
uv sync --all-extras
uv run pytest tests/                 # expect: 413 passed

# api + web (no DB / NATS needed; in-process session store)
NERVE_MOCK_INFER=1 \
NERVE_SSO_ISSUER=https://sso.celestium.life/realms/celestium \
NERVE_LOCAL_ADMIN=1 \
  .venv/bin/python -m uvicorn backend.api.app:app --port 8000 --host 127.0.0.1

# web (in a second terminal)
cd web && npx vite --port 3000 --strictPort
# → http://localhost:3000/  (proxies /api/* and /ws/* to :8000)

# e2e (self-contained: boots its own mock backend)
cd web && npx playwright test       # expect: 42 passed

# keycloak health
curl -s https://sso.celestium.life/realms/celestium/.well-known/openid-configuration | jq
```
