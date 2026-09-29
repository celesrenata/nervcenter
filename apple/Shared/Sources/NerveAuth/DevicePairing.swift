import Foundation

import NerveModels

/// Device pairing state per spec §71.
public enum PairingState: String, Codable, Sendable {
    case pending
    case authenticated
    case rejected
}

/// A pairing challenge issued during device registration.
public struct PairingChallenge: Codable, Hashable, Sendable {
    /// Unique challenge identifier.
    public var id: String

    /// The challenge value (nonce).
    public var nonce: String

    /// When the challenge expires (UTC).
    public var expiresAt: Date

    /// Optional device hint.
    public var deviceHint: String?

    public init(id: String, nonce: String, expiresAt: Date, deviceHint: String? = nil) {
        self.id = id
        self.nonce = nonce
        self.expiresAt = expiresAt
        self.deviceHint = deviceHint
    }

    /// Check if the challenge is still valid.
    public var isValid: Bool {
        expiresAt > Date()
    }
}

/// Result of a pairing operation.
public struct PairingResult: Codable, Hashable, Sendable {
    /// The authenticated device's credential.
    public var credential: Credential

    /// Pairing metadata.
    public var metadata: [String: AnyCodable]

    public init(credential: Credential, metadata: [String: AnyCodable] = [:]) {
        self.credential = credential
        self.metadata = metadata
    }
}
