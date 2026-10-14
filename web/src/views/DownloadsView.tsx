import { useEffect, useState } from 'react'

/**
 * A single artifact entry as described by `manifest.json` (produced by
 * apple/Distribution/generate_manifest.py).
 */
interface ManifestArtifact {
  name: string
  kind: string
  label: string
  path: string
  present: boolean
  embedded: boolean
  bundle_id: string
  min_ios?: string
  min_watch?: string
  sha256?: string
  bytes?: number
}

interface DownloadManifest {
  name: string
  generated_at: string
  versions: { phone: string; watch: string; widget: string }
  artifacts: ManifestArtifact[]
}

/** Human-readable byte formatting (10-based, e.g. 12.3 MB). */
function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '—'
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = n / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v.toFixed(1)} ${units[i]}`
}

/** Format an API / network failure as `<status> — <detail>`. */
function formatError(e: unknown): string {
  if (e && typeof e === 'object' && 'message' in e) return String(e.message)
  return String(e ?? 'Unknown error')
}

const manifestUrl = '/downloads/manifest.json'

/**
 * Downloads — self-hosted app distribution.
 *
 * Reads the static `manifest.json` published under `/downloads` (mounted by
 * nginx, see the `Distribution` README) and renders a card per artifact with
 * a direct download link. Artifacts that have not been exported yet
 * (`present: false`) are shown disabled. The iOS widget ships embedded in
 * NervePhone.ipa and is marked as such.
 */
export function DownloadsView() {
  const [manifest, setManifest] = useState<DownloadManifest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const res = await fetch(manifestUrl, {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) {
          throw new Error(`${res.status} — manifest unavailable`)
        }
        const data: DownloadManifest = await res.json()
        if (alive) setManifest(data)
      } catch (e) {
        if (alive) setError(formatError(e))
      } finally {
        if (alive) setLoading(false)
      }
    }
    load()
    return () => {
      alive = false
    }
  }, [])

  // Download anchor for a present artifact.
  const downloadHref = (a: ManifestArtifact) =>
    `/downloads/${a.path}`

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800 dark:text-white">Downloads</h1>

      {loading ? (
        <div className="text-center py-12" role="status">
          Loading downloads…
        </div>
      ) : error !== null ? (
        <div
          role="alert"
          className="text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/40 border border-red-300 dark:border-red-700 p-4 rounded-lg"
        >
          <p className="font-semibold mb-1">Download manifest unavailable</p>
          <p className="text-sm">{error}</p>
          <p className="text-sm mt-2 text-gray-500 dark:text-gray-400">
            Run <code>export_app.sh</code> (or <code>fastlane publish</code>) to
            build the app artifacts and publish them under <code>/downloads</code>.
          </p>
        </div>
      ) : manifest === null ? (
        <div className="text-center py-12" role="status">
          No download data.
        </div>
      ) : (
        <>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Product</p>
                <span className="text-xl font-semibold text-gray-800 dark:text-white">
                  {manifest.name}
                </span>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-500 dark:text-gray-400">Released</p>
                <span className="text-sm tabular-nums text-gray-800 dark:text-white">
                  {manifest.generated_at}
                </span>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
              {(['phone', 'watch', 'widget'] as const).map((k) => (
                <div key={k} className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                  <p className="text-xs text-gray-500 dark:text-gray-400 capitalize">{k}</p>
                  <span className="text-2xl font-bold text-blue-600 dark:text-blue-400 tabular-nums">
                    {manifest.versions[k]}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {manifest.artifacts.map((a) => {
              if (a.embedded) {
                return (
                  <div
                    key={a.name}
                    className="bg-gray-50 dark:bg-gray-700 rounded-lg p-6 border border-gray-200 dark:border-gray-600"
                  >
                    <h3 className="text-lg font-semibold text-gray-800 dark:text-white mb-1">
                      {a.label}
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                      Embedded in NervePhone.ipa — no separate download.
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                      {a.bundle_id}
                    </p>
                  </div>
                )
              }
              return (
                <div
                  key={a.name}
                  className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-gray-800 dark:text-white">
                      {a.label}
                    </h3>
                    {a.min_ios && (
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        iOS {a.min_ios}+
                      </span>
                    )}
                    {a.min_watch && (
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        watchOS {a.min_watch}+
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 font-mono">
                    {a.name}
                  </p>
                  {typeof a.bytes === 'number' && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 tabular-nums">
                      {formatBytes(a.bytes)}
                    </p>
                  )}
                  {typeof a.sha256 === 'string' && (
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-2 truncate font-mono">
                      {a.sha256}
                    </p>
                  )}
                  {a.present ? (
                    <a
                      href={downloadHref(a)}
                      className="mt-4 inline-flex items-center justify-center w-full px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold"
                    >
                      Download
                    </a>
                  ) : (
                    <div
                      className="mt-4 w-full px-4 py-2 rounded-lg bg-gray-200 dark:bg-gray-600 text-gray-400 dark:text-gray-300 text-sm text-center"
                    >
                      Not built yet
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 text-sm text-gray-600 dark:text-gray-300">
            <p>
              <strong>Installing:</strong> download <code>NervePhone.ipa</code> and
              install via Apple Configurator, a device-management (MDM) profile, or
              the <code>devicectl</code> / <code>cfg</code> tooling on a paired
              device. <code>NerveWatch.app</code> is installed onto a paired Apple
              Watch together with the watchOS widget archive. Self-hosted builds
              are signed with a personal-team ad-hoc profile — see
              <code>apple/Distribution/README.md</code>.
            </p>
          </div>
        </>
      )}
    </div>
  )
}
