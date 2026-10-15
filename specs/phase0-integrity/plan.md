# Plan: Phase 0 — Integrity Gate (H-1…H-5, G-0.x)

**Feature:** phase0-integrity · **Spec:** [`spec.md`](./spec.md) · **Tasks:** [`tasks.md`](./tasks.md)
**Upstream:** [gaps2.md](../../gaps2.md) §3 (Failures found this pass), §5 (Sequenced closure plan, Phase 0)

> **Relationship to sibling packs.** `specs/t001-stabilization` (T002/T003/T004),
> `specs/personal-reasoning-policy-closure` (R101–R113), and
> `specs/gap-closure-t003` (T003-01…12) were all written against the *morning*
> gap inventory (`gaps1.md`). `gaps2.md` (evening) found the repo changed
> materially: the mail-connector plane was **committed broken** at `a3c07da`,
> two calendar tests became clock time-bombs, and the web theme rename is
> half-applied. Those integrity items (H-1…H-5) have no home in any existing
> pack. **This pack is that home.** It supersedes t001's T002/T003/T004
> (marked as such in t001's tasks.md); t001's T005–T010 + T008 gate remain
> valid as the Phase 5 hygiene sweep.

## Ground Truth (2026-10-14, ~23:20 UTC — all verified live this session)

| Area | State | Evidence |
|------|-------|----------|
| HEAD `a3c07da` import | 🔴 `backend/connectors/__init__.py` (HEAD) imports `MailConnector`; `backend/connectors/mail/__init__.py` (HEAD) does **not** export it (only `MailConnectorNotFoundError`, `MailConnectorService`) → `import backend.api.app` fails on a clean checkout | `git show HEAD:backend/connectors/__init__.py`; `git show HEAD:backend/connectors/mail/__init__.py` |
| Worktree import fix | ✅ 3-line fix present but **uncommitted** (`M backend/connectors/mail/__init__.py`: `from backend.api.models import MailConnector` + `__all__` entry) | `git diff backend/connectors/mail/__init__.py` |
| Calendar tests | 🔴 `pytest tests/backend/test_calendar.py` → **2 failed, 18 passed** (20 total). Failures: `test_ingest_new_is_201_replay_is_200`, `test_list_filters_to_window` — both rely on the `now`-anchored default window `[now, now+7d)` while `_day()` is the past-fixed date 2026-10-14. The `test_service_reset_hook` fix is in the worktree (uncommitted) | live run; `git diff tests/backend/test_calendar.py` |
| Full Python suite | 🟡 557 passed, 2 failed (the two above) | `pytest tests/ -m "not integration" -q` (gaps2 §2; confirmed by focused calendar run) |
| Web theme rename | 🟡 `Layout.tsx` (M) imports `ThemeToggle` at 3 sites; `ThemeToggle.tsx` **untracked**; `ThemeSwitcher.tsx` tracked and referenced by nothing; HEAD's `Layout.tsx` still says `ThemeSwitcher` | `git diff web/src/components/Layout.tsx`; `git ls-files`; `git show a3c07da:web/src/components/Layout.tsx` |
| SSO key hygiene (T009) | ✅ code done, **uncommitted** (`M tests/backend/test_auth_sso.py`, 64+ byte keys); t001 task-log row also uncommitted (`M specs/t001-stabilization/tasks.md`) | `git diff --stat`; t001 verification log |
| `web/dist` | 🟡 `web/dist/index.html` tracked **and** modified; `.gitignore` already has `dist/` (line 15) + `web/dist/` (line 42); `web/Dockerfile` builds in-image: `RUN npm run build` (line 33) + `COPY --from=build` (line 49) → untracking is safe | `git ls-files web/dist`; `rg -n 'npm run build\|COPY --from' web/Dockerfile` |
| `.patches/` | 🟡 3 worker `.patch` files untracked; **no** `.gitignore` rule | `rg -n 'patches' .gitignore` → no match |
| Untracked gap docs | 🟡 `gaps1.md`, `gaps2.md` untracked at repo root | `git status --short` |
| Workspace file | 🟡 `nervcenter.code-workspace` M — adds Swift debug launch configs for `NervePersonalRelay` (not mentioned in gaps2; verified present) | `git diff nervcenter.code-workspace` |
| Mail-connector tests | ❌ `tests/backend/test_mail_connector.py` does not exist | `ls tests/backend/` |
| Uncommitted surface (vs HEAD) | 7 modified + 4 untracked entries (`.patches/`, `gaps1.md`, `gaps2.md`, `ThemeToggle.tsx`) | `git status --short` |

## Architecture Decisions

1. **The import fix ships with the plane's tests — never alone.** The H-1
   defect happened because the plane's *fix* and the plane's *tests* landed
   out of order (fix uncommitted, plane committed). Commit 1 of P0-04
   bundles the 3-line `mail/__init__.py` re-export **and**
   `tests/backend/test_mail_connector.py` (P0-03 output) into a single
   commit, per gaps2 §3.1 gate.
2. **Complete the theme rename; do not revert.** `ThemeToggle` is the
   newer, better-marked component (gaps2 §7 Q1 default). P0-02 lands
   `ThemeToggle.tsx` + `Layout.tsx` and deletes the dead `ThemeSwitcher.tsx`
   in one commit. Re-running `npm run build` + `npm run e2e` is mandatory
   after the delete (last clean build had both files present).
3. **Calendar fixes are clock-invariant, not re-anchored.** Apply the exact
   gaps2 §3.2 diffs (explicit `start`/`end` query params on the two failing
   GETs; the endpoint already accepts them). Do **not** replace `_day()`
   with `datetime.now()` — the reset-hook NOTE already explains why
   explicit windows are the house technique.
4. **Untrack `web/dist`, don't delete it.** `git rm -r --cached web/dist`
   only; local files stay for dev builds. The in-image build
   (`web/Dockerfile` lines 33/49) was verified this session, so CI never
   depends on a committed dist. `.patches/` gets a `.gitignore` rule in the
   same commit.
5. **Logical commits, small and ordered.** P0-04 produces 6 commits in
   dependency order (import fix+tests → test hygiene → web rename → docs →
   workspace chore → artifact untrack). No monolith; the mail plane finally
   gets a logical commit of its own (G-0.1's "2–3 logical commits" is
   satisfied by this pack + the already-committed plane source).
6. **The detached-worktree import gate becomes a standing rule.** gaps2 §7
   Q6: any commit touching a backend import chain must be verified with
   `import backend.api.app` in a *detached worktree of the resulting
   commit*, not just in the working tree. Recorded in this pack's execution
   rules and added to the sibling packs' execution rules by the gaps2 delta
   amendments (AC-P07).

## Dependency Graph

```text
P0-01 calendar fixes ──┐
P0-02 theme rename ────┼──► P0-04 commit slice (6 commits) ──┐
P0-03 mail tests ──────┘          │                          │
                                  ▼                          ▼
                       P0-05 untrack artifacts       P0-06 final gate
                       (own commit; before P0-06)    (verification only)
```

- P0-01/P0-02/P0-03/P0-05 are mutually independent and can run in one
  parallel wave (disjoint file ownership).
- P0-04 (the commits) is the serialization point: it must wait for
  P0-01/P0-02/P0-03 to be green and in the working tree.
- P0-05 (artifact untrack) produces its own commit; it must land **before**
  P0-06 so the clean-tree evidence includes it.
- P0-06 (gate) depends on everything; it verifies *the commits*, not the
  worktree.

## File Ownership (single owner per path)

| Owner task | Paths |
|-----------|-------|
| P0-01 | `tests/backend/test_calendar.py` |
| P0-02 | `web/src/components/ThemeToggle.tsx` (add), `web/src/components/Layout.tsx`, `web/src/components/ThemeSwitcher.tsx` (delete) |
| P0-03 | `tests/backend/test_mail_connector.py` (new) |
| P0-04 | git commits only (bundles: `backend/connectors/mail/__init__.py`, `tests/backend/test_calendar.py`, `tests/backend/test_auth_sso.py`, `web/src/components/**`, `gaps1.md`, `gaps2.md`, `specs/t001-stabilization/tasks.md` T009 row, `nervcenter.code-workspace`) |
| P0-05 | `.gitignore`, `web/dist/` (index only) |
| P0-06 | verification only: command outputs, this pack's verification log |

Cross-boundary rule: P0-04 owns the *commits*; the working-tree edits belong
to P0-01/P0-02/P0-03/P0-05. P0-06 may not modify any file — if it finds a
failure, the offending task is reopened.

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Committing `Layout.tsx` without `ThemeToggle.tsx` breaks `tsc` on checkout | P0-04 commit 3 bundles both + the delete; P0-06's fresh-worktree check would catch it |
| Mail tests (P0-03) are written against in-memory behavior that differs from a future persistence layer | Tests pin the *current* contract (mirrors `test_email.py`); they are the regression net, not a design spec |
| Untracking `web/dist` breaks the image | Verified this session: `web/Dockerfile` builds in-image (lines 33/49); P0-05 re-checks the stage before `git rm` |
| The calendar "fix" just moves the time-bomb | The fix is window-explicit (clock-invariant by construction); P0-01's exit check includes the generalized grep rule from gaps2 §3.2 |
| Commit slice lands out of order | P0-04's checklist is the ordered list; each commit's `git show --stat` is recorded in the verification log |
| Untracked `nervcenter.code-workspace` churn surprises reviewers | It is a deliberate Swift-debug QoL file; committed as its own `chore` commit with a descriptive message (P0-04 commit 5) |

## Exit Criteria (from spec)

AC-P01…AC-P07 in [`spec.md`](./spec.md) — each maps to a task's verification
section in [`tasks.md`](./tasks.md).

## Initial Todos

- [x] P0-01: Apply the gaps2 §3.2 calendar window fixes (2 tests + NOTE comments); `pytest tests/backend/test_calendar.py` → 20 passed
- [x] P0-02: `git add web/src/components/ThemeToggle.tsx`; `git rm web/src/components/ThemeSwitcher.tsx`; `npm run build && npm run e2e` → 56 passed
- [x] P0-03: Write `tests/backend/test_mail_connector.py` (≥20 tests per checklist); green (37 passed)
- [x] P0-05: `git rm -r --cached web/dist`; add `.patches/` to `.gitignore`; rebuild; `git ls-files web/dist` empty
- [x] P0-04: Create the 6 ordered logical commits (import fix + tests bundled first); record each SHA → 6bdda63, 85e681c, 3f14891, dcf1bfd, 59d946c, 13cefdc (+ commit 7 spec-pack docs, see tasks.md delta note)
- [x] P0-06: Gate — detached worktree of final commit imports `backend.api.app` (IMPORT_OK); full suite green (596 passed); e2e 56; swift full run green (per-bundle `--filter` names stale — see tasks.md log); `git status` clean
