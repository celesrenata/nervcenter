# Tasks: Web UI Quality Audit + SSO Surface

**Spec:** [`spec.md`](./spec.md) · **Plan:** [`plan.md`](./plan.md)

## Task Board

| ID | Title | AC | Deps | Files owned | Verification |
|----|-------|----|------|-------------|--------------|
| W101 | Shell: semantic tokens, SVG icons, responsive collapse, Timeline live data | AC-W01, AC-W02, AC-W03, AC-W04 | — | `web/src/index.css`, `web/src/components/Layout.tsx`, `web/src/views/TimelineView.tsx`, `web/tailwind.config.js`, `web/postcss.config.js`, `web/package.json` | `npm run build` green; computed-style spot checks; screenshots 360/768/1440 |
| W102 | Login/SSO surface per AC-S06 | AC-W05 | S101 contract (read-only) | `web/src/views/LoginView.tsx`, `web/src/auth/AuthContext.tsx`, `web/src/api/client.ts` (+ `/auth/callback` route) | Playwright login → authorized fetch → 401 redirect; 0 console errors |
| W103 | E2E additions + evidence record | AC-W06, AC-W07 | W101, W102 | `web/tests/e2e/**` (new specs), `web/e2e-artifacts/**`, `docs/implementation-status.yaml` | `npm run e2e` green incl. new responsive/focus/login tests; evidence logged |

W101 and W102 are one web worker's internal sequence (single owner of
`web/src/**`); W103 waits for both. AC005 gates
([views.spec.ts](../../web/tests/e2e/views.spec.ts)) must stay green
throughout.

## W101 — Shell: tokens, icons, responsive, live Timeline

Scope:
- Semantic token system in [index.css](../../web/src/index.css) (AC-W01):
  canvas, surface, elevated, primary/secondary text, divider, control border,
  accent, text-on-accent, focus, status colors; consumed by Tailwind theme
  extension; ad-hoc gray pairs removed from [Layout.tsx](../../web/src/components/Layout.tsx).
- Inline SVG icon set replacing emoji ([Layout.tsx](../../web/src/components/Layout.tsx:10)
  AC-W02); decorative `aria-hidden`, functional named.
- Responsive shell (AC-W03): sidebar ≥1024 px, compact header + accessible
  nav trigger below; no overflow at 320 px.
- Focus visibility (AC-W04): visible focus rings on all controls, logical
  order, no traps.
- [TimelineView.tsx](../../web/src/views/TimelineView.tsx) fetches real events
  from `/api/events` (mock client keeps contract shape); no hardcoded
  fixtures.
- Dependency reconciliation: remove `@tailwindcss/postcss ^4.3.3`, keep
  `tailwindcss ^3.4.7`, verify class generation.

## W102 — Login/SSO surface

Scope:
- `/auth/callback` route + PKCE (S256) against `/api/auth/sso/config`
  issuer; tokens in sessionStorage; shared `apiFetch` sends
  `Authorization: Bearer`; 401 → redirect `/login`.
- Login surface per AC-W05: "Sign in with Celestium SSO" primary; break-glass
  form visible only when the config endpoint reports local-admin enabled;
  persistent labels, programmatically-associated errors, pending state,
  single primary action; no default-credential copy.
- Remove the fake decode in [AuthContext.tsx](../../web/src/auth/AuthContext.tsx).
- Mock mode (`VITE_API_BASE` unset) keeps the local login path so e2e stays
  green.

## W103 — E2E additions + evidence

Scope:
- New Playwright specs: responsive shell (360/768/1440 screenshots), Tab-walk
  focus capture, login flow incl. 401 redirect.
- Evidence (AC-W07): screenshot paths, console logs, contrast measurements,
  unverified gaps — into [docs/implementation-status.yaml](../../docs/implementation-status.yaml)
  and this file's verification log.

## Verification Log

*(updated per task completion — commands, results, gaps)*
