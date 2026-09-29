import Foundation

/// In-memory ``APITransport`` for unit tests.
///
/// Records every call and returns canned responses, so tests can assert on
/// the exact `URLRequest` (URL, method, headers, body) the client produced.
public final class MockTransport: APITransport {
    /// A single recorded call and its completion handler.
    public struct Call {
        public let request: URLRequest
        public let completion: (Result<Data, Error>) -> Void
    }

    /// All calls made through this transport, in order.
    public private(set) var calls: [Call] = []

    /// Optional fixed response used for every request.
    public var fixedResponse: Result<Data, Error>?

    /// Optional per-prefix response handlers; the first prefix that matches
    /// the request URL wins.
    public var responseHandlers: [String: (URLRequest) -> Result<Data, Error>] = [:]

    public init() {}

    /// Perform an API request: records the call, then returns a canned response.
    public func perform(request: URLRequest, completion: @escaping (Result<Data, Error>) -> Void) {
        calls.append(Call(request: request, completion: completion))

        if let fixed = fixedResponse {
            completion(fixed)
            return
        }
        if let url = request.url?.absoluteString {
            for (prefix, handler) in responseHandlers where url.hasPrefix(prefix) {
                completion(handler(request))
                return
            }
        }
        completion(.success(Data()))
    }

    /// The most recent call, if any.
    public var lastCall: Call? { calls.last }

    /// The number of recorded calls.
    public var callCount: Int { calls.count }

    /// Clear all recorded state.
    public func reset() {
        calls.removeAll()
        fixedResponse = nil
        responseHandlers.removeAll()
    }
}
