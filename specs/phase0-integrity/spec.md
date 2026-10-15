# Spec: Phase 0 — Integrity Gate (H-1…H-5, G-0.x)

**Feature ID:** phase0-integrity
**Created:** 2026-10-14
**Status:** Active
**Branch target:** main (repo root: nervcenter)
**Upstream:** [gaps2.md](../../gaps2.md) §3 (Failures found this pass), §5 (Sequenced closure plan, Phase 0)
**Supersedes:** `specs/t001-stabilization` T002/T003/T004 (stale premise: they assumed the mail plane was *staged-uncommitted*; it was in fact *committed broken* at `a3c07da` — see gaps2 §3.7)

## Problem

`gaps2.md` (evening re-review) found the repo state changed materially from the
morning's `gaps1.md`, and the three spec packs written against gaps1 no longer
fully describe the work:

1. **H-1 — HEAD `a3c07da` cannot import (highest severity).** The
   mail-connector plane was committed inside the "specs: add three spec packs"
   commit while its *fix* (the `MailConnector` re-export in
   `backend/connectors/mail/__init__.py`) stayed uncommitted in the worktree.
   On any clean checkout of HEAD, `import backend.api.app` raises
   `ImportError: cannot import name 'MailConnector'` — the API server cannot
   boot and every app-based test file fails at collection. The tree only
   passes tests because the fix is present *and uncommitted*.
2. **H-2 — Two calendar tests are clock time-bombs.**
   `tests/backend/test_calendar.py::test_ingest_new_is_201_replay_is_200` and
   `::test_list_filters_to_window` ingest events on the hardcoded reference day
   `2026-10-14` and then read `GET /api/calendar` with the *default* window
   `[now, now+7d)`. Since 2026-10-14T10:00Z they fail deterministically
   (verified live this session: `2 failed, 18 passed`). They will not
   self-heal.
3. **H-3 — Half-applied web theme rename.** `Layout.tsx` (tracked, modified)
   imports `ThemeToggle`, but `ThemeToggle.tsx` is **untracked** and the old
   `ThemeSwitcher.tsx` is tracked and referenced by nothing. Committing
   `Layout.tsx` alone breaks `tsc` on any fresh checkout.
4. **H-4 — T009 (RFC 7518 SSO keys) is done but uncommitted.**
   `tests/backend/test_auth_sso.py` now uses 64+ byte HS256 fixtures; its
   t001 task-log row is in the uncommitted `specs/t001-stabilization/tasks.md`
   diff. It needs to land.
5. **H-5 — Tracked build artifact + untracked worker output.**
   `web/dist/index.html` is tracked (and modified) despite `.gitignore` having
   `web/dist/`; the Dockerfile builds in-image, so untracking is safe.
   `.patches/` (3 worker patches) is untracked and un-ignored.

None of H-1…H-5 is covered by the existing packs: t001's T002/T003/T004 are
stale in premise, and the gap docs themselves (`gaps1.md`, `gaps2.md`) are
untracked. **Phase 0 is the integrity gate that must close before any of
Phase 1–4 runs** — a broken HEAD makes every subsequent commit's evidence
unreliable.

## Goals

1. **HEAD boots.** A clean checkout of the resulting commit imports
   `backend.api.app` without error (verified in a detached worktree).
2. **The mail plane lands with its tests in the same commit** — the H-1
   lesson ("never commit an import fix without the plane's tests") becomes
   the shape of the commit, not just a note.
3. **The Python suite is clock-invariant:** `pytest tests/` green on the
   commit, and the two calendar time-bombs replaced with explicit-window
   assertions that cannot fail on future dates.
4. **The web rename is complete:** `ThemeToggle.tsx` tracked,
   `ThemeSwitcher.tsx` deleted, `tsc && vite build` + 56 e2e green after the
   delete.
5. **The tree is clean:** no tracked build artifacts (`web/dist`), `.patches/`
   ignored, the gap docs committed, the workspace-file change committed as a
   deliberate chore, `git status` empty.
6. **The commit hygiene norm is recorded:** no backend commit touching an
   import chain ships without a detached-worktree import verification (gaps2
   §7 Q6) — applied to this pack now and propagated to the sibling packs.

## Scope

**In scope:**

- `backend/connectors/mail/__init__.py` — commit the existing 3-line
  worktree fix (H-1; G-0.4). No new code.
- `tests/backend/test_mail_connector.py` (new) — ≥20 tests covering the IMAP
  probe mapping, OAuth URL/callback/exchange, `token_ref` round-trip, service
  registry upsert/404/`verify()` transitions, and the HTTP contract
  (secret-never-stored, only `token_ref` returned). Mirrors
  `tests/backend/test_email.py` patterns.
- `tests/backend/test_calendar.py` — the two gaps2 §3.2 explicit-window fixes
  + NOTE comments (H-2).
- `tests/backend/test_auth_sso.py` + the T009 row in
  `specs/t001-stabilization/tasks.md` — commit the completed work (H-4).
- `web/src/components/ThemeToggle.tsx` (add), `web/src/components/Layout.tsx`
  (commit), `web/src/components/ThemeSwitcher.tsx` (delete) (H-3).
- `.gitignore` — add `.patches/` (H-5); `web/dist/` index untrack via
  `git rm -r --cached` (H-5; G-0.3).
- `gaps1.md`, `gaps2.md` — commit at repo root beside `audit-gaps.md`.
- `nervcenter.code-workspace` — commit the Swift debug launch-config additions
  as a `chore` commit.
- Git: six logical commits in the order defined by the plan.

**Out of scope:**

- The G-4.x hygiene sweep (T005 swift-runner, T006 lifespan, T007 doc
  refresh, T010 README) — remains t001's Phase 5 work, unaffected by this
  pack except that its T002/T003/T004 tasks are superseded (see delta note).
- Any backend code change beyond the existing worktree diff: the
  longer-term `MailConnector` model move (gaps2 §3.1 "optional, low
  urgency") is explicitly **not** part of Phase 0.
- The G-1/G-2/G-3 feature planes (Phases 1–4): `backend/communications/**`,
  `backend/inference/**` transport, `apple/**` personal surfaces,
  `synthetic-lab/**`.
- Any change to `audit-gaps.md` (historical record).

## Constraints

- **Fix + tests in one commit.** The H-1 re-export commit must include
  `tests/backend/test_mail_connector.py`; never commit the import fix alone.
- **No behavior change to the mail plane.** Tests pin the existing contract
  (list/create/verify/delete + OAuth); they do not reshape it.
- **Clock-invariant test fix.** The calendar fix passes explicit
  `start`/`end` params (the endpoint already accepts them); it must not
  re-anchor `_day()` to `now` and must not change the service.
- **`web/dist` untracked, not deleted.** Local files remain for dev builds;
  the in-image build (`web/Dockerfile` lines 33/49) makes CI independent of
  the committed dist — re-verify the build stage before untracking.
- **Commit discipline.** Six small logical commits, dependency-ordered; no
  monolith; each commit's `git show --stat` recorded in the verification log.
- **Import-chain gate.** Any commit touching `backend/**` import chains is
  verified with `python -c "import backend.api.app"` in a **detached worktree
  of the resulting commit** (gaps2 §7 Q6 norm; AC-P07).
- **No scope creep.** If P0-06's gate surfaces a failure in a Phase 1–4
  surface (e.g., the e2e masks of G-3.5), it is logged, not fixed here.

## Assumptions

- The worktree diff (7 modified + 4 untracked) is the *complete* surface of
  uncommitted work; no other worker holds pending changes. (Verified
  2026-10-14 ~23:20 UTC via `git status --short`.)
- `web/Dockerfile` builds the web app in-image (`npm run build` at line 33,
  `COPY --from=build` at line 49 — verified this session), so untracking
  `web/dist` cannot break the image.
- `ThemeToggle.tsx` is the desired end state of the rename (gaps2 §7 Q1
  default: complete, not revert). If the decision flips, P0-02 reverses:
  revert `Layout.tsx`, delete `ThemeToggle.tsx`.
- The mail-plane source is functionally complete; P0-03 verifies, not
  rewrites. (Its only known defect at HEAD is the import chain, H-1.)
- The full non-integration suite is 559 tests after the 2 calendar fixes
  (557 passing + 2 failing today; P0-06 asserts ≥559 passed, 0 failed).

## Acceptance Criteria

- **AC-P01 (H-2 / G-0.1):** `pytest tests/backend/test_calendar.py` →
  **20 passed, 0 failed**, with both fixed tests using explicit `start`/
  `end` params and carrying NOTE comments explaining the `now`-anchored
  default window. The generalized rule holds: no test ingests a fixed-date
  datum and reads a list endpoint without an explicit window
  (check: `rg -n 'datetime\(2026' tests/` only inside window-explicit
  fixtures).
- **AC-P02 (H-3 / G-0.1):** `git ls-files web/src/components/` lists
  `ThemeToggle.tsx` and **not** `ThemeSwitcher.tsx`; `rg -n 'ThemeSwitcher'
  web/` → zero matches; `cd web && npm run build` clean (tsc + vite) and
  `npm run e2e` → **56 passed** run *after* the delete.
- **AC-P03 (H-1 / G-0.2 / G-0.4):** `tests/backend/test_mail_connector.py`
  exists with ≥20 tests covering: (a) IMAP probe mapping (CAPABILITY ok →
  CONNECTED, auth reject → AUTH_EXPIRED, network fail → ERROR); (b) OAuth
  `build_authorization_url` (state, redirect_uri, client_id); (c)
  `parse_callback` (state validation, code extraction); (d)
  `exchange_request` shape; (e) `make/validate_token_ref` round-trip +
  expiration; (f) registry upsert/404; (g) `verify()` transitions; (h)
  `reset_mail_connector_service()`; (i) HTTP list/create/verify/delete with
  the secret-never-stored assertion (only `token_ref` returned).
  `pytest tests/backend/test_mail_connector.py` green. **The fix commit
  (`fix(connectors)`) contains both `backend/connectors/mail/__init__.py`
  and this test file.**
- **AC-P04 (H-4 / G-4.4):** `tests/backend/test_auth_sso.py` (≥64-byte keys)
  and the T009 verification-log row in `specs/t001-stabilization/tasks.md`
  are committed; `pytest tests/backend/test_auth_sso.py -W always` → 0 PyJWT
  weak-key warnings.
- **AC-P05 (H-5 / G-0.3):** `git ls-files web/dist` → empty; `.gitignore`
  contains a `.patches/` rule; `git status --short` shows no `.patches/*`
  and no `web/dist/*` entries after `cd web && npm run build`.
- **AC-P06 (G-0.1):** `git status --short` → empty on the resulting HEAD;
  `gaps1.md` and `gaps2.md` are tracked at repo root; the commit log
  contains the six logical commits in the plan's order with descriptive
  messages; each commit's `git show --stat` is in the verification log.
- **AC-P07 (G-0.4 / gaps2 §7 Q6):** On the **final commit** (not the
  worktree): `git worktree add /tmp/nc-p0-gate <sha>` +
  `.venv/bin/python -c "import backend.api.app"` → exit 0;
  `pytest tests/ -m "not integration"` → **≥559 passed, 0 failed**;
  `npx playwright test` → 56 passed. The import-chain gate norm is recorded
  in this pack's execution rules *and* appended to the execution-rules
  sections of `specs/t001-stabilization/tasks.md` and
  `specs/gap-closure-t003/plan.md` (via the gaps2 delta amendments).

## Verification

Each AC maps to a task in [tasks.md](./tasks.md) with its exact command or
verification step. Evidence (commit SHAs, command outputs) lives in the
tasks.md verification log; gaps are stated explicitly, never papered over.
