import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Building2, ClipboardCheck, ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { GovernmentIdentity, HeaderBrand } from '../components/BrandIdentity'
import AppFooter from '../components/AppFooter'

const portalAssurances = [
  { label: 'Role-based secure access', Icon: ShieldCheck },
  { label: 'Institution-level data separation', Icon: Building2 },
  { label: 'Complete audit trail of actions', Icon: ClipboardCheck },
]

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

  return <div className="login-page">
    <a className="skip-link" href="#login-form">Skip to sign in</a>
    <header className="login-topbar"><Link to="/login" aria-label="FDR Guardian sign in"><HeaderBrand /></Link></header>
    <main id="main-content" className="login-main">
      <p className="login-kicker">Secure workspace</p>
      <h1 className="login-page-title">Sign in to FDR Guardian</h1>
      <p className="login-page-subtitle">Access the synthetic security deposit and FDR lifecycle workspace.</p>
      <div className="login-layout">
        <section className="login-intro">
          <GovernmentIdentity />
          <h2>Security Deposit and FDR Management Portal</h2>
          <p className="login-intro-description">Authorised access for institutions and officers to record, monitor and verify fixed deposit receipts.</p>
          <div className="login-intro-divider" aria-hidden="true" />
          <ul className="login-assurances" aria-label="Portal safeguards">
            {portalAssurances.map(({ label, Icon }) => <li key={label}><Icon size={17} strokeWidth={1.8} aria-hidden="true" /><span>{label}</span></li>)}
          </ul>
          <p className="login-authorised-notice">Authorised users only. All activity is logged.</p>
        </section>
        <section className="login-form-panel" aria-labelledby="login-form-title">
          <h2 id="login-form-title">Account sign in</h2>
          <p>Use your authorised account credentials.</p>
          <form id="login-form" onSubmit={handleSubmit} className="login-form" noValidate>
            <div>
              <label htmlFor="email">Email</label>
              <input id="email" name="email" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
            </div>
            <div>
              <label htmlFor="password">Password</label>
              <input id="password" name="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
            </div>
            {error && <p role="alert" className="form-error">{error}</p>}
            <button type="submit" disabled={submitting}>{submitting ? 'Signing in…' : 'Sign in'}</button>
          </form>
          <p className="login-demo-note">Development environment. Use synthetic demo accounts only.</p>
        </section>
      </div>
    </main>
    <AppFooter />
  </div>
}
