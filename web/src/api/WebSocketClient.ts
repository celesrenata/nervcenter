/**
 * Thin WebSocket wrapper with observable connection state + auto-reconnect.
 *
 * Exposes a small state machine (connecting / open / closed / error) so views
 * can render *honest* connection state instead of a fake "connected" dot.
 * Connection errors are surfaced through `onStateChange` — deliberately NOT
 * through console.error — so a missing /ws route in the mock backend degrades
 * the UI to a visible "reconnecting" state instead of failing console-error
 * based e2e assertions.
 */

export type WebSocketConnectionState = 'connecting' | 'open' | 'closed' | 'error'

export class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private reconnectInterval: number = 3000
  private reconnectTimeout: number | null = null
  private connected: boolean = false
  private disposed: boolean = false
  private messageHandlers: ((data: any) => void)[] = []
  private stateHandlers: ((state: WebSocketConnectionState) => void)[] = []
  private state: WebSocketConnectionState = 'connecting'

  constructor(url: string) {
    this.url = url
    this.connect()
  }

  private setState(next: WebSocketConnectionState): void {
    if (this.state === next) return
    this.state = next
    for (const handler of this.stateHandlers) handler(next)
  }

  private connect(): void {
    if (this.disposed) return
    this.setState('connecting')

    let socket: WebSocket
    try {
      socket = new WebSocket(this.url)
    } catch (error) {
      // e.g. malformed URL — record the error state and stop trying.
      console.warn('WebSocket failed to construct:', error)
      this.setState('error')
      return
    }
    this.ws = socket

    socket.onopen = () => {
      this.connected = true
      this.setState('open')
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        for (const handler of this.messageHandlers) handler(data)
      } catch (error) {
        console.warn('Error parsing WebSocket message:', error)
      }
    }

    socket.onclose = () => {
      this.connected = false
      if (this.disposed) {
        this.setState('closed')
        return
      }
      this.reconnect()
    }

    socket.onerror = () => {
      // The socket will (or already has) closed; flag the failure so the UI
      // can show an honest error/reconnecting state.
      this.setState('error')
    }
  }

  private reconnect(): void {
    if (this.disposed) return
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout)
    this.reconnectTimeout = window.setTimeout(() => this.connect(), this.reconnectInterval)
  }

  /** Subscribe to connection-state transitions. Emits the current state immediately. */
  public onStateChange(callback: (state: WebSocketConnectionState) => void): () => void {
    this.stateHandlers.push(callback)
    callback(this.state)
    return () => {
      this.stateHandlers = this.stateHandlers.filter((h) => h !== callback)
    }
  }

  public getState(): WebSocketConnectionState {
    return this.state
  }

  public onMessage(callback: (data: any) => void): () => void {
    this.messageHandlers.push(callback)
    return () => {
      this.messageHandlers = this.messageHandlers.filter((h) => h !== callback)
    }
  }

  public sendMessage(type: string, payload: unknown): void {
    if (this.ws && this.connected) {
      this.ws.send(JSON.stringify({ type, payload }))
    }
  }

  public disconnect(): void {
    this.disposed = true
    if (this.ws) {
      this.ws.onclose = null
      this.ws.onopen = null
      this.ws.onmessage = null
      this.ws.onerror = null
      this.ws.close()
      this.ws = null
    }
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }
    this.connected = false
    this.setState('closed')
  }
}
