# NerveCenter TypeScript SDK

Plain-`fetch` client for the NerveCenter §46 HTTP API.

**Zero npm dependencies** — Node.js built-ins only (`node:crypto` for
UUIDs, global `fetch`). No `package.json`, no `node_modules`, no
build-time network access.

```
sdk/typescript/
├── tsconfig.json        # strict, ES2022, CJS output to dist/
├── src/
│   ├── client.ts        # NerveClient + error types + §46 group methods
│   ├── smoke.ts         # runnable smoke script (no test framework)
│   └── globals.d.ts     # minimal ambient decls (process, node:crypto)
└── dist/                # compiled output (shipped, so no tsc at runtime)
    ├── client.js
    └── smoke.js
```

## Building

```bash
cd sdk/typescript
tsc --noEmit -p tsconfig.json   # type-check (must be clean)
tsc -p tsconfig.json           # emits dist/*.js
```

The compiled `dist/` is committed, so `node dist/smoke.js` works without
TypeScript installed.

## Quick start

```ts
import { NerveClient, ContractError, UnreachableError } from "./client.js";

const client = new NerveClient({ baseUrl: "http://localhost:8310", timeoutMs: 10_000 });

const health = await client.health();        // GET /api/health
const goals = await client.goals();          // GET /api/goals -> unwrapped array
const goal = await client.goal("goal-1");    // GET /api/goals/goal-1
```

## Per-group §46 methods

`events() · entities() · relationships() · evidence() · claims() ·
search() · goals() · tasks() · agents() · runs() · incidents() ·
models() · compute() · routes() · changes() · approvals() ·
clients()` — each returns the unwrapped item array — and single-get
methods `entity(id) · goal(id) · task(id) · agent(id) · incident(id)`.
Plus `health()` / `version()`.

§47 mutation paths (contract targets; backend returns 405 until
implemented — see `cli/CONTRACT_GAP_NOTES.md`):

```ts
await client.ask("why did hellodj restart?");   // POST /api/context/ask
await client.investigate("hellodj");           // POST /api/incidents/investigate
await client.pauseAgents();                    // POST /api/agents/pause
await client.stopMutations();                  // POST /api/changes/stop-mutations
```

## §29 correlation

Every request sends a `Nerve-Trace-Id` header (fresh UUID via
`node:crypto.randomUUID`):

```ts
new NerveClient({ traceHeader: "my-fixed-trace-id" }); // fixed per client
await client.goals({ traceId: "per-request-id" });     // per request
```

## Retry semantics

Exactly **one** retry on HTTP 5xx and on network/timeout failures;
4xx raises `ContractError` immediately. Errors:

- `UnreachableError` — no transport-level response after the retry
- `ContractError` — HTTP ≥ 400 (carries `.status` + parsed `.detail`)
- `ApiError` — base class

## Smoke script

```bash
# against a live server (NERVE_MOCK_INFER=1 uvicorn on :8310)
NERVE_API=http://127.0.0.1:8310 node dist/smoke.js        # -> exit 0
node dist/smoke.js http://127.0.0.1:8310                  # same, via argv

# no server up:
node dist/smoke.js http://127.0.0.1:9
# -> "error: cannot reach NerveCenter API at http://127.0.0.1:9 (...)" + exit 1
#    (graceful; no stack-trace crash)
```

The smoke script calls `GET /api/health` and `GET /api/goals`, prints
both bodies as JSON, and exits `0` on success / `1` on failure. Base URL
resolution order: argv[2] → `NERVE_API` → `http://localhost:8000`.
