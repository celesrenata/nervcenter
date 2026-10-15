# NerveCenter — Frontend Visual & UX Audit (worker-2)

Date: 2026-10-15 · Worktree: `…/parallel-tasks/f27d6c19…/worker-2`
Environment: mock backend `:8000` (uvicorn, no `NERVE_DB_URL`) + Vite dev server `:3000` (`VITE_API_BASE=/api`).
Method: Playwright MCP (headless chromium). Logged in via break-glass credentials. Seeded 3 contacts + 1 Now item + 2 Ask messages for flow testing. Screenshots in `audit-evidence/*.png`.

## Scope note — "the settings panel"
There is **no user-facing Settings panel/page** in this app. Settings surface in two places:
1. **Header** — a theme (light/dark) toggle.
2. **Backend env** — service wiring (`NERVE_DB_URL`, SSO config, etc.), surfaced per-view as read-only degraded states.
If the task expected a dedicated settings screen, it does not exist. Flagged below as a gap.

---

## Findings

### P1 — Login (break-glass credential path) does not redirect after success
- After a valid credential login (API `POST /api/auth/login` → **200** + access token), the session is established (token + user set in `AuthContext`) but the browser **stays on `/login`** — the form is still visible and there is **no navigation to `/`**.
- Root cause: `web/src/auth/AuthContext.tsx:77-110` — `login()` calls `setAccessToken(...)` + `setUserState(...)` then `return authedUser`; it performs **no `navigate()`**. `web/src/views/LoginView.tsx:98` (`handleSubmit`) awaits `login()` and, on success, **also never navigates** — line 99 even carries a comment "`Success: AuthContext navigates to '/' itself.`" documenting a contract that `AuthContext` does not honor, which is what makes this bug misleading to fix. Only `logout()` navigates (to `/login`).
- The SSO path (`handleSso`, `window.location.assign(...)`) is unaffected — it leaves the page to `/auth/callback`. So this specifically breaks the **break-glass / local credential** login, which is the only one available in a local/SSO-disabled setup.
- Empirical: valid creds → API 200 → URL remained `/login`, password field still present. (I could still reach the other views because the in-memory user state was set and the `RequireAuth` gate on the Layout routes then passed on subsequent navigation.)
- Evidence: verified live in this session (valid creds → API 200 → URL remains `/login`, password field still present); re-testable by submitting the form.
- Fix: in `LoginView.handleSubmit`, after `await login(...)` resolves, `navigate('/')` (or a saved `from` location).

### P2 — Unknown routes render a fully blank page (no 404 / no app shell)
- Navigating to any undefined path (e.g. `/activity`, `/nonexistent-xyz`) leaves **`#root` empty**: no app shell, no sidebar, no 404, no error — just a blank white page. The only way out is the browser back button or manual URL entry.
- Root cause: `web/src/App.tsx` defines 19 routes but has **no catch-all** `<Route path="*">` / 404 element.
- Not reachable via the sidebar (all 19 nav links verified to map to real routes), but reachable via a deep link, a stale bookmark, a mistyped URL, or a copy-pasted path.
- Evidence: `audit-04-unknown-route-blank.png` (`#root` children = 0).
- Fix: add a `<Route path="*">` rendering a 404 view (inside the `Layout` so the shell/sidebar persist).

### P2 — No "Settings panel" (gap vs. task)
- No settings view exists (see scope note). Theme is header-only; everything else is backend-config. If a settings screen was in scope, it is missing.

### P3 — Status labels rendered as raw uppercase enum values (Now view)
- The Now view's filter chips and item states show raw enum strings: `NOW`, `TODAY`, `WAITING_ON`, `SUPPRESSED`, `RESOLVED`. Inconsistent with the Task DAG view (which uses lowercase). Minor readability/consistency issue.
- Evidence: `audit-05-now-item-actions.png`.

### P3 — Calendar button label leaks an internal spec reference
- "Suggest (§43)" exposes an internal doc citation to the user. Button works; label is not user-facing copy.

### P3 — Required-field validation is native-only (no inline custom message)
- Required fields (Now "Reason *", Goal "Name *") rely on the browser's native `required`. There is no inline custom error text (e.g. for screen readers / non-Chromium). Acceptable but not ideal.

### P3 — Degraded-state copy leaks raw backend reason
- Many views show verbatim `503 — X service not configured (NERVE_DB_URL unset)`. Technically honest and safe, but the raw backend reason is shown to end users. Consistent; just not polished.

---

## Verified working (end-to-end)

| Area | What was tested | Result |
|------|----------------|--------|
| Theme toggle | Toggle light↔dark | ✅ Works, persists (localStorage), both themes render correctly |
| Logout | Log out after login | ✅ Returns to `/login`, clears state |
| Contacts | List (3 seeded), search filter, VIP-only filter, **VIP toggle** | ✅ All work; header updates `3 persons · 1 VIP`; button label flips to "Remove … from VIP contacts" |
| Now | **Add item** (POST /api/attention → 201), **Resolve** action | ✅ Item renders with Resolve/Snooze/Suppress; Resolve removes it |
| Calendar | Check availability / Find free slot / Suggest | ✅ All 3 return plausible answers against an empty schedule |
| Ask | Chat input + Send + 4 quick-question chips | ✅ All submit; honest degraded responses ("No 'context' service is configured…") |
| Nav | 19 sidebar links | ✅ All map to real routes (hrefs verified) |
| Empty states | Agents, Tasks, Contacts, Incidents, etc. | ✅ Helpful explanatory copy everywhere |
| Console | JS errors during normal navigation | ✅ No crashes (only expected 401/503 network lines) |

## Notable good-degradation UX (worth keeping)
- **Decisions**: `+ New Decision` button is **disabled with a tooltip** ("No decision-create route is exposed by the backend yet") + a clear error banner. Best-in-class handling of an unavailable backend.
- **Goals / Incidents**: forms show the `503 — …not configured` inline and keep the form open (no data loss, no crash).
- **Downloads**: `404 — manifest unavailable` with actionable guidance ("Run export_app.sh …").

## Delete flows
There is **no true "delete" button** anywhere in the UI (by design): incidents are append-only ("never deleted"), contacts are upsert-only via the relay, Now items use Resolve/Snooze/Suppress (not delete), and VIP is a toggle. The closest state transitions (Resolve on Now, VIP-toggle-off on Contacts) were tested and **work**.

## Evidence (screenshots on disk)
- `audit-01-home-light-*.png` — Overview view, light theme (prior session)
- `audit-02-agents-*.png` — Agents view, empty state (prior session)
- `audit-03-decisions-501-*.png` — Decisions 501 banner + disabled `+ New Decision` button
- `audit-04-unknown-route-blank-*.png` — fully blank page on an unknown route (P2)
- `audit-05-now-item-actions-*.png` — Now item card with Resolve/Snooze/Suppress (raw enum labels)
- `audit-06-contacts-vip-*.png` — Contacts list with VIP state + header count
- Login P1 verified live (valid creds → API 200 → URL remains `/login`); not screenshot-captured this session.
- `audit-07-live-settings-postdeploy-*.png` — post-deploy (image `8d3fa59`) Settings view behind SSO:
  Appearance / Connectors / Sideload sections render; SSO login lands on the app root (P1 fix confirmed live).
