# NerveCenter SDKs

Client libraries for the NerveCenter §46 HTTP API, generated against the
live OpenAPI surface (not a stub generator — hand-maintained to match
`backend/api/app.py`).

```
sdk/
├── python/       # nervcenter_sdk — async httpx client + sync wrapper
└── typescript/   # plain-fetch client (Node built-ins only) + smoke script
```

## Shared contract

Both SDKs implement the same cross-cutting behavior:

- **Base URL** — configurable; `NERVE_API` env or constructor argument,
  default `http://localhost:8000`.
- **§29 correlation** — every request carries a `Nerve-Trace-Id` header
  (fresh UUID per request; callers may supply their own value).
- **Timeout** — configurable per client.
- **Retry** — exactly ONE retry on HTTP 5xx (Python also retries
  connect-level failures once); 4xx never retried.
- **Envelope** — the §46 `ListResponse` envelope
  (`{"data": [...], "meta": {...}}`) is unwrapped by collection list
  methods, returning the item array.

## §46 groups covered

`events`, `entities`, `relationships`, `evidence`, `claims`, `search`,
`goals`, `tasks`, `agents`, `runs`, `incidents`, `models`, `compute`,
`routes`, `changes`, `approvals`, `clients`, `context` — each with
`GET /api/<group>` (list) and `GET /api/<group>/<id>` (get), plus the
§47 mutation paths (`POST /api/context/ask`,
`POST /api/incidents/investigate`, `POST /api/agents/pause`,
`POST /api/changes/stop-mutations`).

> **Contract gaps:** the current backend exposes no POST routes for the
> §47 mutation commands (405 today). See
> [`cli/CONTRACT_GAP_NOTES.md`](../cli/CONTRACT_GAP_NOTES.md).

## Running the local smoke target

```bash
NERVE_MOCK_INFER=1 .venv/bin/python -m uvicorn backend.api.app:app --port 8310 &
```

## Verifying

```bash
# Python SDK tests (offline, httpx.MockTransport — no live server)
.venv/bin/python -m pytest sdk/python/tests/ -q

# TypeScript SDK
cd sdk/typescript && tsc --noEmit -p tsconfig.json   # type-check
node dist/smoke.js http://127.0.0.1:8310             # live smoke (exit 0/1)
```
