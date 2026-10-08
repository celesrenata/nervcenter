/**
 * API client with env-based mock mode.
 * If VITE_API_BASE is set → real API; otherwise → mock fixtures.
 */

import { mockOverview, mockTasks, mockAgents, mockComputeNodes, mockRoutes, mockModelHistory, mockIncidents, mockDecisions, mockEvents, mockSystems, mockAskResponse, mockGoals, mockModels } from './mockClient'

// Determine mode based on environment variable
const API_BASE = import.meta.env?.VITE_API_BASE

export const useMockMode = API_BASE === undefined || API_BASE === ''

export interface ApiResponse<T> {
  data: T
  status: number
}

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

// ─── Error type (gates OV-1 / TA-1 / DC-1) ───────────────────────────────────
//
// Every real-API call that receives a non-2xx response rejects with this
// error. `status` is the HTTP status; `detail` is the parsed FastAPI
// `detail` body (or the status text when the body carries none). The old
// behavior — mapping error responses to empty arrays — silently rendered
// 500/501 endpoints as "no data"; views now see a real error they can
// surface.
export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string, message?: string) {
    super(message ?? `API request failed: ${status} ${detail}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

// ─── Auth transport (S102: SSO + authorized fetches) ──────────────────────────

/**
 * Session-scoped token storage. Tokens live in sessionStorage (NOT localStorage)
 * so a closed tab ends the session — the security model the SSO spec calls for.
 */
const ACCESS_TOKEN_KEY = 'nc.accessToken'
const REFRESH_TOKEN_KEY = 'nc.refreshToken'
/** Code-verifier + state for the in-flight PKCE authorization-code exchange. */
const PKCE_VERIFIER_KEY = 'nc.pkce.codeVerifier'
const PKCE_STATE_KEY = 'nc.pkce.state'

function safeGetSession(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function safeSetSession(key: string, value: string): void {
  try {
    window.sessionStorage.setItem(key, value)
  } catch {
    /* sessionStorage unavailable (private mode) — ignore, session is ephemeral anyway */
  }
}

function safeRemoveSession(key: string): void {
  try {
    window.sessionStorage.removeItem(key)
  } catch {
    /* ignore */
  }
}

export function getAccessToken(): string | null {
  return safeGetSession(ACCESS_TOKEN_KEY)
}

/** Store a fresh access token (from break-glass login or the SSO token exchange). */
export function setAccessToken(token: string | null, refreshToken?: string | null): void {
  if (token) safeSetSession(ACCESS_TOKEN_KEY, token)
  else safeRemoveSession(ACCESS_TOKEN_KEY)
  if (refreshToken) safeSetSession(REFRESH_TOKEN_KEY, refreshToken)
  else safeRemoveSession(REFRESH_TOKEN_KEY)
}

/** Clear the whole session (logout or an un-recoverable 401). */
export function clearSessionTokens(): void {
  safeRemoveSession(ACCESS_TOKEN_KEY)
  safeRemoveSession(REFRESH_TOKEN_KEY)
  safeRemoveSession(PKCE_VERIFIER_KEY)
  safeRemoveSession(PKCE_STATE_KEY)
}

/** The in-flight refresh token, if any (kept for the session; unused while
 * the backend exposes no refresh route — see apiFetch 401 handling). */
export function getRefreshToken(): string | null {
  return safeGetSession(REFRESH_TOKEN_KEY)
}

/**
 * The 401 handler is registered by AuthProvider so the API layer can force a
 * redirect to /login without importing React (avoids a module cycle).
 */
export type UnauthorizedHandler = () => void
let unauthorizedHandler: UnauthorizedHandler | null = null
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler
}

/**
 * The single fetch wrapper every real-API request goes through. Adds
 * `Authorization: Bearer <token>` (S102: the token comes from
 * sessionStorage `nc.accessToken`) when a session token is present.
 *
 * S102 401 handling: the backend exposes **no** token-refresh route
 * (backend/api/auth.py: login, me, logout, pairing only), so a 401 on an
 * authorized call is terminal — the sessionStorage session is cleared and
 * the caller surfaces ApiError(status=401) (realApi raises it via
 * responseOrThrow / listFromResponse). The break-glass login itself is
 * excluded: its 401 is a credential error the form should surface, not a
 * session invalidation.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const base = API_BASE ?? ''
  const url = path.startsWith('http') ? path : `${base}${path}`
  const headers = new Headers(init.headers)
  const token = getAccessToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const res = await fetch(url, { ...init, headers })
  if (res.status === 401) {
    if (!path.startsWith('/auth/login')) {
      clearSessionTokens()
      if (unauthorizedHandler) unauthorizedHandler()
    }
  }
  return res
}

// ─── Real API implementation ──────────────────────────────────────────────────

/**
 * Parse a FastAPI error body ({detail: ...}) and build the ApiError.
 * Exported so callers outside the client (AuthContext login, the
 * /auth/callback exchange, tests) can surface non-2xx responses with the
 * same status+detail shape the real-API layer uses.
 */
export async function apiErrorFromResponse(res: Response): Promise<ApiError> {
  let detail = res.statusText || `HTTP ${res.status}`
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body.detail === 'string' && body.detail.length > 0) {
      detail = body.detail
    } else if (body.detail !== undefined) {
      detail = JSON.stringify(body.detail)
    }
  } catch {
    /* non-JSON body — keep the status text */
  }
  return new ApiError(res.status, detail)
}

/** Non-2xx → reject with ApiError; 2xx → return the parsed JSON body. */
async function responseOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) throw await apiErrorFromResponse(res)
  return (await res.json()) as T
}

/**
 * Extract the item list from a real API list response.
 *
 * The backend list endpoints (§46) wrap collections in a
 * `{ data: [...], meta: {...} }` envelope, while the views (and the mock
 * fixtures) consume plain arrays. Non-list bodies — a single-item object
 * (e.g. `/models/history` when the backend resolves it as one resource) or an
 * unparsable body — degrade to an empty list so that a view renders its
 * empty state instead of crashing on `.map()`.
 *
 * Error responses (non-2xx) NO LONGER degrade to `[]`: they reject with
 * `ApiError` (gates OV-1/TA-1/DC-1). Previously a `/api/tasks` 500 or an
 * `/api/overview` 501 rendered as silent zeros; now the views' `catch`
 * blocks see the real failure.
 */
// Returns `any[]` (not `unknown[]`) so the views keep assigning
// `response.data` to their typed state exactly as the mock fixtures do.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const listFromResponse = async (res: Response): Promise<any[]> => {
  if (!res.ok) throw await apiErrorFromResponse(res)
  let body: any
  try {
    body = await res.json()
  } catch {
    return []
  }
  if (Array.isArray(body)) return body
  if (
    body !== null &&
    typeof body === 'object' &&
    Array.isArray((body as { data?: unknown }).data)
  ) {
    return (body as { data: unknown[] }).data
  }
  return []
}

// ─── SSO PKCE helpers (S102: /auth/callback) ──────────────────────────────────

/** AC-S01 shape of GET /api/auth/sso/config. */
export interface SsoConfig {
  enabled: boolean
  issuer: string
  client_id: string
  authorization_endpoint: string
  token_endpoint: string
  userinfo_endpoint?: string | null
  jwks_uri?: string | null
  end_session_endpoint?: string | null
}

/** Fetch the SSO/OIDC discovery config from the backend (or null on error). */
export async function getSsoConfig(): Promise<SsoConfig | null> {
  const res = await apiFetch('/auth/sso/config')
  if (!res.ok) return null
  return (await res.json()) as SsoConfig
}

function base64Url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

/** Generate a cryptographically random code verifier (RFC 7636 §4.1). */
export function generatePkceVerifier(): string {
  return base64Url(crypto.getRandomValues(new Uint8Array(32)))
}

/** Store the in-flight PKCE code verifier + state in sessionStorage. */
export function storePkceChallenge(verifier: string, state: string): void {
  safeSetSession(PKCE_VERIFIER_KEY, verifier)
  safeSetSession(PKCE_STATE_KEY, state)
}

/** The state value stored at authorization start (null if none). */
export function getPkceState(): string | null {
  return safeGetSession(PKCE_STATE_KEY)
}

function consumePkceVerifier(): string | null {
  const verifier = safeGetSession(PKCE_VERIFIER_KEY)
  if (verifier) safeRemoveSession(PKCE_VERIFIER_KEY)
  return verifier
}

/**
 * Build the SSO provider's authorization URL (PKCE S256 authorization-code
 * flow, AC-S06). Stores the code verifier + state in sessionStorage so
 * `exchangeAuthCode` can validate the round-trip on the callback.
 * Returns null when SSO is not enabled (provider not yet provisioned).
 */
export async function getAuthorizationUrl(): Promise<string | null> {
  const cfg = await getSsoConfig()
  if (!cfg?.enabled || !cfg.authorization_endpoint) return null
  const verifier = generatePkceVerifier()
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(verifier),
  )
  const challenge = base64Url(new Uint8Array(digest))
  const state = base64Url(crypto.getRandomValues(new Uint8Array(16)))
  storePkceChallenge(verifier, state)
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: cfg.client_id,
    redirect_uri: window.location.origin + '/auth/callback',
    scope: 'openid profile',
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state,
  })
  return `${cfg.authorization_endpoint}?${params.toString()}`
}

/**
 * Exchange the PKCE authorization code for tokens at the SSO provider's
 * token endpoint (the "backend token route" per AC-S01) and store the
 * session tokens (nc.accessToken / nc.refreshToken).
 *
 * Steps: validate the round-tripped `state` against the stored
 * `nc.pkce.state`, consume the code verifier, POST the code exchange,
 * store the returned access + refresh tokens in sessionStorage.
 * Rejects with ApiError on a state mismatch, a missing verifier, a
 * failed token exchange, or a response without an access token.
 */
export async function exchangeAuthCode(
  code: string,
  state: string | null,
): Promise<{ accessToken: string; refreshToken: string | null }> {
  const expectedState = getPkceState()
  if (!expectedState || expectedState !== state) {
    clearSessionTokens()
    throw new ApiError(400, 'PKCE state mismatch (possible CSRF)')
  }
  const verifier = consumePkceVerifier()
  if (!verifier) {
    clearSessionTokens()
    throw new ApiError(400, 'missing PKCE code verifier')
  }
  const cfg = await getSsoConfig()
  if (!cfg?.token_endpoint) {
    clearSessionTokens()
    throw new ApiError(500, 'no SSO token_endpoint configured')
  }
  const params = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    code_verifier: verifier,
    redirect_uri: window.location.origin + '/auth/callback',
    client_id: cfg.client_id,
  })
  const res = await fetch(cfg.token_endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params.toString(),
  })
  if (!res.ok) throw await apiErrorFromResponse(res)
  const body = (await res.json()) as {
    access_token?: string
    refresh_token?: string | null
  }
  if (!body.access_token) {
    clearSessionTokens()
    throw new ApiError(res.status, 'SSO token exchange returned no access_token')
  }
  setAccessToken(body.access_token, body.refresh_token ?? null)
  return { accessToken: body.access_token, refreshToken: body.refresh_token ?? null }
}

const realApi = {
  // Health & Overview
  getOverview: async () => {
    const res = await apiFetch('/overview')
    return { data: await responseOrThrow(res), status: res.status }
  },
  getHealth: async () => {
    const res = await apiFetch('/health')
    return { data: await responseOrThrow(res), status: res.status }
  },

  // Tasks (Task DAG with 8 states)
  getTasks: async () => {
    const res = await apiFetch('/tasks')
    return { data: await listFromResponse(res), status: res.status }
  },
  getTask: async (taskId: string) => {
    const res = await apiFetch(`/tasks/${taskId}`)
    return { data: await responseOrThrow(res), status: res.status }
  },

  // Agents
  getAgents: async () => {
    const res = await apiFetch('/agents')
    return { data: await listFromResponse(res), status: res.status }
  },
  getAgent: async (agentId: string) => {
    const res = await apiFetch(`/agents/${agentId}`)
    return { data: await responseOrThrow(res), status: res.status }
  },

  // Compute nodes (for Inference view)
  getComputeNodes: async () => {
    const res = await apiFetch('/compute')
    return { data: await listFromResponse(res), status: res.status }
  },
  getComputeNode: async (nodeId: string) => {
    const res = await apiFetch(`/compute/${nodeId}`)
    return { data: await responseOrThrow(res), status: res.status }
  },

  // OmniRoute routes (for Inference view)
  getRoutes: async () => {
    const res = await apiFetch('/routes')
    return { data: await listFromResponse(res), status: res.status }
  },
  getRoute: async (routeId: string) => {
    const res = await apiFetch(`/routes/${routeId}`)
    return { data: await responseOrThrow(res), status: res.status }
  },

  // Historical model performance (for Inference view)
  getModelHistory: async () => {
    const res = await apiFetch('/models/history')
    return { data: await listFromResponse(res), status: res.status }
  },

  // Incidents
  getIncidents: async () => {
    const res = await apiFetch('/incidents')
    return { data: await listFromResponse(res), status: res.status }
  },
  getIncident: async (incidentId: string) => {
    const res = await apiFetch(`/incidents/${incidentId}`)
    return { data: await responseOrThrow(res), status: res.status }
  },

  // Decisions
  getDecisions: async () => {
    const res = await apiFetch('/decisions')
    return { data: await listFromResponse(res), status: res.status }
  },
  getDecision: async (decisionId: string) => {
    const res = await apiFetch(`/decisions/${decisionId}`)
    return { data: await responseOrThrow(res), status: res.status }
  },

  // Events (Timeline)
  getEvents: async () => {
    const res = await apiFetch('/events')
    return { data: await listFromResponse(res), status: res.status }
  },
  getEvent: async (eventId: string) => {
    const res = await apiFetch(`/events/${eventId}`)
    return { data: await responseOrThrow(res), status: res.status }
  },

  // Systems health
  getSystems: async () => {
    const res = await apiFetch('/systems')
    return { data: await listFromResponse(res), status: res.status }
  },
  getMetrics: async () => {
    const res = await apiFetch('/metrics')
    return { data: await responseOrThrow(res), status: res.status }
  },

  // Ask endpoint — §47 `nerve ask` → POST /api/context/ask.
  // Returns the full answer (200) or the accepted-but-not-executed ack
  // (202, `{accepted, executed, detail, request_id, ...}`); AskView renders
  // whichever shape arrives.
  postAsk: async (message: string) => {
    const res = await apiFetch('/context/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: message, message }),
    })
    return { data: await responseOrThrow(res), status: res.status }
  },

  // Goals
  getGoals: async () => {
    const res = await apiFetch('/goals')
    return { data: await listFromResponse(res), status: res.status }
  },
  getGoal: async (goalId: string) => {
    const res = await apiFetch(`/goals/${goalId}`)
    return { data: await responseOrThrow(res), status: res.status }
  },

  // Models
  getModels: async () => {
    const res = await apiFetch('/models')
    return { data: await listFromResponse(res), status: res.status }
  },
  getModel: async (modelId: string) => {
    const res = await apiFetch(`/models/${modelId}`)
    return { data: await responseOrThrow(res), status: res.status }
  },

  // Auth (mock stub)
  login: async (username: string, password: string) => {
    const res = await apiFetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    return { data: await responseOrThrow(res), status: res.status }
  },
  logout: async () => {
    const res = await apiFetch('/auth/logout', { method: 'POST' })
    return { data: await responseOrThrow(res), status: res.status }
  },
  me: async () => {
    const res = await apiFetch('/auth/me')
    return { data: await responseOrThrow(res), status: res.status }
  },
}

// ─── Mock API implementation ──────────────────────────────────────────────────

const mockApi = {
  // Health & Overview
  getOverview: async () => {
    await delay(80)
    return { data: mockOverview, status: 200 }
  },
  getHealth: async () => {
    await delay(50)
    return { data: mockOverview.health, status: 200 }
  },

  // Tasks (Task DAG with 8 states)
  getTasks: async () => {
    await delay(100)
    return { data: mockTasks, status: 200 }
  },
  getTask: async (taskId: string) => {
    await delay(50)
    const task = mockTasks.find((t) => t.task_id === taskId)
    return { data: task, status: task ? 200 : 404 }
  },

  // Agents
  getAgents: async () => {
    await delay(100)
    return { data: mockAgents, status: 200 }
  },
  getAgent: async (agentId: string) => {
    await delay(50)
    const agent = mockAgents.find((a) => a.id === agentId)
    return { data: agent, status: agent ? 200 : 404 }
  },

  // Compute nodes (for Inference view)
  getComputeNodes: async () => {
    await delay(80)
    return { data: mockComputeNodes, status: 200 }
  },
  getComputeNode: async (nodeId: string) => {
    await delay(50)
    const node = mockComputeNodes.find((n) => n.id === nodeId)
    return { data: node, status: node ? 200 : 404 }
  },

  // OmniRoute routes (for Inference view)
  getRoutes: async () => {
    await delay(80)
    return { data: mockRoutes, status: 200 }
  },
  getRoute: async (routeId: string) => {
    await delay(50)
    const route = mockRoutes.find((r) => r.routeId === routeId)
    return { data: route, status: route ? 200 : 404 }
  },

  // Historical model performance (for Inference view)
  getModelHistory: async () => {
    await delay(80)
    return { data: mockModelHistory, status: 200 }
  },

  // Incidents
  getIncidents: async () => {
    await delay(100)
    return { data: mockIncidents, status: 200 }
  },
  getIncident: async (incidentId: string) => {
    await delay(50)
    const incident = mockIncidents.find((i) => i.id === incidentId)
    return { data: incident, status: incident ? 200 : 404 }
  },

  // Decisions
  getDecisions: async () => {
    await delay(80)
    return { data: mockDecisions, status: 200 }
  },
  getDecision: async (decisionId: string) => {
    await delay(50)
    const decision = mockDecisions.find((d) => d.id === decisionId)
    return { data: decision, status: decision ? 200 : 404 }
  },

  // Events (Timeline)
  getEvents: async () => {
    await delay(100)
    return { data: mockEvents, status: 200 }
  },
  getEvent: async (eventId: string) => {
    await delay(50)
    const event = mockEvents.find((e) => e.id === eventId)
    return { data: event, status: event ? 200 : 404 }
  },

  // Systems health
  getSystems: async () => {
    await delay(80)
    return { data: mockSystems, status: 200 }
  },
  getMetrics: async () => {
    await delay(50)
    return { data: { timestamp: new Date().toISOString() }, status: 200 }
  },

  // Ask endpoint
  postAsk: async (_message: string) => {
    await delay(600)
    return { data: mockAskResponse, status: 200 }
  },

  // Goals
  getGoals: async () => {
    await delay(80)
    return { data: mockGoals, status: 200 }
  },
  getGoal: async (goalId: string) => {
    await delay(50)
    const goal = mockGoals.find((g) => g.id === goalId)
    return { data: goal, status: goal ? 200 : 404 }
  },

  // Models
  getModels: async () => {
    await delay(80)
    return { data: mockModels, status: 200 }
  },
  getModel: async (modelId: string) => {
    await delay(50)
    const model = mockModels.find((m) => m.id === modelId)
    return { data: model, status: model ? 200 : 404 }
  },

  // Auth (mock stub)
  login: async (_username: string, _password: string) => {
    await delay(200)
    return {
      data: {
        access_token: 'mock-jwt-token',
        user: { username: 'admin', roles: ['admin'] },
      },
      status: 200,
    }
  },
  logout: async () => {
    await delay(50)
    return { data: { success: true }, status: 200 }
  },
  me: async () => {
    await delay(50)
    return { data: { username: 'admin', roles: ['admin'] }, status: 200 }
  },
}

// ─── Export unified API client ────────────────────────────────────────────────

const api = useMockMode ? mockApi : realApi

// ─── Export typed API clients ─────────────────────────────────────────────────

export const overviewApi = {
  get: () => api.getOverview(),
  getHealth: () => api.getHealth(),
}

export const tasksApi = {
  list: () => api.getTasks(),
  get: (taskId: string) => api.getTask(taskId),
}

export const agentsApi = {
  list: () => api.getAgents(),
  get: (agentId: string) => api.getAgent(agentId),
}

export const computeApi = {
  list: () => api.getComputeNodes(),
  get: (nodeId: string) => api.getComputeNode(nodeId),
}

export const routesApi = {
  list: () => api.getRoutes(),
  get: (routeId: string) => api.getRoute(routeId),
}

export const modelHistoryApi = {
  list: () => api.getModelHistory(),
}

export const incidentsApi = {
  list: () => api.getIncidents(),
  get: (incidentId: string) => api.getIncident(incidentId),
}

export const decisionsApi = {
  list: () => api.getDecisions(),
  get: (decisionId: string) => api.getDecision(decisionId),
}

export const eventsApi = {
  list: () => api.getEvents(),
  get: (eventId: string) => api.getEvent(eventId),
}

export const systemsApi = {
  health: () => api.getSystems(),
  metrics: () => api.getMetrics(),
}

export const askApi = {
  post: (message: string) => api.postAsk(message),
}

export const goalsApi = {
  list: () => api.getGoals(),
  get: (goalId: string) => api.getGoal(goalId),
}

export const modelsApi = {
  list: () => api.getModels(),
  get: (modelId: string) => api.getModel(modelId),
}

export const authApi = {
  login: (username: string, password: string) => api.login(username, password),
  logout: () => api.logout(),
  me: () => api.me(),
}

// Re-export for backward compatibility
export { api }
