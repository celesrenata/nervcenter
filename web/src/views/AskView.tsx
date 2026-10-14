import { useState, useEffect } from 'react'
import { askApi } from '../api/client'

interface EvidenceItem {
  statement: string
  type: 'FACT' | 'HYPOTHESIS' | 'OBSERVATION' | 'CLAIM' | 'DERIVED_FACT' | 'RECOMMENDATION'
  confidence: number
  evidence: string[]
}

interface AskResponse {
  answer: string
  confidence: number
  facts: EvidenceItem[]
  hypotheses: EvidenceItem[]
  reasoning?: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  provenance?: {
    facts: EvidenceItem[]
    hypotheses: EvidenceItem[]
    reasoning?: string
  }
}

const AskView = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const initialMessages: ChatMessage[] = [
      {
        id: '1',
        role: 'assistant',
        content: 'Hello! I am NerveCenter. How can I help you today?',
        timestamp: new Date().toISOString(),
      },
    ]
    setMessages(initialMessages)
  }, [])

  const handleSendMessage = async () => {
    if (!input.trim()) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await askApi.post(input)
      const data = response.data as (AskResponse & {
        accepted?: boolean
        executed?: boolean
        detail?: string
      }) | null

      // The backend answers either with a full answer payload (200) or an
      // accepted-but-not-executed ack (202, no `answer` field). Render
      // whichever shape actually arrived instead of crashing on missing
      // fields.
      const content =
        data && typeof data.answer === 'string' && data.answer.length > 0
          ? data.answer
          : data && data.accepted === true
            ? `Request accepted (execution: ${
                data.executed ? 'completed' : 'pending'
              }). ${data.detail || ''}`.trim()
            : 'Sorry, I encountered an error processing your request.'

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content,
        timestamp: new Date().toISOString(),
        provenance:
          data && Array.isArray(data.facts)
            ? {
                facts: data.facts,
                hypotheses: Array.isArray(data.hypotheses) ? data.hypotheses : [],
                reasoning:
                  typeof data.confidence === 'number'
                    ? `Confidence: ${(data.confidence * 100).toFixed(0)}%`
                    : undefined,
              }
            : undefined,
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request.',
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] space-y-6">
      <h1 className="text-3xl font-bold text-primary">
        Ask NerveCenter
      </h1>

      <div className="flex-1 bg-elevated rounded-lg shadow-lg overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              <div
                className={`max-w-[85%] p-4 rounded-lg shadow ${
                  message.role === 'user'
                    ? 'bg-blue-500 text-white'
                    : 'bg-hover text-primary'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                <p className="text-xs mt-2 opacity-70">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </p>

                {/* Provenance section */}
                {message.provenance && message.provenance.facts.length > 0 && (
                  <div className={`mt-3 pt-3 border-t ${message.role === 'user' ? 'border-blue-300' : 'border-gray-400'}`}>
                    <div className="text-xs font-semibold mb-2">Provenance</div>
                    <div className="space-y-2">
                      {message.provenance.facts.map((fact, idx) => (
                        <div key={idx} className="text-xs">
                          <span className="text-green-600 dark:text-green-400 font-semibold">✓ FACT</span>{' '}
                          <span className="opacity-80">"{fact.statement}"</span>
                          <div className="text-xs opacity-70 mt-0.5">
                            Confidence: {fact.confidence * 100}% | Evidence: {fact.evidence.join(', ')}
                          </div>
                        </div>
                      ))}
                      {message.provenance.hypotheses.map((hypo, idx) => (
                        <div key={idx} className="text-xs">
                          <span className="text-yellow-600 dark:text-yellow-400 font-semibold">❓ HYPOTHESIS</span>{' '}
                          <span className="opacity-80">"{hypo.statement}"</span>
                          <div className="text-xs opacity-70 mt-0.5">
                            Confidence: {hypo.confidence * 100}% | Evidence: {hypo.evidence.join(', ')}
                          </div>
                        </div>
                      ))}
                      {message.provenance.reasoning && (
                        <div className="text-xs opacity-70 mt-2 pt-2 border-t border-gray-300 dark:border-gray-600">
                          <span className="font-semibold">Reasoning:</span> {message.provenance.reasoning}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
        <div className="p-4 border-t border-line">
          <div className="flex space-x-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') handleSendMessage()
              }}
              placeholder="Type your message..."
              className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              disabled={loading}
            />
            <button
              onClick={handleSendMessage}
              disabled={loading || !input.trim()}
              className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? '...' : 'Send'}
            </button>
          </div>
        </div>
      </div>

      <div className="bg-elevated rounded-lg shadow-lg p-6">
        <h3 className="text-lg font-semibold text-primary mb-4">
          Quick Questions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            'What are my active goals?',
            'Show me recent incidents',
            'What agents are running?',
            'List pending tasks',
          ].map((question, index) => (
            <button
              key={index}
              onClick={() => setInput(question)}
              className="text-left px-4 py-3 bg-hover rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
            >
              <p className="text-sm text-gray-700 dark:text-gray-300">
                {question}
              </p>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export { AskView }
