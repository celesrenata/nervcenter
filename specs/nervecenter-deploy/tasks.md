# Tasks: NerveCenter Deployment to K3s via Harbor

**Spec:** [`spec.md`](./spec.md) · **Plan:** [`plan.md`](./plan.md)

## Task Board

| ID | Title | AC | Deps | Files owned | Verification |
|----|-------|----|------|-------------|--------------|
| T101 | Backend boots & all subsystems run | AC001, AC002, AC010 | — | `backend/**`, `schemas/**`, `migrations/**`, `tests/**`, `pyproject.toml` | venv install clean; `uvicorn` boots; pytest ≥1 test/subsystem green |
| T102 | CLI + MCP + SDK against API contract | AC003, AC004 | — | `cli/**`, `mcp/**`, `sdk/**` | contract tests first; live API smoke after T101 |
| T103 | Web UI builds & serves all spec views | AC005 | — | `web/src/**`, `web/index.html`, web build config (not `web/Dockerfile`) | `npm run build` clean; mocked API smoke first, live Playwright after T101 |
| T104 | Docker + k8s manifests + Harbor scripts | AC006, AC007 | — | `Dockerfile.api`, `web/Dockerfile`, `deployments/kubernetes/**`, deployment scripts | manifests/scripts and dry-run first; image build after T101 and T103 |
| T201 | Deploy to K3s via Harbor | AC006, AC007 | T101, T103, T104 | k8s objects in `nervecenter` ns | all pods Running; ingress serves web+API; logs clean |
| T202 | Audit deployed system & fix loop | AC001–AC005, AC007 | T201 | patches across `backend/**`, `web/**`, `deployments/**` | curl matrix + Playwright matrix all green; defects filed & fixed |
| T203 | Synthetic incident demo end-to-end | AC008 | T202 | `synthetic-lab/**` | seeded fault → DAG → ≥3 parallel investigations → remediation → resolution |
| T204 | Apple shared SDK compiles on M5 Max | AC009 | — | `apple/Shared/**`, xcodeproj | compile contract-based models first; regenerate from live OpenAPI after T101 |

T101, T102, T103, T104, and T204 have disjoint initial file ownership and can start in one dispatch wave. Work from `spec.md` and the existing schema/API contract; defer live integration checks until the backend boots. A failing downstream smoke test is an integration finding, not a reason to idle its worker before implementation. Dispatch at least three of these scopes concurrently when three inference hosts are free; keep each worker within its owned paths.

## T101 — Backend boots & all subsystems run

Scope:
- Fix venv: install all deps into `.venv` (py3.11) — `pip install -e ".[dev]"`
- Fix `backend/api/app.py` import surface (expose both `app` and `create_app`)
- Implement the 4 empty modules to spec §26/§37/§44/§74:
  - `backend/evidence/` — EvidenceService (CRUD, immutability, hash verify, claim linkage)
  - `backend/agents/` — agent registry, AgentRun lifecycle, blackboard (spec §25–26, §75 loop protection)
  - `backend/orchestration/` — incident workflow DAG, blackboard coordinator, correlation agent (§38)
  - `backend/observability/` — OTel span wiring, trace correlation, Prometheus metrics (§74)
- Wire all routers into API (events, entities, relationships, evidence, claims, goals, tasks, agents, runs, incidents, models, compute, routes, changes, approvals, clients — spec §46)
- Alembic: upgrade head idempotent; add `initdb` job entrypoint
- Tests: ≥1 pytest per subsystem + integration test posting an event through NATS→DB

## T102 — CLI + MCP + SDK

Scope:
- CLI: all §47 commands (`status`, `ask`, `entity`, `changes`, `goal`, `task`, `agents`, `compute`, `routes`, `incident`, `pause-agents`, `stop-mutations`) with `--json`
- MCP server: spec §45 tool list (15 tools), MCP client wrapper; expose on `/mcp` endpoint or stdio
- SDK python: typed client from OpenAPI (httpx, async); SDK typescript: fetch client
- Verification against live (local then cluster) API

## T103 — Web UI

Scope:
- Implement missing views per §48–51: Overview, Systems, Timeline, Goals, Task DAG (8 states visible), Agents, Inference (nodes/models/routes live), Incidents, Decisions, Ask
- Realtime via SSE/WebSocket from API
- Auth context per §71 device-pairing stub
- Playwright smoke: each view renders, API data shown, 0 console errors

## T104 — Deploy artifacts

Scope:
- `Dockerfile.api` (multi-stage, python3.11-slim, uvicorn, alembic entry)
- `web/Dockerfile` (build stage + nginx static, SPA fallback)
- K3s kustomize `deployments/kubernetes/base/`: namespace `nervecenter`, pull secret, PVC+StatefulSet postgres (pgvector/pgvector:pg16), nats (JetStream), migrations Job, api Deployment, web Deployment+Service, ingress `nervecenter.celestium.life`, ConfigMap/Secret
- `deploy-harbor.sh`: build → tag with git sha → login (harbor creds) → push → kubectl apply -k
- Dry-run validation: `kubectl apply -k --dry-run=server`

## T201 — Deploy to K3s

Steps:
1. Extract Harbor creds: `kubectl get secret -n beeflow-service harbor-pull -o jsonpath='{.data.\.dockerconfigjson}'` or docker login prompt
2. Build+push api & web images
3. `kubectl create ns nervecenter`; copy harbor-pull secret
4. Apply kustomize; watch pods; fix until Running
5. Verify: `curl https://nervecenter.celestium.life/api/health`, ingress cert via cert-manager

## T202 — Audit & fix loop

Matrix:
- API: every §46 group endpoint returns 200/expected JSON
- CLI: §47 commands against cluster URL
- MCP: list_tools + one call each tool
- Web: Playwright script across 10 views + Ask query round-trip
- Defects → fix → T201 redeploy → re-run until green

## T203 — Synthetic incident demo

Scope per §94 canonical demo: seed HelloDJ-equivalent workload via synthetic-lab; break it (config drift); observe NerveCenter investigation DAG with ≥3 concurrent branches; Watch/iPhone-equivalent approval via API; execute reversible remediation; verify recovery; assert permanent record (cause/fix/evidence/timeline) in DB.

## T204 — Apple shared SDK

Scope: `apple/Shared/` SwiftPM package (NerveModels/NerveAPI/NerveAuth/NervePersistence/NerveRealtime/NerveDesign); generate NerveModels from OpenAPI; `xcodebuild -scheme NerveShared -destination 'generic/platform=iOS Simulator' build` on M5 Max.

## Verification Log

*(updated per task completion — commands, results, gaps)*

### T-WEBE2E / AC005 — Web UI e2e audit (Playwright)

- Command: `cd web && npm run e2e` (self-contained: globalSetup boots `NERVE_MOCK_INFER=1 .venv/bin/python -m uvicorn backend.api.app:app` on :8000, Vite dev server on :3000 with `VITE_API_BASE=/api`, then 10 view-render tests + Ask round-trip on chromium; globalTeardown stops the backend)
- Result: **11 passed (14.1s)** under Node v24.20.0 / chromium 1243 — every spec view (Overview, Systems, Timeline, Goals, Task DAG, Agents, Inference, Incidents, Decisions, Ask) renders without console errors; Ask round-trip asserts the real 202 `accepted/executed:false/service:context` ack and renders it with zero console errors.
- Defect found & fixed (blocking): `@playwright/test` 1.48 wedged indefinitely under Node 24 — its `requireOrImport` (`lib/transform/transform.js`) does `eval(import(global-setup.mjs))` and the dynamic import never resolves (sample stack: stuck in `ImportModuleDynamicallyWithPhase`, 0 output, 10+ min; minimal A/B repro with the real global-setup hook: Node 22 = 1s pass, Node 24 = hard-timeout hang). Fixed by bumping `@playwright/test` 1.48 → `^1.63.0`; requires `npx playwright install chromium` once after install.
- Defect found & fixed: the documented 404 console filter in `views.spec.ts`/`ask.spec.ts` parsed the URL out of the console *text* (`text.split(' (').pop()` → `"Not Found"`), which can never match — the URL of a "Failed to load resource" console error is on `msg.location().url`, not `msg.text()` (verified empirically). The proven dead-ends `/api/systems` + `/api/decisions` (404 live; neither is in spec §46's endpoint groups; views degrade to empty state) therefore failed `/systems` + `/decisions`.
- Defect found & fixed: `ask.spec.ts` user-bubble assertion was a strict-mode violation — the question string also renders in the permanent "Quick Questions" suggestion button; scoped to `p.whitespace-pre-wrap`.
- Companion gates: `cd web && npm run build` → exit 0 (tsc + vite, 49 modules); `.venv/bin/python -m pytest tests/ -m "not integration" -q` → 38 passed.
- Commit: `c34712b`
