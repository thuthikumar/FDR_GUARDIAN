import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { BRANDING, SHOW_GOV_BRANDING } from '../config/branding'
import SystemStatusPanel from './SystemStatusPanel'
import { GovernmentIdentity } from './BrandIdentity'

const routePermissions: Record<string, string> = {
  '/dashboard': 'report.read',
  '/institutions': 'institution.read',
  '/fdrs': 'fdr.read',
  '/reports': 'report.read',
  '/alerts': 'alert.read',
}

export default function AppFooter() {
  const { user } = useAuth()
  const pills = SHOW_GOV_BRANDING ? BRANDING.governmentPills : BRANDING.publicPills
  const groups = BRANDING.footerGroups.map((group) => ({
    ...group,
    links: group.links.filter((link) => {
      const permission = routePermissions[link.href]
      return !permission || Boolean(user?.permissions.includes(permission))
    }),
  })).filter((group) => group.links.length > 0)
  return <footer className="app-footer">
    <div className="footer-inner">
      <div className="footer-pills" aria-label="Portal identity">{pills.map((label) => <span key={label}>{label}</span>)}</div>
      <div className="footer-grid">
        {groups.map((group) => <section key={group.title}>
          <h2>{group.title}</h2>
          <ul>{group.links.map((link) => <li key={link.href}>{link.href.startsWith('/')
              ? <Link to={link.href}>{link.label}</Link>
              : <a href="#main-content">{link.label}</a>}</li>)}</ul>
        </section>)}
      </div>
      <div className="footer-identity-row">
        <GovernmentIdentity compact />
        <div className="footer-status"><SystemStatusPanel /></div>
      </div>
      <p className="footer-disclaimer">{BRANDING.footerDisclaimer}</p>
    </div>
  </footer>
}
