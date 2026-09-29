import Foundation

/// Optional half-open interval `[validFrom, validTo)` for time-scoped facts.
///
/// Mirrors `schemas.base.TemporalWindow`. Used by entities and relationships
/// to express *when* a fact is or was true, separate from the moment it was
/// observed.
public struct TemporalWindow: Codable, Hashable, Sendable {
    /// Inclusive lower bound of the validity window (UTC).
    public var validFrom: Date?

    /// Exclusive upper bound of the validity window (UTC).
    public var validTo: Date?

    public init(validFrom: Date? = nil, validTo: Date? = nil) {
        self.validFrom = validFrom
        self.validTo = validTo
    }

    /// Whether `at` falls inside the window (window open means `now` is valid).
    public func contains(_ at: Date) -> Bool {
        if let from = validFrom, at < from { return false }
        if let to = validTo, at >= to { return false }
        return true
    }
}
