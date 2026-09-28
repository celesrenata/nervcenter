import { useState, useEffect } from 'react'

interface TimelineEvent {
  id: string
  timestamp: string
  type: string
  message: string
  severity: 'info' | 'warning' | 'error' | 'success'
}

const TimelineView = () => {
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const sampleEvents: TimelineEvent[] = [
      {
        id: '1',
        timestamp: '2026-09-28T20:30:00Z',
        type: 'agent_start',
        message: 'Agent "data-processor" started successfully',
        severity: 'success',
      },
      {
        id: '2',
        timestamp: '2026-09-28T20:25:00Z',
        type: 'task_complete',
        message: 'Task "data-sync" completed in 45s',
        severity: 'info',
      },
      {
        id: '3',
        timestamp: '2026-09-28T20:20:00Z',
        type: 'goal_progress',
        message: 'Goal "system-optimization" reached 75% completion',
        severity: 'success',
      },
      {
        id: '4',
        timestamp: '2026-09-28T20:15:00Z',
        type: 'incident',
        message: 'High memory usage detected on worker node',
        severity: 'warning',
      },
      {
        id: '5',
        timestamp: '2026-09-28T20:10:00Z',
        type: 'inference',
        message: 'Inference request processed in 120ms',
        severity: 'info',
      },
    ]
    setEvents(sampleEvents)
    setLoading(false)
  }, [])

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'info':
        return 'border-blue-500'
      case 'warning':
        return 'border-yellow-500'
      case 'error':
        return 'border-red-500'
      case 'success':
        return 'border-green-500'
      default:
        return 'border-gray-500'
    }
  }

  const getSeverityBadge = (severity: string) => {
    const colors = {
      info: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
      error: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
      success: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    }
    return colors[severity as keyof typeof colors] || colors.info
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
        Timeline
      </h1>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        {loading ? (
          <div className="text-center py-12">Loading...</div>
        ) : (
          <div className="relative pl-8 border-l-2 border-gray-200 dark:border-gray-700">
            {events.map((event, index) => (
              <div key={index} className="relative mb-6">
                <div className="absolute -left-[41px] top-0">
                  <div
                    className={`w-5 h-5 rounded-full border-2 ${getSeverityColor(
                      event.severity
                    )} bg-white dark:bg-gray-800`}
                  />
                </div>
                <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-800 dark:text-white">
                      {event.type}
                    </span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {event.timestamp}
                    </span>
                  </div>
                  <div className="flex items-center space-x-2 mb-2">
                    <span className={`text-xs px-2 py-1 rounded ${getSeverityBadge(
                      event.severity
                    )}`}>
                      {event.severity}
                    </span>
                  </div>
                  <p className="text-gray-700 dark:text-gray-300">
                    {event.message}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
          Legend
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="flex items-center">
            <div className="w-3 h-3 bg-blue-500 rounded-full mr-2" />
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Info
            </span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 bg-yellow-500 rounded-full mr-2" />
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Warning
            </span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 bg-red-500 rounded-full mr-2" />
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Error
            </span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 bg-green-500 rounded-full mr-2" />
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Success
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export { TimelineView }