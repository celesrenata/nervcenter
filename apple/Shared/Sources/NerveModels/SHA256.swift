import Foundation
import CryptoKit

/// SHA-256 helpers matching `schemas.base.content_hash` (lowercase hex digest).
public enum SHA256Helper {
    /// Return the lowercase hex SHA-256 digest of raw data.
    public static func hexDigest(_ data: Data) -> String {
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    /// Return the lowercase hex SHA-256 digest of a canonical JSON payload.
    public static func contentHash(_ json: Data) -> String {
        hexDigest(json)
    }
}
