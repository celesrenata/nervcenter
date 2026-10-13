import Foundation

/// Personal Relay configuration (prompt2 §47: runs under the user's
/// account, explicit configuration — no remote config, no auto-discovery).
///
/// The config file is a flat `key = value` file (one per line, `#`
/// comments). Default location: `~/.nervcenter/relay.conf`.
///
/// Env overrides (for LaunchAgent use): `NERVE_RELAY_BASE_URL`,
/// `NERVE_RELAY_TOKEN`, `NERVE_RELAY_STORE`, `NERVE_RELAY_OUTBOX`.
public struct RelayConfig: Sendable, Equatable {
    public var baseURL: URL
    public var token: String
    public var storePath: URL
    public var outboxPath: URL
    public var batchSize: Int
    public var interval: TimeInterval

    public static let defaultStore = "~/Library/Messages/chat.db"
    public static let defaultOutbox = "~/.nervcenter/relay/outbox.db"
    public static let defaultConfigPath = "~/.nervcenter/relay.conf"

    public init(
        baseURL: URL,
        token: String,
        storePath: URL,
        outboxPath: URL,
        batchSize: Int = 200,
        interval: TimeInterval = 5
    ) {
        self.baseURL = baseURL
        self.token = token
        self.storePath = storePath
        self.outboxPath = outboxPath
        self.batchSize = max(1, batchSize)
        self.interval = max(1, interval)
    }

    public enum ConfigError: Error, Equatable {
        case missingFile(String)
        case missingRequired(String)
        case invalidValue(String)
    }

    /// Parse `key = value` lines. Tolerates blank lines and `#` comments.
    public static func parse(_ lines: [String]) throws -> [String: String] {
        var out: [String: String] = [:]
        for raw in lines {
            var line = raw.trimmingCharacters(in: .whitespaces)
            if line.isEmpty { continue }
            if line.hasPrefix("#") { continue }
            // Inline comment: everything after ' #' is ignored.
            if let hash = line.firstIndex(of: "#") {
                line = String(line[..<hash]).trimmingCharacters(in: .whitespaces)
            }
            guard let eq = line.firstIndex(of: "=") else {
                throw ConfigError.invalidValue("not 'key = value': \(raw)")
            }
            let key = line[..<eq].trimmingCharacters(in: .whitespaces)
            let value = line[line.index(after: eq)...].trimmingCharacters(in: .whitespaces)
            guard !key.isEmpty else {
                throw ConfigError.invalidValue("empty key in line: \(raw)")
            }
            out[key] = value
        }
        return out
    }

    /// Expand a `~/...` or absolute path into a file URL.
    public static func expand(_ path: String) -> URL {
        let home = FileManager.default.homeDirectoryForCurrentUser
        if path.hasPrefix("~/") {
            return home.appendingPathComponent(String(path.dropFirst(2)))
        }
        return URL(fileURLWithPath: path, isDirectory: false)
    }

    public static func load(path: URL?) throws -> RelayConfig {
        let cfgPath = path ?? expand(defaultConfigPath)
        let fm = FileManager.default
        guard fm.fileExists(atPath: cfgPath.path) else {
            throw ConfigError.missingFile(
                "no config at \(cfgPath.path) — run `nerve-personal-relay init-config`"
            )
        }
        let text = try String(contentsOf: cfgPath, encoding: .utf8)
        var kv = try parse(text.split(separator: "\n").map(String.init))
        // Env overrides win (LaunchAgent secrets never touch the config file).
        if let v = ProcessInfo.processInfo.environment["NERVE_RELAY_BASE_URL"], !v.isEmpty {
            kv["base_url"] = v
        }
        if let v = ProcessInfo.processInfo.environment["NERVE_RELAY_TOKEN"], !v.isEmpty {
            kv["token"] = v
        }
        if let v = ProcessInfo.processInfo.environment["NERVE_RELAY_STORE"], !v.isEmpty {
            kv["store_path"] = v
        }
        if let v = ProcessInfo.processInfo.environment["NERVE_RELAY_OUTBOX"], !v.isEmpty {
            kv["outbox_path"] = v
        }

        func required(_ key: String) throws -> String {
            guard let v = kv[key], !v.isEmpty else {
                throw ConfigError.missingRequired("\(key) (set it in \(cfgPath.path))")
            }
            return v
        }

        guard let base = URL(string: try required("base_url")), base.scheme != nil else {
            throw ConfigError.invalidValue("base_url is not a valid URL")
        }
        let token = try required("token")

        if let s = kv["store_path"] {
            guard !s.hasPrefix("https"), !s.hasPrefix("http") else {
                throw ConfigError.invalidValue("store_path must be a local file (never remote)")
            }
        }
        let store = expand(kv["store_path"] ?? defaultStore)
        let outbox = expand(kv["outbox_path"] ?? defaultOutbox)

        let batch = kv["batch"].flatMap { Int($0) } ?? 200
        let interval = kv["interval_seconds"].flatMap { TimeInterval($0) } ?? 5

        return RelayConfig(
            baseURL: base,
            token: token,
            storePath: store,
            outboxPath: outbox,
            batchSize: batch,
            interval: interval
        )
    }

    public static func template() -> String {
        """
        # NerveCenter Personal Relay — local config (prompt2 §47).
        # Keep this file user-only (chmod 600). The token is a NerveCenter
        # access token; prefer the NERVE_RELAY_TOKEN env var / keychain over
        # storing it here.

        base_url = https://nervecenter.celestium.life
        token = PASTE_YOUR_ACCESS_TOKEN
        store_path = ~/Library/Messages/chat.db
        outbox_path = ~/.nervcenter/relay/outbox.db
        batch = 200
        interval_seconds = 5
        """
    }
}
