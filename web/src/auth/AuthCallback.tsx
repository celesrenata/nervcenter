/**
 * SSO PKCE authorization-code callback (S102 / AC-S06).
 *
 * The SSO provider redirects the browser here as `/auth/callback?code=…&state=…`
 * after the user completes sign-in. This component:
 *   1. reads `code` + `state` from the URL search params,
 *   2. validates the round-tripped `state` against the sessionStorage
 *      `nc.pkce.state` (CSRF guard) and exchanges the code for tokens at the
 *      provider's token endpoint (via `exchangeAuthCode` in client.ts),
 *   3. stores `nc.accessToken` / `nc.refreshToken` in sessionStorage,
 *   4. redirects to the post-login route (default `/`).
 *
 * On any failure it shows a short, actionable error and offers a link back to
 * `/login` — it never leaves the user stranded on a broken callback URL.
 *
 * This route is registered ungated in App.tsx (the auth-gating decision is
 * pending; see RequireAuth.tsx). It is intentionally NOT wrapped in Layout so
 * the callback renders standalone.
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { exchangeAuthCode } from '../api/client'
import { useAuth } from './AuthContext'

type Phase = 'exchanging' | 'done' | 'error'

export function AuthCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { setUser } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>('exchanging')
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true

    const code = searchParams.get('code')
    const state = searchParams.get('state')

    if (!code) {
      setError('No authorization code in the callback URL. Please sign in again.')
      setPhase('error')
      return
    }

    // Introspect the freshly minted access token for the real identity.
    // Best-effort: if /auth/me is unreachable the session still stands (the
    // tokens are stored), so we still redirect to the post-login route.
    const introspect = async (): Promise<{ username: string; roles: string[] }> => {
      try {
        const res = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${sessionStorage.getItem('nc.accessToken') ?? ''}` },
        })
        if (res.ok) {
          const data = (await res.json()) as { sub?: string; roles?: string[] }
          if (data.sub) return { username: data.sub, roles: data.roles ?? [] }
        }
      } catch {
        /* fall through — redirect anyway */
      }
      return { username: 'sso-user', roles: [] }
    }

    exchangeAuthCode(code, state)
      .then(async () => {
        setPhase('done')
        const authed = await introspect()
        // Refresh the auth context so isAuthenticated flips true immediately,
        // then leave the callback (default post-login route: '/').
        setUser(authed)
        navigate('/', { replace: true })
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : 'The SSO token exchange failed. Please sign in again.',
        )
        setPhase('error')
      })
  }, [searchParams, navigate, setUser])

  if (phase === 'exchanging') {
    return (
      <div
        data-testid="auth-callback"
        className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900"
      >
        <p className="text-gray-600 dark:text-gray-300">Signing you in…</p>
      </div>
    )
  }

  if (phase === 'error') {
    return (
      <div
        data-testid="auth-callback"
        className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 p-8"
      >
        <div className="max-w-md w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8">
          <h2 className="text-xl font-bold text-center text-gray-800 dark:text-white mb-4">
            Sign-in failed
          </h2>
          <div
            data-testid="auth-callback-error"
            className="mb-4 p-3 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200 rounded"
          >
            {error}
          </div>
          <button
            type="button"
            onClick={() => navigate('/login', { replace: true })}
            className="w-full rounded bg-gray-800 dark:bg-gray-600 text-white font-medium py-2 hover:opacity-90"
          >
            Back to sign in
          </button>
        </div>
      </div>
    )
  }

  return (
    <div
      data-testid="auth-callback"
      className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900"
    >
      <p className="text-gray-600 dark:text-gray-300">Signed in. Redirecting…</p>
    </div>
  )
}
