# Plan: Web UI Quality Audit + SSO Surface

**Feature:** web-quality-audit · **Spec:** [`spec.md`](./spec.md) · **Tasks:** [`tasks.md`](./tasks.md)

## Ground Truth (2026-10-01)

| Area | State | Evidence |
|------|-------|----------|
| Shell | Emoji nav icons ([Layout.tsx](../../web/src/components/Layout.tsx:10)), fixed `w-64` sidebar ([Layout.tsx](../../web/src/components/Layout.tsx:29)), no mobile collapse, no visible focus rings | file inspection |
| Tokens | Default-gray Tailwind palette + ad-hoc `dark:` variants; no semantic token system ([index.css](../../web/src/index.css)) | file inspection |
| Login | Advertises `admin/password` ([LoginView.tsx](../../web/src/views/LoginView.tsx)); fake decode in [AuthContext.tsx](../../web/src/auth/AuthContext.tsx); no Authorization header on fetches ([client.ts](../../web/src/api/client.ts)) | file inspection |
| Deps | `tailwindcss ^3.4.7` mixed with `@tailwindcss/postcss ^4.3.3` ([package.json](../../web/package.json)) | file inspection |
| Data | [TimelineView.tsx](../../web/src/views/TimelineView.tsx:16) renders 5 hardcoded fixture events; never calls `/api/events` | file inspection |
| E2E | [views.spec.ts](../../web/tests/e2e/views.spec.ts) + [ask.spec.ts](../../web/tests/e2e/ask.spec.ts) gate 10 views + ask flow; [global-setup.mjs](../../web/tests/e2e/global-setup.mjs) boots mock backend on :8000 | file inspection |

## Architecture Decisions

1. Tailwind resolves to one major: 3.x. Remove the stray v4 postcss plugin;
   verify class generation via build + computed-style spot checks.
2. Semantic tokens as CSS variables in `web/src/index.css` (canvas, surface,
   elevated, text-primary/secondary, divider, control-border, accent,
   text-on-accent, focus, status healthy/degraded/warning/critical), consumed
   through Tailwind theme extension; dark mode only where the product needs it.
3. Navigation icons: one inline SVG icon set (stroke 1.5–2, 20–24 px),
   decorative `aria-hidden`, functional named — never emoji.
4. Responsive shell: persistent sidebar ≥1024 px; below, a compact header with
   an accessible nav trigger (disclosure pattern); 320 px reflow verified.
5. Data integrity: [TimelineView.tsx](../../web/src/views/TimelineView.tsx)
   fetches `/api/events` via the api client (mock client keeps the same shape
   for e2e); no fabricated data in any view.
6. SSO surface follows sso-integration AC-S06: `/auth/callback` + PKCE,
   `apiFetch` with `Authorization: Bearer`, 401 → `/login`, break-glass demoted
   behind the config endpoint.

## Dependency Graph

```text
W101 shell/tokens/icons/Timeline ──┐
W102 login/SSO surface ───────────┼──► W103 e2e additions + evidence
S101 backend auth contract ───────┘   (W102 reads the contract, never edits backend)
```

W101 and W102 share `web/src/**` with the single web worker; W103 waits for both.

## File Ownership

| Owner task | Paths |
|-----------|-------|
| W101+W102 (one web worker) | `web/src/**`, `web/index.html`, `web/package.json`, `web/postcss.config.js`, `web/tailwind.config.js`, `web/tests/e2e/**` (new specs) |
| W103 | evidence in `docs/implementation-status.yaml`, `web/e2e-artifacts/**` |
| S101 (cross-ref, sso-integration) | `backend/api/auth.py` — read-only for W102 |

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Tailwind 3.x reconciliation breaks class generation | Build + computed-style spot checks; e2e re-run |
| Authentik provider not yet provisioned | Break-glass local login behind config flag keeps e2e green |
| AC005 gates (10 views) regress | [views.spec.ts](../../web/tests/e2e/views.spec.ts) unchanged and must stay green |
