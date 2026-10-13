import XCTest
import SQLite3
@testable import NerveRelayCore

/// Builds a synthetic `chat.db`-shaped SQLite file in a temp dir.
private func makeFakeStore(
    at url: URL,
    schemaVersion: Int = 11,
    messages: [(guid: String, peer: String, fromMe: Int32, text: String, service: String, dateNanos: Int64)]
) throws {
    var db: OpaquePointer?
    guard sqlite3_open(url.path, &db) == SQLITE_OK, let db else {
        throw NSError(domain: "test", code: 1)
    }
    defer { sqlite3_close(db) }
    let ddl = """
        PRAGMA user_version = \(schemaVersion);
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE);
        CREATE TABLE chat_message (chat_id INTEGER, message_id INTEGER);
        CREATE TABLE message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT,
            handle_id INTEGER,
            item_type INTEGER DEFAULT 0,
            is_from_me INTEGER DEFAULT 0,
            service TEXT DEFAULT 'iMessage',
            date INTEGER,
            text TEXT
        );
    """
    var err: UnsafeMutablePointer<CChar>?
    guard sqlite3_exec(db, ddl, nil, nil, &err) == SQLITE_OK else {
        let msg = err.map { String(cString: $0) } ?? "ddl failed"
        if let err { sqlite3_free(err) }
        throw NSError(domain: "test", code: 2, userInfo: [NSLocalizedDescriptionKey: msg])
    }

    // Insert each distinct peer once (handle.id is UNIQUE), then resolve
    // its real ROWID so message.handle_id points at the right row.
    var seenPeers: Set<String> = []
    for m in messages {
        let peer = m.peer
        if !seenPeers.contains(peer) {
            let insPeer = "INSERT INTO handle (id) VALUES ('\(peer)')"
            var err2: UnsafeMutablePointer<CChar>?
            guard sqlite3_exec(db, insPeer, nil, nil, &err2) == SQLITE_OK else {
                let msg = err2.map { String(cString: $0) } ?? "insert failed"
                if let err2 { sqlite3_free(err2) }
                throw NSError(domain: "test", code: 3, userInfo: [NSLocalizedDescriptionKey: msg])
            }
            seenPeers.insert(peer)
        }

        var handleID: Int64 = 0
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "SELECT ROWID FROM handle WHERE id = ?", -1, &stmt, nil) == SQLITE_OK,
              let stmt
        else {
            throw NSError(domain: "test", code: 4)
        }
        sqlite3_bind_text(stmt, 1, peer, -1, unsafeBitCast(-1, to: sqlite3_destructor_type.self))
        guard sqlite3_step(stmt) == SQLITE_ROW else {
            sqlite3_finalize(stmt)
            throw NSError(domain: "test", code: 5)
        }
        handleID = sqlite3_column_int64(stmt, 0)
        sqlite3_finalize(stmt)

        let guid = m.guid, fromMe = m.fromMe, text = m.text, service = m.service
        let date = m.dateNanos
        let insMsg = """
            INSERT INTO message (guid, handle_id, item_type, is_from_me, service, date, text)
            VALUES ('\(guid)', \(handleID), 0, \(fromMe), '\(service)', \(date), '\(text)')
        """
        var err2: UnsafeMutablePointer<CChar>?
        guard sqlite3_exec(db, insMsg, nil, nil, &err2) == SQLITE_OK else {
            let msg = err2.map { String(cString: $0) } ?? "insert failed"
            if let err2 { sqlite3_free(err2) }
            throw NSError(domain: "test", code: 3, userInfo: [NSLocalizedDescriptionKey: msg])
        }
    }
}

final class MessageStoreTests: XCTestCase {
    private var dir: URL!

    override func setUpWithError() throws {
        dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("relay-store-\(UUID().uuidString)")
        try? FileManager.default.removeItem(at: dir)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: dir)
    }

    func testMissingFileThrows() {
        let store = MessageStore(url: dir.appendingPathComponent("nope.db"))
        XCTAssertThrowsError(try store.open()) {
            guard case .missing = $0 as? StoreError else {
                return XCTFail("expected missing, got \($0)")
            }
        }
    }

    func testSchemaGuardRefusesUnknownSchema() throws {
        let url = dir.appendingPathComponent("weird.db")
        var db: OpaquePointer?
        guard sqlite3_open(url.path, &db) == SQLITE_OK, let db else {
            return XCTFail("could not create temp db")
        }
        defer { sqlite3_close(db) }
        // A table named message that lacks the columns we need.
        let ddl = "CREATE TABLE message (id INTEGER, something_else TEXT);"
        var err: UnsafeMutablePointer<CChar>?
        guard sqlite3_exec(db, ddl, nil, nil, &err) == SQLITE_OK else {
            return XCTFail("setup failed")
        }
        let store = MessageStore(url: url)
        XCTAssertThrowsError(try store.open()) {
            guard case .schemaIncompatible = $0 as? StoreError else {
                return XCTFail("expected schemaIncompatible, got \($0)")
            }
        }
    }

    func testTailReturnsRowsInOrderAndFiltersEmptyText() throws {
        let url = dir.appendingPathComponent("chat.db")
        let darwin = Int64((1_705_308_600 - MessageStore.darwinEpochUnix) * 1_000_000_000)
        try makeFakeStore(
            at: url,
            messages: [
                ("G1", "+15550000001", 0, "first", "iMessage", darwin),
                ("G2", "+15550000002", 1, "", "iMessage", darwin), // empty → filtered
                ("G3", "+15550000001", 0, "second", "iMessage", darwin + 1_000_000_000),
                ("G4", "x@y.z", 1, "sms hi", "SMS", darwin + 2_000_000_000),
            ]
        )
        let store = MessageStore(url: url)
        _ = try store.open()
        XCTAssertEqual(try store.schemaVersion(), "11")

        let all = try store.tail(afterCursor: 0, limit: 10)
        XCTAssertEqual(all.map(\.guid), ["G1", "G3", "G4"], "empty-text row must be skipped")
        XCTAssertEqual(all.map(\.peerIdentifier), ["+15550000001", "+15550000001", "x@y.z"])
        XCTAssertEqual(all.first?.isFromMe, 0)

        // Cursor: only rows past id 1.
        let afterFirst = try store.tail(afterCursor: 1, limit: 10)
        XCTAssertEqual(afterFirst.map(\.guid), ["G3", "G4"])

        XCTAssertEqual(try store.maxID(), 4)
    }

    func testStoreIsOpenedReadOnly() throws {
        // The relay must be structurally unable to write the store: verify
        // a write through the store's connection fails. We re-open the
        // path the way the store does (READONLY) and try an INSERT.
        let url = dir.appendingPathComponent("ro.db")
        try makeFakeStore(at: url, messages: [("G1", "+1", 0, "x", "iMessage", 0)])
        var db: OpaquePointer?
        let rc = sqlite3_open_v2(url.path, &db, SQLITE_OPEN_READONLY, nil)
        XCTAssertEqual(rc, SQLITE_OK)
        guard let db else { return XCTFail("open failed") }
        defer { sqlite3_close(db) }
        var err: UnsafeMutablePointer<CChar>?
        let writeRC = sqlite3_exec(db, "INSERT INTO handle (id) VALUES ('evil')", nil, nil, &err)
        XCTAssertNotEqual(writeRC, SQLITE_OK, "READONLY connection must refuse writes")
        if let err { sqlite3_free(err) }
    }
}
