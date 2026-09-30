# §46 / §47 Contract Gap Notes (T102)

Findings from mapping the §47 CLI command set and the SDK method surface onto
the **actual** backend routes (read-only audit of `backend/api/app.py` and
`backend/api/endpoints/*.py`). Backend code was **not** modified.

## 1. Missing POST endpoints (blocks §47 mutation commands)

The backend currently exposes **only GET routes** for the §46 collections
(plus `/auth/login|refresh|logout`). There is no POST router anywhere in
`backend/api/**` for any of the §7 mutation/ask operations:

| §47 command      | Canonical target path        | Backend status |
|------------------|------------------------------|----------------|
| `nerve ask "…"`  | `POST /api/context/ask`      | **not implemented** → 405 Method Not Allowed |
| `nerve pause-agents`   | `POST /api/agents/pause`        | **not implemented** → 405 |
| `nerve stop-mutations` | `POST /api/changes/stop-mutations` | **not implemented** → 405 |
| `nerve incident investigate <name>` | `POST /api/incidents/investigate` | **not implemented** → 405 |

The CLI targets these canonical paths and reports the HTTP status as a
contract error (exit code 2) until the backend implements them. The Python
SDK exposes the same paths as `context.ask()`, `agents.pause()`,
`changes.stop_mutations()`, and `incidents.investigate(entity)`; the TS SDK
exposes `client.ask()`, `client.pauseAgents()`, `client.stopMutations()`,
and `client.investigate()`.

The spec (§47 line 1855–1859) requires these commands to exist; the spec
(§46) does not name exact POST paths, so the canonical paths above are the
contract targets to implement in a follow-up backend task.

## 2. No entity query/lookup parameter

§47 shows `nerve entity hellodj` (lookup **by name**), but the backend
serves only:

- `GET /api/entities/` (fixed two-item sample list, no query params)
- `GET /api/entities/{entity_id}` (ID lookup, 404 otherwise)

`/api/entities?query=` does not exist. The CLI works around this by
falling back to a client-side name match over the list after an ID 404.
`nerve changes <name> --since 4h` similarly sends `entity`/`since` query
params that the current backend ignores (and applies `--since` filtering
client-side). **Gap:** server-side entity-by-name search and time-windowed
change listing are unimplemented.

## 3. Read-only collection routers return empty data without services

`make_read_router` adapters (events, relationships, claims, search,
context, runs, incidents, models, compute, routes, changes, approvals,
clients) return `{"data": [], "meta": {...}}` whenever no application
service is wired into `app.state.services`. In a bare local boot
(`NERVE_MOCK_INFER=1`, no DB/NATS) these collections are **always empty** —
this is by design in the backend, but it means live smoke checks of those
groups cannot distinguish "no data" from "service not wired".

## 4. `NERVE_MOCK_INFER` is not referenced in the backend

The smoke contract says `NERVE_MOCK_INFER=1` works without DB/NATS. The
backend boots fine without DB/NATS anyway (dependency-tolerant health), and
no code under `backend/` references `NERVE_MOCK_INFER` (grep-verified).
The env var is currently a no-op; harmless, but not wired.

## 5. `status` uses `GET /api/health` + `GET /version`

`/api/health` returns `{"status": "ok"|"degraded", "version", "checks":
{db, nats}}`. Without DB/NATS it reports `degraded` (checks
`unreachable`/"not configured"). The CLI's `status` command treats the
HTTP 200 as success (exit 0) and surfaces the degraded state in the
rendered output — matching the "health stays 200" contract.

## 6. §46 vs §45 (MCP) correlation header naming

§29 names the correlation field `nerve_trace_id`. The MCP layer
(`mcp/api.py`) sends it as the HTTP header `Nerve-Trace-Id`. The CLI and
both SDKs follow the same convention (`Nerve-Trace-Id`) so all three
client layers correlate identically.

## Resolved

T-BE-FIX (this commit) implemented the four canonical POST endpoints listed
in section 1. The historical findings above are preserved verbatim; the
paths now exist and no longer return 405:

| §47 command      | Implemented route                  | Service / method probe (in order)            | Request body                      |
|------------------|------------------------------------|----------------------------------------------|-----------------------------------|
| `nerve ask "…"`  | `POST /api/context/ask`            | `context` → `ask`, `compile`, `list`         | `{"question": "..."}` (alias `query`) |
| `nerve pause-agents` | `POST /api/agents/pause`       | `agents` → `pause`, `pause_agents`           | none                              |
| `nerve stop-mutations` | `POST /api/changes/stop-mutations` | `orchestration` → `stop_mutations`, `stop_mutation` | none                          |
| `nerve incident investigate <name>` | `POST /api/incidents/investigate` | `orchestration` → `investigate`     | `{"entity": "..."}` (alias `name`) |

Response contract (all four routes), via `make_write_endpoint` in
`backend/api/endpoints/_helpers.py`:

- **200** when a configured service method executed successfully:
  `{"accepted": true, "executed": true, "service": <name>, "method":
  <method used>, "detail": null, "result": <json-safe result>,
  "request_id": <uuid4>, "timestamp": <iso8601>}`.
- **202** when the contract is acknowledged but nothing executed — no
  service configured, no matching method, or the method raised — keeping
  the API bootable without dependencies (mirrors the `make_read_router`
  dependency-tolerance): `{"accepted": true, "executed": false,
  "service": <name>, "detail": <reason>, "result": null,
  "request_id": <uuid4>, "timestamp": <iso8601>}`.

When a request body is accepted, the first present key from the
endpoint's `arg_keys` is forwarded as the single positional argument to
the service method, but only when the method's signature (checked with
`inspect.signature`) accepts a positional parameter; zero-arg methods are
called with no arguments.
