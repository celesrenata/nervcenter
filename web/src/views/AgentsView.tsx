import { useState, useEffect } from 'react'
import { agentsApi } from '../api/client'

interface Agent {
  id: string
  name: string
  type: string
  status: 'active' | 'inactive' | 'error' | 'paused'
  lastHeartbeat: string
  cpuUsage: number
  memoryUsage: number
  tasksCompleted: number
  tasksFailed: number
}

const AgentsView = () => {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const response = await agentsApi.list()
        setAgents(response.data)
      } catch (error) {
        console.error('Error fetching agents:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchAgents()
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-500'
      case 'inactive':
        return 'bg-gray-500'
      case 'error':
        return 'bg-red-500'
      case 'paused':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getProgressColor = (value: number) => {
    if (value < 50) return 'bg-green-500'
    if (value < 80) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
        Agents
      </h1>

      <div className="flex justify-between items-center">
        <div className="text-gray-500 dark:text-gray-400">
          {agents.length} total agents
        </div>
        <button className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg">
          + Add Agent
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-semibold text-gray-800 dark:text-white">
                    {agent.name}
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {agent.type}
                  </p>
                </div>
                <div
                  className={`w-3 h-3 rounded-full ${getStatusColor(
                    agent.status
                  )}`}
                />
              </div>
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-500 dark:text-gray-400">
                      CPU Usage
                    </span>
                    <span className="text-gray-800 dark:text-white">
                      {agent.cpuUsage}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${getProgressColor(
                        agent.cpuUsage
                      )}`}
                      style={{ width: `${agent.cpuUsage}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-500 dark:text-gray-400">
                      Memory Usage
                    </span>
                    <span className="text-gray-800 dark:text-white">
                      {agent.memoryUsage}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${getProgressColor(
                        agent.memoryUsage
                      )}`}
                      style={{ width: `${agent.memoryUsage}%` }}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">
                      Tasks Completed
                    </span>
                    <p className="font-medium text-gray-800 dark:text-white">
                      {agent.tasksCompleted}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">
                      Tasks Failed
                    </span>
                    <p className="font-medium text-gray-800 dark:text-white">
                      {agent.tasksFailed}
                    </p>
                  </div>
                </div>
                <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500 dark:text-gray-400">
                      Last Heartbeat
                    </span>
                    <span className="text-gray-800 dark:text-white">
                      {agent.lastHeartbeat}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export { AgentsView }