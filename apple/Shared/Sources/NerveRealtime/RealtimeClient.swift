import Foundation

import NerveModels

/// Abstraction for NerveCenter realtime event streaming.
///
/// Two implementations are provided:
/// - ``WebSocketRealtimeClient`` — `URLSessionWebSocketTask` with
///   exponential-backoff reconnect (primary transport).
/// - ``SSERealtimeClient`` — server-sent-events fallback over plain HTTP.
public protocol RealtimeClient {
    /// Open the stream.
    func connect()

    /// Tear the stream down; no further reconnects are scheduled.
    func disconnect()

    /// Register a handler for a specific `event_type`.
    func subscribe(to eventType: String, handler: @escaping (Event) -> Void)

    /// Remove the handler for a specific `event_type`.
    func unsubscribe(from eventType: String)

    /// Decode and dispatch a raw JSON event payload.
    func handle(rawEvent: Data)
}

/// Base class holding the shared handler dispatch and backoff policy.
open class RealtimeClientBase: NSObject, RealtimeClient {
    let session: URLSession
    let decoder: JSONDecoder
    let maxBackoffSeconds: Double
    let backoffFactor: Double

    private let lock = NSLock()
    private var handlers: [String: (Event) -> Void] = [:]
    private var onEvent: ((Event) -> Void)?
    private var attempts = 0
    private var connected = false
    private var reconnectWork: DispatchWorkItem?

    /// Create the base client.
    public init(
        session: URLSession = .shared,
        onEvent: ((Event) -> Void)? = nil,
        maxBackoffSeconds: Double = 30.0,
        backoffFactor: Double = 2.0
    ) {
        self.session = session
        self.decoder = NerveJSON.decoder
        self.maxBackoffSeconds = maxBackoffSeconds
        self.backoffFactor = backoffFactor
        self.onEvent = onEvent
        super.init()
    }

    /// Whether the stream is currently open.
    open var isConnected: Bool {
        lock.withLock { connected }
    }

    /// Backoff delay (seconds) for the next reconnect attempt given `attempt`
    /// failures so far: `min(max, factor^attempt)`.
    public func backoffDelay(after attempt: Int) -> Double {
        min(maxBackoffSeconds, pow(backoffFactor, Double(max(attempt, 0))))
    }

    /// Register a handler for a specific `event_type`.
    public func subscribe(to eventType: String, handler: @escaping (Event) -> Void) {
        lock.withLock { self.handlers[eventType] = handler }
    }

    /// Remove the handler for a specific `event_type`.
    public func unsubscribe(from eventType: String) {
        lock.withLock { _ = self.handlers.removeValue(forKey: eventType) }
    }

    /// Decode a raw payload into an ``Event`` and dispatch it to handlers.
    /// Unknown payloads are silently ignored (forward-compatibility).
    public func handle(rawEvent: Data) {
        guard let event = try? decoder.decode(Event.self, from: rawEvent) else { return }
        dispatch(event)
    }

    // MARK: - Subclass hooks

    /// Open the underlying transport (called by ``connect()``).
    open func open() {}

    /// Mark the transport closed (called before reconnect scheduling).
    open func markClosed() {}

    /// Mark the transport open and reset the backoff counter.
    open func markOpen() {
        lock.withLock {
            connected = true
            attempts = 0
        }
    }

    // MARK: - Reconnect

    open func connect() {
        lock.withLock {
            guard !connected else { return }
            connected = true
            attempts = 0
        }
        open()
    }

    open func disconnect() {
        lock.withLock {
            connected = false
            reconnectWork?.cancel()
            reconnectWork = nil
            attempts = 0
        }
        markClosed()
    }

    /// Schedule a reconnect after the current backoff delay.
    public func scheduleReconnect() {
        var delay: Double = 0
        var shouldReconnect = false
        lock.withLock {
            guard connected else { shouldReconnect = false; delay = 0; return }
            shouldReconnect = true
            delay = backoffDelay(after: attempts)
            attempts += 1
            reconnectWork?.cancel()
            let work = DispatchWorkItem { [weak self] in
                guard let self else { return }
                self.lock.withLock { self.connected = true }
                self.open()
            }
            reconnectWork = work
        }
        guard shouldReconnect else { return }
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + delay) { [weak self] in
            guard let self else { return }
            self.lock.withLock {
                self.reconnectWork?.cancel()
                self.reconnectWork = nil
            }
        }
        // The work item itself re-opens the transport.
    }

    private func dispatch(_ event: Event) {
        var handler: ((Event) -> Void)?
        var all: ((Event) -> Void)?
        lock.withLock {
            handler = self.handlers[event.eventType]
            all = self.onEvent
        }
        handler?(event)
        all?(event)
    }
}

/// WebSocket-backed realtime client (spec §54: "WebSocket APIs").
public class WebSocketRealtimeClient: RealtimeClientBase {
    private let url: URL
    private var task: URLSessionWebSocketTask?
    private let taskLock = NSLock()

    /// Create a WebSocket realtime client.
    /// - Parameters:
    ///   - url: WebSocket endpoint (`wss://host/ws/events`).
    ///   - session: URLSession (default shared).
    ///   - onEvent: Optional handler invoked for every well-formed event.
    public init(
        url: URL,
        session: URLSession = .shared,
        onEvent: ((Event) -> Void)? = nil
    ) {
        self.url = url
        super.init(session: session, onEvent: onEvent)
    }

    open override func open() {
        let task = session.webSocketTask(with: URLRequest(url: url))
        taskLock.withLock { self.task = task }
        task.resume()
        markOpen()
        receiveNext(from: task)
    }

    open override func markClosed() {
        var closed: URLSessionWebSocketTask?
        taskLock.withLock {
            closed = self.task
            self.task = nil
        }
        closed?.cancel(with: .goingAway, reason: nil)
    }

    /// Disconnect and drop the socket.
    public override func disconnect() {
        super.disconnect()
    }

    private func receiveNext(from task: URLSessionWebSocketTask) {
        task.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure:
                self.taskLock.withLock {
                    // If this is the current socket, schedule a reconnect.
                    if self.task === task {
                        self.task = nil
                    }
                }
                self.scheduleReconnect()
            case .success(let message):
                switch message {
                case .string(let text):
                    if let data = text.data(using: .utf8) {
                        self.handle(rawEvent: data)
                    }
                case .data(let data):
                    self.handle(rawEvent: data)
                @unknown default:
                    break
                }
                // Continue streaming while the socket is current.
                self.taskLock.withLock {
                    if self.task === task {
                        self.receiveNext(from: task)
                    }
                }
            }
        }
    }
}

/// Server-sent-events fallback client (spec: SSE where the server only offers
/// `text/event-stream`).
public class SSERealtimeClient: RealtimeClientBase {
    private let url: URL
    private var streamTask: Swift.Task<Void, Never>?

    /// Create an SSE realtime client.
    /// - Parameters:
    ///   - url: SSE endpoint (`https://host/events/stream`).
    ///   - session: URLSession (default shared).
    ///   - onEvent: Optional handler invoked for every well-formed event.
    public init(
        url: URL,
        session: URLSession = .shared,
        onEvent: ((Event) -> Void)? = nil
    ) {
        self.url = url
        super.init(session: session, onEvent: onEvent)
    }

    open override func open() {
        let task = Swift.Task { [weak self] in
            guard let self else { return }
            do {
                var request = URLRequest(url: self.url)
                request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                let (bytes, response) = try await self.session.bytes(for: request)
                guard let http = response as? HTTPURLResponse,
                      (200..<300).contains(http.statusCode) else {
                    self.scheduleReconnect()
                    return
                }
                self.markOpen()
                var currentData: [String] = []
                for try await line in bytes.lines {
                    if line.isEmpty {
                        // Event boundary: dispatch any accumulated "data:" lines.
                        if !currentData.isEmpty {
                            let payload = currentData.joined(separator: "\n")
                            if let data = payload.data(using: .utf8) {
                                self.handle(rawEvent: data)
                            }
                            currentData.removeAll()
                        }
                        continue
                    }
                    if line.hasPrefix("data:") {
                        currentData.append(String(line.dropFirst(5)).trimmingCharacters(in: .whitespaces))
                    }
                }
                // Stream ended: reconnect.
                self.scheduleReconnect()
            } catch {
                self.scheduleReconnect()
            }
        }
        streamTask = task
    }

    open override func markClosed() {
        streamTask?.cancel()
        streamTask = nil
    }
}
