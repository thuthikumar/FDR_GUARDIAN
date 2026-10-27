import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { PageHeading, Pager, StateMessage, StatusBadge } from '../components/RegistryPrimitives'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { responseError, type Institution, type PageResult } from '../lib/registry'

const PAGE_SIZE = 10

export default function InstitutionsPage() {
  const { apiFetch, user } = useAuth()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<PageResult<Institution> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
    if (search.trim()) query.set('q', search.trim())
    if (status) query.set('status', status)
    void apiFetch(`/api/v1/institutions?${query}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(await responseError(response))
        return response.json() as Promise<PageResult<Institution>>
      })
      .then((result) => { if (active) setData(result) })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Institutions could not be loaded.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [apiFetch, page, search, status])

  function updateSearch(value: string) { setSearch(value); setPage(1) }

  return (
    <section>
      <PageHeading
        title="Institutions"
        description="Browse registered institutions and their synthetic FDR portfolio summaries."
        action={user?.permissions.includes('institution.write')
          ? <Button onClick={() => navigate('/institutions/new')}>Add institution</Button>
          : undefined}
      />
      <Card>
        <CardContent className="p-0">
          <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row">
            <label className="sr-only" htmlFor="institution-search">Search institution name or code</label>
            <Input id="institution-search" placeholder="Search name or code" value={search} onChange={(event) => updateSearch(event.target.value)} className="sm:max-w-sm" />
            <label className="sr-only" htmlFor="institution-status">Filter by status</label>
            <select id="institution-status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }} className="h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-2 focus-visible:outline-ring">
              <option value="">All statuses</option><option value="active">Active</option><option value="pending">Pending</option><option value="inactive">Inactive</option>
            </select>
          </div>
          {loading ? <StateMessage kind="loading">Loading institutions…</StateMessage>
            : error ? <div className="p-4"><StateMessage kind="error">{error}</StateMessage></div>
              : !data?.items.length ? <div className="p-4"><StateMessage kind="empty">No institutions match these filters.</StateMessage></div>
                : <>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[640px] text-left text-sm">
                      <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Institution</th><th className="px-4 py-3">Code</th><th className="px-4 py-3">State</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Data</th></tr></thead>
                      <tbody className="divide-y divide-slate-100">
                        {data.items.map((institution) => <tr key={institution.id} className="hover:bg-slate-50">
                          <td className="px-4 py-4 font-semibold"><Link className="text-blue-800 underline-offset-4 hover:underline" to={`/institutions/${institution.id}`}>{institution.institution_name}</Link></td>
                          <td className="px-4 py-4 font-mono text-xs">{institution.institution_code}</td>
                          <td className="px-4 py-4">{institution.state || '—'}</td>
                          <td className="px-4 py-4"><StatusBadge value={institution.status} /></td>
                          <td className="px-4 py-4">{institution.is_synthetic ? 'Synthetic' : 'Manual'}</td>
                        </tr>)}
                      </tbody>
                    </table>
                  </div>
                  <Pager page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
                </>}
        </CardContent>
      </Card>
    </section>
  )
}
