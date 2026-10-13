import XCTest
@testable import NerveRelayCore

final class RelayConfigTests: XCTestCase {
    private var dir: URL!

    override func setUpWithError() throws {
        dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("relay-cfg-\(UUID().uuidString)")
        try? FileManager.default.removeItem(at: dir)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: dir)
    }

    private func writeConfig(_ text: String) -> URL {
        let url = dir.appendingPathComponent("relay.conf")
        try! text.write(to: url, atomically: true, encoding: .utf8)
        return url
    }

    func testParseValidConfig() throws {
        let url = writeConfig("""
            # a comment
            base_url = https://example.com
            token = abc123

            store_path = /tmp/chat.db
            outbox_path = /tmp/outbox.db
            batch = 50
            interval_seconds = 2
        """)
        let cfg = try RelayConfig.load(path: url)
        XCTAssertEqual(cfg.baseURL.absoluteString, "https://example.com")
        XCTAssertEqual(cfg.token, "abc123")
        XCTAssertEqual(cfg.batchSize, 50)
        XCTAssertEqual(cfg.interval, 2)
        XCTAssertEqual(cfg.storePath.path, "/tmp/chat.db")
        XCTAssertEqual(cfg.outboxPath.path, "/tmp/outbox.db")
    }

    func testMissingFile() {
        XCTAssertThrowsError(try RelayConfig.load(path: dir.appendingPathComponent("nope"))) {
            guard case .missingFile = $0 as? RelayConfig.ConfigError else {
                return XCTFail("expected missingFile, got \($0)")
            }
        }
    }

    func testMissingRequiredKey() {
        let url = writeConfig("base_url = https://example.com\n")
        XCTAssertThrowsError(try RelayConfig.load(path: url)) {
            guard case .missingRequired(let key) = $0 as? RelayConfig.ConfigError else {
                return XCTFail("expected missingRequired, got \($0)")
            }
            // The key names the missing field, followed by the config path.
            XCTAssertTrue(key.hasPrefix("token"), "expected token, got \(key)")
        }
    }

    func testInvalidURL() {
        let url = writeConfig("base_url = not a url\n")
        // "not a url" has no scheme → rejected.
        XCTAssertThrowsError(try RelayConfig.load(path: url)) {
            guard case .invalidValue = $0 as? RelayConfig.ConfigError else {
                return XCTFail("expected invalidValue, got \($0)")
            }
        }
    }

    func testInlineCommentsAndWhitespace() throws {
        let url = writeConfig("""
            base_url   =   https://example.com   # trailing comment
            token=spacedvalue
        """)
        let cfg = try RelayConfig.load(path: url)
        XCTAssertEqual(cfg.baseURL.absoluteString, "https://example.com")
        XCTAssertEqual(cfg.token, "spacedvalue")
    }

    func testRemoteStorePathRejected() {
        let url = writeConfig("""
            base_url = https://example.com
            token = abc
            store_path = https://evil.example/chat.db
        """)
        XCTAssertThrowsError(try RelayConfig.load(path: url)) {
            guard case .invalidValue = $0 as? RelayConfig.ConfigError else {
                return XCTFail("expected invalidValue, got \($0)")
            }
        }
    }

    func testEnvOverrides() throws {
        let url = writeConfig("""
            base_url = https://default.example
            token = filetoken
        """)
        setenv("NERVE_RELAY_TOKEN", "envtoken", 1)
        setenv("NERVE_RELAY_BASE_URL", "https://env.example", 1)
        defer {
            unsetenv("NERVE_RELAY_TOKEN")
            unsetenv("NERVE_RELAY_BASE_URL")
        }
        let cfg = try RelayConfig.load(path: url)
        XCTAssertEqual(cfg.token, "envtoken")
        XCTAssertEqual(cfg.baseURL.absoluteString, "https://env.example")
    }

    func testBatchAndIntervalFloor() throws {
        let url = writeConfig("""
            base_url = https://example.com
            token = abc
            batch = 0
            interval_seconds = 0
        """)
        let cfg = try RelayConfig.load(path: url)
        XCTAssertEqual(cfg.batchSize, 1)
        XCTAssertEqual(cfg.interval, 1)
    }

    func testTemplateIsLoadable() throws {
        let url = dir.appendingPathComponent("template.conf")
        try RelayConfig.template().write(to: url, atomically: true, encoding: .utf8)
        let cfg = try RelayConfig.load(path: url)
        XCTAssertEqual(cfg.token, "PASTE_YOUR_ACCESS_TOKEN")
        XCTAssertTrue(cfg.storePath.path.hasSuffix("Library/Messages/chat.db"))
    }
}
