import { useState, useEffect } from 'react'
import { decisionsApi } from '../api/client'

interface Decision {
  id: string
  title: string
  status: 'proposed' | 'approved' | 'rejected' | 'implemented'
  createdAt: string
  updatedAt: string
  description: string
  rationale: string
  impact: string
  approvers: string[]
  tags: string[]
}

const DecisionsView = () => {
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchDecisions = async () => {
      try {
        const response = await decisionsApi.list()
        setDecisions(response.data)
      } catch (error) {
        console.error('Error fetching decisions:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchDecisions()
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'proposed':
        return 'bg-yellow-500'
      case 'approved':
        return 'bg-green-500'
      case 'rejected':
        return 'bg-red-500'
      case 'implemented':
        return 'bg-blue-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
        Decisions
      </h1>

      <div className="flex justify-between items-center">
        <div className="text-gray-500 dark:text-gray-400">
          {decisions.length} total decisions
        </div>
        <button className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg">
          + New Decision
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : (
        <div className="space-y-4">
          {decisions.map((decision) => (
            <div
              key={decision.id}
              className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-semibold text-gray-800 dark:text-white">
                    {decision.title}
                  </h3>
                  <div className="flex items-center space-x-2 mt-2">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                        decision.status
                      )} text-white`}
                    >
                      {decision.status}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    Created
                  </div>
                  <div className="text-sm text-gray-800 dark:text-white">
                    {decision.createdAt}
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <div>
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    Description
                  </span>
                  <p className="text-gray-700 dark:text-gray-300 mt-1">
                    {decision.description}
                  </p>
                </div>
                {decision.rationale && (
                  <div>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      Rationale
                    </span>
                    <p className="text-gray-700 dark:text-gray-300 mt-1">
                      {decision.rationale}
                    </p>
                  </div>
                )}
                {decision.impact && (
                  <div>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      Impact
                    </span>
                    <p className="text-gray-700 dark:text-gray-300 mt-1">
                      {decision.impact}
                    </p>
                  </div>
                )}
              </div>
              {decision.tags.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <div className="flex flex-wrap gap-2">
                    {decision.tags.map((tag) => (
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

export { DecisionsView }
