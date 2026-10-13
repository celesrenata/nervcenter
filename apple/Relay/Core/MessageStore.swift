import Foundation
import SQLite3

/// A single normalized message row as read from the Messages database.
///
/// Field names mirror the Messages schema (`chat.db`) so the schema guard
/// can verify every column it relies on exists before we touch it.
public struct RawMessage: Sendable, Equatable {
    /// Stable unique key for the outbox. Uses `id`, which is unique per row
    /// (not per handle), so replays are idempotent on the NerveCenter side.
    public let id: Int64
    /// `item_message` GUID — surfaced to the backend as `message_id`.
    public let guid: String
    /// `handle.id` (phone number or email) of the conversation.
    public let peerIdentifier: String
    /// `is_from_me` — 0 = inbound, 1 = outbound.
    public let isFromMe: Int32
    /// `text` — empty for media/tapback-only rows (those are skipped,
    /// not sent as empty-body messages).
    public let body: String
    /// `is_from_me == 0` and service == "iMessage" → iMessage, else SMS.
    public let service: String
    /// `date` — **nanoseconds since 2001-01-01 00:00:00 UTC** (the Darwin
    /// reference date). The normalizer converts to real epoch seconds.
    public let dateNanos: Int64
}

public enum StoreError: Error, Equatable {
    /// The store file is missing (no permission, no sync, or wrong path).
    case missing(String)
    /// We could not open the file even read-only (usually Full Disk
    /// Access has not been granted to the relay process).
    case openFailed(String)
    /// The schema is not recognizable — we refuse to parse rather than
    /// risk misreading data (prompt2 §11: "detect schema incompatibility",
    /// "fail closed when parsing is uncertain").
    case schemaIncompatible(String)
    /// A row failed to read (NULL where we expected a value, etc.).
    case rowError(String)
}

/// Read-only tail of the macOS Messages store (`~/Library/Messages/chat.db`).
///
/// prompt2 §11 Strategy A:
/// - operate **read-only** against source message storage (opened
///   `SQLITE_OPEN_READONLY`; no writes, no `PRAGMA` that mutates);
/// - never modify the Messages database;
/// - detect schema incompatibility before any parse (see
///   `assertSchema`, and `schemaVersion` for observability).
///
/// The reader is deliberately tiny: one `SELECT` against
/// `message`/`handle`/`chat_message`, ordered by `id`, filtered by
/// `id > :cursor`. The WAL journal mode means readers do not block the
/// Messages app, and Messages' own writer does not block us.
public final class MessageStore {
    public let url: URL
    private var db: OpaquePointer?

    /// Darwin reference date: 2001-01-01T00:00:00Z == Unix 978307200 s.
    public static let darwinEpochUnix: TimeInterval = 978_307_200

    public init(url: URL) {
        self.url = url
    }

    deinit {
        close()
    }

    public enum OpenResult {
        case ok(schemaVersion: String)
        case notFound
    }

    /// Open read-only and verify the schema. Idempotent.
    @discardableResult
    public func open() throws -> OpenResult {
        if db != nil { return .ok(schemaVersion: try self.schemaVersion()) }
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw StoreError.missing(url.path)
        }
        var handle: OpaquePointer?
        // READONLY: the relay must never be able to write the store,
        // regardless of process permissions. NO_MUTEX is safe because
        // the store is accessed by a single thread (the relay loop).
        _ = sqlite3_open_v2(
            url.path, &handle,
            SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX, nil
        )
        guard handle != nil else {
            // open_v2 failed before a handle existed (e.g. OOM) —
            // sqlite3_errmsg(nil) is undefined, so report generically.
            throw StoreError.openFailed("sqlite3_open_v2 failed to open \(url.path)")
        }
        self.db = handle
        // Fail closed on schema mismatch BEFORE any data is read.
        _ = try assertSchema()
        return .ok(schemaVersion: try schemaVersion())
    }

    public func close() {
        if let db { sqlite3_close(db); self.db = nil }
    }

    /// Messages store schema marker: the `chat_message` join table is what
    /// links a message to its conversation; its presence plus the exact
    /// columns we SELECT is what we consider "recognizable". If any of
    /// these is missing we throw `schemaIncompatible` and the relay
    /// refuses to run rather than guess.
    public func assertSchema() throws {
        guard let db else { throw StoreError.openFailed("store not opened") }
        let required: [(table: String, column: String)] = [
            ("message", "id"),
            ("message", "guid"),
            ("message", "text"),
            ("message", "is_from_me"),
            ("message", "service"),
            ("message", "date"),
            ("message", "item_type"),
            ("handle", "id"),
            ("chat_message", "message_id"),
        ]
        for (table, column) in required {
            var stmt: OpaquePointer?
            let q = "PRAGMA table_info(\(table))"
            guard sqlite3_prepare_v2(db, q, -1, &stmt, nil) == SQLITE_OK, let stmt else {
                throw StoreError.schemaIncompatible("cannot introspect table \(table)")
            }
            defer { sqlite3_finalize(stmt) }
            var found = false
            while sqlite3_step(stmt) == SQLITE_ROW {
                let name = sqlite3_column_text(stmt, 1).flatMap { String(cString: $0) }
                if name == column { found = true; break }
            }
            if !found {
                throw StoreError.schemaIncompatible(
                    "table \(table) is missing column \(column) — refusing to parse an unrecognized schema"
                )
            }
        }
    }

    /// `PRAGMA user_version` — reported in `status` for observability.
    public func schemaVersion() throws -> String {
        guard let db else { throw StoreError.openFailed("store not opened") }
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "PRAGMA user_version", -1, &stmt, nil) == SQLITE_OK,
              let stmt
        else { throw StoreError.schemaIncompatible("cannot read user_version") }
        defer { sqlite3_finalize(stmt) }
        guard sqlite3_step(stmt) == SQLITE_ROW else { return "unknown" }
        return ncCStr(sqlite3_column_text(stmt, 0)) ?? "unknown"
    }

    /// Tail rows with `id > cursor`. Returns at most `limit` rows, ordered
    /// by `id ASC` (chronological within the store's own ordering).
    ///
    /// Only text rows are returned (`item_type = 0`); tapbacks, media, and
    /// system rows are intentionally skipped (MVP). Rows with an empty
    /// `text` are dropped here so the engine never forwards empty bodies.
    public func tail(afterCursor cursor: Int64, limit: Int) throws -> [RawMessage] {
        guard let db else { throw StoreError.openFailed("store not opened") }
        let sql = """
            SELECT m.id, m.guid, h.id, m.is_from_me, m.text, m.service, m.date
              FROM message m
              JOIN handle h ON m.handle_id = h.ROWID
             WHERE m.id > ?
               AND m.item_type = 0
             ORDER BY m.id ASC
             LIMIT ?
        """
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.openFailed(String(cString: sqlite3_errmsg(db)))
        }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_int64(stmt, 1, cursor)
        sqlite3_bind_int(stmt, 2, Int32(limit))

        var out: [RawMessage] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            let id = sqlite3_column_int64(stmt, 0)
            let guid = ncCStr(sqlite3_column_text(stmt, 1))
            let peer = ncCStr(sqlite3_column_text(stmt, 2))
            let isFromMe = sqlite3_column_int(stmt, 3)
            let bodyText = ncCStr(sqlite3_column_text(stmt, 4))
            let service = ncCStr(sqlite3_column_text(stmt, 5))
            let dateNanos = sqlite3_column_int64(stmt, 6)
            guard let guid, let peer, let bodyText, let service else {
                throw StoreError.rowError("row \(id) has NULL in a required column")
            }
            if bodyText.isEmpty { continue }
            out.append(RawMessage(
                id: id,
                guid: guid,
                peerIdentifier: peer,
                isFromMe: Int32(isFromMe),
                body: bodyText,
                service: service,
                dateNanos: dateNanos
            ))
        }
        return out
    }

    /// The highest `id` currently in the store — used by `init` to seed
    /// the outbox cursor without re-sending history on first run.
    public func maxID() throws -> Int64 {
        guard let db else { throw StoreError.openFailed("store not opened") }
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "SELECT COALESCE(MAX(id), 0) FROM message", -1, &stmt, nil) == SQLITE_OK,
              let stmt
        else { throw StoreError.openFailed(String(cString: sqlite3_errmsg(db))) }
        defer { sqlite3_finalize(stmt) }
        guard sqlite3_step(stmt) == SQLITE_ROW else { return 0 }
        return sqlite3_column_int64(stmt, 0)
    }
}

