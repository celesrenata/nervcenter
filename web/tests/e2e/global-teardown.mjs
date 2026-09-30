/**
 * e2e global teardown (T-WEBE2E / AC005).
 *
 * Stops the mock backend that global-setup.mjs spawned (PID is read from the
 * same temp file). Best-effort: if the backend is already gone or the PID file
 * is missing, the run simply reports it.
 */
import { existsSync, readFileSync, unlinkSync } from 'node:fs'
import * as os from 'node:os'
import * as path from 'node:path'

// Must match global-setup.mjs.
const PID_FILE = path.join(os.tmpdir(), 'nerve-e2e-backend.pid')

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function isAlive(pid) {
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

export default async function main() {
  if (!existsSync(PID_FILE)) {
    console.log('[e2e teardown] no backend PID file — nothing to stop')
    return
  }
  const pid = Number(readFileSync(PID_FILE, 'utf8'))
  unlinkSync(PID_FILE)
  if (!Number.isInteger(pid) || pid <= 0) {
    console.log('[e2e teardown] invalid PID — nothing to stop')
    return
  }
  if (isAlive(pid)) {
    process.kill(pid, 'SIGTERM')
    const deadline = Date.now() + 5_000
    while (isAlive(pid) && Date.now() < deadline) await sleep(100)
    if (isAlive(pid)) {
      try {
        process.kill(pid, 'SIGKILL')
      } catch {
        // already gone
      }
    }
    console.log(`[e2e teardown] stopped mock backend (pid ${pid})`)
  } else {
    console.log(`[e2e teardown] backend (pid ${pid}) already stopped`)
  }
}
