import Foundation

/// Production ``APITransport`` backed by `URLSession`.
public final class URLSessionAPIClient: APITransport {
    private let session: URLSession

    /// Create a client over the given session (default: `.shared`).
    public init(session: URLSession = .shared) {
        self.session = session
    }

    /// Perform an API request.
    /// - Parameters:
    ///   - request: The configured `URLRequest`.
    ///   - completion: Callback with the raw response body (or error).
    public func perform(request: URLRequest, completion: @escaping (Result<Data, Error>) -> Void) {
        let task = self.session.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(NerveAPIError.network(underlying: error.localizedDescription)))
                return
            }

            guard let http = response as? HTTPURLResponse else {
                completion(.failure(NerveAPIError.unexpectedResponse("non-HTTP response")))
                return
            }

            if !(200..<300).contains(http.statusCode) {
                completion(.failure(NerveAPIError.http(statusCode: http.statusCode, data: data)))
                return
            }

            guard let data = data else {
                completion(.failure(NerveAPIError.unexpectedResponse("empty response body")))
                return
            }

            completion(.success(data))
        }
        task.resume()
    }
}
