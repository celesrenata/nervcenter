import Foundation

import NerveAuth
import NerveModels

// MARK: - §71 Device pairing

/// Steps of the §71 device-pairing flow:
///
/// ```text
/// iPhone → pairing challenge → NerveCenter server → device credential → Keychain
/// ```
public enum PairingStep: Int, CaseIterable, Codable, Sendable {
    case requestChallenge
    case awaitingChallenge
    case awaitingCredential
    case stored
    case rejected

    public var description: String {
        switch self {
        case .requestChallenge: return "Requesting pairing challenge"
        case .awaitingChallenge:
            return "Presenting challenge to NerveCenter server"
        case .awaitingCredential:
            return "Server signed the challenge"
        case .stored: return "Device credential stored in Keychain"
        case .rejected: return "Pairing rejected"
        }
    }
}

/// A pairing attempt result (returned from ``PairingFlow/run(using:fetcher:)``).
public struct PairingOutcome: Sendable {
    public let step: PairingStep
    public let credential: Credential?

    public init(step: PairingStep, credential: Credential?) {
        self.step = step
        self.credential = credential
    }
}

public protocol PairingChallengeIssuer: Sendable {
    func requestChallenge() async throws -> PairingChallenge
}

public protocol PairingCredentialFetcher: Sendable {
    func submit(challenge: PairingChallenge) async throws -> PairingResult
}

public enum PairingError: Error {
    case expired
    case missingCredential
}

/// §71 pairing flow: pure, injectable, unit-testable.
///
/// The flow is
///
/// ```text
/// iPhone (initiate)
///   → pairing challenge (server nonce)
///   → NerveCenter server (signs the challenge)
///   → device credential (opaque device-credential pair)
///   → Keychain (via `CredentialStore`)
/// ```
///
/// The platform layer (iOS) wires ``NerveAuth/CredentialStore`` to the
/// SecKeychain; this actor is transport-agnostic so it can be driven from
/// unit tests with ``NerveAuth/InMemoryCredentialStore``.
public actor PairingFlow {
    private let store: any CredentialStore
    private let deviceID: String

    public init(deviceID: String, store: any CredentialStore) {
        self.deviceID = deviceID
        self.store = store
    }

    /// Run the §71 flow and store the resulting device credential.
    ///
    /// - Parameters:
    ///   - issuer: Fetches a fresh ``PairingChallenge`` from the NerveCenter
    ///     server (the "iPhone → pairing challenge" leg).
    ///   - fetcher: Submits the challenge to the server and returns the
    ///     signed ``PairingResult`` with the device credential
    ///     (the "server → device credential" leg).
    /// - Returns: The stored ``PairingOutcome``.
    /// - Throws: ``PairingError/ expired`` if the challenge has expired,
    ///   ``PairingError / missingCredential`` if the server did not return
    ///   a credential, or whatever the issuer/fetcher throws.
    public func run(
        using issuer: any PairingChallengeIssuer,
        fetcher: any PairingCredentialFetcher
    ) async throws -> PairingOutcome {
        // 1. Request a fresh challenge from the NerveCenter server.
        let challenge = try await issuer.requestChallenge()

        // 2. Verify the challenge is still inside its validity window.
        guard challenge.isValid else {
            return PairingOutcome(step: .rejected, credential: nil)
        }

        // 3. Submit the challenge; receive the signed device credential.
        let result = try await fetcher.submit(challenge: challenge)

        // 4. Persist the credential in the Keychain-backed store.
        try await store.storeCredential(result.credential, forDevice: deviceID)

        return PairingOutcome(step: .stored, credential: result.credential)
    }

    /// Load the device's existing credential (for a re-paired device).
    public func loadExisting() async throws -> Credential? {
        try await store.retrieveCredential(forDevice: deviceID)
    }

    /// Delete the stored credential (used by the "unpair" setting).
    public func revoke() async throws {
        try await store.deleteCredential(forDevice: deviceID)
    }
}
