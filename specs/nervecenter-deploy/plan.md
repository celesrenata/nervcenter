# Plan: NerveCenter Deployment to K3s via Harbor

**Feature:** nervecenter-deploy · **Spec:** [`spec.md`](./spec.md) · **Tasks:** [`tasks.md`](./tasks.md)

## Ground Truth (audit 2026-09-28)

| Area | State | Evidence |
|------|-------|----------|
| Python | 17,329 LOC; `.venv` py3.11.16/pip24 works; deps not installed; `create_app` import fails (app module exposes `app`, not `create_app`) | `backend/api/app.py:8` |
| Empty modules | `backend/agents`, `backend/evidence`, `backend/observability`, `backend/orchestration`, `sdk/python`, `sdk/typescript`, root `agents/` | line counts = 1 (stub only) |
| Cluster | K3s v1.36.4, gremlin-1..4 Ready; traefik ingress; per-ns `harbor-pull` dockerconfigjson secrets; `harbor-service/harbor-ca-bundle` | `kubectl get nodes/secrets/ingress` |
| Registry | `registry.celestium.life` (Harbor); push auth via harbor credentials in cluster or local docker config | user instruction |
| Docker | local daemon socket dead at audit time; may need daemon restart or in-cluster build | `docker version` |
| Web | Vite+React+TS scaffolding exists (`web/src/App.tsx`, `views/` unverified) | file listing |
| Git | repo initialized, baseline commit `dcdf09d` | `git log` |

## Architecture Decisions

1. **Namespace:** `nervecenter` (isolated from `docker-*` pattern services; mirrors `hellodj-service` style).
2. **Containers:** 4 in-cluster components:
   - `api` — FastAPI + CLI + MCP in one image (monolith-first; MCP is a thin tool layer over the same services)
   - `web` — static Vite build served by nginx image
   - `postgres` — pgvector image, PVC-backed
   - `nats` — JetStream enabled
3. **Registry layout:** `registry.celestium.life/nervecenter/{api,web}:<git-sha>` — immutable tags + `latest` alias.
4. **Ingress:** `nervecenter.celestium.life` (traefik) → web; path `/api/*` → api; `/mcp/*` → api.
5. **Pull secret:** copy existing `harbor-pull` dockerconfigjson into `nervecenter` ns.
6. **Migrations:** Alembic upgrade runs as a one-shot `initdb` Job before the API deployment.
7. **Config:** ConfigMap for non-sensitive env; Secret for DB URL, NATS URL, OmniRoute URL.
8. **Verification:** every claim backed by command output (curl, kubectl, Playwright screenshots).

## Dependency Graph

```
T101 backend-boot ─────┐
T102 cli-mcp-sdk ───────┤
T103 web-build ─────────┼──► T201 deploy ──► T202 audit-fix-loop ──► T203 demo
T104 docker-k8s ────────┘
T204 apple-sdk (independent, M5 Max only)
```

- Dispatch T101, T102, T103, T104, and T204 as independent implementation scopes against the contracts in `spec.md`; prioritize at least three concurrent workers when three inference hosts are free.
- T101 is on the deployment critical path, but it does not block CLI, MCP, SDK, web, or manifest implementation. Their live integration checks wait for T101.
- T204 starts from the schema contract and regenerates models from live OpenAPI after T101; it does not wait to begin.

## File Ownership (single owner per path)

| Owner task | Paths |
|-----------|-------|
| T101 | `backend/**`, `schemas/**`, `migrations/**`, `tests/**`, `pyproject.toml` |
| T102 | `cli/**`, `mcp/**`, `sdk/**` |
| T103 | `web/src/**`, `web/index.html`, web build config (excluding `web/Dockerfile`) |
| T104 | `deployments/kubernetes/**`, `Dockerfile*`, `.github/**` (if CI added) |
| T201/T202 | k8s objects via kubectl, `deployments/` patches |
| T203 | `synthetic-lab/**` |
| T204 | `apple/Shared/**`, `apple/NerveCenter.xcodeproj` |

Cross-boundary rule: T102 may *read* `backend/` but not modify it; defects found go back as T101 follow-ups.

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Local docker daemon down | fallback: buildx in-cluster or restart daemon; T104 scripts handle both |
| Modules were written blind (never run) | T101 requires boot + tests; audit loop T202 catches runtime gaps |
| Harbor push auth | extract dockerconfigjson from existing ns secret; docker login locally |
| pgvector extension availability | use `pgvector/pgvector:pg16` image directly |
| Web UI views never implemented | T103 scope: implement missing views per spec §48; Playwright gates on all 10 |

## Exit Criteria (from spec)

AC001–AC010 in [`spec.md`](./spec.md) — each maps to a task's verification section.
