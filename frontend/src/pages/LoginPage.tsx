import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { BRANDING } from '../config/branding'
import { GovernmentIdentity, HeaderBrand } from '../components/BrandIdentity'
import DisplayControls from '../components/DisplayControls'
import AppFooter from '../components/AppFooter'

const sharedModules = ['Dashboard', 'Institutions', 'FDR Registry', 'Reports', 'Alert Centre']

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
    <header className="login-topbar"><Link to="/login" aria-label="FDR Guardian sign in"><HeaderBrand /></Link><DisplayControls /></header>
    <p className="prototype-notice login-notice" role="note">{BRANDING.prototypeNotice}</p>
    <main id="main-content" className="login-main">
      <p className="login-kicker">Secure workspace</p>
      <h1 className="login-page-title">Sign in to FDR Guardian</h1>
      <p className="login-page-subtitle">Access the synthetic security deposit and FDR lifecycle workspace.</p>
      <div className="login-layout">
        <section className="login-intro">
          <GovernmentIdentity />
          <h2>Your FDR workspace</h2>
          <p>Sign in with your authorised account to view the modules available for your assigned permissions.</p>
          <h3>After sign-in you will see</h3>
          <ul>{sharedModules.map((module) => <li key={module}>{module}</li>)}</ul>
          <p className="login-role-note">Document, audit and monitoring tools appear only for accounts with the corresponding access.</p>
          <span className="synthetic-demo-badge">Synthetic demo</span>
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
