"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
/**
 * NerveCenter TypeScript SDK smoke script (no test framework).
 *
 * Usage:
 *   node dist/smoke.js [baseUrl]
 *   NERVE_API=http://host:port node dist/smoke.js
 *
 * Calls GET /api/health and GET /api/goals, prints the results, and exits
 * 0 on success / 1 on failure. Graceful: a missing server produces a clear
 * message and exit code 1 — no stack-trace crash.
 */
const client_js_1 = require("./client.js");
function printJson(label, value) {
    console.log(`--- ${label} ---`);
    console.log(JSON.stringify(value, null, 2));
}
async function main() {
    const argUrl = process.argv[2];
    const baseUrl = argUrl ?? process.env["NERVE_API"] ?? undefined;
    const client = new client_js_1.NerveClient({ baseUrl, timeoutMs: 5000 });
    console.log(`NerveCenter SDK smoke — base URL: ${client.apiBase}`);
    // 1. Health check
    const health = await client.health();
    printJson("GET /api/health", health);
    // 2. One group list
    const goalsRaw = await client.goals();
    const goals = (0, client_js_1.unwrapList)(goalsRaw);
    printJson("GET /api/goals", goalsRaw);
    const count = Array.isArray(goals) ? goals.length : 0;
    console.log(`OK: health + ${count} goal(s) retrieved`);
    return 0;
}
main()
    .then((code) => {
    process.exit(code);
})
    .catch((err) => {
    if (err instanceof client_js_1.UnreachableError) {
        console.error(`error: ${err.message}`);
        console.error("hint: start the API (NERVE_MOCK_INFER=1 .venv/bin/python -m uvicorn backend.api.app:app --port 8310) or set NERVE_API");
    }
    else if (err instanceof client_js_1.ContractError) {
        console.error(`error: ${err.message}`);
    }
    else if (err instanceof client_js_1.ApiError) {
        console.error(`error: ${err.message}`);
    }
    else {
        console.error(`error: unexpected failure: ${err instanceof Error ? err.message : String(err)}`);
    }
    process.exit(1);
});
