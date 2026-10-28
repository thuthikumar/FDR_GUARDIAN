import { createContext, useContext, useEffect, useState, type FormEvent } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { BRANDING } from '../config/branding'
import AppFooter from './AppFooter'
import { HeaderBrand } from './BrandIdentity'
import DisplayControls from './DisplayControls'
import { Button } from './ui/button'

type ShellAlertContextValue = { openAlertCount: number | null; setOpenAlertCount: (count: number | null) => void }
const ShellAlertContext = createContext<ShellAlertContextValue>({ openAlertCount: null, setOpenAlertCount: () => undefined })
export function useShellAlertCount() { return useContext(ShellAlertContext) }

const navigation = [
  { label: 'Dashboard', to: '/dashboard', permission: 'report.read' },
  { label: 'Institutions', to: '/institutions', permission: 'institution.read' },
  { label: 'FDR Registry', to: '/fdrs', permission: 'fdr.read' },
  { label: 'Reports', to: '/reports', permission: 'report.read' },
  { label: 'Alert Centre', to: '/alerts', permission: 'alert.read' },
]

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? '').join('') || 'U'
}

function displayRole(role: string) {
  return role.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export default function AppShell() {
  const { user, logout } = useAuth()
  const [loggingOut, setLoggingOut] = useState(false)
  const [search, setSearch] = useState('')
  const [openAlertCount, setOpenAlertCount] = useState<number | null>(null)
  const navigate = useNavigate()
  const location = useLocation()
  const links = user ? navigation.filter((link) => user.permissions.includes(link.permission)) : []
  useEffect(() => {
    setSearch(location.pathname === '/fdrs' ? new URLSearchParams(location.search).get('q') ?? '' : '')
  }, [location.pathname, location.search])
  if (!user) return null

  async function handleLogout() {
    setLoggingOut(true)
    try {
      await logout()
      navigate('/login', { replace: true })
    } finally {
      setLoggingOut(false)
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    navigate(`/fdrs${search.trim() ? `?q=${encodeURIComponent(search.trim())}` : ''}`)
  }

  const shellContext: ShellAlertContextValue = { openAlertCount, setOpenAlertCount }
  return <ShellAlertContext.Provider value={shellContext}>
    <div className="app-root">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="site-header">
        <div className="header-primary">
          <Link className="brand-link" to="/dashboard" aria-label={BRANDING.headerLabel}><HeaderBrand /></Link>
          {user.permissions.includes('fdr.read') && <form className="global-search" role="search" onSubmit={submitSearch}>
            <label className="sr-only" htmlFor="global-fdr-search">Search the FDR registry</label>
            <Search size={19} aria-hidden="true" />
            <input id="global-fdr-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search FDR registry" />
            <label className="sr-only" htmlFor="global-search-fields">Search field</label>
            <select id="global-search-fields" value="all" onChange={() => undefined}><option value="all">All fields</option></select>
            <button type="submit" aria-label="Search FDR registry"><Search size={17} aria-hidden="true" /></button>
          </form>}
          <div className="account-tools">
            <span className="user-avatar" aria-hidden="true">{initials(user.full_name)}</span>
            <span className="user-copy"><strong>{user.full_name}</strong><small>{displayRole(user.role)}</small></span>
            <Button variant="outline" className="sign-out" disabled={loggingOut} onClick={() => void handleLogout()}>
              {loggingOut ? 'Signing out…' : 'Sign out'}
            </Button>
          </div>
        </div>
        <div className="header-secondary">
          <nav className="primary-nav" aria-label="Main navigation">
            {links.map((link) => <NavLink key={link.to} to={link.to} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              {link.label}{link.to === '/alerts' && openAlertCount !== null && <span className="alert-count" aria-label={`${openAlertCount} open alerts`}>{openAlertCount}</span>}
            </NavLink>)}
          </nav>
          <DisplayControls />
        </div>
        <p className="prototype-notice" role="note">{BRANDING.prototypeNotice}</p>
      </header>
      <main id="main-content" className="app-main"><Outlet /></main>
      <AppFooter />
    </div>
  </ShellAlertContext.Provider>
}
