import { useEffect, useState, type ComponentType } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  AgentsIcon,
  CalendarIcon,
  AskIcon,
  CloseIcon,
  EmailIcon,
  DecisionsIcon,
  GoalsIcon,
  IncidentsIcon,
  InferenceIcon,
  MenuIcon,
  MessagesIcon,
  NowIcon,
  OverviewIcon,
  SystemsIcon,
  TasksIcon,
  TimelineIcon,
  VoicemailIcon,
  ContactsIcon,
  WaitingOnIcon,
  type IconProps,
} from './icons'

interface NavItem {
  path: string
  label: string
  Icon: ComponentType<IconProps>
}

const navItems: NavItem[] = [
  { path: '/', label: 'Overview', Icon: OverviewIcon },
  { path: '/now', label: 'Now', Icon: NowIcon },
  { path: '/calendar', label: 'Calendar', Icon: CalendarIcon },
  { path: '/messages', label: 'Messages', Icon: MessagesIcon },
  { path: '/email', label: 'Email', Icon: EmailIcon },
  { path: '/voicemail', label: 'Voicemail', Icon: VoicemailIcon },
  { path: '/contacts', label: 'Contacts', Icon: ContactsIcon },
  { path: '/waiting-on', label: 'Waiting On', Icon: WaitingOnIcon },
  { path: '/systems', label: 'Systems', Icon: SystemsIcon },
  { path: '/timeline', label: 'Timeline', Icon: TimelineIcon },
  { path: '/goals', label: 'Goals', Icon: GoalsIcon },
  { path: '/tasks', label: 'Task DAG', Icon: TasksIcon },
  { path: '/agents', label: 'Agents', Icon: AgentsIcon },
  { path: '/inference', label: 'Inference', Icon: InferenceIcon },
  { path: '/incidents', label: 'Incidents', Icon: IncidentsIcon },
  { path: '/decisions', label: 'Decisions', Icon: DecisionsIcon },
  { path: '/ask', label: 'Ask', Icon: AskIcon },
]

/**
 * App shell: persistent sidebar (≥641px) + top bar with a hamburger drawer
 * (≤640px, the `sm:` Tailwind breakpoint).
 *
 * Mobile (D-1): at 390px the collapsed state leaves zero permanent chrome —
 * content owns 100% of the viewport (acceptance: ≥70%), navigation is one
 * tap away, and the drawer is a bounded overlay (no page-level horizontal
 * scroll). The drawer is not modal: it has no fixed inset-0 scrim, so the
 * page behind it can never scroll or scroll sideways.
 *
 * Active item carries aria-current="page" (D-4); icons come from the
 * uniform inline-SVG set in icons.tsx (no emoji glyphs).
 */
export function Layout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  const activePath = location.pathname === '/' ? '/' : location.pathname.replace(/\/+$/, '')

  // Close the drawer on navigation so it never traps the user on mobile.
  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  // Escape closes the drawer; the close button + nav links do the rest.
  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])

  const closeMenu = () => setMenuOpen(false)

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900">
      {/* Top bar — visible only at ≤640px (mobile) */}
      <header className="sm:hidden sticky top-0 z-20 flex items-center gap-3 px-4 h-12 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
          aria-expanded={menuOpen}
          aria-controls="app-nav"
          className="p-1.5 -ml-1 rounded text-gray-700 dark:text-gray-200"
        >
          {menuOpen ? <CloseIcon size={20} /> : <MenuIcon size={20} />}
        </button>
        <span className="font-semibold text-gray-800 dark:text-white">NerveCenter</span>
      </header>

      {/* Mobile drawer — off-canvas overlay, no full-screen scrim. Starts below
          the h-12 top bar (top-12) so it never paints over the hamburger
          toggle: the old inset-y-0 overlapped the z-20 header and trapped the
          44px button inside the drawer for the whole time it was open (r3
          walk finding — the toggle could not be clicked while open). */}
      {menuOpen && (
        <div
          className="fixed top-12 bottom-0 left-0 z-30 w-64 max-w-[80%] bg-white dark:bg-gray-800 shadow-xl overflow-y-auto sm:hidden"
          role="dialog"
          aria-modal="false"
          aria-label="Navigation menu"
        >
          <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
            <div>
              <h1 className="text-lg font-bold text-gray-800 dark:text-white">NerveCenter</h1>
              <p className="text-xs text-gray-600 dark:text-gray-400">Personal Intelligence Core</p>
            </div>
            <button
              type="button"
              onClick={closeMenu}
              aria-label="Close navigation"
              className="p-1.5 rounded text-gray-500 dark:text-gray-400"
            >
              <CloseIcon size={18} />
            </button>
          </div>
          <NavLinks activePath={activePath} onNavigate={closeMenu} />
          <UserFooter user={user} onLogout={logout} />
        </div>
      )}

      {/* Sidebar — permanent, visible only at ≥641px (desktop) */}
      <div className="hidden sm:flex sm:w-64 sm:flex-col shrink-0 bg-white dark:bg-gray-800 shadow-lg">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <h1 className="text-2xl font-bold text-gray-800 dark:text-white">NerveCenter</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">Personal Intelligence Core</p>
        </div>
        <NavLinks activePath={activePath} />
        <UserFooter user={user} onLogout={logout} />
      </div>

      {/* Main Content */}
      <div className="min-w-0 flex-1 overflow-auto">
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function NavLinks({
  activePath,
  onNavigate,
}: {
  activePath: string
  onNavigate?: () => void
}) {
  return (
    <nav id="app-nav" className="mt-4">
      {navItems.map((item) => {
        const active = activePath === item.path
        const { Icon } = item
        return (
          <Link
            key={item.path}
            to={item.path}
            onClick={onNavigate}
            aria-current={active ? 'page' : undefined}
            className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
              active
                ? 'bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-200 font-medium'
                : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
          >
            <Icon size={18} className="shrink-0" />
            <span>{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}

function UserFooter({
  user,
  onLogout,
}: {
  user: { username: string; roles: string[] } | null
  onLogout: () => void
}) {
  return (
    <div className="mt-auto p-4 border-t border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {user?.username || 'Guest'}
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400">
            {user?.roles?.join(', ') || 'No roles'}
          </p>
        </div>
        {/* r3 walk: no session ⇒ no Logout action (was visible for Guest) */}
        {user && (
          <button
            type="button"
            onClick={onLogout}
            className="text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
          >
            Logout
          </button>
        )}
      </div>
    </div>
  )
}
