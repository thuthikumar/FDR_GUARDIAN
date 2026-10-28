import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function HomePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  if (!user) return null
  return (
    <main className="min-h-screen px-6 py-8 sm:px-10">
      <div className="mx-auto max-w-5xl">
        <header className="flex items-center justify-between border-b border-slate-200 pb-6">
          <a className="flex items-center gap-3" href="/" aria-label="FDR Guardian home">
            <span className="brand-mark" aria-hidden="true">F</span>
            <span className="text-sm font-bold text-slate-900">FDR Guardian</span>
          </a>
          <button type="button" onClick={handleLogout} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Log out</button>
        </header>
        <section className="grid gap-8 py-10">
          <div className="rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-700">Authenticated workspace</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">Welcome, {user.full_name}</h1>
            <dl className="mt-7 grid gap-5 sm:grid-cols-2">
              <div><dt className="text-xs font-medium uppercase tracking-wider text-slate-500">Role</dt><dd className="mt-1 text-sm font-semibold text-slate-800">{user.role.replaceAll('_', ' ')}</dd></div>
              <div><dt className="text-xs font-medium uppercase tracking-wider text-slate-500">Institution</dt><dd className="mt-1 break-all text-sm font-semibold text-slate-800">{user.institution_id || 'All institutions'}</dd></div>
            </dl>
            <p className="mt-8 text-xs text-slate-500">This Phase 3 home is a sign-in demonstration. Business record workflows are out of scope for this phase.</p>
          </div>
        </section>
      </div>
    </main>
  )
}
