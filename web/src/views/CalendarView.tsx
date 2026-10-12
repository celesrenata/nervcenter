import { useState, useEffect, useCallback } from 'react'
import { calendarApi, ApiError } from '../api/client'

/**
 * CalendarView — the Calendar plane (prompt2 Phase P2).
 *
 * Shows upcoming events ingested by calendar sync, and the two reasoning
 * tools the user gets from NerveCenter (§42/§43):
 *   1. **Availability** — "is [start,end) free, what blocks it, and when
 *      could it fit?" (the scheduling guard)
 *   2. **Free-slot search** — "give me the earliest 30/60/90-min slot"
 *   3. **Conflict-aware suggestion** — the exact §43 reply: a blocked window
 *      turns into "I can do after 19:30" (or a next-day proposal) instead of
 *      NerveCenter blindly saying "yes" and colliding with a commitment.
 *
 * NerveCenter holds only read-only copies (§42) — nothing here mutates the
 * user's real calendar.
 */

interface CalEvent {
  event_id: string
  title: string
  description: string | null
  start: string | null
  end: string | null
  all_day: boolean
  location: string | null
  participants: string[]
  source: string
}

interface AvailabilityResult {
  available: boolean
  start: string
  end: string
  conflicts: CalEvent[]
  earliest_free_after: string
}

interface SuggestResult extends AvailabilityResult {
  suggested_at: string
  suggestion: string
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function fmtDay(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })
}

function fmtRange(ev: CalEvent): string {
  if (ev.all_day) return fmtDay(ev.start) + ' (all day)'
  return `${fmtTime(ev.start)} – ${fmtTime(ev.end)}`
}

export function CalendarView() {
  const [events, setEvents] = useState<CalEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Scheduling guard
  const [avail, setAvail] = useState<AvailabilityResult | null>(null)
  // Free-slot search
  const [free, setFree] = useState<{ start: string; duration_minutes: number; free_at: string | null; found: boolean } | null>(null)
  // §43 suggestion
  const [suggest, setSuggest] = useState<SuggestResult | null>(null)
  const [busy, setBusy] = useState<'avail' | 'free' | 'suggest' | null>(null)

  // Inputs
  const [checkStart, setCheckStart] = useState<string>(() =>
    new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString().slice(0, 16),
  )
  const [durationMin, setDurationMin] = useState(60)

  const load = useCallback(async () => {
    try {
      setError(null)
      const res = await calendarApi.list()
      if (res.status >= 400) throw new ApiError(res.status, `HTTP ${res.status}`)
      setEvents(res.data as CalEvent[])
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load calendar')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const runAvailability = useCallback(async () => {
    if (!checkStart) return
    setBusy('avail')
    try {
      const end = new Date(new Date(checkStart).getTime() + durationMin * 60000).toISOString()
      const res = await calendarApi.availability(checkStart, end)
      if (res.status >= 400) throw new ApiError(res.status, `HTTP ${res.status}`)
      setAvail(res.data as AvailabilityResult)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Availability check failed')
    } finally {
      setBusy(null)
    }
  }, [checkStart, durationMin])

  const runFreeSlot = useCallback(async () => {
    if (!checkStart) return
    setBusy('free')
    try {
      const res = await calendarApi.freeTime(checkStart, durationMin)
      if (res.status >= 400) throw new ApiError(res.status, `HTTP ${res.status}`)
      setFree(res.data as { start: string; duration_minutes: number; free_at: string | null; found: boolean })
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Free-slot search failed')
    } finally {
      setBusy(null)
    }
  }, [checkStart, durationMin])

  const runSuggest = useCallback(async () => {
    if (!checkStart) return
    setBusy('suggest')
    try {
      const res = await calendarApi.suggest(checkStart, durationMin)
      if (res.status >= 400) throw new ApiError(res.status, `HTTP ${res.status}`)
      setSuggest(res.data as SuggestResult)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Suggestion failed')
    } finally {
      setBusy(null)
    }
  }, [checkStart, durationMin])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-800 dark:text-white">Calendar</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {loading
            ? 'Loading…'
            : `${events.length} upcoming event${events.length === 1 ? '' : 's'} · read-only`}
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/30 px-4 py-3 text-sm text-red-700 dark:text-red-300"
        >
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Upcoming events */}
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Upcoming
          </h2>
          {loading ? (
            <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-sm text-gray-500 dark:text-gray-400">
              Loading events…
            </div>
          ) : events.length === 0 ? (
            <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-sm text-gray-500 dark:text-gray-400">
              Nothing on the calendar in the next 7 days — availability checks
              against an empty schedule.
            </div>
          ) : (
            <ul className="space-y-2">
              {events.map((ev) => (
                <li
                  key={ev.event_id}
                  className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-sm"
                >
                  <div className="font-medium text-gray-800 dark:text-gray-100">
                    {ev.title}
                  </div>
                  <div className="text-gray-500 dark:text-gray-400">
                    {fmtRange(ev)}
                    {ev.location ? ` · ${ev.location}` : ''}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Reasoning tools */}
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Availability & conflict reasoning
          </h2>

          <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
            <div className="flex flex-wrap items-end gap-3">
              <label className="text-xs text-gray-500 dark:text-gray-400">
                Desired start
                <input
                  type="datetime-local"
                  value={checkStart}
                  onChange={(e) => setCheckStart(e.target.value)}
                  className="ml-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2 py-1 text-sm text-gray-800 dark:text-gray-100"
                />
              </label>
              <label className="text-xs text-gray-500 dark:text-gray-400">
                Duration
                <select
                  value={durationMin}
                  onChange={(e) => setDurationMin(Number(e.target.value))}
                  className="ml-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2 py-1 text-sm text-gray-800 dark:text-gray-100"
                >
                  <option value={30}>30 min</option>
                  <option value={60}>60 min</option>
                  <option value={90}>90 min</option>
                  <option value={120}>2 hr</option>
                </select>
              </label>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={runAvailability}
                disabled={busy !== null}
                className="rounded bg-gray-800 dark:bg-gray-200 px-3 py-1.5 text-sm font-medium text-white dark:text-gray-900 disabled:opacity-50"
              >
                Check availability
              </button>
              <button
                type="button"
                onClick={runFreeSlot}
                disabled={busy !== null}
                className="rounded bg-gray-800 dark:bg-gray-200 px-3 py-1.5 text-sm font-medium text-white dark:text-gray-900 disabled:opacity-50"
              >
                Find free slot
              </button>
              <button
                type="button"
                onClick={runSuggest}
                disabled={busy !== null}
                className="rounded bg-gray-800 dark:bg-gray-200 px-3 py-1.5 text-sm font-medium text-white dark:text-gray-900 disabled:opacity-50"
              >
                Suggest (§43)
              </button>
            </div>
          </div>

          {avail && (
            <div
              className={`rounded-lg border p-4 text-sm ${
                avail.available
                  ? 'border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/20'
                  : 'border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20'
              }`}
            >
              {avail.available ? (
                <p className="text-green-700 dark:text-green-300">
                  <span className="font-semibold">Free.</span> {fmtDay(avail.start)} at {fmtTime(avail.start)} works.
                </p>
              ) : (
                <>
                  <p className="text-amber-700 dark:text-amber-300">
                    <span className="font-semibold">Conflict.</span>{' '}
                    {avail.conflicts.map((c) => c.title).join(', ')}. Earliest it
                    could fit: {fmtDay(avail.earliest_free_after)} at{' '}
                    {fmtTime(avail.earliest_free_after)}.
                  </p>
                </>
              )}
            </div>
          )}

          {free && (
            <div className="rounded-lg border border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20 p-4 text-sm text-blue-700 dark:text-blue-300">
              {free.found ? (
                <>
                  <span className="font-semibold">Earliest {free.duration_minutes}-min slot:</span>{' '}
                  {fmtDay(free.free_at!)} at {fmtTime(free.free_at!)}.
                </>
              ) : (
                <span className="font-semibold">No {free.duration_minutes}-min slot in the 7-day horizon.</span>
              )}
            </div>
          )}

          {suggest && (
            <div
              className={`rounded-lg border p-4 text-sm ${
                suggest.available
                  ? 'border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300'
                  : 'border-violet-300 dark:border-violet-700 bg-violet-50 dark:bg-violet-900/20 text-violet-700 dark:text-violet-300'
              }`}
            >
              <p className="font-semibold">NerveCenter: {suggest.suggestion}</p>
              {!suggest.available && suggest.conflicts.length > 0 && (
                <p className="mt-1 text-xs opacity-80">
                  Reason: overlaps {suggest.conflicts.map((c) => c.title).join(', ')}.
                </p>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
