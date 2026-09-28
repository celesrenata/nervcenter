import { useState, useEffect } from 'react'
import { goalsApi } from '../api/client'

interface Goal {
  id: string
  name: string
  description: string
  status: 'active' | 'completed' | 'pending' | 'cancelled'
  progress: number
  dueDate: string
}

const GoalsView = () => {
  const [goals, setGoals] = useState<Goal[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchGoals = async () => {
      try {
        const response = await goalsApi.list()
        setGoals(response.data)
      } catch (error) {
        console.error('Error fetching goals:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchGoals()
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-blue-500'
      case 'completed':
        return 'bg-green-500'
      case 'pending':
        return 'bg-yellow-500'
      case 'cancelled':
        return 'bg-gray-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
        Goals
      </h1>

      <div className="flex justify-between items-center">
        <div className="text-gray-500 dark:text-gray-400">
          {goals.length} total goals
        </div>
        <button className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg">
          + New Goal
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {goals.map((goal) => (
            <div
              key={goal.id}
              className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg"
            >
              <div className="flex items-start justify-between mb-4">
                <h3 className="text-xl font-semibold text-gray-800 dark:text-white">
                  {goal.name}
                </h3>
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                    goal.status
                  )} text-white`}
                >
                  {goal.status}
                </span>
              </div>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                {goal.description}
              </p>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">
                    Progress
                  </span>
                  <span className="text-gray-800 dark:text-white">
                    {goal.progress}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      goal.progress === 100
                        ? 'bg-green-500'
                        : 'bg-blue-500'
                    }`}
                    style={{ width: `${goal.progress}%` }}
                  />
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">
                    Due
                  </span>
                  <span className="text-gray-800 dark:text-white">
                    {goal.dueDate}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export { GoalsView }