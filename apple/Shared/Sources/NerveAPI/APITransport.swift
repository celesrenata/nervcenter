import Foundation

/// Transport abstraction for NerveCenter API requests.
///
/// `URLSessionAPIClient` provides the production transport; `MockTransport`
/// provides an in-memory transport for tests.
public protocol APITransport: Sendable {
    /// Perform an API request.
    /// - Parameters:
    ///   - request: The configured `URLRequest`.
    ///   - completion: Callback with the raw response body (or error).
    func perform(request: URLRequest, completion: @escaping (Result<Data, Error>) -> Void)
}
