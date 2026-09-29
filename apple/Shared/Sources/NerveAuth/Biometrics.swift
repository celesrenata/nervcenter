import Foundation

/// Biometric / device-credential authorization hook (spec §72:
/// "Sensitive mobile operations should require biometric authorization where
/// appropriate").
///
/// The app target maps this to `LocalAuthentication` (`LAContext`); the shared
/// SDK stays dependency-free and testable with ``InMemoryBiometricAuthenticator``.
public protocol BiometricAuthenticator {
    /// Present the biometric prompt and report the result.
    /// - Parameter reason: User-facing reason string for the prompt.
    /// - Returns: `true` when the user is authenticated.
    func authenticate(reason: String) async throws -> Bool
}

/// Test/dry-run authenticator.
public final class InMemoryBiometricAuthenticator: BiometricAuthenticator {
    /// Scripted result returned by every `authenticate` call.
    public var result: Bool

    /// Number of authentication requests made.
    public private(set) var requestCount = 0

    public init(result: Bool = true) {
        self.result = result
    }

    public func authenticate(reason: String) async throws -> Bool {
        requestCount += 1
        return result
    }
}

/// Gate that requires biometric approval before a sensitive operation runs.
public struct BiometricApprovalGate {
    private let authenticator: any BiometricAuthenticator

    public init(authenticator: any BiometricAuthenticator) {
        self.authenticator = authenticator
    }

    /// Require biometric approval, then run the operation.
    /// - Parameters:
    ///   - reason: Why the operation needs biometric approval.
    ///   - operation: The sensitive operation to perform.
    /// - Returns: The operation's result.
    /// - Throws: ``BiometricError.denied`` when the user declines.
    public func requireApproval<T>(
        reason: String,
        operation: () async throws -> T
    ) async throws -> T {
        let ok = try await authenticator.authenticate(reason: reason)
        guard ok else { throw BiometricError.denied(reason: reason) }
        return try await operation()
    }
}

/// Errors produced by the biometric gate.
public enum BiometricError: Error, CustomStringConvertible {
    /// The user denied the biometric prompt.
    case denied(reason: String)
    /// The authenticator failed (e.g. unavailable hardware).
    case unavailable(underlying: String)

    public var description: String {
        switch self {
        case .denied(let reason):
            return "Biometric approval denied: \(reason)"
        case .unavailable(let underlying):
            return "Biometric authentication unavailable: \(underlying)"
        }
    }
}
