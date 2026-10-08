import { useState, useEffect, useCallback } from 'react'
import { WebSocketClient, WebSocketConnectionState } from '../api/WebSocketClient'

interface RealtimeState<T> {
  data: T
  loading: boolean
  error: string | null
  lastUpdate: Date | null
}

/**
 * Subscribe to a realtime update channel over WebSocket.
 *
 * `enabled` (default true) gates the socket: when false, no WebSocket is
 * opened and `connection` stays 'closed' — use it to avoid opening a socket
 * against a route the backend does not serve.
 *
 * `connection` mirrors the underlying socket state machine
 * (connecting/open/closed/error) so views can render an honest status
 * indicator with text instead of a bare colored dot.
 */
export function useRealtimeUpdates<T>(url: string, initialData: T, enabled: boolean = true) {
  const [state, setState] = useState<RealtimeState<T>>({
    data: initialData,
    loading: true,
    error: null,
    lastUpdate: null,
  })

  const [ws, setWs] = useState<WebSocketClient | null>(null)
  const [connection, setConnection] = useState<WebSocketConnectionState>('closed')

  useEffect(() => {
    if (!enabled) {
      setConnection('closed')
      setWs(null)
      return
    }

    const wsClient = new WebSocketClient(url)
    setWs(wsClient)

    const handleUpdate = (data: any) => {
      if (data.type === 'update') {
        setState((prev) => ({
          ...prev,
          data: data.payload,
          loading: false,
          lastUpdate: new Date(),
        }))
      } else if (data.type === 'error') {
        setState((prev) => ({
          ...prev,
          error: data.payload.message,
          loading: false,
        }))
      }
    }

    const unsubscribe = wsClient.onMessage(handleUpdate)
    const unsubscribeState = wsClient.onStateChange(setConnection)

    return () => {
      unsubscribe()
      unsubscribeState()
      wsClient.disconnect()
    }
  }, [url, enabled])

  const refresh = useCallback(() => {
    setState((prev) => ({ ...prev, loading: true }))
  }, [])

  return { ...state, connection, refresh, ws }
}
