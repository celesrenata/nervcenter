import { useState, useEffect } from 'react'
import { tasksApi } from '../api/client'

interface Task {
  id: string
  name: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  priority: 'low' | 'medium' | 'high' | 'critical'
  goalId?: string
  dependencies: string[]
  estimatedDuration: string
}

const TaskDagView = () => {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const response = await tasksApi.list()
        setTasks(response.data)
      } catch (error) {
        console.error('Error fetching data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchTasks()
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'bg-blue-500'
      case 'completed':
        return 'bg-green-500'
      case 'failed':
        return 'bg-red-500'
      case 'pending':
        return 'bg-yellow-500'
      case 'cancelled':
        return 'bg-gray-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical':
        return 'text-red-600 dark:text-red-400'
      case 'high':
        return 'text-orange-600 dark:text-orange-400'
      case 'medium':
        return 'text-yellow-600 dark:text-yellow-400'
      case 'low':
        return 'text-gray-500 dark:text-gray-400'
      default:
        return 'text-gray-500 dark:text-gray-400'
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
        Task DAG
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-3">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
            {loading ? (
              <div className="text-center py-12">Loading...</div>
            ) : (
              <div className="space-y-4">
                {tasks.map((task) => (
                  <div
                    key={task.id}
                    className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <div className="flex items-center space-x-3">
                          <span className="font-semibold text-gray-800 dark:text-white">
                            {task.name}
                          </span>
                          <span
                            className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                              task.status
                            )} text-white`}
                          >
                            {task.status}
                          </span>
                          <span
                            className={`text-sm font-medium ${getPriorityColor(
                              task.priority
                            )}`}
                          >
                            {task.priority}
                          </span>
                        </div>
                        {task.description && (
                          <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                            {task.description}
                          </p>
                        )}
                      </div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">
                        {task.estimatedDuration}
                      </div>
                    </div>
                    {task.dependencies.length > 0 && (
                      <div className="mt-2">
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          Dependencies:
                        </span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {task.dependencies.map((depId) => (
                            <span
                              key={depId}
                              className="text-xs bg-gray-200 dark:bg-gray-600 px-2 py-1 rounded"
                            >
                              Task #{depId.slice(-3)}
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
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
          Legend
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {[
            'running',
            'completed',
            'failed',
            'pending',
            'cancelled',
          ].map((status) => (
            <div key={status} className="flex items-center">
              <div
                className={`w-3 h-3 rounded-full ${getStatusColor(
                  status
                )} mr-2`}
              />
              <span className="text-sm text-gray-600 dark:text-gray-400 capitalize">
                {status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export { TaskDagView }