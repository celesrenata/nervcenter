import axios from 'axios'

const API_BASE_URL = '/api'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add request interceptor for auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Export API endpoints
export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  refresh: (refreshToken: string) =>
    api.post('/auth/refresh', { refresh_token: refreshToken }),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
}

export const agentsApi = {
  list: () => api.get('/agents'),
  get: (agentId: string) => api.get(`/agents/${agentId}`),
}

export const goalsApi = {
  list: () => api.get('/goals'),
  get: (goalId: string) => api.get(`/goals/${goalId}`),
}

export const tasksApi = {
  list: () => api.get('/tasks'),
  get: (taskId: string) => api.get(`/tasks/${taskId}`),
}

export const evidenceApi = {
  list: () => api.get('/evidence'),
  get: (evidenceId: string) => api.get(`/evidence/${evidenceId}`),
}

export const knowledgeApi = {
  list: () => api.get('/knowledge'),
  get: (knowledgeId: string) => api.get(`/knowledge/${knowledgeId}`),
}

export const systemsApi = {
  health: () => api.get('/health'),
  metrics: () => api.get('/metrics'),
}

export const incidentsApi = {
  list: () => api.get('/incidents'),
  get: (incidentId: string) => api.get(`/incidents/${incidentId}`),
}