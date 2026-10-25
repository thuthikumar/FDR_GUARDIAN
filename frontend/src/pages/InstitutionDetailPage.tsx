import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { PageHeading, StateMessage, StatusBadge } from '../components/RegistryPrimitives'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { formatDate, formatInr, responseError, type FdrRecord, type InstitutionDetail, type PageResult } from '../lib/registry'

export default function InstitutionDetailPage() {
  const { institutionId = '' } = useParams()
  const { apiFetch } = useAuth()
  const [institution, setInstitution] = useState<InstitutionDetail | null>(null)
  const [records, setRecords] = useState<FdrRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    void Promise.all([
      apiFetch(`/api/v1/institutions/${institutionId}`),
      apiFetch(`/api/v1/fdrs?institution_id=${encodeURIComponent(institutionId)}&page=1&page_size=10&sort_by=maturity_date`),
    ]).then(async ([institutionResponse, recordsResponse]) => {
      if (!institutionResponse.ok) throw new Error(await responseError(institutionResponse))
      if (!recordsResponse.ok) throw new Error(await responseError(recordsResponse))
      const [detail, page] = await Promise.all([
        institutionResponse.json() as Promise<InstitutionDetail>,
        recordsResponse.json() as Promise<PageResult<FdrRecord>>,
      ])
      if (active) { setInstitution(detail); setRecords(page.items) }
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Institution details could not be loaded.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [apiFetch, institutionId])

  if (loading) return <StateMessage kind="loading">Loading institution details…</StateMessage>
  if (error || !institution) return <StateMessage kind="error">{error || 'Institution not found.'}</StateMessage>

  const stats = institution.stats
  return (
    <section>
      <PageHeading title={institution.institution_name} description={`${institution.institution_code}${institution.state ? ` · ${institution.state}` : ''}`} action={<Button variant="outline" render={<Link to="/institutions" />}>Back to institutions</Button>} />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Total FDRs" value={stats.total_fdrs.toLocaleString('en-IN')} />
        <Stat label="Active FDRs" value={stats.active_fdrs.toLocaleString('en-IN')} />
        <Stat label="Total principal" value={formatInr(stats.total_principal_amount)} />
        <Stat label="Nearest maturity" value={formatDate(stats.nearest_upcoming_maturity_date)} />
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">Institution FDRs</CardTitle></CardHeader>
        <CardContent className="p-0">
          {records.length === 0 ? <div className="p-4"><StateMessage kind="empty">No FDR records are registered for this institution.</StateMessage></div> : (
            <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Internal ID</th><th className="px-4 py-3">Bank / FDR number</th><th className="px-4 py-3">Principal</th><th className="px-4 py-3">Maturity</th><th className="px-4 py-3">Status</th></tr></thead>
              <tbody className="divide-y divide-slate-100">{records.map((record) => <tr key={record.id}>
                <td className="px-4 py-4 font-mono text-xs"><Link to={`/fdrs/${record.id}`} className="text-blue-800 underline-offset-4 hover:underline">{record.internal_fdr_id}</Link></td>
                <td className="px-4 py-4">{record.bank_name}<span className="block text-xs text-slate-500">{record.fdr_number}</span></td>
                <td className="px-4 py-4">{formatInr(record.amount, record.currency)}</td>
                <td className="px-4 py-4">{formatDate(record.maturity_date)}</td>
                <td className="px-4 py-4"><StatusBadge value={record.record_status} /></td>
              </tr>)}</tbody>
            </table></div>
          )}
        </CardContent>
      </Card>
    </section>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return <Card><CardContent className="p-5"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 text-xl font-bold text-slate-900">{value}</p></CardContent></Card>
}
