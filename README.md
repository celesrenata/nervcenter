# NerveCenter

NerveCenter is a personal intelligence system: a local-first, event-driven core that
captures evidence, maintains a structured knowledge graph, tracks goals, orchestrates
agents, and exposes the results through APIs, MCP tools, SDKs, a CLI, a web UI, and
native Apple clients.

## Design Principles

- **Local-first**: All state lives in an on-device database; cloud is optional.
- **Event-driven**: A single event bus drives every subsystem; nothing polls.
- **Evidence-based**: Every inference and decision cites captured evidence.
- **Schema-first**: Interfaces and stored records are validated against versioned schemas.
- **Multi-client**: One core, many surfaces — API, MCP, CLI, web, iOS, and watchOS.

## Repository Layout

The layout below matches Section 8 (Repository Structure) of the NerveCenter specification.

| Path | Purpose |
| --- | --- |
| `backend/` | Python core: API, event bus, knowledge, evidence, goals, tasks, context, orchestration, scheduler, agents, inference, policy, connectors, observability, persistence |
| `schemas/` | Versioned JSON Schema / data contracts for all records and interfaces |
| `sdk/` | Client SDKs: Python (`sdk/python`) and TypeScript (`sdk/typescript`) |
| `mcp/` | MCP server exposing NerveCenter tools to model clients |
| `cli/` | Terminal client for the core |
| `web/` | Browser UI |
| `apple/` | Native Apple clients: `Shared`, `iOS`, `Watch`, `Widgets`, `Tests` |
| `agents/` | Agent definitions, prompts, and capability manifests |
| `deployments/` | Deployment definitions: `nix`, `kubernetes`, `local` |
| `synthetic-lab/` | Synthetic-data lab for testing and evaluation |
| `migrations/` | Database schema migrations |
| `tests/` | Cross-cutting integration and end-to-end tests |
| `docs/` | Specifications, architecture notes, and implementation status |

## Backend Modules

| Module | Responsibility |
| --- | --- |
| `backend/api` | HTTP/gRPC interface surface |
| `backend/events` | Event bus, subscriptions, replay |
| `backend/knowledge` | Knowledge graph, entities, relations |
| `backend/evidence` | Evidence capture, provenance, citations |
| `backend/goals` | Goal models, progress, decomposition |
| `backend/tasks` | Task queues, scheduling, execution |
| `backend/context` | Context assembly and budgeting |
| `backend/orchestration` | Multi-agent orchestration, plan execution |
| `backend/scheduler` | Time-based scheduling and reminders |
| `backend/agents` | Agent runtime and registries |
| `backend/inference` | Model routing, inference adapters |
| `backend/policy` | Guardrails, permissions, redaction |
| `backend/connectors` | External system integrations |
| `backend/observability` | Tracing, metrics, logs |
| `backend/persistence` | Storage engines, WAL, snapshots |

## Implementation Status

Live workstream tracking lives in [`docs/implementation-status.yaml`](docs/implementation-status.yaml).

## Development

```bash
# Python core tooling (ruff, pyright, pytest)
pip install -e ".[dev]"
ruff check .
pyright backend
pytest tests
```

## Documentation

- Specification and architecture notes: `docs/`
- Schemas and data contracts: `schemas/`
