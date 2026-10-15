# NerveCenter — Visual & Cross-Platform Lift Audit

**Auditor:** visual-auditor (read-only; no app code edited)
**Date:** 2026-10-15
**Scope:** "make sure I created what people want" — dark/light/theme **sync**, **SSO credentials** on web + Apple, and **buttons/options** (add/delete) across Web, iPhone, Apple Watch, and Widgets.

**Method.** Static read of `web/`, `apple/`, `backend/`, `deployments/`; plus a **live probe** of the deployed service (`https://nervecenter.celestium.life`) via headless Chromium. Findings cite `file:line`.

**Measurement caveats:**
- The web SPA is **gated by SSO** (verified live: every path → Keycloak), so the post-login web UI could not be visually exercised this run; web UI findings are code-based, not screenshot-confirmed.
- Apple targets can't be built/run here; Apple UI findings are code-based.

---

## TL;DR — the four highest-leverage gaps

1. **Theme is not *synced* across platforms.** Both the web app and the Apple apps *independently* follow the OS appearance in "system" mode (good), but there is **no bridge** between the web preference (browser `localStorage['nerve-theme']`) and the Apple preference (`@AppStorage('nerveTheme')`). A choice in one place never reaches the other. Additionally, the **web toggle can't select "System"** (it only flips light↔dark), and the **Apple apps expose no theme picker at all**, so a phone/watch user is locked to the default `.system`.
2. **SSO is provisioned twice, at two different providers, and the in-app flow is pointed at the wrong one.** The deployed cluster gate is **Keycloak** (oauth2-proxy; verified live). The in-app SSO the web/Apple UIs call defaults to an **Authentik** issuer (`backend/api/auth_service.py:77`). Enabling in-app SSO without overriding the issuer sends users to an IdP that isn't the one running. Separately, the Apple "Keychain" credential store is **in-memory only** — paired device credentials don't survive a relaunch.
3. **"Add" exists, "Delete" is essentially absent in the UI** (web), and a class of options is missing: the web theme toggle lacks a *System* option, the phone's server-config button is a **dead `// TODO`**, the Watch "Ask" button is a **no-op**, and **neither Apple app exposes any theme control**.
4. **The App Group identifier is split across targets** (`group.com.celestium.nervecenter` on phone vs `group.nerv.center` on watch/widget) — the phone↔watch↔widget shared-state "sync" **cannot work on a real device** until aligned. The code even documents this mismatch in comments.

---

## 1. Theme system & "sync" parity

### 1.1 Web (`web/src/index.css`, `web/src/theme/ThemeContext.tsx`)
- **Tokens are complete in both themes.** `:root` is the full **dark** set (`--bg`, `--bg-elevated`, `--bg-hover`, `--surface`, `--border`, `--text-primary/secondary/muted`, `--accent(-hover/-soft/-contrast)`, `--success`, `--warning`, `--danger`, `--ring`, spacing, radii, shadows — lines 25–66). `[data-theme='light']` is a **full** light set that overrides *all* of those (lines 68–92), and `@media (prefers-color-scheme: light) [data-theme='system']` mirrors it (lines 108–133). There is **no divergence** between the light and dark token *sets* — both define every semantic color. (Good.)
- **System mode tracks the OS live.** `ThemeProvider` subscribes to `matchMedia('(prefers-color-scheme: light)').change` while `theme === 'system'` and re-applies `data-theme`/`dark` class on every flip (`ThemeContext.tsx:95-102`). So the web **does** react to OS appearance changes in system mode. (Good.)

**Finding A-1 (theme *options* gap — web).** `ThemeToggle.tsx:22-23` computes `nextTheme = isLight ? 'dark' : 'light'` — the button only ever sets `light` or `dark`, never `system`. Once a user toggles once, they **can never return to following the OS**. The web app *supports* system mode (the default), but the UI gives no way to get back to it. This is the single biggest "theme options" gap on the web side.

**Finding A-2 (undefined CSS variable — confirmed).** `ThemeToggle.tsx:29` references `var(--surface-hover)` in `hover:bg-[var(--surface-hover)]`. **`--surface-hover` is not defined anywhere in `index.css`** (only `--surface` and `--bg-hover` exist). The theme-toggle button therefore has **no hover fill** — the hover affordance silently does nothing. (Almost certainly meant `--bg-hover`.)

**Finding A-3 (login view bypasses the token system).** `LoginView.tsx` renders with **raw Tailwind colors** (`bg-blue-500 hover:bg-blue-600`, `bg-red-100 dark:bg-red-900`, `dark:bg-gray-700`) instead of the semantic tokens (`var(--accent)`, `var(--danger)`, `var(--bg-elevated)`) used everywhere else. The very surface SSO users stare at is off the theme system, so any future token change won't reach it.

### 1.2 Apple (`apple/Shared/Sources/NerveDesign/Theme.swift`)
- **Both dark and light Themes exist.** `Theme.dark` (lines 57–66) and `Theme.light` (68–78) are full token sets (background, surface, textPrimary, textSecondary, accent, success, warning, danger). `ThemePreference` = `.system/.light/.dark`; `ThemeStore.resolvedTheme(for:)` resolves `.system` against the SwiftUI `colorScheme` passed in from the app roots (`NervePhoneApp.swift:22,29`, `NerveWatchApp.swift:30,42`), which re-render when OS appearance changes — so Apple **does** track the OS live too. (Good.)

**Finding A-4 (cross-platform *value* divergence).** The dark/light token *sets* match structurally, but the **values differ** for status colors:
| token | Web dark | Apple dark | Web light | Apple light |
|---|---|---|---|---|
| accent | `#3b82f6` | `#3b82f6` ✔ | `#2563eb` | `#2563eb` ✔ |
| success | `#4ade80` | `#34d399` ✗ | `#16a34a` | `#10b981` ✗ |
| warning | `#facc15` | `#fbbf24` ✗ | `#ca8a04` | `#f59e0b` ✗ |
| danger  | `#f87171` | `#f87171` ✔ | `#dc2626` | `#b91c1c` ✗ |

So success/warning/danger use **different Tailwind shades per platform** — a status badge that's green on the web will be a slightly different green on the phone/watch. Minor, but it reads as "inconsistent."

**Finding A-5 (no theme *picker* in Apple apps).** `ThemeStore` is wired into both `NervePhoneApp` and `NerveWatchApp` and defaults to `.system`, but **neither app exposes any UI to change the preference** — no `Picker`/`Menu`/toggle. A phone or watch user cannot choose light/dark/system; they're permanently locked to OS-follow. The "options" half of the theme audit is unmet on Apple.

### 1.3 "Sync" — does a preference propagate?
**No, not across platforms.**
- **Web preference** → `localStorage['nerve-theme']` (`ThemeContext.tsx:28`).
- **Apple preference** → `@AppStorage('nerveTheme')` (`ThemeStore.swift:105`, sandbox storage, *not* the App Group container).
- Different storage medium, different key, **no bridge of any kind**. A choice made in the browser never reaches the phone/watch, and vice-versa. There is also **no server-side theme store** (the backend has no theme persistence endpoint), so "sync" has nowhere to converge.
- **Within Apple:** phone and watch are separate processes; `@AppStorage('nerveTheme')` is per-sandbox, not the shared App Group container, so they don't share the preference either — and they currently can't share *state* at all (see Finding B-4 / C-7).

**Net:** "system-preference live sync" works *within* each platform (web tracks OS in system mode; Apple tracks OS via `colorScheme`), but (a) the web toggle can't select system (A-1), (b) Apple exposes no theme option to change it (A-5), and (c) **cross-platform sync does not exist** — the premise "dark/light theme syncs across my devices" is not achievable in the current code.

---

## 2. SSO / OIDC credentials

### 2.1 Two independent SSO mechanisms — pointing at two different providers
**Mechanism 1 — cluster gate (deployed & live).** `deployments/kubernetes/base/oauth-deployment.yaml` puts the whole site behind **oauth2-proxy → Keycloak** (`realm celestium`, issuer `https://sso.celestium.life/realms/celestium`). **Live-verified:** navigating to `https://nervecenter.celestium.life/` *and* `/api/health` both 302 to the Keycloak authorize endpoint:
```
client_id=nervecenter, code_challenge_method=S256,
redirect_uri=https://nervecenter.celestium.life/oauth2/callback,
scope=openid profile email, state=…:/api/health
```
So the **cluster-level SSO is the Keycloak gate**, and it *is* active (the SPA is unreachable without it).

**Mechanism 2 — in-app SSO (web + Apple).** On top of the gate, the app has its *own* SSO flow:
- Web `LoginView.tsx:121-153`: fetches `/api/auth/sso/config`, runs a **local PKCE S256** redirect to `cfg.authorization_endpoint`.
- Backend `auth_service.py:77` → `DEFAULT_SSO_ISSUER = "https://sso.celestium.life/application/o/nervecenter/"` — that path shape is **Authentik**, not Keycloak.

**Finding B-1 (provider mismatch — in-app SSO is pointed at a provider that isn't the live one).** The deployed IdP is Keycloak; the in-app SSO defaults to an Authentik issuer. If an operator enables in-app SSO (`NERVE_SSO_CLIENT_ID`) without overriding `NERVE_SSO_ISSUER`, the web/Apple "Continue with SSO" button redirects to an Authentik endpoint that **doesn't match the Keycloak client** the cluster gate actually uses → the exchange fails. `sso_config` also reports `provider="authentik"` by default, so the UI would *claim* Authentik while the cluster runs Keycloak. **This is the central "SSO credentials / OIDC RP" risk: the RP config and the production IdP are two different identity stacks.**

**Finding B-2 (gate provisioned out-of-band vs. the repo's own notes).** `deployments/kubernetes/base/secrets.yaml.example` says the `nervecenter-oauth` Secret ships a **placeholder `client-secret`** that "makes the gate's redirect work but the token exchange fail," and the gate is "NOT wired into the Ingress until the Keycloak client `nervecenter` exists." Yet the live probe shows the gate *is* active and the Keycloak client `nervecenter` *does* exist. So the repo docs/template are **out of sync with production** — either activation was done without updating them, or the placeholder was patched out-of-band. Confirm the *real* client-secret is what's in the cluster Secret, not the template.

**Finding B-3 (Apple credential store is not actually Keychain).** `apple/Shared/Sources/NerveAuth/CredentialStore.swift` defines a `CredentialStore` protocol + `InMemoryCredentialStore`. `PhoneEnvironment.init` defaults to **`InMemoryCredentialStore()`** (`PhoneEnvironment.swift:98`) with **no real Keychain implementation anywhere** (a search for `Keychain|kSecClass|SecItem|import Security` finds only *comments* claiming "Keychain-backed (§71)"). So paired device credentials **are persisted in memory only** in the shipped code and **are lost on relaunch**. The spec §71 "Keychain" claim is unmet; the pairing "credential setup" the user goes through does not survive an app restart.

### 2.2 Credential *exposure* (the other half of "credentials")
- Web local-admin login: **no default password** is baked in; `NERVE_LOCAL_ADMIN` is off unless explicitly enabled (`auth_service.py:92-94`, `AC-S03`). No leaked default credential in code.
- Login UI: on 401 it shows a **stable** "Invalid credentials." message and deliberately does **not** echo the raw backend detail (good, avoids leaking implementation); on 403/other it surfaces the real detail.
- No `VITE_API_BASE`/token defaults in the web repo that would leak a usable credential.
- The real credential-hygiene items are **B-1** (RP/IdP provider mismatch) and **B-2** (placeholder secret in the committed template).

---

## 3. Buttons & options — add/delete, focus, empty/error states

### 3.1 Web (16 nav views)
**Create ("add"):** present and honest on several surfaces — `AgentsView` "+ Add Agent" → real `POST /api/agents` (refreshes on 201, surfaces non-2xx verbatim); `GoalsView` "+ New Goal" → create form with `Creating…` spinner and real error handling; incidents have create + resolve/close wired (`incidents.py:138,176,182`).
**Delete ("remove"):** essentially **absent in the UI.** A search of `web/src` finds only `sessionStorage.removeItem` (auth) and a `Set.delete` in DAG ranking math — **no "delete goal/agent/incident/entity" button anywhere**, even though the backend exposes `DELETE /api/relationships`, `DELETE /api/evidence/{id}`, `DELETE /api/entities/{id}` (`relationships.py:120`, `evidence.py:107`, `entities.py:154`).
**Finding C-1 (delete parity).** Users can create entities but have no in-app way to delete them — an asymmetry that reads as "this app only adds." If delete is out of scope by design, it should at least be a visible "managed elsewhere" note; if in scope, the affordance is missing.

**Options (theme):** see A-1 (no System option) and A-2 (broken hover token).

**Focus / empty / error states:**
- Login: solid — `aria-live` regions, focus returns to submit on failed submit, `aria-invalid`, spinner during submit.
- `OverviewView`/`AgentsView` render honest empty states and an API-failure banner (`<status> — <detail>`).
- **Finding C-2 (error-state inconsistency).** See A-3 — Login uses raw Tailwind colors, so its error/success styling isn't part of the token system.

### 3.2 iPhone app (`apple/iOS/App`)
- **Finding C-3 (dead button — confirmed).** `OverviewView.swift:40` — the header button showing the server host is `Button(action: { /* TODO: open server config */ }) { … }`. Tapping the host does **nothing** — a visible control with no action.
- Six §56 tabs (Overview, Goals, Incidents, Agents, Systems, Ask). Approve/Reject surfaced on Watch, mirrored on phone.
- **Finding C-4 (no theme option).** No theme picker anywhere in the phone app (only `ThemeStore` wiring in `NervePhoneApp.swift`). The user can't pick light/dark/system on iPhone (reinforces A-5).
- **No delete affordances** in the phone views (add-only, mirroring C-1).

### 3.3 Apple Watch (`apple/Watch`)
- `WatchHomeView` has `Refresh`, `Ack`, `Approve`. `WatchApprovalsView` offers **both Approve and Reject** per row with honest handoff copy ("sent to iPhone for the canonical decision") — good.
- `WatchGoalViews.swift:102` — `Button("Ask") {}` is a **no-op** (empty action). **Finding C-5.**
- `WatchStopView` has a deliberate confirm surface ("I understand — continue") — good.
- Watch uses the full dark+light Theme via `resolvedTheme(for: colorScheme)` (see 1.2), so no dark-only concern.

### 3.4 Widgets (`apple/Widgets`)
- **Finding C-6 (App Group identifier split — blocks widget "sync").** `NerveCenterWidgetBundle.swift` / `AppGroupWidgetDataSource.swift` use `group.nerv.center`; the **phone** uses `group.com.celestium.nervecenter` (`PhoneEnvironment.swift:16`), and the **Watch** also uses `group.nerv.center` (`WatchSnapshotSource.swift:16`). The widget's own doc comment *admits* this ("Note the phone currently uses `group.com.celestium.nervecenter` — align the two before device use"). With mismatched App Group entitlements, **the widget reads a different container than the phone writes**, so it renders "no data" / stale on a real device even when the phone is fine.
- The widget renders "Not connected" honestly when there's no snapshot — good.

### 3.5 Cross-surface consistency summary
| Surface | Create | Delete | Theme pick | System live | Notes |
|---|---|---|---|---|---|
| Web | ✅ (agents/goals/incidents) | ❌ (backend has it, UI doesn't) | Light/Dark only, **no System** | ✅ (tracks OS in system mode) | Toggle hover var undefined (A-2); Login uses raw Tailwind colors (A-3/C-2) |
| iPhone | ✅ | ❌ | **None exposed** | ✅ (OS-driven) | Dead server-config button (C-3) |
| Watch | — | — | None | ✅ (OS-driven) | Dead "Ask" button (C-5); Approve/Reject good |
| Widgets | — | — | n/a | reads App Group | **Wrong App Group id vs phone (C-6)** |

---

## 4. Prioritized fix list (by "does the user notice / trust it")

**P0 — trust-breaking / silently wrong**
1. **B-1** Reconcile the two SSO stacks: make the in-app `NERVE_SSO_ISSUER` default match the deployed Keycloak issuer (`/realms/celestium`), or explicitly document that in-app SSO uses a *different* IdP than the cluster gate. Confirm which client is real.
2. **C-6** Align the App Group identifier across phone/watch/widget to one value (the task pins `group.nerv.center`; update `PhoneEnvironment`). Until then, widget/watch shared-state is broken on device.
3. **B-3** Implement (or descope + document) a real `KeychainCredentialStore` so paired device credentials survive relaunch.

**P1 — broken affordances / missing options**
4. **A-1** Add a **System** option to the web theme toggle so a user who toggles can return to following the OS.
5. **A-5 / C-4** Expose a theme picker in the phone (and watch) app, or clearly state Apple is system-only in the UI.
6. **C-1** Add delete affordances (or an explicit "managed in backend" note) for goals/agents/incidents/entities in the web UI, backed by the existing `DELETE` endpoints.
7. **C-3 / C-5** Wire the dead buttons: phone server-config button and Watch "Ask" button.
8. **A-2** Replace `var(--surface-hover)` with `--bg-hover` in `ThemeToggle` (and audit for other undefined `var(--…)` refs).

**P2 — polish / consistency**
9. **A-4** Align the success/warning/danger token values across web and Apple (pick one Tailwind shade per state).
10. **A-3 / C-2** Unify LoginView on the token variables instead of raw Tailwind colors.
11. **B-2** Update `deployments/README.md` + `secrets.yaml.example` to match the live (activated, Keycloak) state.
12. **Cross-platform sync** Decide on a server-side theme store (or an explicit "sync" story) if "theme syncs across devices" is a goal — currently there is no shared persistence.

---

## 5. What's already good (keep)
- **Live SSO gate works** — cluster Keycloak + oauth2-proxy redirect is correct (S256 PKCE, proper redirect_uri, scope), verified live.
- **Web light theme is a complete token set** and **system mode tracks the OS live** (matchMedia `change` listener).
- **Apple has both dark and light Themes** and resolves `.system` live via the passed-in `colorScheme`.
- **Honest empty/failed states** across web (no fabricated numbers, real error banners) and Apple (Watch "Not connected", "Sent to iPhone for the canonical decision").
- **PKCE S256** implemented correctly in the web login.
- **No default credentials** in local-admin; login error message deliberately non-leaking.
- **Approve/Reject with explicit handoff copy** on Watch; deliberate Stop-confirm surface.

---

## 6. Suggested verification next (needs a logged-in browser session, out of read-only scope)
- Confirm the in-app **SSO button** behavior on the live cluster: capture the *actual* `authorization_endpoint` returned by `/api/auth/sso/config` (currently gated, so unobservable without credentials) to confirm the Keycloak-vs-Authentik mismatch (B-1) at runtime.
- Screenshot the web theme-toggle hover to confirm the undefined `--surface-hover` (A-2) renders no fill.
- In a logged-in session, toggle web theme and check the light-theme status colors against the Apple values (A-4).

*Report generated by the visual-auditor; no files were modified except this report.*
