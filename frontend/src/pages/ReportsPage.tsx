import { useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { PageHeading, Pager, StateMessage } from '../components/RegistryPrimitives'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { formatDate, formatInr, responseError } from '../lib/registry'

type InstitutionRow = { institution_id: string; institution_name: string; total_fdrs: number; active_fdrs: number; total_principal: string; nearest_upcoming_maturity: string | null }
type MaturityRow = { record_id: string; institution_id: string; institution_name: string; internal_fdr_id: string; fdr_number: string; bank_name: string; amount: string; currency: string; maturity_date: string; record_status: string; bucket: string }
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

export default function ReportsPage() {
  const { apiFetch, user } = useAuth()
  const [summary, setSummary] = useState<Page<InstitutionRow> | null>(null)
  const [maturities, setMaturities] = useState<Page<MaturityRow> | null>(null)
  const [institutionPage, setInstitutionPage] = useState(1)
  const [page, setPage] = useState(1)
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [bucket, setBucket] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [exporting, setExporting] = useState(false)
  const canExport = Boolean(user?.permissions.includes('report.export'))
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    const params = new URLSearchParams({ page: String(page), page_size: '10' })
    if (from) params.set('maturity_from', from)
    if (to) params.set('maturity_to', to)
    if (bucket) params.set('bucket', bucket)
    void Promise.all([apiFetch(`/api/v1/reports/institution-summary?page=${institutionPage}&page_size=10`), apiFetch(`/api/v1/reports/maturities?${params}`)])
      .then(async ([a,b]) => { if (!a.ok) throw new Error(await responseError(a)); if (!b.ok) throw new Error(await responseError(b)); return Promise.all([a.json() as Promise<Page<InstitutionRow>>, b.json() as Promise<Page<MaturityRow>>]) })
      .then(([a,b]) => { if(active){setSummary(a);setMaturities(b)} })
      .catch((reason: unknown) => { if(active) setError(reason instanceof Error ? reason.message : 'Reports could not be loaded.') })
      .finally(() => { if(active) setLoading(false) })
    return () => { active = false }
  }, [apiFetch, institutionPage, page, from, to, bucket])
  async function exportCsv(report: 'institution-summary'|'maturities') {
    setExporting(true)
    try {
      const query = new URLSearchParams({ format: 'csv' })
      if (report === 'maturities') { if(from) query.set('maturity_from', from); if(to) query.set('maturity_to', to); if(bucket) query.set('bucket', bucket) }
      const response = await apiFetch(`/api/v1/reports/${report}?${query}`, { headers: { Accept: 'text/csv' } })
      if (!response.ok) throw new Error(await responseError(response))
      const blob = await response.blob(), url = URL.createObjectURL(blob), anchor = document.createElement('a')
      anchor.href = url; anchor.download = report === 'maturities' ? 'maturities.csv' : 'institution-summary.csv'; anchor.click(); URL.revokeObjectURL(url)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'CSV export failed.') } finally { setExporting(false) }
  }
  return <section className="space-y-6"><PageHeading title="Reports" description="Read-only institution and maturity reports for authorised data."/>
    {error && <StateMessage kind="error">{error}</StateMessage>}
    <Card><CardHeader><div className="flex items-center justify-between gap-3"><CardTitle>Institution summary</CardTitle>{canExport && <Button variant="outline" disabled={exporting} onClick={() => void exportCsv('institution-summary')}>Export CSV</Button>}</div></CardHeader><CardContent>
      {loading ? <p role="status">Loading institution summary…</p> : !summary?.items.length ? <p>No institution summary data.</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-2">Institution</th><th className="p-2">Total FDRs</th><th className="p-2">Active</th><th className="p-2">Total principal</th><th className="p-2">Nearest maturity</th></tr></thead><tbody>{summary.items.map((r)=><tr key={r.institution_id} className="border-t"><td className="p-2">{r.institution_name}</td><td className="p-2">{r.total_fdrs}</td><td className="p-2">{r.active_fdrs}</td><td className="p-2">{formatInr(r.total_principal)}</td><td className="p-2">{formatDate(r.nearest_upcoming_maturity)}</td></tr>)}</tbody></table></div>}
      {summary && <Pager page={summary.page} pageSize={summary.page_size} total={summary.total} onPageChange={setInstitutionPage}/>}
    </CardContent></Card>
    <Card><CardHeader><div className="flex items-center justify-between gap-3"><CardTitle>Maturity report</CardTitle>{canExport && <Button variant="outline" disabled={exporting} onClick={() => void exportCsv('maturities')}>Export CSV</Button>}</div></CardHeader><CardContent>
      <div className="mb-4 grid gap-3 sm:grid-cols-4"><label className="text-xs">Maturity from<Input aria-label="Maturity from" type="date" value={from} onChange={(e)=>{setFrom(e.target.value);setPage(1)}}/></label><label className="text-xs">Maturity to<Input aria-label="Maturity to" type="date" value={to} onChange={(e)=>{setTo(e.target.value);setPage(1)}}/></label><label className="text-xs">Bucket<select aria-label="Maturity bucket" value={bucket} onChange={(e)=>{setBucket(e.target.value);setPage(1)}} className="mt-1 h-9 w-full rounded-lg border bg-white px-2"><option value="">All buckets</option>{['urgent','attention','upcoming','normal','overdue-date review'].map(v=><option key={v}>{v}</option>)}</select></label></div>
      {loading ? <p role="status">Loading maturity report…</p> : !maturities?.items.length ? <p>No maturities match these filters.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><thead><tr><th className="p-2">Institution</th><th className="p-2">Internal ID</th><th className="p-2">FDR / Bank</th><th className="p-2">Principal</th><th className="p-2">Maturity</th><th className="p-2">Bucket</th></tr></thead><tbody>{maturities.items.map((r)=><tr key={r.record_id} className="border-t"><td className="p-2">{r.institution_name}</td><td className="p-2">{r.internal_fdr_id}</td><td className="p-2">{r.fdr_number} · {r.bank_name}</td><td className="p-2">{formatInr(r.amount,r.currency)}</td><td className="p-2">{formatDate(r.maturity_date)}</td><td className="p-2 capitalize">{r.bucket}</td></tr>)}</tbody></table></div>}
      {maturities && <Pager page={maturities.page} pageSize={maturities.page_size} total={maturities.total} onPageChange={setPage}/>}
    </CardContent></Card>
  </section>
}
