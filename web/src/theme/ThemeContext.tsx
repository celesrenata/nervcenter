import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

/**
 * Theme plumbing for the NerveCenter web app.
 *
 * `theme` is the user preference (persisted to localStorage under
 * 'nerve-theme'); `effectiveTheme` is what the UI actually renders —
 * 'system' resolves through `matchMedia('(prefers-color-scheme: light)')`
 * and tracks the OS preference live.
 *
 * The CSS side lives in index.css: `:root` carries the dark token set (the
 * app's default look), `[data-theme='light']` the light set, and
 * `[data-theme='system']` falls back to dark with a
 * `prefers-color-scheme: light` media rule mirroring this file's JS check.
 */

export type Theme = 'dark' | 'light' | 'system'
export type EffectiveTheme = 'dark' | 'light'

const STORAGE_KEY = 'nerve-theme'
const LIGHT_QUERY = '(prefers-color-scheme: light)'

function isSystemLight(): boolean {
  return typeof window !== 'undefined' && window.matchMedia(LIGHT_QUERY).matches
}

/**
 * Resolve the stored preference (no side effects). Used both to seed the
 * provider state and to apply the attribute before first paint.
 */
export function readStoredTheme(): Theme {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'dark' || stored === 'light' || stored === 'system') {
      return stored
    }
  } catch {
    // localStorage unavailable (private mode, blocked) — use the default.
  }
  return 'system'
}

/**
 * Apply theme + the class-based `dark` variant to <html> synchronously.
 *
 * Call from main.tsx before `createRoot(...).render(...)` so the stored
 * preference is live before React paints anything (no theme flash); the
 * ThemeProvider's effect re-applies the same state afterwards and keeps it
 * in sync on preference changes. The `dark` class keeps the not-yet-migrated
 * `dark:` Tailwind utilities correct under 'system' + OS light.
 */
export function applyThemeToDocument(theme: Theme): void {
  const root = document.documentElement
  const effective: EffectiveTheme =
    theme === 'system' ? (isSystemLight() ? 'light' : 'dark') : theme
  root.setAttribute('data-theme', theme)
  if (effective === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
}

export interface ThemeContextValue {
  /** The user-selected preference. */
  theme: Theme
  /** Persist the preference and re-resolve. */
  setTheme: (theme: Theme) => void
  /** The theme actually rendered ('system' already resolved). */
  effectiveTheme: EffectiveTheme
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme)
  const [systemLight, setSystemLight] = useState<boolean>(isSystemLight)

  // What the UI actually renders — 'system' resolved through the OS scheme.
  const effectiveTheme: EffectiveTheme =
    theme === 'system' ? (systemLight ? 'light' : 'dark') : theme

  // Keep <html data-theme> (and the `dark` class) in sync with the resolved
  // theme; this is the contract's "applies in an effect" hook.
  useEffect(() => {
    applyThemeToDocument(theme)
  }, [theme, systemLight])

  // 'system' follows the OS color scheme live.
  useEffect(() => {
    if (theme !== 'system') return
    const mql = window.matchMedia(LIGHT_QUERY)
    const onChange = (event: MediaQueryListEvent) => setSystemLight(event.matches)
    setSystemLight(mql.matches)
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [theme])

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Persistence is best-effort; the in-memory preference still applies.
    }
  }, [])

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, setTheme, effectiveTheme }),
    [theme, setTheme, effectiveTheme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

/** Access the theme preference, setter, and resolved theme. */
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider')
  return ctx
}
