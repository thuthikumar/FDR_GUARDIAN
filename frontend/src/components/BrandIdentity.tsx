import { Shield } from 'lucide-react'
import { BRANDING, SHOW_GOV_BRANDING } from '../config/branding'

type BrandingModeProps = { showGovBranding?: boolean }

export function BrandMark({ showGovBranding = SHOW_GOV_BRANDING, compact = false }: BrandingModeProps & { compact?: boolean }) {
  return showGovBranding
    ? <img className={`brand-emblem${compact ? ' brand-emblem-compact' : ''}`} src="/indian-state-emblem.png" alt={BRANDING.emblemAlt} />
    : <span className={`brand-shield${compact ? ' brand-emblem-compact' : ''}`} aria-label={BRANDING.neutralMarkLabel}><Shield aria-hidden="true" /></span>
}

export function HeaderBrand({ showGovBranding = SHOW_GOV_BRANDING }: BrandingModeProps) {
  return <span className="header-brand-lockup">
    <BrandMark showGovBranding={showGovBranding} />
    <span className="header-brand-copy">
      <strong>{BRANDING.productName}</strong>
      <small>{BRANDING.subtitle}</small>
      {showGovBranding && <small className="header-gov-meta">{BRANDING.governmentIdentity.join(' / ')}</small>}
    </span>
  </span>
}

export function GovernmentIdentity({ showGovBranding = SHOW_GOV_BRANDING, compact = false }: BrandingModeProps & { compact?: boolean }) {
  const identity = showGovBranding ? BRANDING.governmentIdentity : BRANDING.publicIdentity
  return <div className={`government-identity${compact ? ' government-identity-compact' : ''}`}>
    <BrandMark showGovBranding={showGovBranding} compact={compact} />
    <span><strong>{identity[0]}</strong><small>{identity[1]}</small></span>
  </div>
}
