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
 * `Authorization: Bearer <token>` when a session token is present, and routes
 * any 401 (except the break-glass login itself, where a 401 is a credential
 * error the form should surface, not a redirect) to the registered handler.
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
  if (res.status === 401 && !path.startsWith('/auth/login') && unauthorizedHandler) {
    unauthorizedHandler()
  }
  return res
}

// ─── Real API implementation ──────────────────────────────────────────────────

/**
 * Extract the item list from a real API list response.
 *
 * The backend list endpoints (§46) wrap collections in a
 * `{ data: [...], meta: {...} }` envelope, while the views (and the mock
 * fixtures) consume plain arrays. Non-list responses — a 404 body, a
 * single-item object (e.g. `/models/history` when the backend resolves it as
 * one resource), or an unparsable body — degrade to an empty list so that a
 * view renders its empty state instead of crashing on `.map()`.
 */
// Returns `any[]` (not `unknown[]`) so the views keep assigning
// `response.data` to their typed state exactly as the mock fixtures do.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const listFromResponse = async (res: Response): Promise<any[]> => {
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

const realApi = {
  // Health & Overview
  getOverview: async () => {
    const res = await fetch(`${API_BASE}/overview`)
    return { data: await res.json(), status: res.status }
  },
  getHealth: async () => {
    const res = await fetch(`${API_BASE}/health`)
    return { data: await res.json(), status: res.status }
  },

  // Tasks (Task DAG with 8 states)
  getTasks: async () => {
    const res = await fetch(`${API_BASE}/tasks`)
    return { data: await listFromResponse(res), status: res.status }
  },
  getTask: async (taskId: string) => {
    const res = await fetch(`${API_BASE}/tasks/${taskId}`)
    return { data: await res.json(), status: res.status }
  },

  // Agents
  getAgents: async () => {
    const res = await fetch(`${API_BASE}/agents`)
    return { data: await listFromResponse(res), status: res.status }
  },
  getAgent: async (agentId: string) => {
    const res = await fetch(`${API_BASE}/agents/${agentId}`)
    return { data: await res.json(), status: res.status }
  },

  // Compute nodes (for Inference view)
  getComputeNodes: async () => {
    const res = await fetch(`${API_BASE}/compute`)
    return { data: await listFromResponse(res), status: res.status }
  },
  getComputeNode: async (nodeId: string) => {
    const res = await fetch(`${API_BASE}/compute/${nodeId}`)
    return { data: await res.json(), status: res.status }
  },

  // OmniRoute routes (for Inference view)
  getRoutes: async () => {
    const res = await fetch(`${API_BASE}/routes`)
    return { data: await listFromResponse(res), status: res.status }
  },
  getRoute: async (routeId: string) => {
    const res = await fetch(`${API_BASE}/routes/${routeId}`)
    return { data: await res.json(), status: res.status }
  },

  // Historical model performance (for Inference view)
  getModelHistory: async () => {
    const res = await fetch(`${API_BASE}/models/history`)
    return { data: await listFromResponse(res), status: res.status }
  },

  // Incidents
  getIncidents: async () => {
    const res = await fetch(`${API_BASE}/incidents`)
    return { data: await listFromResponse(res), status: res.status }
  },
  getIncident: async (incidentId: string) => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}`)
    return { data: await res.json(), status: res.status }
  },

  // Decisions
  getDecisions: async () => {
    const res = await fetch(`${API_BASE}/decisions`)
    return { data: await listFromResponse(res), status: res.status }
  },
  getDecision: async (decisionId: string) => {
    const res = await fetch(`${API_BASE}/decisions/${decisionId}`)
    return { data: await res.json(), status: res.status }
  },

  // Events (Timeline)
  getEvents: async () => {
    const res = await fetch(`${API_BASE}/events`)
    return { data: await listFromResponse(res), status: res.status }
  },
  getEvent: async (eventId: string) => {
    const res = await fetch(`${API_BASE}/events/${eventId}`)
    return { data: await res.json(), status: res.status }
  },

  // Systems health
  getSystems: async () => {
    const res = await fetch(`${API_BASE}/systems`)
    return { data: await listFromResponse(res), status: res.status }
  },
  getMetrics: async () => {
    const res = await fetch(`${API_BASE}/metrics`)
    return { data: await res.json(), status: res.status }
  },

  // Ask endpoint — §47 `nerve ask` → POST /api/context/ask.
  // Returns the full answer (200) or the accepted-but-not-executed ack
  // (202, `{accepted, executed, detail, request_id, ...}`); AskView renders
  // whichever shape arrives.
  postAsk: async (message: string) => {
    const res = await fetch(`${API_BASE}/context/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: message, message }),
    })
    return { data: await res.json(), status: res.status }
  },

  // Goals
  getGoals: async () => {
    const res = await fetch(`${API_BASE}/goals`)
    return { data: await listFromResponse(res), status: res.status }
  },
  getGoal: async (goalId: string) => {
    const res = await fetch(`${API_BASE}/goals/${goalId}`)
    return { data: await res.json(), status: res.status }
  },

  // Models
  getModels: async () => {
    const res = await fetch(`${API_BASE}/models`)
    return { data: await listFromResponse(res), status: res.status }
  },
  getModel: async (modelId: string) => {
    const res = await fetch(`${API_BASE}/models/${modelId}`)
    return { data: await res.json(), status: res.status }
  },

  // Auth (mock stub)
  login: async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    return { data: await res.json(), status: res.status }
  },
  logout: async () => {
    const res = await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
    })
    return { data: await res.json(), status: res.status }
  },
  me: async () => {
    const res = await fetch(`${API_BASE}/auth/me`)
    return { data: await res.json(), status: res.status }
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
