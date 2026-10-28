import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Card, CardContent } from './ui/card'

export function PageHeading({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  const location = useLocation()
  const parts = location.pathname.split('/').filter(Boolean)
  const parent = parts[0] === 'fdrs' ? { label: 'FDR Registry', to: '/fdrs' }
    : parts[0] === 'institutions' ? { label: 'Institutions', to: '/institutions' }
      : null
  const nested = Boolean(parent && parts.length > 1)
  const isDashboard = location.pathname === '/dashboard' || location.pathname === '/'
  return <div className="page-heading">
    <nav className="breadcrumb" aria-label="Breadcrumb">
      {isDashboard ? <span aria-current="page">Dashboard</span> : <><Link to="/dashboard">Dashboard</Link><span aria-hidden="true">/</span>{parent && <>{nested ? <><Link to={parent.to}>{parent.label}</Link><span aria-hidden="true">/</span></> : null}<span aria-current="page">{nested ? title : parent.label}</span></>}{!parent && <span aria-current="page">{title}</span>}</>}
    </nav>
    <div className="page-title-row"><div><h1>{title}</h1><p className="page-subtitle">{description}</p></div>{action}</div>
  </div>
}

export function StateMessage({ kind, children }: { kind: 'loading' | 'error' | 'empty'; children: ReactNode }) {
  return <Card><CardContent className="py-10 text-center text-sm text-slate-600" role={kind === 'error' ? 'alert' : undefined}>{children}</CardContent></Card>
}

export function Pager({ page, pageSize, total, onPageChange }: { page: number; pageSize: number; total: number; onPageChange: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 text-sm text-slate-600">
      <span>Showing {total === 0 ? 0 : (page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}</span>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Previous</Button>
        <span aria-live="polite">Page {page} of {pages}</span>
        <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>Next</Button>
      </div>
    </div>
  )
}

export function StatusBadge({ value }: { value: string }) {
  const tone = value === 'active' || value === 'verified' || value === 'released' || value === 'approved'
    ? 'status-green'
    : value === 'cancelled' || value === 'rejected' || value === 'inactive'
      ? 'status-red'
      : value === 'draft' || value === 'pending' || value === 'not_submitted'
        ? 'status-blue'
        : 'status-amber'
  return <Badge variant="outline" className={`status-chip ${tone}`}>{value.replaceAll('_', ' ')}</Badge>
}

export function SourceBadges({ sourceSystem }: { sourceSystem: string }) {
  const label = sourceSystem === 'SYNTHETIC_DEMO' ? 'Synthetic demo'
    : sourceSystem === 'MANUAL_ENTRY' ? 'Manual entry'
      : sourceSystem
  return <div className="flex flex-wrap gap-1.5" aria-label="Record data source">
    <Badge variant="outline" className={sourceSystem === 'SYNTHETIC_DEMO' ? 'synthetic-source-badge' : 'manual-source-badge'}>{label}</Badge>
  </div>
}
