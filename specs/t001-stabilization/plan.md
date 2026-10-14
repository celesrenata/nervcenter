# Plan: T001 — Stabilization and Hygiene Closure (G-0 / G-4)

**Feature:** t001-stabilization · **Spec:** [`spec.md`](./spec.md) · **Tasks:** [`tasks.md`](./tasks.md)

## Ground Truth (2026-10-14)

| Area | State | Evidence |
|------|-------|----------|
| Python tests | ✅ 559 passed, 0 failed (after 2 Crash fixes) | `pytest tests/ -m "not integration"` (gaps1.md §2) |
| Mail-connector plane | ⚠️ staged in worktree, **zero tests**, uncommitted | grep `MailConnector*` in `tests/` → empty; `git status` (68 staged files) |
| `web/dist` | ⚠️ tracked + staged (`web/dist/index.html`); `.gitignore` already has `web/dist/` + `dist/` but the file predates the rule | `git ls-files web/dist`; `ls .gitignore` lines 15/42 |
| `.patches/` | ⚠️ untracked but **not** gitignored (worker-1/2/3.patch present) | `ls .patches`; grep `.gitignore` for `patches` → absent |
| Swift tests | ⚠️ `swift test` runs only `NerveAppsTests` (2); `NerveRelayTests` (31) + `NerveSharedTests` need `--filter` | gaps1.md §2 (Apple tests row) |
| Lifespan | ⚠️ `backend/api/wiring.py:352,357` uses `@target.on_event` (docstring line 348: "no lifespan refactor"); 687 deprecation warnings/run | `wiring.py:348-361` |
| Status docs | ⚠️ stale: reference `backend/events/`, `backend/knowledge/` (paths don't match tree); personal planes listed as pending | `docs/implementation-status.yaml`, `docs/architecture/current-state.md` |
| JWT test keys | ⚠️ 32-byte HS256 keys trigger PyJWT "weak key" warnings | `tests/backend/test_auth_sso.py` |
| README | ⚠️ "Development" section has tooling but no canonical test-suite commands | `README.md:60-68` |

## Architecture Decisions

1. **Mail-connector tests (G-0.2) precede the commit (G-0.1).** Tests
   must exist and pass before the plane is committed, so the commit lands
   on a green, verified surface. Follow the established pattern of
   `tests/backend/test_email.py` (in-memory service, HTTP TestClient,
   `reset_*_service()` teardown, envelope assertions).
2. **`web/dist` untracked, not deleted (G-0.3).** `git rm -r --cached
   web/dist` removes it from the index only; local files stay so dev
   builds are unaffected. Confirm the Docker build stage produces dist
   in-image before relying on this. `.patches/` is appended to
   `.gitignore` under the build-artifacts section.
3. **Swift test runner via a canonical script (G-4.1).** Root-cause the
   `Package.swift` wiring first (platform gating / default test-target
   resolution); if a clean in-package fix is not found, add
   `apple/scripts/test-apple.sh` that runs all three bundles explicitly
   (e.g., `swift test --filter NerveRelayTests`, etc.). Either outcome
   satisfies AC004.
4. **Lifespan migration (G-4.2).** Replace the `on_event` decorators in
   `install_dependency_wiring` with an `@asynccontextmanager`
   (`wire_dependencies` on enter, `teardown_dependencies` on exit) and
   wire it into `FastAPI(lifespan=...)` for both the module-level `app`
   and `create_app()`. Behavior order is preserved: startup before
   request handling, shutdown after.
5. **Doc refresh (G-4.3) is structural, not exhaustive.** Update the two
   stale status docs to match the real tree (personal planes P0–P4,
   mail-connector plane, policy PDP, event bus, persistence, auth).
   `audit-gaps.md` is left untouched as history.
6. **JWT key hygiene (G-4.4) and README (G-4.5) are leaf tasks** with no
   cross-dependencies; they can run in parallel with the others.

## Dependency Graph

```
T002 mail-connector tests ──────┐
T003 commit mail-plane + web    ┤
T004 untrack dist + gitignore   ┼──► T008 gate: git status clean + all suites green
T005 swift test runner          ┤
T006 lifespan handlers          ┤
T007 doc refresh               ┤
T009 JWT test keys             ┤
T010 README test commands      ┘
```

- T002 is the only prerequisite for T003 (tests must pass before commit).
- T004–T010 are independent of one another and of T002/T003; they can be
  dispatched in a parallel wave.
- T008 (the gate) depends on **all** prior tasks completing so it can
  verify the whole tree in one pass.

## File Ownership (single owner per path)

| Owner task | Paths |
|-----------|-------|
| T002 | `tests/backend/test_mail_connector.py` (new) |
| T003 | `backend/connectors/mail/**`, `backend/api/endpoints/mail_connectors.py`, `backend/api/models.py` (re-export), `backend/api/app.py` (router mount), `web/src/**` (theme/Downloads), `.gitignore` (dist), git commits |
| T004 | `.gitignore` (`.patches/`), `web/dist` (index only), `web/Dockerfile` (build-stage check) |
| T005 | `apple/Package.swift`, `apple/scripts/test-apple.sh` (new, if needed) |
| T006 | `backend/api/wiring.py`, `backend/api/app.py` |
| T007 | `docs/implementation-status.yaml`, `docs/architecture/current-state.md` |
| T009 | `tests/backend/test_auth_sso.py` |
| T010 | `README.md` |
| T008 | verification only: command outputs, this file's log |

Cross-boundary rule: T003 owns the mail-plane *source + commit*; T002 owns
the mail-plane *tests* only. T006 owns `wiring.py`/`app.py` for the
lifespan change; T003 owns `app.py` for the router mount — the two edits to
`app.py` are distinct regions and must be reconciled at integration (T008).

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Untracking `web/dist` breaks the Docker image | Verify `web/Dockerfile` builds in-image before/while untracking; add a build stage if missing (within T004) |
| Lifespan refactor subtly changes startup/shutdown ordering | `test_app_wiring.py` gates on behavior; preserve enter-then-exit order; run full `pytest -m "not integration"` |
| Swift default `swift test` won't run all bundles after the fix | Ship `apple/scripts/test-apple.sh` as a fallback; document the canonical command in README (T010) |
| Doc refresh diverges from reality (stale again) | Refresh only against verified tree state (gaps1.md §2); keep claims minimal and path-accurate |
| T003 and T006 both touch `app.py` | Keep edits in separate, well-separated regions; reconcile at T008 |

## Exit Criteria (from spec)

AC001–AC008 in [`spec.md`](./spec.md) — each maps to a task's verification
section in [`tasks.md`](./tasks.md).

## Initial Todos

- [ ] T002: Write `tests/backend/test_mail_connector.py` (~20 tests); run and make green
- [ ] T003: Commit mail-connector plane (connectors / web theme / web downloads) on a green tree
- [ ] T004: `git rm -r --cached web/dist`; add `.patches/` to `.gitignore`; verify Docker build stage
- [ ] T005: Fix `swift test` to run all 3 bundles (Package.swift root-cause or `test-apple.sh`); wire into docs
- [ ] T006: Migrate `wiring.py` `on_event` → lifespan handler; wire `app.py`; verify 0 warnings
- [ ] T007: Refresh `docs/implementation-status.yaml` + `docs/architecture/current-state.md`
- [ ] T009: Bump `test_auth_sso.py` JWT keys to ≥64 bytes; verify 0 PyJWT warnings
- [ ] T010: Add a "Testing" section to `README.md` with canonical commands
- [ ] T008: Gate — `git status` clean; `pytest -m "not integration"`, web e2e, Apple all-bundle tests all green
