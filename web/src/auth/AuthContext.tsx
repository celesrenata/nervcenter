import { useContext, createContext, useState, useEffect, ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  apiErrorFromResponse,
  apiFetch,
  clearSessionTokens,
  getAccessToken,
  setAccessToken,
} from '../api/client'

/**
 * Unified auth context (S102).
 *
 * Tokens live in the sessionStorage transport owned by `web/src/api/client.ts`
 * (keys `nc.accessToken` / `nc.refreshToken`) — NOT in localStorage. The old
 * localStorage `authToken` break-glass was stale: it was written by login
 * but never read by the fetch layer, so no request was ever authorized.
 *
 *   - login()  → POST /api/auth/login (break-glass), stores the returned
 *     access+refresh tokens in sessionStorage, resolves the user info,
 *     navigates to `/` (the app root) on success, and REJECTS with ApiError
 *     (status 401/403 + backend detail) on failure so LoginView can map
 *     credential errors to actionable messages.
 *   - logout() → clears the sessionStorage token keys and drops the session.
 *   - mount    → if a token is present, introspect /api/auth/me for the user;
 *     an expired/invalid token 401s, which clears the session (apiFetch).
 *
 * The App remains ungated: no view is wrapped in RequireAuth yet (the
 * break-glass vs SSO gating decision is pending — see RequireAuth.tsx).
 */

interface User {
  username: string
  roles: string[]
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<User>
  logout: () => void
  /** Mark the session active (used by the SSO callback after the token
   *  exchange has already persisted nc.accessToken/nc.refreshToken). */
  setUser: (user: User | null) => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    const token = getAccessToken()
    if (!token) {
      setLoading(false)
      return
    }
    // Introspect the presenting token. A 401 here clears the stale session
    // (handled inside apiFetch); anything else just leaves the user unset.
    apiFetch('/auth/me')
      .then((res) => {
        if (!res.ok) return
        return res.json() as Promise<{ sub?: string; roles?: string[] }>
      })
      .then((data) => {
        if (data && data.sub) {
          setUserState({ username: data.sub, roles: data.roles ?? [] })
        }
      })
      .catch(() => {
        /* network failure — user stays unset, token left as-is */
      })
      .finally(() => setLoading(false))
  }, [])

  const login = async (username: string, password: string): Promise<User> => {
    const res = await apiFetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })

    // Non-2xx → reject with ApiError (status 401/403 + FastAPI detail) so
    // LoginView can surface actionable credential errors.
    if (!res.ok) throw await apiErrorFromResponse(res)

    // backend/api/auth.py login response:
    // { token_type, access_token, expires_at, refresh_token,
    //   refresh_expires_at, sub, roles }
    const data = (await res.json()) as {
      access_token?: string
      refresh_token?: string | null
      sub?: string
      roles?: string[]
      user?: { username?: string; roles?: string[] }
    }
    if (!data.access_token) {
      throw new Error('Login response did not include an access token')
    }
    setAccessToken(data.access_token, data.refresh_token ?? null)
    const authedUser: User = {
      username: data.sub ?? data.user?.username ?? username,
      roles: Array.isArray(data.roles)
        ? data.roles
        : data.user?.roles ?? [],
    }
    setUserState(authedUser)
    // Successful break-glass login lands the user in the app: navigate away
    // from /login (replace so browser-back does not re-open the sign-in
    // form). Mirrors the SSO callback's post-exchange redirect (AuthCallback
    // → navigate('/')), so both entry points now reach the app the same way.
    navigate('/', { replace: true })
    return authedUser
  }

  const logout = () => {
    clearSessionTokens()
    setUserState(null)
    navigate('/login')
  }

  const setUser = (nextUser: User | null) => setUserState(nextUser)

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    login,
    logout,
    setUser,
  }

  if (loading) {
    return <div>Loading...</div>
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
