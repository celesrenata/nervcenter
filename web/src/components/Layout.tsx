import { Link, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

interface NavItem {
  path: string
  label: string
  icon: string
}

const navItems: NavItem[] = [
  { path: '/', label: 'Overview', icon: '📊' },
  { path: '/systems', label: 'Systems', icon: '🖥️' },
  { path: '/timeline', label: 'Timeline', icon: '⏱️' },
  { path: '/goals', label: 'Goals', icon: '🎯' },
  { path: '/tasks', label: 'Task DAG', icon: '📋' },
  { path: '/agents', label: 'Agents', icon: '🤖' },
  { path: '/inference', label: 'Inference', icon: '🧠' },
  { path: '/incidents', label: 'Incidents', icon: '⚠️' },
  { path: '/decisions', label: 'Decisions', icon: '📜' },
  { path: '/ask', label: 'Ask', icon: '💬' },
]

export function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-screen bg-gray-100 dark:bg-gray-900">
      {/* Sidebar */}
      <div className="w-64 bg-white dark:bg-gray-800 shadow-lg">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <h1 className="text-2xl font-bold text-gray-800 dark:text-white">
            NerveCenter
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Personal Intelligence Core
          </p>
        </div>

        <nav className="mt-4">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className="flex items-center px-4 py-3 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
            >
              <span className="mr-3">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>

        <div className="mt-auto p-4 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {user?.username || 'Guest'}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {user?.roles?.join(', ') || 'No roles'}
              </p>
            </div>
            <button
              onClick={logout}
              className="text-sm text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
            >
              Logout
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto">
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}