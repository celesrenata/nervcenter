# NerveCenter CLI (spec §47)

A Click-based command line client for the NerveCenter §46 HTTP API.
Zero dependencies beyond `click` (and optional `tabulate`) — the HTTP
client is stdlib `urllib`, and the table renderer falls back to a
built-in formatter when `tabulate` is not installed.

## Running

```bash
# from the repo root, with the project venv
source .venv/bin/activate
python -m cli.main --help
```

## Configuration

| Source | Effect |
|---|---|
| `--api URL` flag | API base URL for that invocation |
| `NERVE_API` env | API base URL (used when `--api` is absent) |
| default | `http://localhost:8000` |

Every command accepts `--json` (raw API JSON body) and
`--output-format {table|text}` (default: table for lists, key: value
for objects). Every request carries a §29 correlation header
(`Nerve-Trace-Id`, fresh UUID per request).

**Exit codes:** `0` success · `2` contract/usage error (bad URL,
HTTP ≥ 400, not found) · `127` API unreachable.

## Command inventory

| Command | Request | Notes |
|---|---|---|
| `status` | `GET /api/health` + `GET /version` | health checks + API version |
| `ask "<question>"` | `POST /api/context/ask` | **contract gap — backend 405 today** |
| `entity <name>` | `GET /api/entities/<id>` → fallback `GET /api/entities` + client-side name match | |
| `changes [<name>] [--since 4h]` | `GET /api/changes?entity=…&since=…` | `--since` (e.g. `4h`, `30m`, `2d`) also filters client-side |
| `goal list` | `GET /api/goals` | |
| `goal show <id>` | `GET /api/goals/<id>` | |
| `task list` | `GET /api/tasks` | |
| `task show <id>` | `GET /api/tasks/<id>` | |
| `agents` | `GET /api/agents` | |
| `compute` | `GET /api/compute` | |
| `routes` | `GET /api/routes` | |
| `incident investigate <name>` | `POST /api/incidents/investigate` | **contract gap — backend 405 today** |
| `incident show <id>` | `GET /api/incidents/<id>` | |
| `pause-agents` | `POST /api/agents/pause` | **contract gap — backend 405 today** |
| `stop-mutations` | `POST /api/changes/stop-mutations` | **contract gap — backend 405 today** |

See [CONTRACT_GAP_NOTES.md](CONTRACT_GAP_NOTES.md) for the full gap
analysis against the current backend routes.

## Examples

```bash
$ python -m cli.main status --json --api http://127.0.0.1:8310
{
  "api": "http://127.0.0.1:8310",
  "health": {
    "status": "degraded",
    "version": "0.1.0",
    "checks": {
      "db":   {"status": "unreachable", "message": "database is not configured"},
      "nats": {"status": "unreachable", "message": "NATS is not configured"}
    }
  },
  "version": {
    "version": "0.1.0",
    "release_date": "2026-09-28",
    "compatible_versions": ["0.1.x"],
    "endpoints": {"base": "/api/v1", "auth": "/auth", "observability": "/observability"}
  }
}
```

```bash
$ python -m cli.main goal list --api http://127.0.0.1:8310
+--------+--------+-----------+
| id     | name   | status    |
+========+========+===========+
| goal-1 | Goal 1 | active    |
+--------+--------+-----------+
| goal-2 | Goal 2 | completed |
+--------+--------+-----------+
```

```bash
$ python -m cli.main entity ent-1 --json --api http://127.0.0.1:8310
{
  "match": "id",
  "entity": {"id": "ent-1", "type": "person", "name": "Ada Lovelace"}
}
```

```bash
$ python -m cli.main task list --json --api http://127.0.0.1:8310
[
  {"id": "task-1", "name": "Task 1", "status": "pending"},
  {"id": "task-2", "name": "Task 2", "status": "completed"}
]
```

```bash
$ python -m cli.main changes --since 4h --json --api http://127.0.0.1:8310
[]
```

### Unreachable server (exit 127, no traceback)

```bash
$ python -m cli.main status --json --api http://127.0.0.1:9
error: cannot reach NerveCenter API at http://127.0.0.1:9 ([Errno 61] Connection refused)
$ echo $?
127
```

### Contract error (exit 2)

```bash
$ python -m cli.main pause-agents --json --api http://127.0.0.1:8310
error: POST /api/agents/pause returned HTTP 405: Method Not Allowed
$ echo $?
2
```

## Local smoke

```bash
NERVE_MOCK_INFER=1 .venv/bin/python -m uvicorn backend.api.app:app --port 8310 &
python -m cli.main status --json --api http://127.0.0.1:8310
python -m cli.main goal list --api http://127.0.0.1:8310
```
