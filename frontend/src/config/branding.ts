const brandingSetting = import.meta.env.VITE_SHOW_GOV_BRANDING

export const SHOW_GOV_BRANDING = brandingSetting === undefined || brandingSetting.toLowerCase() !== 'false'

export const BRANDING = {
  productName: 'FDR Guardian',
  headerLabel: 'FDR Guardian dashboard',
  emblemAlt: 'State Emblem of India',
  neutralMarkLabel: 'FDR Guardian shield',
  subtitle: 'Security Deposit and FDR Lifecycle Management',
  prototypeNotice: 'Prototype for SIH 2026. Synthetic data only. Not an official government website.',
  footerDisclaimer: 'Prototype for Smart India Hackathon 2026 (SIH26265). Demo with synthetic data only. Not an official government website and not connected to AICTE or any government system.',
  governmentIdentity: ['Government of India', 'Ministry of Education · AICTE'] as const,
  publicIdentity: ['FDR Guardian', 'Demo workspace'] as const,
  governmentPills: ['Ministry of Education', 'Government of India', 'Digital India', 'National Portal of India', 'AICTE'] as const,
  publicPills: ['FDR Guardian', 'Synthetic demo'] as const,
  policyCaution: SHOW_GOV_BRANDING
    ? 'Maturity thresholds are demo defaults, not verified AICTE policy. A past stored maturity date means overdue-date review, not that an instrument is invalid.'
    : 'Maturity thresholds are demo defaults, not verified policy. A past stored maturity date means overdue-date review, not that an instrument is invalid.',
  systemStatusNote: SHOW_GOV_BRANDING
    ? 'Phase 1 health monitoring remains available. No production AICTE data is connected.'
    : 'Health monitoring remains available. This demo is not connected to production data.',
  footerGroups: [
    { title: 'Workflow', links: [{ label: 'Dashboard', href: '/dashboard' }, { label: 'Institutions', href: '/institutions' }, { label: 'FDR Registry', href: '/fdrs' }] },
    { title: 'Monitoring', links: [{ label: 'Reports', href: '/reports' }, { label: 'Alert Centre', href: '/alerts' }] },
    { title: 'Support', links: [{ label: 'Help', href: '#help' }, { label: 'Accessibility', href: '#accessibility' }] },
    { title: 'Information', links: [{ label: 'About this demo', href: '#about' }, { label: 'Terms', href: '#terms' }] },
  ],
} as const
