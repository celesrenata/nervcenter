import XCTest
import SQLite3
@testable import NerveRelayCore

final class OutboxTests: XCTestCase {
    private var dir: URL!

    override func setUpWithError() throws {
        dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("relay-oubox-\(UUID().uuidString)")
        try? FileManager.default.removeItem(at: dir)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: dir)
    }

    private func makeOutbox() -> Outbox {
        Outbox(url: dir.appendingPathComponent("sub/outbox.db"))
    }

    func testEnqueueAndPendingFIFO() throws {
        let ob = makeOutbox()
        _ = try ob.open()
        _ = try ob.enqueue(storeID: 10, payloads: ["a"])
        _ = try ob.enqueue(storeID: 20, payloads: ["b", "c"])

        let pending = try ob.pending(limit: 10)
        XCTAssertEqual(pending.map(\.payloadJSON), ["a", "b", "c"], "FIFO order preserved")
        XCTAssertEqual(pending.map(\.storeID), [10, 20, 20])
        // seq is strictly increasing.
        let seqs = pending.map(\.seq)
        XCTAssertEqual(seqs, seqs.sorted(), "seq must be monotonic")
        XCTAssertEqual(try ob.count(), 3)
    }

    func testAckRemovesOnlyListed() throws {
        let ob = makeOutbox()
        _ = try ob.open()
        _ = try ob.enqueue(storeID: 1, payloads: ["a"])
        _ = try ob.enqueue(storeID: 2, payloads: ["b"])
        let pending = try ob.pending(limit: 10)
        // Ack only the second.
        _ = try ob.ack([pending[1].seq])
        let remaining = try ob.pending(limit: 10)
        XCTAssertEqual(remaining.map(\.payloadJSON), ["a"])
        XCTAssertEqual(try ob.count(), 1)
    }

    func testPersistenceAcrossReopen() throws {
        let path = dir.appendingPathComponent("sub/persist.db")
        let ob = Outbox(url: path)
        _ = try ob.open()
        _ = try ob.enqueue(storeID: 5, payloads: ["x"])
        ob.close()

        let ob2 = Outbox(url: path)
        _ = try ob2.open()
        let pending = try ob2.pending(limit: 10)
        XCTAssertEqual(pending.map(\.payloadJSON), ["x"], "outbox survives process restart")
        XCTAssertEqual(pending.first?.storeID, 5)
    }

    func testMaxStoreIDTracksHighest() throws {
        let ob = makeOutbox()
        _ = try ob.open()
        XCTAssertEqual(try ob.maxStoreID(), 0)
        _ = try ob.enqueue(storeID: 100, payloads: ["a"])
        _ = try ob.enqueue(storeID: 42, payloads: ["b"])  // lower id, later seq
        XCTAssertEqual(try ob.maxStoreID(), 100, "cursor must be max store_id, not oldest seq")

        // After acking the highest-store row, the cursor steps down.
        let pending = try ob.pending(limit: 10)
        let forRow100 = pending.first { $0.storeID == 100 }
        _ = try ob.ack([forRow100!.seq])
        XCTAssertEqual(try ob.maxStoreID(), 42)
    }

    func testEmptyEnqueueIsNoOp() throws {
        let ob = makeOutbox()
        _ = try ob.open()
        let seqs = try ob.enqueue(storeID: 1, payloads: [])
        XCTAssertTrue(seqs.isEmpty)
        XCTAssertEqual(try ob.count(), 0)
    }
}
