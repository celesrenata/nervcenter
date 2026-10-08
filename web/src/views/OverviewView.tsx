import { useState, useEffect } from 'react'
import { agentsApi, goalsApi, tasksApi, incidentsApi } from '../api/client'

interface GoalItem {
  id: string
  name: string
  status: string
  progressPct: number
  deadline: string | null
}

interface AgentItem {
  id: string
  name: string
  status: string
  task: string | null
}

/**
 * Defensive progress normalizer. The real backend reports `progress` as a
 * 0..1 fraction while the in-browser mock fixture reports 0..100. Values ≤ 1
 * are treated as fractions and scaled to a percentage; anything larger is
 * already a percentage. Non-numeric input degrades to 0.
 */
function toPercent(p: unknown): number {
  const n = typeof p === 'number' ? p : parseFloat(String(p ?? ''))
  if (!Number.isFinite(n) || n < 0) return 0
  const pct = n <= 1 ? Math.round(n * 100) : Math.round(n)
  return Math.max(0, Math.min(100, pct))
}

function normalizeGoal(g: any, idx: number): GoalItem {
  return {
    id: String(g?.id ?? g?.goal_id ?? `goal-${idx}`),
    name: g?.title ?? g?.name ?? 'Untitled goal',
    status: g?.status ?? 'unknown',
    progressPct: toPercent(g?.progress),
    deadline: g?.deadline ?? g?.dueDate ?? null,
  }
}

function normalizeAgent(a: any, idx: number): AgentItem {
  return {
    id: String(a?.id ?? `agent-${idx}`),
    name: a?.name ?? a?.id ?? `Agent ${idx + 1}`,
    status: a?.status ?? 'unknown',
    task: a?.currentTask ?? a?.task ?? null,
  }
}

/**
 * Render an API failure as `<status> — <detail>`. Codes against the shared
 * `ApiError { status, detail }` contract via duck-typing so the banner works
 * whether or not the client has adopted `ApiError` yet; falls back to
 * `Error.message` then a generic message.
 */
function formatApiError(err: unknown): string {
  const e = err as { status?: number; detail?: string; message?: string } | null
  if (e && typeof e.status === 'number' && typeof e.detail === 'string') {
    return `${e.status} — ${e.detail}`
  }
  if (e && typeof e.message === 'string' && e.message) return e.message
  return 'Request failed'
}

/**
 * Defensive status guard for the transitional client contract.
 *
 * The in-flight `ApiError` contract (sibling task) will make `realApi` reject
 * on non-2xx; until it lands, `realApi` still *resolves* `{ data, status }`
 * even on 5xx — which is exactly what swallowed `/api/tasks` 500 into silent
 * zero tiles (OV-1). This guard converts a resolved non-2xx into a thrown
 * `ApiError`-shaped error so the view can render an honest banner.
 */
type ApiResult = {
  ok?: boolean
  status?: number
  detail?: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data?: any
}

function assertOk(res: ApiResult | undefined | null, context: string): ApiResult {
  if (res && typeof res.status === 'number' && res.status >= 400 && !res.ok) {
    const status = res.status
    const detail = res.detail
    const err: any = new Error(`${status} — ${typeof detail === 'string' && detail ? detail : `${context}: HTTP ${status}`}`)
    err.status = status
    err.detail = typeof detail === 'string' && detail ? detail : `${context}: HTTP ${status}`
    throw err
  }
  if (!res) {
    const err: any = new Error(`${context}: no response`)
    err.status = 500
    err.detail = `${context}: no response`
    throw err
  }
  return res
}

const goalStatusColor = (status: string): string => {
  switch (status) {
    case 'active':
    case 'ACTIVE':
      return 'bg-blue-500'
    case 'achieved':
    case 'completed':
    case 'done':
      return 'bg-green-500'
    case 'paused':
    case 'pending':
      return 'bg-yellow-500'
    case 'abandoned':
    case 'cancelled':
      return 'bg-gray-500'
    default:
      return 'bg-gray-400'
  }
}

const OverviewView = () => {
  const [stats, setStats] = useState({
    activeGoals: 0,
    activeAgents: 0,
    pendingTasks: 0,
    activeIncidents: 0,
  })
  const [goals, setGoals] = useState<GoalItem[]>([])
  const [agents, setAgents] = useState<AgentItem[]>([])
  const [errors, setErrors] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    const load = async () => {
      const labels = ['goals', 'agents', 'tasks', 'incidents']
      // allSettled so one failing endpoint degrades only its own tile/panel
      // instead of silently zeroing the whole view (OV-1).
      const results = await Promise.allSettled([
        goalsApi.list().then((r) => assertOk(r, 'goals')),
        agentsApi.list().then((r) => assertOk(r, 'agents')),
        tasksApi.list().then((r) => assertOk(r, 'tasks')),
        incidentsApi.list().then((r) => assertOk(r, 'incidents')),
      ])

      const errs: string[] = []
      results.forEach((r, i) => {
        if (r.status === 'rejected') errs.push(`${labels[i]}: ${formatApiError(r.reason)}`)
      })

      const r0 = results[0]
      const r1 = results[1]
      const r2 = results[2]
      const r3 = results[3]

      if (!alive) return
      setStats((s) => ({
        activeGoals: r0.status === 'fulfilled' ? (r0.value.data?.length ?? 0) : s.activeGoals,
        activeAgents: r1.status === 'fulfilled' ? (r1.value.data?.length ?? 0) : s.activeAgents,
        pendingTasks: r2.status === 'fulfilled' ? (r2.value.data?.length ?? 0) : s.pendingTasks,
        activeIncidents: r3.status === 'fulfilled' ? (r3.value.data?.length ?? 0) : s.activeIncidents,
      }))
      if (r0.status === 'fulfilled') {
        const rows = (r0.value.data ?? []) as any[]
        setGoals(rows.map((g, i) => normalizeGoal(g, i)))
      }
      if (r1.status === 'fulfilled') {
        const rows = (r1.value.data ?? []) as any[]
        setAgents(rows.map((a, i) => normalizeAgent(a, i)))
      }
      setErrors(errs)
      setLoading(false)
    }
    load()
    return () => {
      alive = false
    }
  }, [])

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">Overview</h1>

      {errors.length > 0 && (
        <div
          role="alert"
          className="text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/40 border border-red-300 dark:border-red-700 p-4 rounded-lg"
        >
          <p className="font-semibold mb-1">Some data is unavailable</p>
          <ul className="list-disc list-inside text-sm space-y-1">
            {errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12" role="status">
          Loading overview…
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Active Goals</p>
                  <span className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                    {stats.activeGoals}
                  </span>
                </div>
                <div className="text-4xl" aria-hidden="true">🎯</div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Active Agents</p>
                  <span className="text-3xl font-bold text-green-600 dark:text-green-400">
                    {stats.activeAgents}
                  </span>
                </div>
                <div className="text-4xl" aria-hidden="true">🤖</div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Pending Tasks</p>
                  <span className="text-3xl font-bold text-yellow-600 dark:text-yellow-400">
                    {stats.pendingTasks}
                  </span>
                </div>
                <div className="text-4xl" aria-hidden="true">📋</div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Active Incidents</p>
                  <span className="text-3xl font-bold text-red-600 dark:text-red-400">
                    {stats.activeIncidents}
                  </span>
                </div>
                <div className="text-4xl" aria-hidden="true">⚠️</div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
              <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
                Goals
              </h3>
              {goals.length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                  No goals yet. Create a goal from the Goals page to give NerveCenter a target to
                  work toward.
                </p>
              ) : (
                <div className="space-y-3">
                  {goals.slice(0, 5).map((goal) => (
                    <div
                      key={goal.id}
                      className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium text-gray-800 dark:text-white truncate">
                          {goal.name}
                        </p>
                        <span
                          role="img"
                          aria-label={`Status: ${goal.status}`}
                          className="shrink-0 flex items-center px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-600 text-xs"
                        >
                          <span
                            className={`w-2 h-2 rounded-full mr-1.5 ${goalStatusColor(goal.status)}`}
                            aria-hidden="true"
                          />
                          <span className="text-gray-700 dark:text-gray-200 capitalize">
                            {goal.status}
                          </span>
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mt-2">
                        <div
                          className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden"
                          role="progressbar"
                          aria-valuenow={goal.progressPct}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${goal.name} progress`}
                        >
                          <div
                            className="h-full bg-blue-500"
                            style={{ width: `${goal.progressPct}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400 tabular-nums">
                          {goal.progressPct}%
                        </span>
                      </div>
                    </div>
                  ))}
                  {goals.length > 5 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      +{goals.length - 5} more on the Goals page
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
              <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
                Agents
              </h3>
              {agents.length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                  No agents registered. Agents show up here once the agent service is wired and
                  reports its roster.
                </p>
              ) : (
                <div className="space-y-3">
                  {agents.map((agent) => (
                    <div
                      key={agent.id}
                      className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium text-gray-800 dark:text-white truncate">
                          {agent.name}
                        </p>
                        <span
                          role="img"
                          aria-label={`Agent status: ${agent.status}`}
                          className="shrink-0 flex items-center px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-600 text-xs"
                        >
                          <span
                            className={`w-2 h-2 rounded-full mr-1.5 ${
                              agent.status === 'active' || agent.status === 'running'
                                ? 'bg-green-500'
                                : agent.status === 'paused' || agent.status === 'idle'
                                  ? 'bg-yellow-500'
                                  : 'bg-gray-400'
                            }`}
                            aria-hidden="true"
                          />
                          <span className="text-gray-700 dark:text-gray-200 capitalize">
                            {agent.status}
                          </span>
                        </span>
                      </div>
                      {agent.task && (
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 truncate">
                          {agent.task}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export { OverviewView }
