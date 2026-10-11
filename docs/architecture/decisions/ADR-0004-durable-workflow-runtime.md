# ADR-0004: Durable workflow runtime

- **Number:** ADR-0004
- **Title:** Durable workflow runtime — Temporal as primary; DAG scheduler demoted to compute placement
- **Status:** Proposed
- **Date:** 2026-10-10
- **Spec:** NC-SPEC-2026-010 (C0)

## Context

- The task DAG is implemented in-process: `DAGScheduler` — "Scheduler that identifies runnable tasks from a DAG of goal-associated tasks" — [backend/scheduler/scheduler.py:102](../../../backend/scheduler/scheduler.py), with dependency resolution in [backend/tasks/dag.py:1-3](../../../backend/tasks/dag.py) ("Task DAG and dependency resolution for NerveCenter (spec Section 23)").
- Task state lives in Postgres (`tasks`, `task_runs` tables created in the initial migration — [backend/persistence/alembic/versions/001_initial.py:20-21](../../../backend/persistence/alembic/versions/001_initial.py)), but **there is no durable execution runtime**: a search for "temporal" across the repository (code, manifests, docs) finds no runtime (grep, checked 2026-10-10). Long-running task sequences survive neither API restarts nor worker failures; anything beyond the current in-process scheduling is hand-rolled.
- Production runs on K3s (audit notes reference the `nervecenter` K3s namespace — [specs/web-quality-audit/gaps-walk.md:6](../../../specs/web-quality-audit/gaps-walk.md)).

## Decision

1. **Adopt Temporal as the primary production durable workflow runtime.** Long-running, multi-step, retryable work (task pipelines, reconciliation, replay, incident response) is expressed as Temporal workflows; every workflow is durable across process restarts by construction.
2. **The existing DAG scheduler remains for compute placement.** [backend/scheduler/scheduler.py:102](../../../backend/scheduler/scheduler.py) keeps its job of deciding *which* runnable tasks exist and *where* they should run (worker class, cluster node, GPU/host via the connector layer — e.g. [backend/connectors/gpu.py:52](../../../backend/connectors/gpu.py), [backend/connectors/kubernetes.py:25](../../../backend/connectors/kubernetes.py)). It becomes the scheduling/placement layer; Temporal becomes the execution/durability layer. The scheduler is consulted by the workflow runtime, not the other way around.
3. **Versioned workflow definitions.** Workflow code and its schema are versioned (Temporal versioning semantics); in-flight executions continue under their recorded version; new versions are opt-in. No silent behavioral change under a running execution.
4. **No silent fork.** There is exactly one source of truth for a task's definition and lifecycle. The DAG/scheduler module and the workflow module must not each maintain parallel state machines for the same task; integration is a single contract (task → workflow start, workflow progress → `task_runs` updates).
5. **Temporal is infrastructure, not a library convenience.** Deployed alongside the existing K3s stack (see ADR-0005 for the K3s baseline); it is never emulated away in production.

## Alternatives considered

1. **Argo Workflows (Kubernetes-native).** Attractive because production is K3s, but workflow-as-manifest is weaker for per-execution retry/backoff business logic and couples workflow identity to the cluster. Noted; Temporal's durable execution model fit better.
2. **Postgres queue + in-process workers.** No new dependency, but re-implements checkpointing, retry, timers, and history; exactly the durability gap being closed. Rejected.
3. **Celery.** Durability is broker- and backend-dependent (Redis/rabbitmq), history/visibility is weaker, and it adds a second task-system vocabulary on top of the existing DAG. Rejected.
4. **Keep the in-process scheduler as the durable runtime.** It is in-process by design ([backend/scheduler/scheduler.py:102](../../../backend/scheduler/scheduler.py)); no durability guarantees exist today. Rejected.

## Consequences

- New infrastructure: Temporal cluster (server + UI) on K3s, plus a worker deployment that hosts workflow code and consults the DAG scheduler for placement.
- Task lifecycle semantics change subtly: "runnable" now means "temporal workflow started and in flight"; `task_runs` ([backend/persistence/alembic/versions/001_initial.py:21](../../../backend/persistence/alembic/versions/001_initial.py)) remains the queryable record, mirroring workflow progress.
- Versioning discipline is mandatory for every workflow; CI must pin workflow schema versions.
- Operational cost rises (one more stateful service); in exchange, replay, recovery, and multi-day workflows stop being bespoke code.
- The DAG module's API surface shrinks to placement questions; any code that currently assumes in-process execution of a task must move behind the workflow contract.

## References

- [backend/scheduler/scheduler.py:102](../../../backend/scheduler/scheduler.py)
- [backend/tasks/dag.py:1-3](../../../backend/tasks/dag.py)
- [backend/persistence/alembic/versions/001_initial.py:20-21](../../../backend/persistence/alembic/versions/001_initial.py)
- [backend/connectors/gpu.py:52](../../../backend/connectors/gpu.py), [backend/connectors/kubernetes.py:25](../../../backend/connectors/kubernetes.py)
- [specs/web-quality-audit/gaps-walk.md:6](../../../specs/web-quality-audit/gaps-walk.md)
- Absence of a durable workflow runtime in the repository: grep for "temporal" over code/manifests/docs, checked 2026-10-10.
