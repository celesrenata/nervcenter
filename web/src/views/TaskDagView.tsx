import { useState, useEffect, useMemo } from 'react'
import { tasksApi } from '../api/client'

/**
 * Normalized task shape used by the DAG renderer.
 *
 * The real §46 backend returns `id` / `title` / `status` (lowercase lifecycle
 * values: pending/scheduled/in_progress/completed/failed/cancelled, see
 * `schemas/tasks.py`), while the in-browser mock fixture uses
 * `task_id` / `title` / `state` (uppercase). Both shapes are normalized here
 * so the view renders honestly against either (TA-3).
 */
interface TaskRecord {
  id: string
  name: string
  description: string | null
  status: TaskDisplayStatus
  priority: number
  dependencies: string[]
  estimatedDuration?: string
}

type TaskDisplayStatus =
  | 'PENDING'
  | 'READY'
  | 'RUNNING'
  | 'BLOCKED'
  | 'VERIFYING'
  | 'COMPLETED'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELLED'

const STATUS_META: Record<TaskDisplayStatus, { dot: string; badge: string }> = {
  PENDING: { dot: 'bg-yellow-500', badge: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200' },
  READY: { dot: 'bg-blue-500', badge: 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200' },
  RUNNING: { dot: 'bg-green-500', badge: 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200' },
  BLOCKED: { dot: 'bg-orange-500', badge: 'bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-200' },
  VERIFYING: { dot: 'bg-purple-500', badge: 'bg-purple-100 dark:bg-purple-900/40 text-purple-800 dark:text-purple-200' },
  COMPLETED: { dot: 'bg-green-600', badge: 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200' },
  SUCCEEDED: { dot: 'bg-green-600', badge: 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200' },
  FAILED: { dot: 'bg-red-500', badge: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200' },
  CANCELLED: { dot: 'bg-gray-400', badge: 'bg-hover text-gray-600 dark:text-gray-300' },
}

/** Map a raw backend status (either vocabulary) onto the display vocabulary. */
function normalizeStatus(raw: unknown): TaskDisplayStatus {
  const s = String(raw ?? '').toUpperCase()
  switch (s) {
    case 'IN_PROGRESS':
    case 'IN-PROGRESS':
    case 'RUNNING':
      return 'RUNNING'
    case 'SCHEDULED':
    case 'QUEUED':
    case 'READY':
      return 'READY'
    // Task.status lifecycle value (schemas/tasks.py: TaskStatus) — a finished
    // task is `completed`, NOT `succeeded` (that belongs to TaskRun.status).
    case 'COMPLETED':
    case 'DONE':
      return 'COMPLETED'
    // TaskRun.status value — keep the distinct run-level success badge.
    case 'SUCCEEDED':
      return 'SUCCEEDED'
    case 'FAILED':
    case 'ERROR':
      return 'FAILED'
    case 'CANCELLED':
    case 'CANCELED':
      return 'CANCELLED'
    case 'BLOCKED':
      return 'BLOCKED'
    case 'VERIFYING':
      return 'VERIFYING'
    case 'PENDING':
    default:
      return s === '' ? 'PENDING' : (s in STATUS_META ? (s as TaskDisplayStatus) : 'PENDING')
  }
}

function normalizeTask(t: any, idx: number): TaskRecord {
  const id = String(t?.id ?? t?.task_id ?? `task-${idx}`)
  return {
    id,
    name: t?.title ?? t?.name ?? id,
    description: t?.description ?? null,
    status: normalizeStatus(t?.status ?? t?.state ?? 'PENDING'),
    priority: Number.isFinite(Number(t?.priority)) ? Number(t?.priority) : 0,
    dependencies: Array.isArray(t?.dependencies)
      ? (t.dependencies as unknown[]).map((d) => String(d))
      : [],
    estimatedDuration: t?.estimatedDuration ?? undefined,
  }
}

/**
 * Render an API failure as `<status> — <detail>`. Duck-types the shared
 * `ApiError { status, detail }` contract so it works whether or not the
 * client has adopted `ApiError` yet; falls back to `Error.message`.
 */
function formatApiError(err: unknown): string {
  const e = err as { status?: number; detail?: string; message?: string } | null
  if (e && typeof e.status === 'number' && typeof e.detail === 'string') {
    return `${e.status} — ${e.detail}`
  }
  if (e && typeof e.message === 'string' && e.message) return e.message
  return 'Request failed'
}

type ApiResult = {
  ok?: boolean
  status?: number
  detail?: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data?: any
}

/**
 * Defensive status guard for the transitional client contract. The in-flight
 * `ApiError` contract (sibling task) will make `realApi` reject on non-2xx;
 * until it lands, `realApi` still *resolves* `{ data, status }` on 5xx —
 * which is what swallowed the `/api/tasks` 500 into a silent empty list (OV-1).
 */
function assertOk(res: ApiResult | undefined | null, context: string): ApiResult {
  if (res && typeof res.status === 'number' && res.status >= 400 && !res.ok) {
    const status = res.status
    const detail = res.detail
    const err: any = new Error(
      `${status} — ${typeof detail === 'string' && detail ? detail : `${context}: HTTP ${status}`}`,
    )
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

// ─── DAG layout (TA-2) ────────────────────────────────────────────────────────

const NODE_W = 248
const NODE_H = 92
const COL_GAP = 72
const ROW_GAP = 24
const PAD = 20

interface LayoutNode {
  task: TaskRecord
  x: number
  y: number
  level: number
}

interface Edge {
  from: string
  to: string
  d: string
}

interface DagLayout {
  nodes: LayoutNode[]
  edges: Edge[]
  width: number
  height: number
}

/**
 * Rank each task by its longest dependency path (roots at level 0), then lay
 * out nodes in left-to-right columns per rank. Cycles and dangling
 * dependencies (ids not present in the list) degrade gracefully instead of
 * throwing: cycle members pin to their current depth, dangling deps are
 * ignored when drawing edges.
 */
function layoutDag(tasks: TaskRecord[]): DagLayout {
  const byId = new Map<string, TaskRecord>(tasks.map((t) => [t.id, t]))
  const memo = new Map<string, number>()
  const visiting = new Set<string>()

  const rankOf = (id: string): number => {
    if (memo.has(id)) return memo.get(id)!
    if (visiting.has(id)) return 0 // cycle guard
    const task = byId.get(id)
    if (!task) return 0 // dangling dependency
    visiting.add(id)
    const knownDeps = task.dependencies.filter((d) => byId.has(d))
    const rank = knownDeps.length === 0 ? 0 : Math.max(...knownDeps.map(rankOf)) + 1
    visiting.delete(id)
    memo.set(id, rank)
    return rank
  }

  const levels = new Map<number, LayoutNode[]>()
  for (const task of tasks) {
    const level = rankOf(task.id)
    if (!levels.has(level)) levels.set(level, [])
    levels
      .get(level)!
      .push({ task, x: 0, y: 0, level })
  }

  const maxLevel = Math.max(0, ...[...levels.keys()])
  for (const [level, nodes] of levels) {
    nodes.forEach((node, i) => {
      node.x = PAD + level * (NODE_W + COL_GAP)
      node.y = PAD + i * (NODE_H + ROW_GAP)
    })
  }

  const allNodes = [...levels.values()].flat()
  const edges: Edge[] = []
  for (const node of allNodes) {
    for (const depId of node.task.dependencies) {
      const dep = byId.get(depId)
      if (!dep) continue // dangling dependency — skip edge
      const depNode = allNodes.find((n) => n.task.id === depId)
      if (!depNode) continue
      const x1 = depNode.x + NODE_W
      const y1 = depNode.y + NODE_H / 2
      const x2 = node.x
      const y2 = node.y + NODE_H / 2
      const bend = Math.max(24, (x2 - x1) / 2)
      edges.push({
        from: depId,
        to: node.task.id,
        d: `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`,
      })
    }
  }

  const width =
    allNodes.length === 0 ? 0 : PAD * 2 + maxLevel * (NODE_W + COL_GAP) + NODE_W
  const height =
    allNodes.length === 0
      ? 0
      : Math.max(...allNodes.map((n) => n.y)) + NODE_H + PAD

  return { nodes: allNodes, edges, width, height }
}

// ─── View ────────────────────────────────────────────────────────────────────

const TaskDagView = () => {
  const [tasks, setTasks] = useState<TaskRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const response = await assertOk(await tasksApi.list(), 'tasks')
        const rows = (response.data ?? []) as any[]
        setTasks(rows.map((t, i) => normalizeTask(t, i)))
        setError(null)
      } catch (err) {
        setError(formatApiError(err))
      } finally {
        setLoading(false)
      }
    }

    fetchTasks()
  }, [])

  const layout = useMemo(() => layoutDag(tasks), [tasks])

  const concurrency = useMemo(() => {
    const counts = new Map<TaskDisplayStatus, number>()
    for (const t of tasks) counts.set(t.status, (counts.get(t.status) ?? 0) + 1)
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([status, count]) => ({ status, count }))
  }, [tasks])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-bold text-primary">Task DAG</h1>
        <div
          className="flex flex-wrap gap-2"
          role="status"
          aria-label={`Concurrency: ${tasks.length} tasks total`}
        >
          <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-hover text-gray-700 dark:text-gray-200">
            {tasks.length} task{tasks.length === 1 ? '' : 's'}
          </span>
          {concurrency.map(({ status, count }) => (
            <span
              key={status}
              className={`flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_META[status].badge}`}
              aria-label={`${count} task${count === 1 ? '' : 's'} ${status.toLowerCase()}`}
            >
              <span
                className={`w-2 h-2 rounded-full mr-1.5 ${STATUS_META[status].dot}`}
                aria-hidden="true"
              />
              {count} {status.toLowerCase()}
            </span>
          ))}
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/40 border border-red-300 dark:border-red-700 p-4 rounded-lg"
        >
          <p className="font-semibold mb-1">Tasks unavailable</p>
          <p className="text-sm font-mono break-words">{error}</p>
        </div>
      )}

      <div className="bg-elevated rounded-lg shadow-lg p-4">
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          {(Object.keys(STATUS_META) as TaskDisplayStatus[]).map((status) => (
            <span
              key={status}
              className="flex items-center text-xs text-gray-600 dark:text-gray-300"
            >
              <span
                className={`w-2.5 h-2.5 rounded-full mr-1.5 ${STATUS_META[status].dot}`}
                aria-hidden="true"
              />
              {status.toLowerCase()}
            </span>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12" role="status">
          Loading task DAG…
        </div>
      ) : tasks.length === 0 ? (
        <div className="bg-elevated rounded-lg shadow-lg p-8 text-center">
          <p className="text-sm text-muted">
            No tasks scheduled. Tasks appear here when goals or decisions are
            decomposed into work; the dependency graph renders as each task
            lands.
          </p>
        </div>
      ) : (
        <div className="bg-elevated rounded-lg shadow-lg p-6 overflow-x-auto">
          <div
            className="relative"
            style={{ width: layout.width, height: layout.height }}
            data-testid="task-dag"
          >
            <svg
              width={layout.width}
              height={layout.height}
              className="absolute inset-0 pointer-events-none"
              role="img"
              aria-label={`Dependency graph: ${layout.edges.length} edges between ${layout.nodes.length} tasks`}
              data-testid="task-dag-svg"
            >
              <defs>
                <marker
                  id="dag-arrow"
                  viewBox="0 0 10 10"
                  refX="9"
                  refY="5"
                  markerWidth="7"
                  markerHeight="7"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ca3af" />
                </marker>
              </defs>
              {layout.edges.map((edge) => (
                <path
                  key={`${edge.from}->${edge.to}`}
                  d={edge.d}
                  fill="none"
                  stroke="#9ca3af"
                  strokeWidth={1.5}
                  markerEnd="url(#dag-arrow)"
                  data-testid={`task-edge-${edge.from}-${edge.to}`}
                />
              ))}
            </svg>
            {layout.nodes.map(({ task, x, y, level }) => (
              <div
                key={task.id}
                className="absolute bg-hover rounded-lg border border-gray-200 dark:border-gray-600 p-3 shadow-sm"
                style={{ left: x, top: y, width: NODE_W, height: NODE_H }}
                data-testid={`task-node-${task.id}`}
                data-name={task.name}
                role="group"
                aria-label={`${task.name}, status ${task.status.toLowerCase()}, depends on ${
                  task.dependencies.length === 0 ? 'nothing' : task.dependencies.join(', ')
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`shrink-0 w-2.5 h-2.5 rounded-full ${STATUS_META[task.status].dot}`}
                    aria-hidden="true"
                  />
                  <span className="font-medium text-sm text-primary truncate">
                    {task.name}
                  </span>
                </div>
                <div className="flex items-center justify-between mt-2">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_META[task.status].badge}`}
                  >
                    {task.status}
                  </span>
                  <span className="text-xs text-muted tabular-nums">
                    P{task.priority} · L{level}
                  </span>
                </div>
                {task.description && (
                  <p className="text-xs text-muted mt-1 truncate">
                    {task.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export { TaskDagView }
