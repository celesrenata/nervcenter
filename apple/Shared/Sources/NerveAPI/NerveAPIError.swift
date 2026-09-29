import Foundation

/// Errors produced by the NerveCenter API client.
public enum NerveAPIError: Error, CustomStringConvertible {
    /// HTTP status code outside the 2xx range.
    case http(statusCode: Int, data: Data?)
    /// Underlying transport failure (DNS, TLS, connection reset, ...).
    case network(underlying: String)
    /// Response body could not be decoded into the expected type.
    case decoding(underlying: String)
    /// Invalid client configuration (e.g. malformed base URL).
    case invalidConfiguration(String)
    /// The request exceeded its timeout budget.
    case timeout
    /// The server responded with an unexpected body.
    case unexpectedResponse(String)

    public var description: String {
        switch self {
        case .http(let statusCode, _):
            return "HTTP \(statusCode)"
        case .network(let underlying):
            return "Network error: \(underlying)"
        case .decoding(let underlying):
            return "Decoding error: \(underlying)"
        case .invalidConfiguration(let message):
            return "Invalid configuration: \(message)"
        case .timeout:
            return "Request timed out"
        case .unexpectedResponse(let message):
            return "Unexpected response: \(message)"
        }
    }
}
