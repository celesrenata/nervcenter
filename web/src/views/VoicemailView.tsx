import { useState, useEffect, useCallback, type FormEvent } from 'react'
import { voicemailApi, ApiError } from '../api/client'

/**
 * VoicemailView — the Voicemail plane (prompt2 Phase P2).
 *
 * Shows reconstructed voicemail threads ingested by the macOS Personal Relay
 * (NerveCenter never touches voicemail audio or a transcript model — §14/§15
 * source-side deliverables, out of scope; the relay posts *normalized*
 * events with the transcript already computed). Each thread can produce an
 * AttentionItem, so unread threads also appear on the Now screen (§77). This
 * view is the human side of that link: read the transcript, mark it read
 * (which resolves its AttentionItem), and see a visible Callback badge when a
 * voicemail asks to be called back (§15 example: "Please call us regarding
 * your appointment" → CALLBACK REQUIRED).
 *
 * There is deliberately no reply-drafting here (§77 has no reply drafting for
 * voicemail) — a callback request only flags the thread.
 *
 * API failures surface as an `role="alert"` banner (OV-1 contract) rather
 * than a silent empty state; the empty-inbox case is an honest empty state.
 */

interface Voicemail {
  voicemail_id: string
  thread_id: string
  caller_phone: string
  caller_name: string | null
  transcript: string
  duration_seconds: number
  received_at: string
  read: boolean
  needs_callback: boolean
  callback_reason: string | null
  source?: string
}

interface VoicemailThread {
  thread_id: string
  caller_phone: string
  caller_name: string | null
  voicemail_count: number
  unread: number
  last_transcript: string | null
  last_duration_seconds: number
  last_received_at: string | null
  needs_callback: boolean
  callback_reason: string | null
  attention_id: string | null
  created_at?: string | null
  updated_at?: string | null
}

interface ThreadData {
  thread: VoicemailThread
  voicemails: Voicemail[]
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

function formatWhen(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString()
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '0s'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export function VoicemailView() {
  const [threads, setThreads] = useState<VoicemailThread[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [thread, setThread] = useState<ThreadData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<'ack' | null>(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      const res = await voicemailApi.list()
      if (res.status >= 400) throw new ApiError(res.status, `HTTP ${res.status}`)
      setThreads(res.data as VoicemailThread[])
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const selectThread = useCallback(async (threadId: string) => {
    setSelected(threadId)
    try {
      const res = await voicemailApi.thread(threadId)
      if (res.status >= 400) throw new ApiError(res.status, `HTTP ${res.status}`)
      setThread(res.data as ThreadData)
    } catch (err) {
      setThread(null)
      setError(formatApiError(err))
    }
  }, [])

  const acknowledge = useCallback(async (e: FormEvent) => {
    e.preventDefault()
    if (!selected) return
    setBusy('ack')
    try {
      const res = await voicemailApi.acknowledge(selected)
      if (res.status >= 400) throw new ApiError(res.status, `HTTP ${res.status}`)
      await load()
      await selectThread(selected)
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setBusy(null)
    }
  }, [selected, load, selectThread])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-primary">Voicemail</h1>
        <p className="text-sm text-muted">
          {loading
            ? 'Loading…'
            : `${threads.length} thread${threads.length === 1 ? '' : 's'} · via Personal Relay`}
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
        {/* Thread list */}
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
            Threads
          </h2>
          {loading ? (
            <div className="rounded-lg border border-line p-4 text-sm text-muted">
              Loading voicemails…
            </div>
          ) : threads.length === 0 ? (
            <div className="rounded-lg border border-line p-4 text-sm text-muted">
              No voicemail yet — threads arrive here from the Personal Relay on
              your Mac.
            </div>
          ) : (
            <ul className="space-y-2">
              {threads.map((t) => {
                const who = t.caller_name ?? t.caller_phone
                const active = selected === t.thread_id
                return (
                  <li key={t.thread_id}>
                    <button
                      type="button"
                      onClick={() => selectThread(t.thread_id)}
                      className={`w-full rounded-lg border px-4 py-3 text-left transition-colors ${
                        active
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                          : 'border-line hover:bg-gray-50 dark:hover:bg-gray-800/60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-gray-800 dark:text-gray-100">
                          {who}
                          <span className="ml-2 text-xs font-normal text-gray-400">
                            {t.caller_phone}
                          </span>
                        </span>
                        <div className="flex items-center gap-1.5">
                          {t.needs_callback && (
                            <span
                              className="rounded-full bg-amber-500 px-2 py-0.5 text-xs font-semibold text-white"
                              aria-label="Callback requested"
                            >
                              Callback
                            </span>
                          )}
                          {t.unread > 0 && (
                            <span
                              className="rounded-full bg-blue-600 px-2 py-0.5 text-xs font-semibold text-white"
                              aria-label={`${t.unread} unread`}
                            >
                              {t.unread}
                            </span>
                          )}
                        </div>
                      </div>
                      <p className="mt-1 truncate text-sm text-muted">
                        {t.last_transcript ?? ''}
                      </p>
                      <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                        {formatWhen(t.last_received_at)} ·{' '}
                        {formatDuration(t.last_duration_seconds)}
                      </p>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </section>

        {/* Thread detail */}
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
            Conversation
          </h2>
          {!selected ? (
            <div className="rounded-lg border border-line p-4 text-sm text-muted">
              Select a thread to read it.
            </div>
          ) : !thread ? (
            <div className="rounded-lg border border-line p-4 text-sm text-muted">
              Loading conversation…
            </div>
          ) : (
            <div className="space-y-3">
              {thread.thread.needs_callback && (
                <div
                  role="status"
                  className="rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-3 text-sm text-amber-800 dark:text-amber-200"
                >
                  <p className="font-semibold">Callback required</p>
                  <p className="mt-1">
                    This caller asked to be called back
                    {thread.thread.callback_reason
                      ? ` (matched “${thread.thread.callback_reason}”)`
                      : ''}
                    .
                  </p>
                </div>
              )}
              <ul className="space-y-2">
                {thread.voicemails.map((m) => {
                  return (
                    <li
                      key={m.voicemail_id}
                      className="max-w-full rounded-lg bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm text-gray-800 dark:text-gray-100"
                    >
                      <p className="whitespace-pre-wrap break-words">
                        {m.transcript || '(no transcript)'}
                      </p>
                      <p className="mt-1 text-xs text-gray-400">
                        {m.caller_name ?? m.caller_phone} ·{' '}
                        {formatWhen(m.received_at)} ·{' '}
                        {formatDuration(m.duration_seconds)}
                        {m.needs_callback ? ' · callback requested' : ''}
                      </p>
                    </li>
                  )
                })}
              </ul>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={(e) => acknowledge(e)}
                  disabled={busy !== null}
                  className="rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50"
                >
                  {busy === 'ack' ? 'Marking read…' : 'Mark as read'}
                </button>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
