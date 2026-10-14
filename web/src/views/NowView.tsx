import { useState, useEffect, useCallback, type FormEvent } from 'react'
import { attentionApi, ApiError, type AttentionCreatePayload } from '../api/client'

/**
 * NowView — the Personal Operations Plane (prompt2 Phase P0).
 *
 * Renders the ranked "what deserves my attention now" queue. The backend
 * (`/api/attention`) is deterministic and explainable: every item carries a
 * 0..1 `priority` and a `why[]` breakdown of the scoring factors. This view
 * surfaces that honestly — the default tab is the NOW bucket, and each card
 * shows *why* it is ranked where it is, not just *what* it is.
 *
 * The list, the create form, and the resolve/snooze/suppress actions all
 * render real backend state; failures surface as an `role="alert"` banner
 * (OV-1 contract) rather than a silent empty state.
 */

const STATUSES = ['NOW', 'TODAY', 'SOON', 'WAITING_ON', 'FYI', 'SUPPRESSED', 'RESOLVED'] as const
type Status = (typeof STATUSES)[number]

interface AttentionItem {
  attention_id: string
  reason: string
  priority: number
  urgency: number
  importance: number
  due: string | null
  entities: string[]
  sources: string[]
  suggested_action: string | null
  status: string
  why: string[]
  created_at?: string
  updated_at?: string
}

/** Render an API failure as `<status> — <detail>` (OV-1 contract). */
function formatApiError(err: unknown): string {
  const e = err as { status?: number; detail?: string; message?: string } | null
  if (e && typeof e.status === 'number' && typeof e.detail === 'string') {
    return `${e.status} — ${e.detail}`
  }
  if (e && typeof e.message === 'string' && e.message) return e.message
  return 'Request failed'
}

/** Convert an ISO timestamp to a compact local label, or null. */
function formatDue(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const now = Date.now()
  const hours = (d.getTime() - now) / 3_600_000
  if (Math.abs(hours) < 1) {
    return hours < 0 ? `overdue ${Math.round(Math.abs(hours))}h` : 'due now'
  }
  if (Math.abs(hours) < 48) {
    return `${hours < 0 ? 'overdue ' : ''}in ${Math.round(Math.abs(hours))}h`
  }
  return d.toLocaleString()
}

/** Priority → accent class bucket (visual rank signal, not data). */
function priorityAccent(p: number): string {
  if (p >= 0.9) return 'bg-red-100 dark:bg-red-900/40 border-red-300 dark:border-red-700 text-red-700 dark:text-red-300'
  if (p >= 0.7) return 'bg-amber-100 dark:bg-amber-900/40 border-amber-300 dark:border-amber-700 text-amber-700 dark:text-amber-300'
  if (p >= 0.4) return 'bg-blue-100 dark:bg-blue-900/40 border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300'
  return 'bg-gray-100 dark:bg-gray-900/60 border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-300'
}

export function NowView() {
  const [status, setStatus] = useState<Status>('NOW')
  const [items, setItems] = useState<AttentionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  // Create-form state
  const [draftReason, setDraftReason] = useState('')
  const [draftAction, setDraftAction] = useState('')
  const [draftUrgency, setDraftUrgency] = useState(0.5)
  const [draftImportance, setDraftImportance] = useState(0.5)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const load = useCallback(async (nextStatus: Status) => {
    setLoading(true)
    setError(null)
    try {
      const res = await attentionApi.list(nextStatus)
      if (res.status >= 400) throw new ApiError(res.status, `HTTP ${res.status}`)
      setItems(((res.data ?? []) as unknown as AttentionItem[]).sort((a, b) => b.priority - a.priority))
    } catch (err) {
      setError(formatApiError(err))
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(status)
  }, [status, load])

  const doAction = useCallback(
    async (id: string, action: 'resolve' | 'snooze' | 'suppress') => {
      try {
        await attentionApi.action(id, action)
        await load(status)
      } catch (err) {
        setError(formatApiError(err))
      }
    },
    [status, load],
  )

  const onCreate = useCallback(
    async (e: FormEvent) => {
      e.preventDefault()
      if (!draftReason.trim()) {
        setCreateError('A reason is required.')
        return
      }
      setCreating(true)
      setCreateError(null)
      try {
        const payload: AttentionCreatePayload = {
          reason: draftReason.trim(),
          urgency: draftUrgency,
          importance: draftImportance,
          suggested_action: draftAction.trim() || null,
        }
        const res = await attentionApi.create(payload)
        if (res.status >= 400) throw new ApiError(res.status, `HTTP ${res.status}`)
        setDraftReason('')
        setDraftAction('')
        setDraftUrgency(0.5)
        setDraftImportance(0.5)
        await load(status)
      } catch (err) {
        setCreateError(formatApiError(err))
      } finally {
        setCreating(false)
      }
    },
    [draftReason, draftAction, draftUrgency, draftImportance, status, load],
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-primary">Now</h1>
        <p className="text-sm text-muted">
          {loading ? 'Loading…' : `${items.length} ${status.toLowerCase()} item${items.length === 1 ? '' : 's'}`}
        </p>
      </div>

      {/* Status filter */}
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Attention status">
        {STATUSES.map((s) => (
          <button
            key={s}
            type="button"
            role="tab"
            aria-selected={status === s}
            onClick={() => setStatus(s)}
            className={`px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors ${
              status === s
                ? 'bg-blue-600 border-blue-600 text-white'
                : 'bg-elevated border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {error && (
        <div
          role="alert"
          className="text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/40 border border-red-300 dark:border-red-700 p-4 rounded-lg"
        >
          <p className="font-semibold">Attention feed unavailable</p>
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Ranked queue */}
      {!loading && !error && items.length === 0 && (
        <div className="bg-elevated p-8 rounded-lg shadow-lg text-center">
          <p className="text-gray-600 dark:text-gray-300">
            Nothing in the <span className="font-semibold">{status}</span> bucket right now.
          </p>
        </div>
      )}

      <ul className="space-y-4" aria-live="polite">
        {items.map((item) => (
          <li
            key={item.attention_id}
            className="bg-elevated p-5 rounded-lg shadow-lg"
            data-testid={`attention-${item.attention_id}`}
          >
            <div className="flex items-start gap-4">
              {/* Priority badge */}
              <div
                className={`shrink-0 w-16 h-16 flex flex-col items-center justify-center rounded-lg border ${priorityAccent(
                  item.priority,
                )}`}
                aria-label={`priority ${item.priority.toFixed(2)}`}
              >
                <span className="text-xl font-bold leading-none">{(item.priority * 100).toFixed(0)}</span>
                <span className="text-[10px] uppercase tracking-wide opacity-70">priority</span>
              </div>

              {/* Body */}
              <div className="min-w-0 flex-1">
                <p className="text-lg font-semibold text-gray-900 dark:text-white break-words">
                  {item.reason}
                </p>

                {item.suggested_action && (
                  <p className="mt-1 text-sm text-gray-700 dark:text-gray-200">
                    <span className="font-medium text-blue-700 dark:text-blue-400">Suggested:</span>{' '}
                    {item.suggested_action}
                  </p>
                )}

                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                  <span>urgency {item.urgency.toFixed(2)}</span>
                  <span>importance {item.importance.toFixed(2)}</span>
                  {item.due && <span className="font-medium">due {formatDue(item.due)}</span>}
                  {item.sources.length > 0 && <span>sources: {item.sources.join(', ')}</span>}
                  {item.entities.length > 0 && <span>entities: {item.entities.join(', ')}</span>}
                </div>

                {/* Why it's ranked here */}
                <div className="mt-3">
                  <button
                    type="button"
                    onClick={() => setExpanded((prev) => ({ ...prev, [item.attention_id]: !prev[item.attention_id] }))}
                    className="text-xs font-medium text-muted hover:text-gray-700 dark:hover:text-gray-200"
                  >
                    {expanded[item.attention_id] ? 'Hide why' : 'Why this rank'}
                  </button>
                  {expanded[item.attention_id] && (
                    <ul className="mt-1 list-disc list-inside text-xs text-gray-600 dark:text-gray-300 space-y-0.5">
                      {(item.why ?? []).map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="shrink-0 flex flex-col gap-2">
                <button
                  type="button"
                  onClick={() => doAction(item.attention_id, 'resolve')}
                  className="text-sm px-3 py-1.5 rounded-md bg-green-600 hover:bg-green-700 text-white font-medium"
                >
                  Resolve
                </button>
                <button
                  type="button"
                  onClick={() => doAction(item.attention_id, 'snooze')}
                  className="text-sm px-3 py-1.5 rounded-md bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-100 font-medium"
                >
                  Snooze
                </button>
                <button
                  type="button"
                  onClick={() => doAction(item.attention_id, 'suppress')}
                  className="text-sm px-3 py-1.5 rounded-md bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300"
                >
                  Suppress
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      {/* Create */}
      <form
        onSubmit={onCreate}
        className="bg-elevated p-5 rounded-lg shadow-lg space-y-4"
        aria-label="Add an attention item"
      >
        <h2 className="text-lg font-semibold text-primary">Add to the queue</h2>
        {createError && (
          <div role="alert" className="text-sm text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/40 p-3 rounded-lg">
            {createError}
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="block md:col-span-2">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Reason *</span>
            <input
              type="text"
              value={draftReason}
              onChange={(e) => setDraftReason(e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
              placeholder="e.g. Sign the NDA before the client call"
              data-testid="now-reason-input"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Suggested action</span>
            <input
              type="text"
              value={draftAction}
              onChange={(e) => setDraftAction(e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
              placeholder="e.g. Sign it in DocuSign"
            />
          </label>
          <div className="grid grid-cols-2 gap-4">
            <label className="block">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                Urgency ({draftUrgency.toFixed(2)})
              </span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={draftUrgency}
                onChange={(e) => setDraftUrgency(Number(e.target.value))}
                className="mt-2 w-full"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                Importance ({draftImportance.toFixed(2)})
              </span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={draftImportance}
                onChange={(e) => setDraftImportance(Number(e.target.value))}
                className="mt-2 w-full"
              />
            </label>
          </div>
        </div>
        <button
          type="submit"
          disabled={creating}
          className="text-sm font-medium px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white"
        >
          {creating ? 'Adding…' : 'Add item'}
        </button>
      </form>
    </div>
  )
}
