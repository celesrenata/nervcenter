"use strict";
/**
 * NerveCenter TypeScript SDK (spec §29 correlation, §46 API surface).
 *
 * Plain-fetch client using ONLY Node.js built-ins (no npm packages):
 * - configurable base URL (default `http://localhost:8000`, overridable via
 *   the `NERVE_API` environment variable or constructor argument)
 * - per-group §46 methods
 * - configurable timeout + exactly one retry on HTTP 5xx
 * - §29 correlation: a `Nerve-Trace-Id` header (fresh UUID) on every
 *   request unless the caller supplies `traceId`
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.NerveClient = exports.UnreachableError = exports.ContractError = exports.ApiError = exports.TRACE_HEADER = exports.DEFAULT_BASE_URL = void 0;
exports.unwrapList = unwrapList;
const node_crypto_1 = require("node:crypto");
exports.DEFAULT_BASE_URL = "http://localhost:8000";
exports.TRACE_HEADER = "Nerve-Trace-Id";
/** Base error for NerveCenter API calls. */
class ApiError extends Error {
    status;
    detail;
    constructor(message, status = null, detail = null) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.detail = detail;
    }
}
exports.ApiError = ApiError;
/** The API answered with HTTP >= 400 (or a non-JSON success body). */
class ContractError extends ApiError {
    constructor(message, status = null, detail = null) {
        super(message, status, detail);
        this.name = "ContractError";
    }
}
exports.ContractError = ContractError;
/** Network-level failure (refused, DNS, timeout) after the single retry. */
class UnreachableError extends ApiError {
    constructor(message, detail = null) {
        super(message, null, detail);
        this.name = "UnreachableError";
    }
}
exports.UnreachableError = UnreachableError;
function parseBody(text) {
    if (!text)
        return null;
    try {
        return JSON.parse(text);
    }
    catch {
        return text;
    }
}
function isListEnvelope(value) {
    if (typeof value !== "object" || value === null)
        return false;
    const obj = value;
    return Array.isArray(obj["data"]) && typeof obj["meta"] === "object" && obj["meta"] !== null;
}
/** Unwrap the §46 ListResponse envelope into the item array.
 * Non-envelope payloads pass through as-is (lists) or as a 1-element array. */
function unwrapList(payload) {
    if (isListEnvelope(payload))
        return payload.data;
    if (Array.isArray(payload))
        return payload;
    return [payload];
}
/**
 * Async fetch client for the §46 NerveCenter HTTP API.
 */
class NerveClient {
    baseUrl;
    timeoutMs;
    fixedTraceId;
    constructor(options = {}) {
        const fromEnv = process.env["NERVE_API"];
        this.baseUrl = (options.baseUrl ?? fromEnv ?? exports.DEFAULT_BASE_URL).replace(/\/+$/, "");
        this.timeoutMs = options.timeoutMs ?? 10_000;
        this.fixedTraceId = options.traceHeader;
    }
    /** The resolved API base URL. */
    get apiBase() {
        return this.baseUrl;
    }
    /**
     * Perform one HTTP request (exactly one retry on 5xx / network errors)
     * and decode the JSON body.
     */
    async request(method, path, opts = {}) {
        const url = new URL(path, this.baseUrl);
        if (opts.params) {
            for (const [key, value] of Object.entries(opts.params)) {
                if (value !== undefined) {
                    url.searchParams.set(key, String(value));
                }
            }
        }
        const headers = {
            [exports.TRACE_HEADER]: this.traceId(opts.traceId),
            Accept: "application/json",
        };
        let payload;
        if (opts.body !== undefined) {
            headers["Content-Type"] = "application/json";
            payload = JSON.stringify(opts.body);
        }
        let lastError = null;
        for (let attempt = 0; attempt < 2; attempt++) {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), this.timeoutMs);
            let response;
            try {
                response = await fetch(url, {
                    method,
                    headers,
                    body: payload,
                    signal: controller.signal,
                });
            }
            catch (err) {
                clearTimeout(timer);
                const reason = err instanceof Error ? err.name : String(err);
                if (attempt === 0) {
                    lastError = new UnreachableError(`cannot reach NerveCenter API at ${this.baseUrl} (${reason})`, err);
                    continue; // exactly one retry
                }
                throw lastError;
            }
            clearTimeout(timer);
            if (response.status >= 500 && attempt === 0) {
                continue; // exactly one retry on 5xx
            }
            if (response.status >= 400) {
                const detail = parseBody(await response.text());
                throw new ContractError(`${method} ${path} returned HTTP ${response.status}`, response.status, detail);
            }
            const text = await response.text();
            if (!text)
                return null;
            const value = parseBody(text);
            if (typeof value === "string") {
                throw new ContractError(`${method} ${path} returned a non-JSON body`, response.status, value);
            }
            return value;
        }
        // Unreachable after the single retry.
        throw lastError ?? new UnreachableError(`cannot reach NerveCenter API at ${this.baseUrl}`);
    }
    traceId(explicit) {
        if (explicit)
            return explicit;
        if (this.fixedTraceId)
            return this.fixedTraceId;
        return (0, node_crypto_1.randomUUID)();
    }
    async get(path, opts = {}) {
        return this.request("GET", path, opts);
    }
    async post(path, opts = {}) {
        return this.request("POST", path, opts);
    }
    /** GET /api/health */
    health(opts = {}) {
        return this.get("/api/health", opts);
    }
    /** GET /version */
    version(opts = {}) {
        return this.get("/version", opts);
    }
    // -- §46 collection groups ------------------------------------------------
    /** GET /api/events */
    events(opts = {}) {
        return this.get("/api/events", opts).then(unwrapList);
    }
    /** GET /api/entities */
    entities(opts = {}) {
        return this.get("/api/entities", opts).then(unwrapList);
    }
    /** GET /api/entities/<id> */
    entity(id, opts = {}) {
        return this.get(`/api/entities/${encodeURIComponent(id)}`, opts);
    }
    /** GET /api/relationships */
    relationships(opts = {}) {
        return this.get("/api/relationships", opts).then(unwrapList);
    }
    /** GET /api/evidence */
    evidence(opts = {}) {
        return this.get("/api/evidence", opts).then(unwrapList);
    }
    /** GET /api/claims */
    claims(opts = {}) {
        return this.get("/api/claims", opts).then(unwrapList);
    }
    /** GET /api/search */
    search(opts = {}) {
        return this.get("/api/search", opts).then(unwrapList);
    }
    /** GET /api/goals */
    goals(opts = {}) {
        return this.get("/api/goals", opts).then(unwrapList);
    }
    /** GET /api/goals/<id> */
    goal(id, opts = {}) {
        return this.get(`/api/goals/${encodeURIComponent(id)}`, opts);
    }
    /** GET /api/tasks */
    tasks(opts = {}) {
        return this.get("/api/tasks", opts).then(unwrapList);
    }
    /** GET /api/tasks/<id> */
    task(id, opts = {}) {
        return this.get(`/api/tasks/${encodeURIComponent(id)}`, opts);
    }
    /** GET /api/agents */
    agents(opts = {}) {
        return this.get("/api/agents", opts).then(unwrapList);
    }
    /** GET /api/agents/<id> */
    agent(id, opts = {}) {
        return this.get(`/api/agents/${encodeURIComponent(id)}`, opts);
    }
    /** GET /api/runs */
    runs(opts = {}) {
        return this.get("/api/runs", opts).then(unwrapList);
    }
    /** GET /api/incidents */
    incidents(opts = {}) {
        return this.get("/api/incidents", opts).then(unwrapList);
    }
    /** GET /api/incidents/<id> */
    incident(id, opts = {}) {
        return this.get(`/api/incidents/${encodeURIComponent(id)}`, opts);
    }
    /** GET /api/models */
    models(opts = {}) {
        return this.get("/api/models", opts).then(unwrapList);
    }
    /** GET /api/compute */
    compute(opts = {}) {
        return this.get("/api/compute", opts).then(unwrapList);
    }
    /** GET /api/routes */
    routes(opts = {}) {
        return this.get("/api/routes", opts).then(unwrapList);
    }
    /** GET /api/changes */
    changes(opts = {}) {
        return this.get("/api/changes", opts).then(unwrapList);
    }
    /** GET /api/approvals */
    approvals(opts = {}) {
        return this.get("/api/approvals", opts).then(unwrapList);
    }
    /** GET /api/clients */
    clients(opts = {}) {
        return this.get("/api/clients", opts).then(unwrapList);
    }
    // -- §47 mutation paths (contract targets; see cli/CONTRACT_GAP_NOTES.md) --
    /** POST /api/context/ask */
    ask(question, opts = {}) {
        return this.post("/api/context/ask", { body: { question }, ...opts });
    }
    /** POST /api/incidents/investigate */
    investigate(entity, opts = {}) {
        return this.post("/api/incidents/investigate", { body: { entity }, ...opts });
    }
    /** POST /api/agents/pause */
    pauseAgents(opts = {}) {
        return this.post("/api/agents/pause", { body: {}, ...opts });
    }
    /** POST /api/changes/stop-mutations */
    stopMutations(opts = {}) {
        return this.post("/api/changes/stop-mutations", { body: {}, ...opts });
    }
}
exports.NerveClient = NerveClient;
exports.default = NerveClient;
