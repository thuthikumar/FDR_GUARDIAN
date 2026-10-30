const brandingSetting = import.meta.env.VITE_SHOW_GOV_BRANDING

export const SHOW_GOV_BRANDING = brandingSetting?.toLowerCase() === 'true'

export const BRANDING = {
  productName: 'FDR Guardian',
  headerLabel: 'FDR Guardian dashboard',
  emblemAlt: 'State Emblem of India',
  neutralMarkLabel: 'FDR Guardian shield',
  subtitle: 'Security Deposit and FDR Lifecycle Management',
  footerDisclaimer: 'Prototype for Smart India Hackathon 2026 (SIH26265). Demo with synthetic data only. Not an official government website and not connected to AICTE or any government system.',
  governmentIdentity: ['Government of India', 'Ministry of Education · AICTE'] as const,
  publicIdentity: ['FDR Guardian', 'Demo workspace'] as const,
  governmentPills: ['Ministry of Education', 'Government of India', 'Digital India', 'National Portal of India', 'AICTE'] as const,
  publicPills: ['FDR Guardian', 'Synthetic demo'] as const,
  policyCaution: SHOW_GOV_BRANDING
    ? 'Maturity thresholds are demo defaults, not verified AICTE policy. Review past stored maturity dates as overdue; this does not mean an instrument is invalid.'
    : 'Maturity thresholds are demo defaults, not verified policy. Review past stored maturity dates as overdue; this does not mean an instrument is invalid.',
  footerGroups: [
    { title: 'Workflow', links: [{ label: 'Dashboard', href: '/dashboard' }, { label: 'Institutions', href: '/institutions' }, { label: 'FDR Registry', href: '/fdrs' }] },
    { title: 'Monitoring', links: [{ label: 'Reports', href: '/reports' }, { label: 'Alert Centre', href: '/alerts' }] },
    { title: 'Support', links: [{ label: 'Help', href: '#help' }, { label: 'Accessibility', href: '#accessibility' }] },
    { title: 'Information', links: [{ label: 'About this demo', href: '#about' }, { label: 'Terms', href: '#terms' }] },
  ],
} as const
