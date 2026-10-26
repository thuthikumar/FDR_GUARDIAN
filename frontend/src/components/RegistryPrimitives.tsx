import type { ReactNode } from 'react'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Card, CardContent } from './ui/card'

export function PageHeading({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="mb-6 flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-2xl font-bold tracking-tight">{title}</h1><p className="mt-1 text-sm text-slate-600">{description}</p></div>{action}</div>
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
    ? 'bg-emerald-50 text-emerald-800'
    : value === 'cancelled' || value === 'rejected' || value === 'inactive'
      ? 'bg-rose-50 text-rose-800'
      : value === 'draft' || value === 'pending' || value === 'not_submitted'
        ? 'bg-slate-100 text-slate-700'
        : 'bg-amber-50 text-amber-800'
  return <Badge variant="outline" className={`border-transparent capitalize ${tone}`}>{value.replaceAll('_', ' ')}</Badge>
}

export function SourceBadges({ sourceSystem }: { sourceSystem: string }) {
  const label = sourceSystem === 'SYNTHETIC_DEMO' ? 'Synthetic demo'
    : sourceSystem === 'MANUAL_ENTRY' ? 'Manual entry'
      : sourceSystem.replaceAll('_', ' ')
  return <div className="flex flex-wrap gap-1.5" aria-label="Record data source">
    <Badge variant="outline" className={sourceSystem === 'MANUAL_ENTRY'
      ? 'border-violet-200 bg-violet-50 text-violet-800'
      : 'border-slate-200 bg-slate-50 text-slate-700'}>{label}</Badge>
  </div>
}
