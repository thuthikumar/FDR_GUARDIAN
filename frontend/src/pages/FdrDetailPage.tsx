import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { PageHeading, SourceBadges, StateMessage, StatusBadge } from '../components/RegistryPrimitives'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import FdrDocuments from '../components/FdrDocuments'
import { formatDate, formatInr, formatHistoryAction, formatHistoryChanges, formatRecordStatusLabel, responseError, type FdrHistoryItem, type FdrRecord } from '../lib/registry'

const transitions: Record<string, string[]> = {
  draft: ['active', 'cancelled'], active: ['matured', 'cancelled'], matured: ['released'], released: [], cancelled: [],
}

export default function FdrDetailPage() {
  const { recordId = '' } = useParams()
  const { apiFetch, user } = useAuth()
  const [record, setRecord] = useState<FdrRecord | null>(null)
  const [history, setHistory] = useState<FdrHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusChoice, setStatusChoice] = useState('')
  const [remarks, setRemarks] = useState('')
  const [savingStatus, setSavingStatus] = useState(false)
  const [statusError, setStatusError] = useState('')

  const load = useCallback(async () => {
    const [recordResponse, historyResponse] = await Promise.all([
      apiFetch(`/api/v1/fdrs/${recordId}`), apiFetch(`/api/v1/fdrs/${recordId}/history`),
    ])
    if (!recordResponse.ok) throw new Error(await responseError(recordResponse))
    if (!historyResponse.ok) throw new Error(await responseError(historyResponse))
    const [recordBody, historyBody] = await Promise.all([
      recordResponse.json() as Promise<FdrRecord>, historyResponse.json() as Promise<FdrHistoryItem[]>,
    ])
    setRecord(recordBody)
    setHistory(historyBody)
  }, [apiFetch, recordId])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    void load().catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'FDR details could not be loaded.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [load])

  async function changeStatus(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!statusChoice || !remarks.trim()) { setStatusError('Choose a status and enter remarks.'); return }
    setSavingStatus(true)
    setStatusError('')
    try {
      const response = await apiFetch(`/api/v1/fdrs/${recordId}/status`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ record_status: statusChoice, remarks: remarks.trim() }),
      })
      if (!response.ok) throw new Error(await responseError(response))
      setRemarks('')
      setStatusChoice('')
      await load()
    } catch (reason) {
      setStatusError(reason instanceof Error ? reason.message : 'Status could not be changed.')
    } finally { setSavingStatus(false) }
  }

  if (loading) return <StateMessage kind="loading">Loading FDR details…</StateMessage>
  if (error || !record) return <StateMessage kind="error">{error || 'FDR record not found.'}</StateMessage>
  const allowedNext = transitions[record.record_status] || []

  return <section>
    <PageHeading title={record.internal_fdr_id} description={`${record.bank_name}${record.branch_name ? ` · ${record.branch_name}` : ''}`} action={<div className="flex gap-2"><Link to="/fdrs" className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100">Back to registry</Link>{user?.permissions.includes('fdr.write') && <Link to={`/fdrs/${record.id}/edit`} className="rounded-lg bg-blue-800 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-900">Edit record</Link>}</div>} />
    <div className="grid gap-5 xl:grid-cols-[1fr_22rem]">
      <div className="space-y-5">
        <Card><CardHeader><CardTitle className="text-base">Record details</CardTitle></CardHeader><CardContent>
          <dl className="grid gap-x-6 gap-y-5 sm:grid-cols-2">
            <Detail label="FDR number" value={record.fdr_number} /><Detail label="Institution ID" value={record.institution_id} />
            <Detail label="Bank" value={record.bank_name} /><Detail label="Branch" value={record.branch_name || '—'} />
            <Detail label="Principal" value={formatInr(record.amount, record.currency)} /><Detail label="Currency" value={record.currency} />
            <Detail label="Issue date" value={formatDate(record.issue_date)} /><Detail label="Maturity date" value={formatDate(record.maturity_date)} />
            <div><dt className="text-xs uppercase text-slate-500">Record status</dt><dd className="mt-1"><StatusBadge value={record.record_status} /></dd></div>
            <div><dt className="text-xs uppercase text-slate-500">Verification status</dt><dd className="mt-1"><StatusBadge value={record.verification_status} /></dd></div>
            <div className="sm:col-span-2"><dt className="mb-1 text-xs uppercase text-slate-500">Data source</dt><dd><SourceBadges sourceSystem={record.source_system} /></dd></div>
          </dl>
        </CardContent></Card>
        <ActiveAlerts recordId={record.id} />
        {(user?.permissions.includes('document.read') || user?.permissions.includes('document.upload')) && <FdrDocuments recordId={record.id} />}
        <Card><CardHeader><CardTitle className="text-base">Change history</CardTitle></CardHeader><CardContent>
          {history.length === 0 ? <p className="text-sm text-slate-500">No changes have been recorded yet.</p> : <ol className="space-y-5 border-l border-slate-200 pl-5">
            {history.map((item, index) => <li key={`${index}-${item.timestamp}`} className="relative"><span className="absolute -left-[1.6rem] top-1 size-2.5 rounded-full bg-blue-700" />
              <p className="text-sm font-semibold">{formatHistoryAction(item.action)} <span className="font-normal text-slate-500">by {item.actor_name}</span></p>
              <time className="text-xs text-slate-500" dateTime={item.timestamp}>{new Date(item.timestamp).toLocaleString('en-IN')}</time>
              <ul className="mt-2 space-y-1 text-sm text-slate-700">{formatHistoryChanges(item).map(({ field, oldValue, newValue }) => <li key={field}><span>{field}</span>: {oldValue} → {newValue}</li>)}</ul>
              {item.remarks && <p className="mt-2 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{item.remarks}</p>}
            </li>)}
          </ol>}
        </CardContent></Card>
      </div>
      {user?.permissions.includes('fdr.write') && <Card className="h-fit"><CardHeader><CardTitle className="text-base">Change record status</CardTitle></CardHeader><CardContent>
        {allowedNext.length ? <form className="space-y-4" onSubmit={changeStatus}>
          <div className="space-y-1.5"><label htmlFor="next-status" className="text-sm font-medium">New status</label><select id="next-status" required value={statusChoice} onChange={(event) => setStatusChoice(event.target.value)} className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm"><option value="">Choose a status</option>{allowedNext.map((value) => <option key={value} value={value}>{formatRecordStatusLabel(value)}</option>)}</select></div>
          <div className="space-y-1.5"><label htmlFor="status-remarks" className="text-sm font-medium">Remarks</label><textarea id="status-remarks" required minLength={1} maxLength={1000} value={remarks} onChange={(event) => setRemarks(event.target.value)} rows={4} className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-ring" /></div>
          {statusError && <p role="alert" className="text-sm text-rose-700">{statusError}</p>}
          <Button type="submit" disabled={savingStatus || !remarks.trim()}>{savingStatus ? 'Saving…' : 'Save status'}</Button>
        </form> : <p className="text-sm text-slate-600">This record has no remaining status transitions.</p>}
      </CardContent></Card>}
    </div>
  </section>
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs uppercase text-slate-500">{label}</dt><dd className="mt-1 break-words text-sm font-medium">{value}</dd></div>
}

function ActiveAlerts({ recordId }: { recordId: string }) {
  const { apiFetch } = useAuth()
  const [items, setItems] = useState<Array<{id:string;alert_type:string;severity:string;status:string;explanation:string}>>([])
  const [state, setState] = useState<'loading'|'ready'|'error'>('loading')
  useEffect(() => {
    let active=true
    void apiFetch(`/api/v1/alerts?fdr_id=${recordId}&status=unresolved&page_size=100`).then(async (response)=>{
      if(!response.ok)throw new Error('Unable to load active alerts')
      const body=await response.json() as {items:Array<{id:string;alert_type:string;severity:string;status:string;explanation:string}>}
      if(active)setItems(body.items)
    }).then(()=>{if(active)setState('ready')}).catch(()=>{if(active)setState('error')})
    return()=>{active=false}
  },[apiFetch,recordId])
  return <Card><CardHeader><CardTitle className="text-base">Active alerts</CardTitle></CardHeader><CardContent>
    {state==='loading'?<p role="status" className="text-sm text-slate-500">Loading active alerts…</p>:state==='error'?<p role="alert" className="text-sm text-rose-700">Active alerts could not be loaded.</p>:items.length===0?<p className="text-sm text-slate-500">No active alerts for this record.</p>:<ul className="space-y-3">{items.map((item)=><li key={item.id} className="rounded-lg border p-3"><p className="text-sm font-semibold capitalize">{item.alert_type.replaceAll('_',' ')} · {item.severity} · {item.status}</p><p className="mt-1 text-sm text-slate-700">{item.explanation}</p></li>)}</ul>}
  </CardContent></Card>
}
