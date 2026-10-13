import Foundation
import NerveRelayCore

/// `nerve-personal-relay` — macOS Personal Relay CLI (prompt2 §46).
///
/// Subcommands:
///   init-config [path]   write a template config (default ~/.nervcenter/relay.conf)
///   status               open store + outbox, report schema/cursor/backlog
///   run                  loop: capture + flush every `interval_seconds`
///   run --once           a single capture + flush cycle (then exit)
///
/// All output goes to stdout/stderr so the LaunchAgent can tee it to a
/// log file (§47: observable, user-account scoped, no remote shell).

enum Exit: Int {
    case ok = 0
    case usage = 2
    case config = 3
    case refused = 4      // schema refused / store missing — fail closed
    case transport = 5    // NerveCenter unreachable (outbox keeps data)
}

func log(_ line: String) {
    let ts = ISO8601DateFormatter.iso8601Second.string(from: Date())
    FileHandle.standardOutput.write(Data(("[\(ts)] \(line)\n".utf8)))
}

func fail(_ code: Exit, _ message: String) -> Never {
    FileHandle.standardError.write(Data(("[relay] \(message)\n".utf8)))
    exit(Int32(code.rawValue))
}

let args = CommandLine.arguments.dropFirst().map { $0 }

func usage() -> Never {
    let text = """
    nerve-personal-relay — local Messages relay to NerveCenter (§46/§47)

    USAGE
      nerve-personal-relay init-config [path]
      nerve-personal-relay status
      nerve-personal-relay run [--once]

    ENV OVERRIDES
      NERVE_RELAY_BASE_URL, NERVE_RELAY_TOKEN, NERVE_RELAY_STORE,
      NERVE_RELAY_OUTBOX
    """
    FileHandle.standardError.write(Data(text.utf8))
    exit(Int32(Exit.usage.rawValue))
}

guard let sub = args.first else { usage() }

switch sub {
case "init-config":
    let path = args.count > 1
        ? RelayConfig.expand(args[1])
        : RelayConfig.expand(RelayConfig.defaultConfigPath)
    try? FileManager.default.createDirectory(
        at: path.deletingLastPathComponent(), withIntermediateDirectories: true)
    try RelayConfig.template().write(to: path, atomically: true, encoding: .utf8)
    try? FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: path.path)
    log("wrote config template to \(path.path)")
    log("set a real access token (or NERVE_RELAY_TOKEN), then: nerve-personal-relay run --once")

case "status":
    do {
        let config = try RelayConfig.load(path: nil)
        let engine = RelayEngine(config: config)
        let (schema, backlog) = try engine.open()
        let cursor = try engine.outbox.maxStoreID()
        let maxID = try engine.store.maxID()
        log("store       : \(config.storePath.path)")
        log("schema      : recognizable (user_version=\(schema)) — read-only")
        log("outbox      : \(config.outboxPath.path)")
        log("queued      : \(backlog) pending, cursor=\(cursor), store max_id=\(maxID)")
        log("target      : \(config.baseURL.absoluteString)")
    } catch let e as RelayConfig.ConfigError {
        fail(.config, "config: \(e)")
    } catch let e as StoreError {
        switch e {
        case .missing(let p):
            fail(.refused, "store not found at \(p) — is Full Disk Access granted and Messages synced?")
        case .openFailed:
            fail(.refused, "cannot open store read-only — grant this process Full Disk Access (System Settings → Privacy & Security)")
        case .schemaIncompatible(let why):
            fail(.refused, "schema refused (fail-closed): \(why)")
        default:
            fail(.refused, "store: \(e)")
        }
    } catch let e as OutboxError {
        fail(.config, "outbox: \(e)")
    } catch {
        fail(.config, "\(error)")
    }

case "run":
    let once = args.contains("--once")
    do {
        let config = try RelayConfig.load(path: nil)
        let engine = RelayEngine(config: config)
        let (schema, _) = try engine.open()
        log("relay starting: store=\(config.storePath.path) schema=v\(schema) target=\(config.baseURL.absoluteString) interval=\(config.interval)s \(once ? "mode=once" : "mode=loop")")
        while true {
            do {
                let cycle = try await engine.runOnce()
                if cycle.captured > 0 || cycle.sent > 0 || cycle.failed > 0 || cycle.skipped > 0 {
                    log("captured=\(cycle.captured) sent=\(cycle.sent) replayed=\(cycle.replayed) skipped=\(cycle.skipped) failed=\(cycle.failed) backlog=\(cycle.backlog) cursor=\(cycle.maxStoreID)\(cycle.note.isEmpty ? "" : " note=\(cycle.note)")")
                }
                if once { break }
            } catch let e as StoreError {
                // Store disappeared / permission revoked mid-run: stop
                // rather than spinning. Data in the outbox is safe.
                log("store error: \(e) — stopping (outbox preserves queued events)")
                exit(Int32(Exit.refused.rawValue))
            } catch let e as OutboxError {
                log("outbox error: \(e) — stopping")
                exit(Int32(Exit.config.rawValue))
            } catch {
                // Engine-level (should be rare; transport errors are
                // handled inside flush and stay in the outbox).
                log("cycle error: \(error) — retrying next interval")
            }
            if once { break }
            try? await Task.sleep(nanoseconds: UInt64(config.interval) * 1_000_000_000)
        }
    } catch let e as RelayConfig.ConfigError {
        fail(.config, "config: \(e)")
    } catch {
        fail(.config, "\(error)")
    }

default:
    usage()
}
