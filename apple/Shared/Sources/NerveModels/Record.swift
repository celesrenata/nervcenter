import Foundation

/// Base shape of every NerveCenter persisted record.
///
/// Mirrors `schemas.base.Record` (Pydantic v2). Provides the common identity,
/// provenance, and integrity fields:
///
/// - ``id`` — stable unique identifier (UUID string).
/// - ``createdAt`` — when the record was first written (UTC).
/// - ``schemaVersion`` — contract version this record conforms to (`v0`).
/// - ``hash`` — optional SHA-256 integrity digest; compute with
///   ``NerveIntegrity/fingerprint(for:)`` and verify with ``verifyIntegrity``.
public struct RecordBase: Codable, Hashable, Sendable {
    /// Contract version stamped on every v0 record.
    public static let schemaVersion = "v0"

    /// Stable unique identifier for the record (UUID string).
    public var id: String

    /// Timestamp of when the record was created (UTC).
    public var createdAt: Date

    /// SHA-256 integrity digest of the record content (excludes this field).
    public var hash: String?

    /// Contract version this record conforms to (always `v0` in the v0 set;
    /// encoded on the wire, decoded from the `schema_version` key).
    public var schemaVersion: String

    public init(
        id: String,
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
    }
}

/// Integrity helpers for records whose wire payload includes
/// `id` / `created_at` / `schema_version` / `hash` keys.
public enum NerveIntegrity {
    /// Compute the SHA-256 digest of a record's canonical JSON content,
    /// excluding its `hash` field (mirrors `Record.fingerprint()`).
    public static func fingerprint<T: Encodable>(for record: T) -> String? {
        var encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.outputFormatting = [.sortedKeys]

        guard let baseData = try? encoder.encode(record),
              let json = try? JSONSerialization.jsonObject(with: baseData) as? [String: Any],
              var cleaned = json as [String: Any]? else { return nil }

        cleaned.removeValue(forKey: "hash")
        guard let canonical = try? JSONSerialization.data(
            withJSONObject: cleaned,
            options: [.sortedKeys]
        ) else { return nil }

        return SHA256Helper.contentHash(canonical)
    }

    /// Verify a stored digest against a freshly computed fingerprint.
    /// Returns `true` when `storedHash` is `nil` or matches.
    public static func verify<T: Encodable>(storedHash: String?, for record: T) -> Bool {
        guard let storedHash else { return true }
        return storedHash == fingerprint(for: record)
    }
}
