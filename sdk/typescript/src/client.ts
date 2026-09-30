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

import { randomUUID } from "node:crypto";

export const DEFAULT_BASE_URL = "http://localhost:8000";
export const TRACE_HEADER = "Nerve-Trace-Id";

export type Params = Record<string, string | number | boolean | undefined>;

/** The §46 ListResponse envelope: `{ data: T[], meta: {...} }`. */
export interface ListEnvelope<T> {
  data: T[];
  meta: {
    version: string;
    request_id: string;
    timestamp: string;
    pagination?: Record<string, number>;
  };
}

/** Base error for NerveCenter API calls. */
export class ApiError extends Error {
  status: number | null;
  detail: unknown;
  constructor(message: string, status: number | null = null, detail: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** The API answered with HTTP >= 400 (or a non-JSON success body). */
export class ContractError extends ApiError {
  constructor(message: string, status: number | null = null, detail: unknown = null) {
    super(message, status, detail);
    this.name = "ContractError";
  }
}

/** Network-level failure (refused, DNS, timeout) after the single retry. */
export class UnreachableError extends ApiError {
  constructor(message: string, detail: unknown = null) {
    super(message, null, detail);
    this.name = "UnreachableError";
  }
}

export interface NerveClientOptions {
  /** API base URL. Defaults to `NERVE_API` env or `http://localhost:8000`. */
  baseUrl?: string;
  /** Per-request timeout in milliseconds (default 10000). */
  timeoutMs?: number;
  /** Fixed trace id sent on every request (else a UUID per request). */
  traceHeader?: string;
}

function parseBody(text: string): unknown {
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function isListEnvelope(value: unknown): value is ListEnvelope<unknown> {
  if (typeof value !== "object" || value === null) return false;
  const obj = value as Record<string, unknown>;
  return Array.isArray(obj["data"]) && typeof obj["meta"] === "object" && obj["meta"] !== null;
}

/** Unwrap the §46 ListResponse envelope into the item array.
 * Non-envelope payloads pass through as-is (lists) or as a 1-element array. */
export function unwrapList(payload: unknown): unknown[] {
  if (isListEnvelope(payload)) return (payload as ListEnvelope<unknown>).data;
  if (Array.isArray(payload)) return payload as unknown[];
  return [payload];
}

/**
 * Async fetch client for the §46 NerveCenter HTTP API.
 */
export class NerveClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly fixedTraceId: string | undefined;

  constructor(options: NerveClientOptions = {}) {
    const fromEnv = process.env["NERVE_API"];
    this.baseUrl = (options.baseUrl ?? fromEnv ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs ?? 10_000;
    this.fixedTraceId = options.traceHeader;
  }

  /** The resolved API base URL. */
  get apiBase(): string {
    return this.baseUrl;
  }

  /**
   * Perform one HTTP request (exactly one retry on 5xx / network errors)
   * and decode the JSON body.
   */
  async request(
    method: "GET" | "POST" | "PATCH",
    path: string,
    opts: {
      params?: Params;
      body?: Record<string, unknown>;
      traceId?: string;
    } = {}
  ): Promise<unknown> {
    const url = new URL(path, this.baseUrl);
    if (opts.params) {
      for (const [key, value] of Object.entries(opts.params)) {
        if (value !== undefined) {
          url.searchParams.set(key, String(value));
        }
      }
    }
    const headers: Record<string, string> = {
      [TRACE_HEADER]: this.traceId(opts.traceId),
      Accept: "application/json",
    };
    let payload: string | undefined;
    if (opts.body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(opts.body);
    }

    let lastError: ApiError | null = null;
    for (let attempt = 0; attempt < 2; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);
      let response: Response;
      try {
        response = await fetch(url, {
          method,
          headers,
          body: payload,
          signal: controller.signal,
        });
      } catch (err) {
        clearTimeout(timer);
        const reason = err instanceof Error ? err.name : String(err);
        if (attempt === 0) {
          lastError = new UnreachableError(
            `cannot reach NerveCenter API at ${this.baseUrl} (${reason})`,
            err
          );
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
        throw new ContractError(
          `${method} ${path} returned HTTP ${response.status}`,
          response.status,
          detail
        );
      }
      const text = await response.text();
      if (!text) return null;
      const value = parseBody(text);
      if (typeof value === "string") {
        throw new ContractError(`${method} ${path} returned a non-JSON body`, response.status, value);
      }
      return value;
    }
    // Unreachable after the single retry.
    throw lastError ?? new UnreachableError(`cannot reach NerveCenter API at ${this.baseUrl}`);
  }

  private traceId(explicit?: string): string {
    if (explicit) return explicit;
    if (this.fixedTraceId) return this.fixedTraceId;
    return randomUUID();
  }

  async get(path: string, opts: { params?: Params; traceId?: string } = {}): Promise<unknown> {
    return this.request("GET", path, opts);
  }

  async post(
    path: string,
    opts: { body?: Record<string, unknown>; traceId?: string } = {}
  ): Promise<unknown> {
    return this.request("POST", path, opts);
  }

  /** GET /api/health */
  health(opts: { traceId?: string } = {}): Promise<unknown> {
    return this.get("/api/health", opts);
  }

  /** GET /version */
  version(opts: { traceId?: string } = {}): Promise<unknown> {
    return this.get("/version", opts);
  }

  // -- §46 collection groups ------------------------------------------------

  /** GET /api/events */
  events(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/events", opts).then(unwrapList);
  }

  /** GET /api/entities */
  entities(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/entities", opts).then(unwrapList);
  }

  /** GET /api/entities/<id> */
  entity(id: string, opts: { traceId?: string } = {}): Promise<unknown> {
    return this.get(`/api/entities/${encodeURIComponent(id)}`, opts);
  }

  /** GET /api/relationships */
  relationships(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/relationships", opts).then(unwrapList);
  }

  /** GET /api/evidence */
  evidence(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/evidence", opts).then(unwrapList);
  }

  /** GET /api/claims */
  claims(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/claims", opts).then(unwrapList);
  }

  /** GET /api/search */
  search(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/search", opts).then(unwrapList);
  }

  /** GET /api/goals */
  goals(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/goals", opts).then(unwrapList);
  }

  /** GET /api/goals/<id> */
  goal(id: string, opts: { traceId?: string } = {}): Promise<unknown> {
    return this.get(`/api/goals/${encodeURIComponent(id)}`, opts);
  }

  /** GET /api/tasks */
  tasks(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/tasks", opts).then(unwrapList);
  }

  /** GET /api/tasks/<id> */
  task(id: string, opts: { traceId?: string } = {}): Promise<unknown> {
    return this.get(`/api/tasks/${encodeURIComponent(id)}`, opts);
  }

  /** GET /api/agents */
  agents(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/agents", opts).then(unwrapList);
  }

  /** GET /api/agents/<id> */
  agent(id: string, opts: { traceId?: string } = {}): Promise<unknown> {
    return this.get(`/api/agents/${encodeURIComponent(id)}`, opts);
  }

  /** GET /api/runs */
  runs(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/runs", opts).then(unwrapList);
  }

  /** GET /api/incidents */
  incidents(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/incidents", opts).then(unwrapList);
  }

  /** GET /api/incidents/<id> */
  incident(id: string, opts: { traceId?: string } = {}): Promise<unknown> {
    return this.get(`/api/incidents/${encodeURIComponent(id)}`, opts);
  }

  /** GET /api/models */
  models(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/models", opts).then(unwrapList);
  }

  /** GET /api/compute */
  compute(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/compute", opts).then(unwrapList);
  }

  /** GET /api/routes */
  routes(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/routes", opts).then(unwrapList);
  }

  /** GET /api/changes */
  changes(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/changes", opts).then(unwrapList);
  }

  /** GET /api/approvals */
  approvals(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/approvals", opts).then(unwrapList);
  }

  /** GET /api/clients */
  clients(opts: { params?: Params; traceId?: string } = {}): Promise<unknown[]> {
    return this.get("/api/clients", opts).then(unwrapList);
  }

  // -- §47 mutation paths (contract targets; see cli/CONTRACT_GAP_NOTES.md) --

  /** POST /api/context/ask */
  ask(question: string, opts: { traceId?: string } = {}): Promise<unknown> {
    return this.post("/api/context/ask", { body: { question }, ...opts });
  }

  /** POST /api/incidents/investigate */
  investigate(entity: string, opts: { traceId?: string } = {}): Promise<unknown> {
    return this.post("/api/incidents/investigate", { body: { entity }, ...opts });
  }

  /** POST /api/agents/pause */
  pauseAgents(opts: { traceId?: string } = {}): Promise<unknown> {
    return this.post("/api/agents/pause", { body: {}, ...opts });
  }

  /** POST /api/changes/stop-mutations */
  stopMutations(opts: { traceId?: string } = {}): Promise<unknown> {
    return this.post("/api/changes/stop-mutations", { body: {}, ...opts });
  }
}

export default NerveClient;
