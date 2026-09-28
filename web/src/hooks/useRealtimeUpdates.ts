import { useState, useEffect, useCallback } from 'react'
import { WebSocketClient } from '../api/WebSocketClient'

interface RealtimeState<T> {
  data: T
  loading: boolean
  error: string | null
  lastUpdate: Date | null
}

export function useRealtimeUpdates<T>(url: string, initialData: T) {
  const [state, setState] = useState<RealtimeState<T>>({
    data: initialData,
    loading: true,
    error: null,
    lastUpdate: null,
  })

  const [ws, setWs] = useState<WebSocketClient | null>(null)

  useEffect(() => {
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

    return () => {
      unsubscribe()
      wsClient.disconnect()
    }
  }, [url])

  const refresh = useCallback(() => {
    setState((prev) => ({ ...prev, loading: true }))
  }, [])

  return { ...state, refresh, ws }
}