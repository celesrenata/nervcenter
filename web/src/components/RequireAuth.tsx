import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

/**
 * Route guard that redirects unauthenticated users to /login.
 *
 * PENDING DECISION — intentionally NOT wired into App.tsx yet:
 *   - The SSO spec (sso-integration, AC-S09) wants the whole app gated behind
 *     the SSO realm, but the Authentik OIDC provider is not yet provisioned
 *     (AC-S01 `enabled=false`; see S104) and the break-glass local-admin path
 *     is disabled unless NERVE_LOCAL_ADMIN is set.
 *   - Until the provider is live + a break-glass vs SSO gating decision is
 *     made, the App is rendered UNGATED (App.tsx) so the read-only views keep
 *     working. Wiring this component in is the follow-up once that decision
 *     is finalized.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return children
}