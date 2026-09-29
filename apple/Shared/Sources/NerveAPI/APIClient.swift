import Foundation

import NerveModels

/// Correlation metadata carried on every NerveCenter request (spec §29:
/// "Every request should carry correlation metadata").
///
/// Serialized as HTTP headers:
///
/// ```text
/// nerve_trace_id
/// nerve_goal_id
/// nerve_task_id
/// nerve_agent_id
/// nerve_agent_run_id
/// verification_policy
/// ```
public struct CorrelationMetadata: Hashable, Sendable {
    /// Distributed trace id linking related requests.
    public var traceId: String

    /// Id of the ``Goal`` driving the work, if any.
    public var goalId: String?

    /// Id of the ``Task`` being executed, if any.
    public var taskId: String?

    /// Id of the agent performing the work, if any.
    public var agentId: String?

    /// Id of the agent run performing the work, if any.
    public var agentRunId: String?

    /// Verification policy identifier, if any.
    public var verificationPolicy: String?

    public init(
        traceId: String,
        goalId: String? = nil,
        taskId: String? = nil,
        agentId: String? = nil,
        agentRunId: String? = nil,
        verificationPolicy: String? = nil
    ) {
        self.traceId = traceId
        self.goalId = goalId
        self.taskId = taskId
        self.agentId = agentId
        self.agentRunId = agentRunId
        self.verificationPolicy = verificationPolicy
    }

    /// Header name → value pairs (only non-nil entries).
    public var headerValues: [String: String] {
        var headers: [String: String] = ["nerve_trace_id": traceId]
        if let goalId { headers["nerve_goal_id"] = goalId }
        if let taskId { headers["nerve_task_id"] = taskId }
        if let agentId { headers["nerve_agent_id"] = agentId }
        if let agentRunId { headers["nerve_agent_run_id"] = agentRunId }
        if let verificationPolicy { headers["verification_policy"] = verificationPolicy }
        return headers
    }
}

/// High-level NerveCenter API client.
///
/// Wraps an ``APITransport`` and adds the shared request policy:
/// - JSON content type,
/// - bearer token (when set),
/// - correlation headers (when set, per spec §29).
public final class APIClient {
    private let transport: any APITransport
    private let baseURL: URL
    private let token: String?

    /// Correlation metadata attached to every request (spec §29).
    public var correlation: CorrelationMetadata?

    /// Create a new client.
    /// - Parameters:
    ///   - baseURL: Base URL for all API endpoints (e.g. `https://nerv.bot/api`).
    ///   - transport: Transport implementation (`URLSessionAPIClient` in
    ///     production, `MockTransport` in tests).
    ///   - token: Optional bearer token sent as `Authorization: Bearer …`.
    ///   - correlation: Optional correlation metadata applied to every request.
    public init(
        baseURL: URL,
        transport: any APITransport,
        token: String? = nil,
        correlation: CorrelationMetadata? = nil
    ) {
        self.baseURL = baseURL
        self.transport = transport
        self.token = token
        self.correlation = correlation
    }

    /// Build a `URLRequest` for a relative API path.
    /// - Parameters:
    ///   - path: API path relative to the base URL (e.g. `/events`).
    ///   - method: HTTP method (default `GET`).
    ///   - query: Optional query items.
    ///   - body: Optional JSON body.
    public func makeRequest(
        path: String,
        method: String = "GET",
        query: [URLQueryItem]? = nil,
        body: Data? = nil
    ) -> URLRequest {
        var components = URLComponents(
            url: baseURL.appendingPathComponent(path),
            resolvingAgainstBaseURL: true
        )
        components?.queryItems = query

        guard let url = components?.url else {
            fatalError("NerveCenter: cannot build URL from base \(baseURL) + \(path)")
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = body

        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        for (name, value) in correlation?.headerValues ?? [:] {
            request.setValue(value, forHTTPHeaderField: name)
        }
        return request
    }

    /// Send a request and decode the JSON response.
    /// - Parameters:
    ///   - path: API path relative to the base URL.
    ///   - method: HTTP method (default `GET`).
    ///   - query: Optional query items.
    ///   - body: Optional JSON body (encoded from any `Encodable`).
    /// - Returns: The decoded response value.
    /// - Throws: ``NerveAPIError`` on transport, HTTP, or decode failure.
    public func send<T: Decodable>(
        path: String,
        method: String = "GET",
        query: [URLQueryItem]? = nil,
        body: (any Encodable)? = nil
    ) async throws -> T {
        var bodyData: Data?
        if let body {
            guard let encoded = NerveJSON.encode(body) else {
                throw NerveAPIError.decoding(underlying: "cannot encode request body")
            }
            bodyData = encoded
        }

        let request = makeRequest(path: path, method: method, query: query, body: bodyData)

        let data: Data = try await withCheckedThrowingContinuation { continuation in
            transport.perform(request: request) { result in
                switch result {
                case .success(let d): continuation.resume(returning: d)
                case .failure(let error): continuation.resume(throwing: error)
                }
            }
        }

        guard let value = NerveJSON.decode(T.self, from: data) else {
            throw NerveAPIError.decoding(underlying: "response is not valid \(T.self)")
        }
        return value
    }

    /// Send a request and discard the (empty) response body.
    public func sendVoid(
        path: String,
        method: String = "POST",
        body: (any Encodable)? = nil
    ) async throws {
        var bodyData: Data?
        if let body {
            guard let encoded = NerveJSON.encode(body) else {
                throw NerveAPIError.decoding(underlying: "cannot encode request body")
            }
            bodyData = encoded
        }
        let request = makeRequest(path: path, method: method, body: bodyData)
        _ = try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Data, Error>) in
            transport.perform(request: request) { result in
                switch result {
                case .success(let d): continuation.resume(returning: d)
                case .failure(let error): continuation.resume(throwing: error)
                }
            }
        }
    }
}
