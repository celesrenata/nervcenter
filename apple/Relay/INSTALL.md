# nerve-personal-relay — Install (macOS host)

Durable relay daemon (spec §46/§47/§48): tails `~/Library/Messages/chat.db`
**read-only** and forwards normalized messages to NerveCenter's
`POST /api/messages/ingest`, with a local SQLite outbox so nothing is lost
while the backend is down.

Zero external dependencies — pure Swift + the system SQLite C library.

## 1. Build

```bash
cd apple
swift build          # artifact: .build/debug/NervePersonalRelay
./build_and_test.sh  # or: swift build && swift test
```

## 2. Grant Full Disk Access (required)

`~/Library/Messages/chat.db` is protected by macOS TCC. Until the *binary path*
has Full Disk Access, `status` and `run` exit with the store error
(`permission denied` / `schema guard refused`), **by design** — the reader
opens the DB `SQLITE_OPEN_READONLY | NOMUTEX | FAILIFREFUSED` and refuses to
run on a stale copy.

One-time grant (grant the *binary*; re-grant after every `swift build` only if
the path or signature changes — a local SPM debug binary is fine):

```bash
sudo codesign --force --deep --sign - .build/debug/NervePersonalRelay
open /System/Library/CoreServices/Finder.app/Contents/SharedSupport/Documents
  # System Settings → Privacy & Security → Full Disk Access → add:
  #   ~/.../nervcenter/apple/.build/debug/NervePersonalRelay
```

(Then re-run; first launch will prompt for the FDA grant.)

> The LaunchAgent (§4) runs under your user session, so the FDA grant is
> inherited — no sudo needed.

## 3. Configure the token (LaunchAgent / env)

The relay talks to NerveCenter with **Bearer auth**. Set the token either:

- **env var** (preferred — never in a file): `NERVE_RELAY_TOKEN=...`
- **config file**: `~/.nervcenter/relay.conf` (`token = nc_live_…`)

Config file template (write it once):

```bash
.build/debug/NervePersonalRelay init-config
# → creates ~/.nervcenter/relay.conf, then edit:
```

```ini
base_url = http://127.0.0.1:8000        # or https://…
token = replace-me (or leave empty and set NERVE_RELAY_TOKEN)

# optional overrides (env vars below win over these)
store_path = ~/Library/Messages/chat.db
outbox_path = ~/.nervcenter/relay/outbox.db
batch_size = 200
interval_seconds = 5
```

Env overrides (all optional; win over the file) — see CLI help:

```
NERVE_RELAY_BASE_URL, NERVE_RELAY_TOKEN, NERVE_RELAY_STORE, NERVE_RELAY_OUTBOX
```

## 4. Run (foreground / one-shot)

```bash
.build/debug/NervePersonalRelay status        # schema, cursor, backlog
.build/debug/NervePersonalRelay run --once    # one capture+flush cycle, exit
.build/debug/NervePersonalRelay run           # loop every `interval_seconds`
```

Exit codes: `0` ok · `2` bad usage · `3` bad config · `4` store missing/
schema-refused (fail-closed). Transport failures are **non-fatal** — the
engine leaves events in the outbox and retries next interval (§48); it never
exits on a network error.

## 5. Install as a LaunchAgent

`~/Library/LaunchAgents/com.nerve.personal-relay.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.nerve.personal-relay</string>
  <key>ProgramArguments</key>
  <array>
    <string>/ABSOLUTE/PATH/TO/apple/.build/debug/NervePersonalRelay</string>
    <string>run</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>NERVE_RELAY_TOKEN</key><string>nc_live_…</string>
    <!-- or point NERVE_RELAY_BASE_URL / NERVE_RELAY_STORE / NERVE_RELAY_OUTBOX -->
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>~/.nervcenter/relay/out.log</string>
  <key>StandardErrorPath</key><string>~/.nervcenter/relay/err.log</string>
</dict>
</plist>
```

```bash
launchctl load  -w ~/Library/LaunchAgents/com.nerve.personal-relay.plist
launchctl list  | grep com.nerve.personal-relay          # "PID 0 label" = healthy
tail -f ~/.nervcenter/relay/out.log                     # cycle counters
```

Unload: `launchctl unload ~/Library/LaunchAgents/com.nerve.personal-relay.plist`.

## 6. Ops notes (from the spec, §48)

- **First run** seeds the capture cursor at the *current* `chat.db` max id —
  the entire old message history is **not** replayed. Only *new* messages
  flow. The cursor is persisted in `outbox.db` (`meta('cursor')`) and advanced
  atomically inside each `enqueue` transaction.
- **Backend down** → entries stay in `outbox.db`, FIFO; next good cycle
  drains oldest-first. A 2xx from the backend acks the batch.
- **4xx/5xx from ingest** → batch stays queued, `err.log` shows the HTTP
  status + first 200 chars. A 401 means the token is wrong; the relay will
  keep failing loudly (by design) until fixed — do not "heal" it by deleting
  the outbox.
- **Schema guard**: on upgrade of `chat.db` to a version the reader does not
  know, the store opens and reads the schema, refuses tailing, and exits 2
  (`schemaVersionMismatch`). The outbox is preserved either way.

## 7. Troubleshooting

| Symptom                          | Likely cause / fix                                            |
| -------------------------------- | ------------------------------------------------------------- |
| `openFailed: permission denied`  | FDA not granted to *this* binary path. Re-grant.              |
| `schemaVersionMismatch 12`       | macOS added columns. Inspect `PRAGMA user_version` and bump.  |
| `401 Unauthorized` in `err.log`  | Token wrong/expired. Rotate in NerveCenter, restart agent.    |
| `backlog` grows, `sent` flat     | Backend down or slow. Wait; do not drop the outbox.           |
| `status` shows `cursor 0`        | Never ran yet (or outbox deleted). First `run` will seed it.  |
