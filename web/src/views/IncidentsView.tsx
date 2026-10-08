import { useState, useEffect, type FormEvent } from 'react'
import { incidentsApi, apiFetch, apiErrorFromResponse, ApiError } from '../api/client'

/**
 * Incidents view — round 3 (IN-1 resolved, IN-2).
 *
 * The '+ Report Incident' button submits to the real incident *create* route
 * (`POST /api/incidents`, backend/api/endpoints/incidents.py) added in round 3.
 * A non-2xx response is surfaced verbatim (`status — detail`) via `ApiError`
 * rather than faked as success; a 201 refreshes the list so the new incident
 * renders. The legacy `POST /api/incidents/investigate` route (investigate an
 * *existing* entity) is untouched and remains available to the CLI.
 */

interface Incident {
  id: string
  title: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  status: 'active' | 'resolved' | 'in-progress' | 'closed'
  createdAt: string
  updatedAt: string
  description: string
  impact: string
  tags: string[]
}

const IncidentsView = () => {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<{ status: number; detail: string } | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [reportTitle, setReportTitle] = useState('')
  const [reportDescription, setReportDescription] = useState('')
  const [reportSeverity, setReportSeverity] = useState('high')
  const [formBusy, setFormBusy] = useState(false)
  const [formError, setFormError] = useState<{ status: number; detail: string } | null>(null)
  const [formSuccess, setFormSuccess] = useState(false)

  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        const response = await incidentsApi.list()
        setIncidents(response.data as Incident[])
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
    fetchIncidents()
  }, [])

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900'
      case 'high':
        return 'text-orange-600 dark:text-orange-400 bg-orange-100 dark:bg-orange-900'
      case 'medium':
        return 'text-yellow-600 dark:text-yellow-400 bg-yellow-100 dark:bg-yellow-900'
      case 'low':
        return 'text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900'
      default:
        return 'text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-900'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-red-500'
      case 'resolved':
        return 'bg-green-500'
      case 'in-progress':
        return 'bg-blue-500'
      default:
        return 'bg-gray-500'
    }
  }

  const openForm = () => {
    setShowForm(true)
    setFormError(null)
    setFormSuccess(false)
  }

  const closeForm = () => {
    setShowForm(false)
    setReportTitle('')
    setReportDescription('')
    setReportSeverity('high')
    setFormError(null)
    setFormSuccess(false)
    setFormBusy(false)
  }

  const submitReport = async (e: FormEvent) => {
    e.preventDefault()
    if (!reportTitle.trim()) {
      setFormError({ status: 0, detail: 'Title is required.' })
      return
    }
    setFormBusy(true)
    setFormError(null)
    setFormSuccess(false)
    try {
      // IN-1 (round 3): submit to the real incident *create* route. The
      // backend answers 201 with the new row; any non-2xx (e.g. 409) is
      // surfaced verbatim rather than faked as success.
      const res = await apiFetch('/incidents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: reportTitle.trim(),
          description: reportDescription.trim() || null,
          severity: reportSeverity,
        }),
      })
      if (!res.ok) {
        throw await apiErrorFromResponse(res)
      }
      setFormSuccess(true)
      // Refresh so the newly created incident renders in the list.
      const response = await incidentsApi.list()
      setIncidents(response.data as Incident[])
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
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
        Incidents
      </h1>

      {fetchError && (
        <div
          role="alert"
          data-testid="incidents-error"
          className="p-3 rounded-md bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 text-sm font-medium"
        >
          Failed to load incidents: {fetchError.status} — {fetchError.detail}
        </div>
      )}

      <div className="flex justify-between items-center">
        <div className="text-gray-500 dark:text-gray-400">
          {incidents.filter((i) => i.status === 'active').length} active
          incidents
        </div>
        <button
          onClick={openForm}
          className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg"
        >
          + Report Incident
        </button>
      </div>

      {showForm && (
        <form
          data-testid="incident-form"
          onSubmit={submitReport}
          className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg space-y-4"
        >
          <h3 className="text-xl font-semibold text-gray-800 dark:text-white">
            Report incident
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Creates a new incident via the write route (POST{' '}
            <code className="text-xs">/api/incidents</code>). Non-2xx responses
            are shown as-is.
          </p>

          <div>
            <label
              htmlFor="incident-title"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Title / entity
            </label>
            <input
              id="incident-title"
              data-testid="incident-form-title"
              type="text"
              required
              value={reportTitle}
              onChange={(e) => setReportTitle(e.target.value)}
              placeholder="What is affected?"
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-white"
            />
          </div>

          <div>
            <label
              htmlFor="incident-severity"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Severity
            </label>
            <select
              id="incident-severity"
              data-testid="incident-form-severity"
              value={reportSeverity}
              onChange={(e) => setReportSeverity(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-white"
            >
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
              <option value="critical">critical</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="incident-description"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Description
            </label>
            <textarea
              id="incident-description"
              data-testid="incident-form-description"
              rows={3}
              value={reportDescription}
              onChange={(e) => setReportDescription(e.target.value)}
              placeholder="What happened, and what is the impact?"
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-white"
            />
          </div>

          {formError && (
            <div
              role="alert"
              data-testid="incident-form-error"
              className="p-3 rounded-md bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 text-sm font-medium"
            >
              {formError.status ? `${formError.status} — ` : ''}
              {formError.detail}
            </div>
          )}
          {formSuccess && (
            <div
              role="status"
              data-testid="incident-form-success"
              className="p-3 rounded-md bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300 text-sm font-medium"
            >
              Incident submitted.
            </div>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              data-testid="incident-form-submit"
              disabled={formBusy}
              className="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white px-4 py-2 rounded-lg"
            >
              {formBusy ? 'Submitting…' : 'Submit report'}
            </button>
            <button
              type="button"
              onClick={closeForm}
              className="bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-white px-4 py-2 rounded-lg"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : incidents.length === 0 ? (
        <div
          data-testid="incidents-empty"
          className="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg text-center"
        >
          <p className="text-gray-700 dark:text-gray-300 font-medium">
            No incidents recorded.
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
            Use “+ Report Incident” to file the first incident, or wait for the
            event bus to surface one. Incidents are append-only and never
            deleted.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {incidents.map((incident) => (
            <div
              key={incident.id}
              className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-semibold text-gray-800 dark:text-white">
                    {incident.title}
                  </h3>
                  <div className="flex items-center space-x-2 mt-2">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${getSeverityColor(
                        incident.severity
                      )}`}
                    >
                      {incident.severity}
                    </span>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                        incident.status
                      )} text-white`}
                    >
                      {incident.status}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    Created
                  </div>
                  <div className="text-sm text-gray-800 dark:text-white">
                    {incident.createdAt}
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <div>
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    Description
                  </span>
                  <p className="text-gray-700 dark:text-gray-300 mt-1">
                    {incident.description}
                  </p>
                </div>
                {incident.impact && (
                  <div>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      Impact
                    </span>
                    <p className="text-gray-700 dark:text-gray-300 mt-1">
                      {incident.impact}
                    </p>
                  </div>
                )}
              </div>
              {incident.tags.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <div className="flex flex-wrap gap-2">
                    {incident.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-xs bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export { IncidentsView }
