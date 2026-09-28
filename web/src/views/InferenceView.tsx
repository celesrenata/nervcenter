import { useState, useEffect } from 'react'
import { api } from '../api/client'

interface InferenceRequest {
  id: string
  prompt: string
  model: string
  response?: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  latency: number
  timestamp: string
}

const InferenceView = () => {
  const [requests, setRequests] = useState<InferenceRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [prompt, setPrompt] = useState('')
  const [model, setModel] = useState('claude-3-5-sonnet')
  const [processing, setProcessing] = useState(false)

  useEffect(() => {
    const fetchRequests = async () => {
      try {
        const response = await api.get('/inference/requests')
        setRequests(response.data)
      } catch (error) {
        console.error('Error fetching inference requests:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchRequests()
  }, [])

  const handleGenerate = async () => {
    if (!prompt) return

    setProcessing(true)

    try {
      const response = await api.post('/inference/generate', {
        prompt,
        model,
      })
      setRequests((prev) => [
        {
          id: response.data.id,
          prompt,
          model,
          response: response.data.response,
          status: 'completed',
          latency: response.data.latency,
          timestamp: new Date().toISOString(),
        },
        ...prev,
      ])
      setPrompt('')
    } catch (error) {
      console.error('Error generating response:', error)
    } finally {
      setProcessing(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'processing':
        return 'bg-blue-500'
      case 'completed':
        return 'bg-green-500'
      case 'failed':
        return 'bg-red-500'
      case 'pending':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
        Inference
      </h1>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
          Generate Response
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Prompt
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white min-h-[100px]"
              placeholder="Enter your prompt..."
              disabled={processing}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Model
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              disabled={processing}
            >
              <option value="claude-3-5-sonnet">
                Claude 3.5 Sonnet
              </option>
              <option value="claude-3-opus">Claude 3 Opus</option>
              <option value="claude-3-sonnet">
                Claude 3 Sonnet
              </option>
              <option value="claude-3-haiku">Claude 3 Haiku</option>
            </select>
          </div>
          <button
            onClick={handleGenerate}
            disabled={processing || !prompt}
            className="w-full bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {processing ? 'Generating...' : 'Generate'}
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-semibold text-gray-800 dark:text-white mb-4">
          Recent Requests
        </h3>
        {loading ? (
          <div className="text-center py-12">Loading...</div>
        ) : (
          <div className="space-y-4">
            {requests.map((req) => (
              <div
                key={req.id}
                className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg"
              >
                <div className="flex items-center justify-between mb-2">
                  <span
                    className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                      req.status
                    )} text-white`}
                  >
                    {req.status}
                  </span>
                  <div className="flex items-center space-x-3">
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {req.latency}ms
                    </span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {req.timestamp}
                    </span>
                  </div>
                </div>
                <div className="mb-2">
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    Model:
                  </span>
                  <span className="text-sm text-gray-700 dark:text-gray-300 ml-1">
                    {req.model}
                  </span>
                </div>
                <div className="mb-2">
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    Prompt:
                  </span>
                  <p className="text-sm text-gray-700 dark:text-gray-300 mt-1">
                    {req.prompt}
                  </p>
                </div>
                {req.response && (
                  <div>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      Response:
                    </span>
                    <p className="text-sm text-gray-700 dark:text-gray-300 mt-1">
                      {req.response}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export { InferenceView }