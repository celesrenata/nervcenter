import { useState, useEffect } from 'react'
import { agentsApi, goalsApi, tasksApi, incidentsApi } from '../api/client'

const OverviewView = () => {
  const [stats, setStats] = useState({
    activeGoals: 0,
    activeAgents: 0,
    pendingTasks: 0,
    activeIncidents: 0,
  })

  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [goals, agents, tasks, incidents] = await Promise.all([
          goalsApi.list(),
          agentsApi.list(),
          tasksApi.list(),
          incidentsApi.list(),
        ])
        setStats({
          activeGoals: goals.data.length,
          activeAgents: agents.data.length,
          pendingTasks: tasks.data.length,
          activeIncidents: incidents.data.length,
        })
      } catch (error) {
        console.error('Error fetching stats:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
  }, [])

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">Overview</h1>
      
      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Active Goals</p>
                  <span className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                    {stats.activeGoals}
                  </span>
                </div>
                <div className="text-4xl">🎯</div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Active Agents</p>
                  <span className="text-3xl font-bold text-green-600 dark:text-green-400">
                    {stats.activeAgents}
                  </span>
                </div>
                <div className="text-4xl">🤖</div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Pending Tasks</p>
                  <span className="text-3xl font-bold text-yellow-600 dark:text-yellow-400">
                    {stats.pendingTasks}
                  </span>
                </div>
                <div className="text-4xl">📋</div>
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Active Incidents</p>
                  <span className="text-3xl font-bold text-red-600 dark:text-red-400">
                    {stats.activeIncidents}
                  </span>
                </div>
                <div className="text-4xl">⚠️</div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
              <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
                Recent Goals
              </h3>
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
                  >
                    <p className="font-medium text-gray-800 dark:text-white">
                      Goal {i}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Status: In Progress
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
              <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
                Active Agents
              </h3>
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
                  >
                    <p className="font-medium text-gray-800 dark:text-white">
                      Agent {i}
                    </p>
                    <p className="text-sm text-green-500 dark:text-green-400">
                      Status: Active
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export { OverviewView }