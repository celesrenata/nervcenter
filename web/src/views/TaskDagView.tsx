import { useState, useEffect } from 'react'
import { tasksApi } from '../api/client'

interface Task {
  task_id: string
  title: string
  description: string
  state: 'PENDING' | 'READY' | 'RUNNING' | 'BLOCKED' | 'VERIFYING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'
  priority: number
  dependencies: string[]
  capabilities: string[]
  estimatedDuration?: string
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

  const getStatusColor = (state: string) => {
    switch (state) {
      case 'PENDING':
        return 'bg-yellow-500'
      case 'READY':
        return 'bg-blue-500'
      case 'RUNNING':
        return 'bg-green-500'
      case 'BLOCKED':
        return 'bg-orange-500'
      case 'VERIFYING':
        return 'bg-purple-500'
      case 'SUCCEEDED':
        return 'bg-green-500'
      case 'FAILED':
        return 'bg-red-500'
      case 'CANCELLED':
        return 'bg-gray-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getPriorityColor = (priority: number) => {
    if (priority >= 90) return 'text-red-600 dark:text-red-400'
    if (priority >= 70) return 'text-orange-600 dark:text-orange-400'
    if (priority >= 50) return 'text-yellow-600 dark:text-yellow-400'
    return 'text-gray-500 dark:text-gray-400'
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
        Task DAG
      </h1>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-4 mb-6">
        <div className="flex flex-wrap gap-4">
          {['PENDING', 'READY', 'RUNNING', 'BLOCKED', 'VERIFYING', 'SUCCEEDED', 'FAILED', 'CANCELLED'].map((state) => (
            <div key={state} className="flex items-center">
              <div className={`w-3 h-3 rounded-full ${getStatusColor(state)} mr-2`} />
              <span className="text-sm text-gray-700 dark:text-gray-300">{state}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-3">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
            {loading ? (
              <div className="text-center py-12">Loading...</div>
            ) : (
              <div className="space-y-4">
                {tasks.map((task) => (
                  <div
                    key={task.task_id}
                    className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg border-l-4"
                    style={{ borderLeftColor: getStatusColor(task.state) }}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <div className="flex items-center space-x-3">
                          <span className="font-semibold text-gray-800 dark:text-white">
                            {task.title}
                          </span>
                          <span
                            className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                              task.state
                            )} text-white`}
                          >
                            {task.state}
                          </span>
                          <span
                            className={`text-sm font-medium ${getPriorityColor(
                              task.priority
                            )}`}
                          >
                            P{task.priority}
                          </span>
                        </div>
                        {task.description && (
                          <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                            {task.description}
                          </p>
                        )}
                      </div>
                      {task.estimatedDuration && (
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          Est: {task.estimatedDuration}
                        </div>
                      )}
                    </div>
                    {task.dependencies.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-gray-300 dark:border-gray-600">
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
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
          {[
            'PENDING',
            'READY',
            'RUNNING',
            'BLOCKED',
            'VERIFYING',
            'SUCCEEDED',
            'FAILED',
            'CANCELLED',
          ].map((state) => (
            <div key={state} className="flex items-center">
              <div
                className={`w-3 h-3 rounded-full ${getStatusColor(
                  state
                )} mr-2`}
              />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {state}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export { TaskDagView }
