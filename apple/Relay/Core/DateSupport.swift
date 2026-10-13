import Foundation

/// `sqlite3_column_text` returns `const unsigned char *`; Swift's
/// `String(cString:)` wants `Int8`. Both are 1-byte types, so a raw
/// reinterpret is a safe, zero-capacity-check view of the NUL-terminated
/// string SQLite owns (we never write through it).
func ncCStr(_ ptr: UnsafePointer<UInt8>?) -> String? {
    guard let ptr else { return nil }
    return String(cString: UnsafeRawPointer(ptr).assumingMemoryBound(to: CChar.self))
}

/// Shared date formatting for the relay.
///
/// ISO-8601 with `Z` suffix, second precision (`YYYY-MM-DDTHH:MM:SSZ`) —
/// matches the backend's `datetime` parse expectations without requiring
/// sub-second noise, and keeps outbox rows human-readable.
public extension ISO8601DateFormatter {
    static let iso8601Second: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()
}
