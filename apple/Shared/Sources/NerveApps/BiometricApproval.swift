import Foundation

import NerveAuth
import NerveModels

// MARK: - §72 Biometric-bound approval

/// §72: Biometric authorization is tied to an **exact** `PlannedChange`.
///
/// The gate has two properties that matter for safety:
///
/// 1. Biometric authentication must succeed (`BiometricAuthenticator`).
/// 2. The approved `PlannedChange.id` at approval time must match the id of the
///    change submitted in the same call — this prevents replay where a
///    biometric result obtained earlier is reused to approve a different
///    (higher-risk) change.
///
/// Both gates are enforced here so they can be unit-tested together.
///
/// Note: named `BiometricBoundApprovalGate` (not `BiometricApprovalGate`)
/// because `NerveAuth` already exports a `BiometricApprovalGate`; the
/// NerveApps version is the *app-layer* wrapper that binds the approval to
/// an exact `PlannedChange`.
public struct BiometricBoundApprovalResult: Sendable, Hashable {
    public let plannedChangeId: String
    public let deviceID: String
    public let decidedAt: Date
    public let rationale: String?
}

/// Thrown when the biometric-bound gate fails (denied or replay mismatch).
public struct BiometricBoundApprovalError: Error, CustomStringConvertible {
    public let reason: String
    public var description: String { reason }
}

/// Biometric-bound approval gate (§72).
///
/// - `BiometricAuthenticator` must return `true`.
/// - If the caller passes `expectedPlannedChangeId`, it must match
///   `plannedChange.id`; mismatch → reject.
public struct BiometricBoundApprovalGate {
    private let authenticator: any BiometricAuthenticator
    private let deviceID: String

    public init(authenticator: any BiometricAuthenticator, deviceID: String) {
        self.authenticator = authenticator
        self.deviceID = deviceID
    }

    /// Run the biometric prompt; on success, return the biometric approval
    /// result scoped to `plannedChange.id`. If the caller supplies an
    /// `expectedPlannedChangeId` that does not match `plannedChange.id`, this
    /// throws ``BiometricBoundApprovalError`` (replay protection).
    public func authorize(
        plannedChange: PlannedChange,
        expectedPlannedChangeId: String? = nil,
        rationale: String? = nil
    ) async throws -> BiometricBoundApprovalResult {
        let promptReason = promptReason(for: plannedChange)
        let ok = try await authenticator.authenticate(reason: promptReason)
        guard ok else {
            throw BiometricBoundApprovalError(reason: promptReason)
        }

        if let expected = expectedPlannedChangeId, expected != plannedChange.id {
            throw BiometricBoundApprovalError(
                reason: "Planned change id \(plannedChange.id) does not match expected id \(expected)"
            )
        }

        return BiometricBoundApprovalResult(
            plannedChangeId: plannedChange.id,
            deviceID: deviceID,
            decidedAt: Date(),
            rationale: rationale
        )
    }

    private func promptReason(for change: PlannedChange) -> String {
        "Authorize planned change '\(change.title)' (risk \(change.riskLevel)/4)"
    }
}
