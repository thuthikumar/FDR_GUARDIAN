import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import SystemStatusPanel from '../components/SystemStatusPanel'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Enter a valid email address.')
      return
    }
    if (!password) {
      setError('Enter your password.')
      return
    }
    setSubmitting(true)
    try {
      await login(email.trim(), password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Email or password is incorrect.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen px-6 py-8 sm:px-10">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-5xl items-center gap-10 lg:grid-cols-2">
        <section>
          <Link to="/login" className="flex items-center gap-3" aria-label="FDR Guardian sign in">
            <span className="brand-mark" aria-hidden="true">F</span>
            <span className="text-sm font-bold text-slate-900">FDR Guardian</span>
          </Link>
          <p className="mt-12 text-sm font-semibold uppercase tracking-[0.18em] text-blue-700">Secure workspace</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">Sign in to FDR Guardian</h1>
          <p className="mt-4 max-w-lg text-base leading-7 text-slate-600">Use your authorised account to access institution and verification workflows.</p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5" noValidate>
            <div>
              <label htmlFor="email" className="mb-2 block text-sm font-medium text-slate-700">Email</label>
              <input id="email" name="email" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
            </div>
            <div>
              <label htmlFor="password" className="mb-2 block text-sm font-medium text-slate-700">Password</label>
              <input id="password" name="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
            </div>
            {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
            <button type="submit" disabled={submitting} className="w-full rounded-xl bg-blue-800 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-900 disabled:cursor-wait disabled:opacity-60">
              {submitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
          <p className="mt-5 text-xs leading-5 text-slate-500">Development environment. Use synthetic demo accounts only.</p>
        </section>
        <SystemStatusPanel />
      </div>
    </main>
  )
}
