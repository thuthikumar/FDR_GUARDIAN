import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { PageHeading, Pager, SourceBadges, StateMessage, StatusBadge } from '../components/RegistryPrimitives'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { formatDate, formatInr, responseError, type FdrRecord, type PageResult } from '../lib/registry'

const PAGE_SIZE = 10

export default function FdrsPage() {
  const { apiFetch, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [search, setSearch] = useState(() => new URLSearchParams(location.search).get('q') || '')
  const [status, setStatus] = useState(() => new URLSearchParams(window.location.search).get('record_status') || '')
  const [maturityFrom, setMaturityFrom] = useState(() => new URLSearchParams(window.location.search).get('maturity_from') || '')
  const [maturityTo, setMaturityTo] = useState(() => new URLSearchParams(window.location.search).get('maturity_to') || '')
  const [institutionId] = useState(() => new URLSearchParams(window.location.search).get('institution_id') || '')
  const [sortBy, setSortBy] = useState('maturity_date')
  const [sortOrder, setSortOrder] = useState('asc')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<PageResult<FdrRecord> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => { setSearch(new URLSearchParams(location.search).get('q') || '') }, [location.search])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE), sort_by: sortBy, sort_order: sortOrder })
    if (search.trim()) query.set('q', search.trim())
    if (status) query.set('record_status', status)
    if (maturityFrom) query.set('maturity_from', maturityFrom)
    if (maturityTo) query.set('maturity_to', maturityTo)
    if (institutionId) query.set('institution_id', institutionId)
    void apiFetch(`/api/v1/fdrs?${query}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(await responseError(response))
        return response.json() as Promise<PageResult<FdrRecord>>
      })
      .then((result) => { if (active) setData(result) })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'FDR records could not be loaded.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [apiFetch, page, search, status, maturityFrom, maturityTo, institutionId, sortBy, sortOrder])

  function resetPage(update: () => void) { update(); setPage(1) }

  return <section>
    <PageHeading title="FDR Registry" description="Search and review fixed deposit records. Development records are synthetic." action={user?.permissions.includes('fdr.write') ? <Button onClick={() => navigate('/fdrs/new')}>Add FDR</Button> : undefined} />
    <Card><CardContent className="p-0">
      <div className="grid gap-3 border-b border-slate-200 p-4 sm:grid-cols-2 xl:grid-cols-5">
        <label className="sr-only" htmlFor="fdr-search">Search internal ID, FDR number, or bank</label>
        <Input id="fdr-search" placeholder="Search ID, FDR number, or bank" value={search} onChange={(event) => resetPage(() => setSearch(event.target.value))} />
        <label className="sr-only" htmlFor="fdr-status">Filter by record status</label>
        <select id="fdr-status" value={status} onChange={(event) => resetPage(() => setStatus(event.target.value))} className="h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-2 focus-visible:outline-ring">
          <option value="">All statuses</option><option value="draft">Draft</option><option value="active">Active</option><option value="matured">Matured</option><option value="released">Released</option><option value="cancelled">Cancelled</option>
        </select>
        <label className="flex items-center gap-2 text-xs text-slate-600">Maturity from<Input aria-label="Maturity from" type="date" value={maturityFrom} onChange={(event) => resetPage(() => setMaturityFrom(event.target.value))} /></label>
        <label className="flex items-center gap-2 text-xs text-slate-600">Maturity to<Input aria-label="Maturity to" type="date" value={maturityTo} onChange={(event) => resetPage(() => setMaturityTo(event.target.value))} /></label>
        <div className="flex gap-2">
          <label className="sr-only" htmlFor="fdr-sort">Sort records by</label>
          <select id="fdr-sort" value={sortBy} onChange={(event) => resetPage(() => setSortBy(event.target.value))} className="h-9 min-w-0 flex-1 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-2 focus-visible:outline-ring">
            <option value="maturity_date">Maturity</option><option value="bank_name">Bank</option><option value="amount">Principal</option><option value="record_status">Status</option><option value="updated_at">Recently updated</option>
          </select>
          <Button variant="outline" aria-label={`Sort ${sortOrder === 'asc' ? 'ascending' : 'descending'}`} onClick={() => resetPage(() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc'))}>{sortOrder === 'asc' ? '↑' : '↓'}</Button>
        </div>
      </div>
      {loading ? <StateMessage kind="loading">Loading FDR records…</StateMessage>
        : error ? <div className="p-4"><StateMessage kind="error">{error}</StateMessage></div>
          : !data?.items.length ? <div className="p-4"><StateMessage kind="empty">No FDR records match these filters.</StateMessage></div>
            : <>
              <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Internal ID / FDR number</th><th className="px-4 py-3">Bank</th><th className="px-4 py-3">Principal</th><th className="px-4 py-3">Maturity</th><th className="px-4 py-3">Record / review</th><th className="px-4 py-3">Source</th></tr></thead>
                <tbody className="divide-y divide-slate-100">{data.items.map((record) => <tr key={record.id} className="hover:bg-slate-50">
                  <td className="px-4 py-4"><Link to={`/fdrs/${record.id}`} className="font-mono text-xs font-semibold text-blue-800 underline-offset-4 hover:underline">{record.internal_fdr_id}</Link><span className="mt-1 block text-xs text-slate-500">{record.fdr_number}</span></td>
                  <td className="px-4 py-4">{record.bank_name}{record.branch_name && <span className="block text-xs text-slate-500">{record.branch_name}</span>}</td>
                  <td className="px-4 py-4 whitespace-nowrap">{formatInr(record.amount, record.currency)}</td>
                  <td className="px-4 py-4 whitespace-nowrap">{formatDate(record.maturity_date)}</td>
                  <td className="px-4 py-4"><div className="flex flex-col items-start gap-1"><StatusBadge value={record.record_status} /><StatusBadge value={record.verification_status} /></div></td>
                  <td className="px-4 py-4"><SourceBadges sourceSystem={record.source_system} /></td>
                </tr>)}</tbody>
              </table></div>
              <Pager page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
            </>}
    </CardContent></Card>
  </section>
}
