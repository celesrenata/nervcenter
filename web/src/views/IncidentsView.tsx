import { useState, useEffect } from 'react'
import { api } from '../api/client'

interface Incident {
  id: string
  title: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  status: 'active' | 'resolved' | 'in-progress'
  createdAt: string
  updatedAt: string
  description: string
  impact: string
  tags: string[]
}

const IncidentsView = () => {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        const response = await api.get('/incidents')
        setIncidents(response.data)
      } catch (error) {
        console.error('Error fetching incidents:', error)
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

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
        Incidents
      </h1>

      <div className="flex justify-between items-center">
        <div className="text-gray-500 dark:text-gray-400">
          {incidents.filter((i) => i.status === 'active').length} active
          incidents
        </div>
        <button className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg">
          + Report Incident
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12">Loading...</div>
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