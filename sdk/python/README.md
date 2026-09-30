# nervcenter_sdk (Python)

Async `httpx` client for the NerveCenter §46 HTTP API, with a small sync
convenience wrapper. Lives at `sdk/python/nervcenter_sdk/`.

## Install / import

The package is not published; run from the repo root (the venv already
ships `httpx`):

```bash
# from repo root
.venv/bin/python -c "import nervcenter_sdk"  # fails unless sdk/python is on the path
PYTHONPATH=sdk/python .venv/bin/python -c "import nervcenter_sdk; print('ok')"
```

For tests, pytest inserts `sdk/python` onto `sys.path` automatically
(the test package `sdk/python/tests/` has an `__init__.py` but
`sdk/python` does not), so `import nervcenter_sdk` works from a
root-level `pytest sdk/python/tests/` run — no extra packaging needed.

## Quick start (async)

```python
import asyncio

from nervcenter_sdk import NerveClient

async def main() -> None:
    async with NerveClient(base_url="http://localhost:8310", timeout=10.0) as client:
        health = await client.health()          # GET /api/health
        goals = await client.goals.list()       # GET /api/goals -> unwrapped list
        goal = await client.goals.get("goal-1") # GET /api/goals/goal-1
        print(health)
        print([g["name"] for g in goals])

asyncio.run(main())
```

## Per-group §46 methods

`client.<group>.list(**params)` and `client.<group>.get(item_id)` for:

`events · entities · relationships · evidence · claims · search ·
goals · tasks · agents · runs · incidents · models · compute · routes ·
changes · approvals · clients · context`

Plus the §47 mutation paths (contract targets; backend returns 405
until implemented — see `cli/CONTRACT_GAP_NOTES.md`):

```python
await client.context.ask("why did hellodj restart?")      # POST /api/context/ask
await client.incidents.investigate("hellodj")             # POST /api/incidents/investigate
await client.agents.pause()                               # POST /api/agents/pause
await client.changes.stop_mutations()                     # POST /api/changes/stop-mutations
```

## §29 correlation

Every request sends a `Nerve-Trace-Id` header (UUID). Override per
request or per client:

```python
await client.goals.list(trace_id="my-fixed-trace-id")   # per request
NerveClient(base_url=..., trace_header_value="abc")    # fixed per client
```

## Retry semantics

- Exactly **one** retry on HTTP 5xx (and on connect-level network
  errors) — then `ContractError` / `UnreachableError` is raised.
- 4xx raises `ContractError` immediately (no retry).

```python
from nervcenter_sdk import ContractError, UnreachableError

try:
    await client.entities.get("missing")
except ContractError as exc:
    print(exc.status, exc.detail)   # e.g. 404 {"detail": "Entity not found"}
```

## Sync convenience wrapper

`NerveSync` wraps the async client on a private event loop per call —
for plain scripts:

```python
from nervcenter_sdk import NerveSync

sync = NerveSync(base_url="http://localhost:8310")
print(sync.health())       # GET /api/health
print(sync.goals().list()) # GET /api/goals -> unwrapped list
```

## Tests

```bash
.venv/bin/python -m pytest sdk/python/tests/ -q
```

All tests run offline against `httpx.MockTransport` (no live server):
GET envelope unwrap + correlation header, POST body + correlation
header, 5xx retry (exactly once), 4xx no-retry, connect-failure retry,
and the sync wrapper.
