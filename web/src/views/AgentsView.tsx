import { useState, useEffect, type FormEvent } from 'react'
import { agentsApi, apiFetch, apiErrorFromResponse, ApiError } from '../api/client'

/**
 * Agents view — round 3 (AG-2, AG-3 resolved).
 *
 * AG-2: every status carries visible text AND an `aria-label` — never a bare
 * dot.
 * AG-3 (round 3): the backend now exposes a real agent *create* route
 * (`POST /api/agents`, backend/api/endpoints/agents.py), so '+ Add Agent' is
 * enabled and opens a create form. The form submits to the write route; a 201
 * refreshes the list so the new instance renders, and any non-2xx (e.g. a 409
 * name conflict) is surfaced verbatim rather than faked as success.
 * Persisted agent instances have no live telemetry, so those fields render as
 * "none" / omitted rather than invented numbers.
 */

interface Agent {
  id: string
  name: string
  type: string
  status: string
  description: string | null
  lastHeartbeat: string | null
  cpuUsage: number | null
  memoryUsage: number | null
  tasksCompleted: number | null
  tasksFailed: number | null
}

// The 14 native agent types (spec §26), from backend/agents/registry.py.
// Used as the options for the create form's type <select>.
const NATIVE_AGENT_TYPES = [
  'planner',
  'repository_inspector',
  'runtime_inspector',
  'log_investigator',
  'infrastructure_inspector',
  'architecture_analyst',
  'incident_correlator',
  'code_reviewer',
  'test_runner',
  'benchmark_agent',
  'research_agent',
  'verifier',
  'context_critic',
  'route_critic',
] as const

const AgentsView = () => {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<{ status: number; detail: string } | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [agentName, setAgentName] = useState('')
  const [agentType, setAgentType] = useState<string>(NATIVE_AGENT_TYPES[0])
  const [agentDescription, setAgentDescription] = useState('')
  const [formBusy, setFormBusy] = useState(false)
  const [formError, setFormError] = useState<{ status: number; detail: string } | null>(null)
  const [formSuccess, setFormSuccess] = useState(false)

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const response = await agentsApi.list()
        setAgents(response.data as Agent[])
        setFetchError(null)
      } catch (error) {
        if (error instanceof ApiError) {
          setFetchError({ status: error.status, detail: error.detail })
        } else {
          setFetchError({ status: 0, detail: 'Request failed (network error)' })
        }
      } finally {
        setLoading(false)
      }
    }

    fetchAgents()
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-500'
      case 'inactive':
        return 'bg-gray-500'
      case 'error':
        return 'bg-red-500'
      case 'paused':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getProgressColor = (value: number) => {
    if (value < 50) return 'bg-green-500'
    if (value < 80) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  const openForm = () => {
    setShowForm(true)
    setFormError(null)
    setFormSuccess(false)
  }

  const closeForm = () => {
    setShowForm(false)
    setAgentName('')
    setAgentType(NATIVE_AGENT_TYPES[0])
    setAgentDescription('')
    setFormError(null)
    setFormSuccess(false)
    setFormBusy(false)
  }

  const submitAgent = async (e: FormEvent) => {
    e.preventDefault()
    if (!agentName.trim()) {
      setFormError({ status: 0, detail: 'Name is required.' })
      return
    }
    setFormBusy(true)
    setFormError(null)
    setFormSuccess(false)
    try {
      // AG-3 (round 3): create a durable agent instance. 201 -> refresh the
      // list so the new row renders; non-2xx (e.g. 409 duplicate name) is
      // surfaced verbatim, not faked as success.
      const res = await apiFetch('/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: agentName.trim(),
          type: agentType,
          description: agentDescription.trim() || null,
        }),
      })
      if (!res.ok) {
        throw await apiErrorFromResponse(res)
      }
      setFormSuccess(true)
      const response = await agentsApi.list()
      setAgents(response.data as Agent[])
      setFetchError(null)
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError({ status: error.status, detail: error.detail })
      } else {
        setFormError({ status: 0, detail: 'Request failed (network error)' })
      }
    } finally {
      setFormBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-primary">
        Agents
      </h1>

      {fetchError && (
        <div
          role="alert"
          data-testid="agents-error"
          className="p-3 rounded-md bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 text-sm font-medium"
        >
          Failed to load agents: {fetchError.status} — {fetchError.detail}
        </div>
      )}

      <div className="flex justify-between items-center">
        <div className="text-muted">
          {agents.length} total agents
        </div>
        {/* AG-3 (round 3): create route exists → enabled. */}
        <button
          onClick={openForm}
          className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg"
        >
          + Add Agent
        </button>
      </div>

      {showForm && (
        <form
          data-testid="agent-form"
          onSubmit={submitAgent}
          className="bg-elevated p-6 rounded-lg shadow-lg space-y-4"
        >
          <h3 className="text-xl font-semibold text-primary">
            Add agent
          </h3>
          <p className="text-sm text-muted">
            Creates a durable agent instance via the write route (POST{' '}
            <code className="text-xs">/api/agents</code>). Non-2xx responses
            are shown as-is.
          </p>

          <div>
            <label
              htmlFor="agent-name"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Name
            </label>
            <input
              id="agent-name"
              data-testid="agent-form-name"
              type="text"
              required
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              placeholder="e.g. scout-1"
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-primary"
            />
          </div>

          <div>
            <label
              htmlFor="agent-type"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Type
            </label>
            <select
              id="agent-type"
              data-testid="agent-form-type"
              value={agentType}
              onChange={(e) => setAgentType(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-primary"
            >
              {NATIVE_AGENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="agent-description"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Description
            </label>
            <textarea
              id="agent-description"
              data-testid="agent-form-description"
              rows={2}
              value={agentDescription}
              onChange={(e) => setAgentDescription(e.target.value)}
              placeholder="What does this agent do?"
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-primary"
            />
          </div>

          {formError && (
            <div
              role="alert"
              data-testid="agent-form-error"
              className="p-3 rounded-md bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 text-sm font-medium"
            >
              {formError.status ? `${formError.status} — ` : ''}
              {formError.detail}
            </div>
          )}
          {formSuccess && (
            <div
              role="status"
              data-testid="agent-form-success"
              className="p-3 rounded-md bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300 text-sm font-medium"
            >
              Agent created.
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              type="submit"
              data-testid="agent-form-submit"
              disabled={formBusy}
              className="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white px-4 py-2 rounded-lg"
            >
              {formBusy ? 'Creating…' : 'Create agent'}
            </button>
            <button
              type="button"
              onClick={closeForm}
              className="text-muted px-4 py-2"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : !fetchError && agents.length === 0 ? (
        <div
          data-testid="agents-empty"
          className="bg-elevated p-8 rounded-lg shadow-lg text-center"
        >
          <p className="text-gray-700 dark:text-gray-300 font-medium">
            No agents registered.
          </p>
          <p className="text-sm text-muted mt-2">
            Agents appear here once the AgentRegistry reports them, or use
            “+ Add Agent” to create a durable agent instance via
            POST /api/agents.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="bg-elevated p-6 rounded-lg shadow-lg"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-semibold text-primary">
                    {agent.name}
                  </h3>
                  <p className="text-sm text-muted">
                    {agent.type}
                  </p>
                </div>
                {/* AG-2: text + aria-label, never a bare dot. */}
                <div
                  role="status"
                  aria-label={`Agent ${agent.name} status: ${agent.status}`}
                  data-testid="agent-status"
                  className="flex items-center gap-2"
                >
                  <span
                    aria-hidden="true"
                    className={`w-3 h-3 rounded-full ${getStatusColor(
                      agent.status
                    )}`}
                  />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {agent.status}
                  </span>
                </div>
              </div>
              <div className="space-y-3">
                {agent.cpuUsage != null && agent.memoryUsage != null ? (
                  <>
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-muted">
                          CPU Usage
                        </span>
                        <span className="text-primary">
                          {agent.cpuUsage}%
                        </span>
                      </div>
                      <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
                        <div
                          className={`h-2 rounded-full ${getProgressColor(
                            agent.cpuUsage
                          )}`}
                          style={{ width: `${agent.cpuUsage}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-muted">
                          Memory Usage
                        </span>
                        <span className="text-primary">
                          {agent.memoryUsage}%
                        </span>
                      </div>
                      <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
                        <div
                          className={`h-2 rounded-full ${getProgressColor(
                            agent.memoryUsage
                          )}`}
                          style={{ width: `${agent.memoryUsage}%` }}
                        />
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-gray-400 dark:text-gray-500">
                    No live telemetry reported.
                  </div>
                )}
                <div className="flex justify-between text-sm">
                  <span className="text-muted">
                    Tasks completed
                  </span>
                  <span className="text-primary">
                    {agent.tasksCompleted ?? '—'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted">
                    Tasks failed
                  </span>
                  <span className="text-primary">
                    {agent.tasksFailed ?? '—'}
                  </span>
                </div>
                <div className="text-xs text-gray-400 dark:text-gray-500">
                  Last heartbeat: {agent.lastHeartbeat ?? 'none'}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export { AgentsView }
