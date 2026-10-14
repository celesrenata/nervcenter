import { useState, useEffect } from 'react'
import { eventsApi, ApiError } from '../api/client'

/**
 * Timeline view — gap-closure round 2 (TL-1).
 *
 * Round 1 rendered five *hardcoded* sample events, so the timeline looked
 * live with zero data. This round removes the fixtures and fetches real
 * events from `GET /api/events` (backend/api/endpoints/events.py, backed by
 * the NATS JetStream bus). Field mapping follows the frozen
 * `schemas.events.Event` contract: `event_type` → type, `occurred_at` →
 * timestamp, `payload.message`/`subject` → message, `severity` → severity.
 *
 * Honest states:
 *   - bus not configured  → backend returns 200 with an empty list → we show
 *     guidance copy (not fake data).
 *   - bus unreachable     → backend returns 503 → we surface `status — detail`
 *     in a `role=alert` banner.
 */

interface TimelineEvent {
  id: string
  timestamp: string
  type: string
  message: string
  severity: 'info' | 'warning' | 'error' | 'success' | 'critical' | 'debug'
}

type RawEvent = {
  id?: string
  event_type?: string
  category?: string
  occurred_at?: string
  subject?: string | null
  payload?: Record<string, unknown> | null
  severity?: string
  stream?: string | null
}

const TimelineView = () => {
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<{ status: number; detail: string } | null>(null)

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const response = await eventsApi.list()
        const raw = (response.data ?? []) as RawEvent[]
        setEvents(
          raw.map((ev, i) => ({
            id: ev.id ?? `event-${i}`,
            timestamp: ev.occurred_at ?? '',
            type: ev.event_type ?? ev.category ?? 'event',
            message:
              (typeof (ev.payload?.message ?? ev.payload?.summary) === 'string'
                ? String(ev.payload?.message ?? ev.payload?.summary)
                : ev.subject ?? 'No message recorded'),
            severity: (ev.severity ?? 'info') as TimelineEvent['severity'],
          })),
        )
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

    fetchEvents()
  }, [])

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'info':
        return 'border-blue-500'
      case 'warning':
        return 'border-yellow-500'
      case 'error':
        return 'border-red-500'
      case 'critical':
        return 'border-red-700'
      case 'success':
        return 'border-green-500'
      case 'debug':
        return 'border-gray-400'
      default:
        return 'border-gray-400'
    }
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'info':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300'
      case 'warning':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300'
      case 'error':
        return 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300'
      case 'critical':
        return 'bg-red-200 text-red-900 dark:bg-red-800/60 dark:text-red-200'
      case 'success':
        return 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300'
      case 'debug':
        return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
      default:
        return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-primary">
        Timeline
      </h1>

      {fetchError && (
        <div
          role="alert"
          data-testid="timeline-error"
          className="p-3 rounded-md bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 text-sm font-medium"
        >
          Failed to load timeline: {fetchError.status} — {fetchError.detail}
        </div>
      )}

      <div className="bg-elevated rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-semibold text-primary mb-4">
          Recent events
        </h3>
        {loading ? (
          <div className="text-center py-12">Loading...</div>
        ) : events.length === 0 ? (
          <div
            data-testid="timeline-empty"
            className="text-center py-8"
          >
            <p className="text-gray-700 dark:text-gray-300 font-medium">
              No events recorded yet.
            </p>
            <p className="text-sm text-muted mt-2 max-w-md mx-auto">
              The event bus has not published any activity (or is not
              configured). Events are append-only and appear here the moment
              the system records them — nothing is hidden.
            </p>
          </div>
        ) : (
          <div className="relative pl-8 border-l-2 border-line">
            {events.map((event, index) => (
              <div key={index} className="relative mb-6">
                <div className="absolute -left-[41px] top-0">
                  <div
                    className={`w-5 h-5 rounded-full border-2 ${getSeverityColor(
                      event.severity
                    )} bg-elevated`}
                  />
                </div>
                <div className="bg-hover p-4 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-primary">
                      {event.type}
                    </span>
                    <span className="text-sm text-muted">
                      {event.timestamp}
                    </span>
                  </div>
                  <div className="flex items-center space-x-2 mb-2">
                    <span className={`text-xs px-2 py-1 rounded ${getSeverityBadge(
                      event.severity
                    )}`}>
                      {event.severity}
                    </span>
                  </div>
                  <p className="text-gray-700 dark:text-gray-300">
                    {event.message}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-elevated rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-semibold text-primary mb-4">
          Legend
        </h3>
        <div className="flex flex-wrap gap-4 text-sm text-secondary">
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full border-2 border-blue-500 bg-elevated" />
            info
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full border-2 border-yellow-500 bg-elevated" />
            warning
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full border-2 border-red-500 bg-elevated" />
            error
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full border-2 border-green-500 bg-elevated" />
            success
          </span>
        </div>
      </div>
    </div>
  )
}

export { TimelineView }
