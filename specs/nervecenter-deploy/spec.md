# Spec: NerveCenter Deployment to K3s via Harbor

**Feature ID:** nervecenter-deploy
**Created:** 2026-09-28
**Status:** Active
**Branch target:** main (repo root: nervcenter)

## Problem

The NerveCenter codebase (Phases 0–2 written) has never been executed end-to-end:
- `.venv` deps were never installed (`create_app` import fails, CLI missing `tabulate`)
- 4 backend modules are empty stubs (`agents`, `evidence`, `observability`, `orchestration`)
- `sdk/python`, `sdk/typescript`, root `agents/` are empty
- No Docker image exists; nothing is deployed to the gremlin K3s cluster
- Web UI, MCP, CLI, API have never been audited against a live system

The user goal: **deploy NerveCenter to K3s via `registry.celestium.life` (Harbor), and ensure each component actually works, using Playwright to audit the Web UI, deploying new containers as needed until all features from the original spec work.**

## Goals

1. Make the local build runnable: all backend modules boot, tests pass, CLI/MCP/API work.
2. Produce deploy artifacts: Dockerfile(s), Harbor push scripts, K3s kustomize manifests.
3. Deploy the full stack (API, web UI, MCP, PostgreSQL, NATS) to the cluster.
4. Audit every deployed component with concrete evidence (curl, Playwright, kubectl logs).
5. Iterate: fix → rebuild → redeploy → re-audit until acceptance criteria pass.

## Scope

**In scope:** backend fixes, deployment artifacts, Harbor push, K3s deploy, live audit (API/CLI/MCP/web via Playwright), synthetic-incident demo, Apple shared SDK compile on M5 Max (xcodebuild).

**Out of scope:** real iPhone/Watch device testing, cloud inference integration beyond OmniRoute adapter stub, multi-user auth hardening.

## Constraints

- Registry: `registry.celestium.life` (Harbor, self-signed CA bundle in cluster secret `harbor-service/harbor-ca-bundle`)
- Cluster: gremlin-1..4, K3s v1.36.4+k3s1, traefik ingress, existing patterns: `docker-*` namespaces, `harbor-pull` pull secrets per namespace
- Local docker daemon was down at audit time; image build may need kaniko/buildkit in-cluster or daemon restart
- Python 3.11.16 venv with pip 24.0 works; system python 3.13 has no pip
- Spec Kit installed; use speckit workflows, do not reset

## Assumptions

- Harbor credentials obtainable via kubectl (namespace secrets) or docker login with existing config
- PostgreSQL and NATS may run as in-cluster containers in the NerveCenter namespace
- OmniRoute is reachable from cluster (adapter config via env)
- Playwright available via npx or python playwright for web audits

## Acceptance Criteria

- AC001: `pip install -e .` succeeds; `python -c "from backend.api.app import app"` imports; FastAPI app boots with uvicorn on :8000
- AC002: `pytest tests/` passes with ≥1 test per backend subsystem (events, knowledge, goals, tasks, inference, connectors, persistence)
- AC003: CLI `python -m cli.main --help` and `nerve status` work against live API (JSON output)
- AC004: MCP server exposes ≥15 tools from spec §45 and responds to `list_tools`
- AC005: Web UI builds (`npm run build`) and Playwright audit confirms all 10 views (Overview, Systems, Timeline, Goals, Task DAG, Agents, Inference, Incidents, Decisions, Ask) render without console errors
- AC006: Docker image builds and pushes to `registry.celestium.life/nervecenter/api:<tag>`
- AC007: K3s deployment: pods Running (api, web, postgres, nats, mcp), ingress serves web at `<host>.celestium.life`, API reachable, no CrashLoopBackOff
- AC008: Synthetic incident demo: seeded fault → investigation DAG → ≥3 parallel investigations → remediation proposal → approval → resolution, verified end-to-end on cluster
- AC009: Apple shared SDK compiles (`xcodebuild -scheme NerveShared build`) on M5 Max
- AC010: `docs/implementation-status.yaml` reflects verified state with evidence links
