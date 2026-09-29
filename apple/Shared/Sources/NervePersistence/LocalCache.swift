import Foundation

import NerveModels

/// Actor-isolated local cache (spec §73): systems, incidents, goals, agent
/// activity, compute, approvals, recent responses.
///
/// All mutations happen inside the actor; flushes are serialized JSON files,
/// so a crash or restart never leaves the JSON corrupted mid-write
/// (`.atomic` replace on write).
public actor LocalCache {
    private let storageUrl: URL
    private(set) var state: CachedState

    /// Create a cache rooted at `directory`; state file name is `stateName`.
    ///
    /// If a previous snapshot exists on disk it is loaded; otherwise a fresh
    /// ``CachedState`` is created (and immediately persisted when mutated).
    public init(directory: URL, stateName: String = "nerve-cache.json") {
        let fileURL = directory.appendingPathComponent(stateName)
        self.storageUrl = fileURL
        if let data = try? Data(contentsOf: fileURL),
           let decoded = try? NerveJSON.decoder.decode(CachedState.self, from: data) {
            self.state = decoded
        } else {
            self.state = CachedState()
        }
    }

    /// The on-disk location of the snapshot.
    public var fileURL: URL { storageUrl }

    /// The current in-memory snapshot.
    public var snapshot: CachedState { state }

    /// Replace the entire snapshot and flush to disk.
    public func replace(with newState: CachedState) {
        state = newState
        flush()
    }

    /// Mutate the snapshot and flush to disk.
    public func update(_ mutate: (inout CachedState) -> Void) {
        mutate(&state)
        flush()
    }

    /// Write the current snapshot to disk atomically.
    public func flush() {
        guard let data = try? NerveJSON.encoder.encode(state) else { return }
        let parent = storageUrl.deletingLastPathComponent()
        try? FileManager.default.createDirectory(at: parent, withIntermediateDirectories: true)
        try? data.write(to: storageUrl, options: .atomic)
    }

    /// Decode a snapshot from raw JSON (used by tests).
    public static func decode(_ data: Data) -> CachedState? {
        try? NerveJSON.decoder.decode(CachedState.self, from: data)
    }
}
