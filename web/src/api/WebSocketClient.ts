export class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private reconnectInterval: number = 3000
  private reconnectTimeout: number | null = null
  private connected: boolean = false
  private messageHandlers: ((data: any) => void)[] = []

  constructor(url: string) {
    this.url = url
    this.connect()
  }

  private connect() {
    this.ws = new WebSocket(this.url)

    this.ws.onopen = () => {
      this.connected = true
      console.log('WebSocket connected')
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        this.messageHandlers.forEach((handler) => handler(data))
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    this.ws.onclose = () => {
      this.connected = false
      console.log('WebSocket disconnected, reconnecting...')
      this.reconnect()
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      this.reconnect()
    }
  }

  private reconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
    }
    this.reconnectTimeout = window.setTimeout(() => {
      this.connect()
    }, this.reconnectInterval)
  }

  public onMessage(callback: (data: any) => void) {
    this.messageHandlers.push(callback)
    return () => {
      this.messageHandlers = this.messageHandlers.filter((h) => h !== callback)
    }
  }

  public sendMessage(type: string, payload: any) {
    if (this.ws && this.connected) {
      this.ws.send(JSON.stringify({ type, payload }))
    }
  }

  public disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }
    this.connected = false
  }
}