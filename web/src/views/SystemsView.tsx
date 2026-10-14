import { useState, useEffect } from 'react'
import { systemsApi } from '../api/client'
import { useRealtimeUpdates } from '../hooks/useRealtimeUpdates'
import type { WebSocketConnectionState } from '../api/WebSocketClient'

interface SystemStatus {
  name: string
  status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown'
  version: string
  message: string
  checkedAt: string
}

/**
 * Honest connection-state metadata. Every state carries visible text and an
 * `aria-label` — the status dot is decorative and never the sole signal.
 */
const WS_STATUS: Record<
  WebSocketConnectionState,
  { label: string; dot: string; ring: string; text: string }
> = {
  connecting: {
    label: 'Connecting',
    dot: 'bg-yellow-500',
    ring: 'border-yellow-300 dark:border-yellow-600',
    text: 'text-yellow-700 dark:text-yellow-300 bg-yellow-100 dark:bg-yellow-900/40',
  },
  open: {
    label: 'Connected',
    dot: 'bg-green-500',
    ring: 'border-green-300 dark:border-green-700',
    text: 'text-green-700 dark:text-green-300 bg-green-100 dark:bg-green-900/40',
  },
  closed: {
    label: 'Disconnected',
    dot: 'bg-gray-400',
    ring: 'border-gray-300 dark:border-gray-600',
    text: 'text-gray-700 dark:text-gray-300 bg-hover',
  },
  error: {
    label: 'Reconnecting',
    dot: 'bg-red-500',
    ring: 'border-red-300 dark:border-red-700',
    text: 'text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/40',
  },
}

/**
 * Render an API failure as `<status> — <detail>`. Duck-types the shared
 * `ApiError { status, detail }` contract so it works whether or not the
 * client has adopted `ApiError` yet (SY-3).
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
 * until it lands, `realApi` still *resolves* `{ data, status }` on 5xx — which
 * is what let the 501 detail get swallowed into a generic banner (SY-3).
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

const SystemsView = () => {
  const [systems, setSystems] = useState<SystemStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Live update channel: the badge reflects the REAL connection state of the
  // backend's only live WebSocket (``GET /api/events/ws``). With the socket up
  // it honestly shows "Connected"; if the event bus is down it shows
  // "Reconnecting" instead of a fake green dot (SY-2). The socket streams
  // *events*, not system snapshots, so it drives the badge only — the systems
  // list is populated solely by the REST fetch above (shape-guarded below).
  const realtime = useRealtimeUpdates<SystemStatus[]>('/api/events/ws', systems)

  useEffect(() => {
    const fetchSystems = async () => {
      try {
        const response = await assertOk(await systemsApi.health(), 'systems')
        const rows = (response.data ?? []) as any[]
        setSystems(rows.map((s) => ({
          name: s?.name ?? 'unknown',
          status: s?.status ?? 'unknown',
          version: s?.version ?? '—',
          message: s?.message ?? '',
          checkedAt: s?.checkedAt ?? '',
        })))
        setError(null)
      } catch (err) {
        setError(formatApiError(err))
        console.warn('systems endpoint failed:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchSystems()
  }, [])

  // The /api/events/ws socket streams *event objects* (not system snapshots),
  // so it must never replace the REST-derived list. Only fold in a payload when
  // it is a non-empty array whose first row looks like a system row (name +
  // status) — anything else (a single event object) is ignored.
  useEffect(() => {
    const rows = realtime.data
    if (!Array.isArray(rows) || rows.length === 0) return
    if (typeof rows[0]?.name !== 'string' || typeof rows[0]?.status !== 'string') return
    setSystems(rows as SystemStatus[])
    if (realtime.lastUpdate) setError(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [realtime.data, realtime.lastUpdate])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-500'
      case 'unhealthy':
        return 'bg-red-500'
      case 'degraded':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  const conn = WS_STATUS[realtime.connection] ?? WS_STATUS.closed
  const lastUpdate = realtime.lastUpdate

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-bold text-primary">Systems</h1>
        <div
          role="status"
          aria-label={`Real-time connection: ${conn.label}`}
          className={`flex items-center px-3 py-1.5 rounded-full border ${conn.ring} ${conn.text}`}
        >
          <span
            className={`w-2.5 h-2.5 rounded-full mr-2 ${conn.dot}`}
            aria-hidden="true"
          />
          <span className="text-sm font-medium">
            Real-time: {conn.label}
          </span>
        </div>
      </div>

      {lastUpdate && (
        <p className="text-xs text-muted">
          Last live update:{' '}
          {lastUpdate.toLocaleTimeString()}
        </p>
      )}

      {loading ? (
        <div className="text-center py-12" role="status">
          Loading system status…
        </div>
      ) : error ? (
        <div
          role="alert"
          className="text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/40 border border-red-300 dark:border-red-700 p-4 rounded-lg"
        >
          <p className="font-semibold mb-1">System status unavailable</p>
          <p className="text-sm font-mono break-words">{error}</p>
          <p className="text-sm mt-2">
            The /api/systems endpoint was reachable but returned an error. See the status
            and detail above; the backend service is up — check its logs for the cause.
          </p>
        </div>
      ) : (
        <>
          {systems.length === 0 && (
            <div className="bg-elevated rounded-lg shadow-lg p-6">
              <p className="text-sm text-muted">
                No systems reported. The /api/systems endpoint returned successfully but the
                system registry is empty — no system has reported status yet.
              </p>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {systems.map((system) => (
              <div
                key={system.name}
                className="bg-elevated rounded-lg shadow-lg p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      role="img"
                      aria-label={`${system.name} status: ${system.status}`}
                      className="shrink-0 w-3 h-3 rounded-full flex"
                    >
                      <span
                        className={`w-3 h-3 rounded-full ${getStatusColor(system.status)}`}
                        aria-hidden="true"
                      />
                    </span>
                    <span className="font-semibold text-primary truncate">
                      {system.name}
                    </span>
                    <span className="text-xs text-gray-400">{system.version}</span>
                  </div>
                  <span
                    className="text-xs font-medium px-2 py-0.5 rounded-full bg-hover text-gray-700 dark:text-gray-200 capitalize"
                    aria-label={`Status: ${system.status}`}
                  >
                    {system.status}
                  </span>
                </div>
                {system.message && (
                  <p className="text-sm text-gray-600 dark:text-gray-300">{system.message}</p>
                )}
                {system.checkedAt && (
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                    Checked {system.checkedAt}
                  </p>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export { SystemsView }
