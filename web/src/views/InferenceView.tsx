import { useState, useEffect } from 'react'
import { computeApi, routesApi, modelHistoryApi } from '../api/client'

interface ComputeNode {
  id: string
  hostname: string
  hardware: string
  vram: string
  gpuUtilization: number
  loadedModel: string | null
  tokensPerSec: number
  contextUsage: string | null
  activeCalls: number
  latency: { p50: number; p95: number; p99: number } | null
  failures24h: number
  fallbacks24h: number
}

interface Route {
  routeId: string
  taskType: string
  chain: string[]
  strategy: string
  activeCalls: number
  successRate: number
  avgLatency: number
}

interface ModelHistory {
  model: string
  node: string
  window: string
  avgTokPerSec: number
  p95Latency: number
  successRate: number
  fallbackRate: number
}

interface EmptyStateProps {
  testId: string
  title: string
  body: string
}

/** INF-1: guidance copy for a section that is live but currently empty. */
function EmptyState({ testId, title, body }: EmptyStateProps) {
  return (
    <div
      data-testid={testId}
      className="text-center py-8"
    >
      <p className="text-gray-700 dark:text-gray-300 font-medium">{title}</p>
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 max-w-md mx-auto">
        {body}
      </p>
    </div>
  )
}

const InferenceView = () => {
  const [nodes, setNodes] = useState<ComputeNode[]>([])
  const [routes, setRoutes] = useState<Route[]>([])
  const [history, setHistory] = useState<ModelHistory[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [nodesRes, routesRes, historyRes] = await Promise.all([
          computeApi.list(),
          routesApi.list(),
          modelHistoryApi.list(),
        ])
        setNodes(nodesRes.data)
        setRoutes(routesRes.data)
        setHistory(historyRes.data)
      } catch {
        // Each of the three sections is fetched independently via Promise.all;
        // a fetch failure is already handled by the per-section empty states,
        // so there is nothing further to surface here.
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const getNodeColor = (util: number) => {
    if (util === 0) return 'bg-gray-500'
    if (util < 50) return 'bg-green-500'
    if (util < 80) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  const getStrategyColor = (strategy: string) => {
    switch (strategy) {
      case 'latency-first':
        return 'bg-blue-500'
      case 'quality-first':
        return 'bg-purple-500'
      case 'cost-first':
        return 'bg-green-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
        Inference
      </h1>

      {/* Physical Nodes Section */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
          Physical Nodes
        </h3>
        {loading ? (
          <div className="text-center py-12">Loading...</div>
        ) : nodes.length === 0 ? (
          <EmptyState
            testId="inference-empty-nodes"
            title="No compute nodes reported."
            body="No nodes are currently reporting to the inference layer. Nodes appear here the moment they register and start serving — confirm compute nodes are running and reachable from the API."
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {nodes.map((node) => (
              <div key={node.id} className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-gray-800 dark:text-white">{node.hostname}</h4>
                  <div className={`w-2 h-2 rounded-full ${getNodeColor(node.gpuUtilization)}`} />
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">{node.hardware} • {node.vram}</div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Model:</span>
                  <span className="text-gray-800 dark:text-white">{node.loadedModel || 'Idle'}</span>
                </div>
                <div className="mt-2">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-500 dark:text-gray-400">GPU Usage</span>
                    <span className="text-gray-800 dark:text-white">{node.gpuUtilization}%</span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                    <div
                      className={`h-1.5 rounded-full ${getNodeColor(node.gpuUtilization)}`}
                      style={{ width: `${node.gpuUtilization}%` }}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Tokens/s:</span>
                    <span className="text-gray-800 dark:text-white ml-1">{node.tokensPerSec}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Calls:</span>
                    <span className="text-gray-800 dark:text-white ml-1">{node.activeCalls}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">p95 Lat:</span>
                    <span className="text-gray-800 dark:text-white ml-1">{node.latency?.p95 || 0}ms</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Failures (24h):</span>
                    <span className="text-gray-800 dark:text-white ml-1">{node.failures24h}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Fallbacks (24h):</span>
                    <span className="text-gray-800 dark:text-white ml-1">{node.fallbacks24h}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Context:</span>
                    <span className="text-gray-800 dark:text-white ml-1">{node.contextUsage || 'N/A'}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* OmniRoute Routes Section */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
          OmniRoute Routes
        </h3>
        {loading ? (
          <div className="text-center py-12">Loading...</div>
        ) : routes.length === 0 ? (
          <EmptyState
            testId="inference-empty-routes"
            title="No OmniRoute routes configured."
            body="No routing policies are defined yet. Routes map task types to model chains and appear here once OmniRoute registers a policy for a task type."
          />
        ) : (
          <div className="space-y-3">
            {routes.map((route) => (
              <div key={route.routeId} className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-gray-800 dark:text-white">{route.routeId}</span>
                  <span className={`text-xs px-2 py-1 rounded ${getStrategyColor(route.strategy)} text-white`}>
                    {route.strategy}
                  </span>
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400 mb-2">
                  Chain: {route.chain.join(' → ')}
                </div>
                <div className="flex items-center justify-between text-xs">
                  <div className="flex space-x-3">
                    <span>
                      Calls: <span className="text-gray-800 dark:text-white">{route.activeCalls}</span>
                    </span>
                    <span>
                      Success: <span className="text-gray-800 dark:text-white">{(route.successRate * 100).toFixed(0)}%</span>
                    </span>
                    <span>
                      Latency: <span className="text-gray-800 dark:text-white">{route.avgLatency}ms</span>
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Historical Model Performance Section */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
          Historical Model Performance
        </h3>
        {loading ? (
          <div className="text-center py-12">Loading...</div>
        ) : history.length === 0 ? (
          <EmptyState
            testId="inference-empty-history"
            title="No model history recorded."
            body="Per-model performance samples (tok/s, p95 latency, success/fallback rates) appear here once the inference layer has served traffic. This is an honest empty state, not a failed fetch."
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {history.map((item, idx) => (
              <div key={idx} className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                <div className="font-medium text-gray-800 dark:text-white">{item.model} ({item.node})</div>
                <div className="text-xs text-gray-600 dark:text-gray-400 mb-2">{item.window} window</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Tok/s:</span>
                    <span className="text-gray-800 dark:text-white ml-1">{item.avgTokPerSec}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">p95 Lat:</span>
                    <span className="text-gray-800 dark:text-white ml-1">{item.p95Latency}ms</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Success:</span>
                    <span className="text-gray-800 dark:text-white ml-1">{(item.successRate * 100).toFixed(0)}%</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Fallback:</span>
                    <span className="text-gray-800 dark:text-white ml-1">{(item.fallbackRate * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export { InferenceView }
