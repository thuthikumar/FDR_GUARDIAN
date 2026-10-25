import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import SystemStatusPanel from './SystemStatusPanel'
import { Button } from './ui/button'

export default function AppShell() {
  const { user, logout } = useAuth()
  const [loggingOut, setLoggingOut] = useState(false)
  const navigate = useNavigate()
  if (!user) return null

  const links = [
    { label: 'Institutions', to: '/institutions', permission: 'institution.read' },
    { label: 'FDR Registry', to: '/fdrs', permission: 'fdr.read' },
  ].filter((link) => user.permissions.includes(link.permission))

  async function handleLogout() {
    setLoggingOut(true)
    try {
      await logout()
      navigate('/login', { replace: true })
    } finally {
      setLoggingOut(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 md:flex">
      <aside className="flex w-full flex-col border-b border-slate-200 bg-white md:min-h-screen md:w-64 md:border-b-0 md:border-r">
        <div className="flex items-center gap-3 px-5 py-5">
          <span className="brand-mark" aria-hidden="true">F</span>
          <div><p className="text-sm font-bold">FDR Guardian</p><p className="text-xs text-slate-500">Synthetic data workspace</p></div>
        </div>
        <nav aria-label="Main navigation" className="flex gap-2 px-4 pb-4 md:flex-col md:py-2">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} className={({ isActive }) => `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-blue-50 text-blue-800' : 'text-slate-600 hover:bg-slate-100'}`}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto hidden space-y-4 p-4 md:block"><SystemStatusPanel /></div>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="flex min-h-16 items-center justify-between border-b border-slate-200 bg-white px-5 py-3 sm:px-8">
          <p className="text-sm text-slate-500">Institution and deposit registry</p>
          <details className="relative">
            <summary className="cursor-pointer list-none rounded-lg px-3 py-2 text-right hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-blue-700">
              <span className="block text-sm font-semibold">{user.full_name}</span>
              <span className="block text-xs capitalize text-slate-500">{user.role.replaceAll('_', ' ')}</span>
            </summary>
            <div className="absolute right-0 z-20 mt-2 w-52 rounded-xl border border-slate-200 bg-white p-3 shadow-lg">
              <p className="mb-3 break-all text-xs text-slate-500">{user.email}</p>
              <Button variant="outline" className="w-full" disabled={loggingOut} onClick={handleLogout}>
                {loggingOut ? 'Signing out…' : 'Log out'}
              </Button>
            </div>
          </details>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-8 sm:py-9"><Outlet /></main>
        <div className="px-4 pb-5 md:hidden"><SystemStatusPanel /></div>
      </div>
    </div>
  )
}
