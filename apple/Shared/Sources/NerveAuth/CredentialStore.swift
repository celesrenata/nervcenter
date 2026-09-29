import Foundation

/// Protocol for storing and retrieving device credentials.
public protocol CredentialStore {
    /// Store a credential.
    func storeCredential(_ credential: Credential, forDevice deviceID: String) async throws

    /// Retrieve a credential for a device.
    func retrieveCredential(forDevice deviceID: String) async throws -> Credential?

    /// Delete a credential for a device.
    func deleteCredential(forDevice deviceID: String) async throws
}

/// In-memory credential store (default implementation for testing).
public class InMemoryCredentialStore: CredentialStore {
    private var storage: [String: Credential] = [:]

    public init() {}

    public func storeCredential(_ credential: Credential, forDevice deviceID: String) async throws {
        storage[deviceID] = credential
    }

    public func retrieveCredential(forDevice deviceID: String) async throws -> Credential? {
        storage[deviceID]
    }

    public func deleteCredential(forDevice deviceID: String) async throws {
        storage.removeValue(forKey: deviceID)
    }
}

/// A device credential for authentication.
public struct Credential: Codable, Hashable, Sendable {
    /// Unique device identifier.
    public var deviceID: String

    /// The credential value (e.g., JWT, API key, or token).
    public var value: String

    /// When the credential expires (UTC).
    public var expiresAt: Date

    /// Optional scope constraint.
    public var scope: String?

    public init(deviceID: String, value: String, expiresAt: Date, scope: String? = nil) {
        self.deviceID = deviceID
        self.value = value
        self.expiresAt = expiresAt
        self.scope = scope
    }

    /// Check if the credential is still valid.
    public var isValid: Bool {
        expiresAt > Date()
    }
}
