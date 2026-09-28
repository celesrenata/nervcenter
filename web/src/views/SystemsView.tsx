import { useState, useEffect } from 'react'
import { systemsApi } from '../api/client'

interface SystemStatus {
  name: string
  status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown'
  version: string
  message: string
  checkedAt: string
}

const SystemsView = () => {
  const [systems, setSystems] = useState<SystemStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchSystems = async () => {
      try {
        const response = await systemsApi.health()
        setSystems(response.data)
      } catch (err) {
        setError('Failed to fetch system status')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchSystems()
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-500'
      case 'unhealthy':
        return 'bg-red-500'
      case 'degraded':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
        Systems
      </h1>

      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : error ? (
        <div className="text-red-500 bg-red-100 dark:bg-red-900 p-4 rounded">
          {error}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {systems.map((system, index) => (
            <div
              key={index}
              className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-semibold text-gray-800 dark:text-white">
                  {system.name}
                </h3>
                <div
                  className={`w-3 h-3 rounded-full ${getStatusColor(
                    system.status
                  )}`}
                />
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">
                    Status
                  </span>
                  <span className="text-gray-800 dark:text-white capitalize">
                    {system.status}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">
                    Version
                  </span>
                  <span className="text-gray-800 dark:text-white">
                    {system.version}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">
                    Message
                  </span>
                  <span className="text-gray-800 dark:text-white">
                    {system.message}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">
                    Last Check
                  </span>
                  <span className="text-gray-800 dark:text-white">
                    {system.checkedAt}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
          Real-time Updates
        </h3>
        <div className="flex items-center space-x-4">
          <div className="flex items-center">
            <div className="w-3 h-3 bg-green-500 rounded-full mr-2" />
            <span className="text-gray-600 dark:text-gray-400">
              WebSocket Connected
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export { SystemsView }