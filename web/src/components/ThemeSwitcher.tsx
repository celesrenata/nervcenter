import type { ReactElement } from 'react'
import { useTheme, type Theme } from '../theme/ThemeContext'

/**
 * Segmented control for the app theme (Dark / Light / System).
 *
 * Sits in the Layout chrome: the desktop sidebar footer and the mobile top
 * bar. Style follows the existing UI conventions — small rounded segments,
 * border-line hairline, token-backed colors, focus-visible ring from
 * index.css.
 */

const OPTIONS: { value: Theme; label: string; Icon: () => ReactElement }[] = [
  { value: 'dark', label: 'Dark', Icon: MoonIcon },
  { value: 'light', label: 'Light', Icon: SunIcon },
  { value: 'system', label: 'System', Icon: MonitorIcon },
]

function MoonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  )
}

function SunIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  )
}

function MonitorIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </svg>
  )
}

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme()

  return (
    <div
      role="group"
      aria-label="Color theme"
      className="inline-flex rounded-md border border-line bg-elevated p-0.5"
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = theme === value
        return (
          <button
            key={value}
            type="button"
            onClick={() => setTheme(value)}
            aria-pressed={active}
            title={`${label} theme`}
            className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs transition-colors ${
              active
                ? 'bg-accent text-white'
                : 'text-secondary hover:bg-hover hover:text-primary'
            }`}
          >
            <Icon />
            <span>{label}</span>
          </button>
        )
      })}
    </div>
  )
}
