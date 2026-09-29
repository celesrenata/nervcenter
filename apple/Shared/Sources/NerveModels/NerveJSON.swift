import Foundation

/// Shared JSON configuration for the NerveCenter v0 wire contract.
///
/// Mirrors the Python `pydantic` v2 defaults used by `schemas/`:
/// - ISO-8601 timestamps (UTC).
/// - Keys are converted snake_case ⇄ camelCase on the wire.
/// - `null` values are omitted on encode (Pydantic `exclude_none`).
public enum NerveJSON {
    /// Encoder for the NerveCenter v0 wire contract.
    ///
    /// Swift camelCase properties are written as snake_case keys
    /// (`createdAt` -> `created_at`), matching the Pydantic v2 schemas.
    public static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        e.keyEncodingStrategy = .convertToSnakeCase
        e.outputFormatting = [.sortedKeys]
        return e
    }()

    /// Decoder for the NerveCenter v0 wire contract.
    ///
    /// Snake_case wire keys are read as camelCase Swift properties
    /// (`created_at` -> `createdAt`), matching the Pydantic v2 schemas.
    public static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    /// Encode a value to Data (omit `null` members, matching Pydantic
    /// serialization used for content hashing on the backend).
    public static func encode<T: Encodable>(_ value: T) -> Data? {
        var encoder = Self.encoder
        encoder.outputFormatting = [.sortedKeys]
        return try? encoder.encode(value)
    }

    /// Decode a value from Data.
    public static func decode<T: Decodable>(_ type: T.Type, from data: Data) -> T? {
        try? Self.decoder.decode(T.self, from: data)
    }
}
