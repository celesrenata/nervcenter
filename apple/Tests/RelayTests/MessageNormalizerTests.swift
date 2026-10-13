import XCTest
@testable import NerveRelayCore

final class MessageNormalizerTests: XCTestCase {
    private let n = MessageNormalizer()

    /// 2024-01-15T10:30:00Z in Darwin nanoseconds.
    private func darwin(_ unixSeconds: TimeInterval) -> Int64 {
        Int64((unixSeconds - MessageStore.darwinEpochUnix) * 1_000_000_000)
    }

    func testInboundIMessage() throws {
        let raw = RawMessage(
            id: 1, guid: "GUID-1", peerIdentifier: "+15551234567",
            isFromMe: 0, body: "hi", service: "iMessage",
            dateNanos: darwin(1_705_314_600) // 2024-01-15T10:30:00Z
        )
        let m = try n.normalize(raw)
        XCTAssertEqual(m.direction, "INBOUND")
        XCTAssertEqual(m.channel, "imessage")
        XCTAssertEqual(m.peerIdentifier, "+15551234567")
        XCTAssertEqual(m.body, "hi")
        XCTAssertEqual(m.source, "personal-relay")
        XCTAssertEqual(m.timestampISO8601, "2024-01-15T10:30:00Z")
        XCTAssertNil(m.peerName)
    }

    func testOutboundSMS() throws {
        let raw = RawMessage(
            id: 2, guid: "GUID-2", peerIdentifier: "jane@example.com",
            isFromMe: 1, body: "yo", service: "SMS",
            dateNanos: darwin(1_705_308_600)
        )
        let m = try n.normalize(raw)
        XCTAssertEqual(m.direction, "OUTBOUND")
        XCTAssertEqual(m.channel, "sms")
        XCTAssertEqual(m.peerIdentifier, "jane@example.com")
    }

    func testChannelMapping() {
        XCTAssertEqual(MessageNormalizer.channel(for: "iMessage"), "imessage")
        XCTAssertEqual(MessageNormalizer.channel(for: "SMS"), "sms")
        XCTAssertEqual(MessageNormalizer.channel(for: "MMS"), "sms")
        XCTAssertEqual(MessageNormalizer.channel(for: "messaging"), "sms")
        // Unknown → nil (fail closed).
        XCTAssertNil(MessageNormalizer.channel(for: "SomeNewService"))
        XCTAssertNil(MessageNormalizer.channel(for: ""))
    }

    func testEmptyGUIDThrows() {
        let raw = RawMessage(
            id: 1, guid: "", peerIdentifier: "+1555",
            isFromMe: 0, body: "x", service: "iMessage", dateNanos: darwin(1_705_308_600)
        )
        XCTAssertThrowsError(try n.normalize(raw)) {
            XCTAssertEqual($0 as? NormalizationError, .emptyGUID)
        }
    }

    func testEmptyPeerThrows() {
        let raw = RawMessage(
            id: 1, guid: "g", peerIdentifier: "",
            isFromMe: 0, body: "x", service: "iMessage", dateNanos: darwin(1_705_308_600)
        )
        XCTAssertThrowsError(try n.normalize(raw)) {
            XCTAssertEqual($0 as? NormalizationError, .emptyPeer)
        }
    }

    func testImplausibleDateThrows() {
        // dateNanos is in DARWIN seconds (since 2001-01-01). -1e17 ns =
        // -1e8 s → maps to ~1997-11, which is before our min window
        // (2000-03-01) → implausible, must throw.
        let raw = RawMessage(
            id: 1, guid: "g", peerIdentifier: "+1555",
            isFromMe: 0, body: "x", service: "iMessage", dateNanos: -100_000_000_000_000_000
        )
        XCTAssertThrowsError(try n.normalize(raw)) {
            guard case .implausibleDate = $0 as? NormalizationError else {
                return XCTFail("expected implausibleDate, got \($0)")
            }
        }
    }

    func testUnknownServiceThrows() {
        let raw = RawMessage(
            id: 1, guid: "g", peerIdentifier: "+1555",
            isFromMe: 0, body: "x", service: "MysteryService",
            dateNanos: darwin(1_705_308_600)
        )
        XCTAssertThrowsError(try n.normalize(raw)) {
            XCTAssertEqual($0 as? NormalizationError, .unknownService("MysteryService"))
        }
    }
}
