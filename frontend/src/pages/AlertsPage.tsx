import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { FormEvent } from 'react'
import { useAuth } from '../auth/AuthContext'
import { BRANDING } from '../config/branding'
import { PageHeading, Pager, StateMessage } from '../components/RegistryPrimitives'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { formatDate, responseError } from '../lib/registry'

type AlertRow = { id:string; alert_type:string; rule_key:string|null; severity:string; status:string; explanation:string; created_at:string; fdr:{record_id:string;internal_fdr_id:string;fdr_number:string;bank_name:string;maturity_date:string;record_status:string;institution_id:string;institution_name:string} }
type AlertDetail = AlertRow & { details:{days_remaining:number|null;maturity_date:string|null;lifecycle:Array<{event:string;at:string;remarks?:string;reason?:string}>}; history:Array<{event:string;at:string;remarks?:string}> }
type Page = { items:AlertRow[];total:number;page:number;page_size:number }
const badge = 'inline-flex rounded-full px-2 py-1 text-xs font-medium capitalize'

export default function AlertsPage() {
  const { apiFetch, user } = useAuth()
  const [searchParams] = useSearchParams()
  const [data,setData]=useState<Page|null>(null), [detail,setDetail]=useState<AlertDetail|null>(null)
  const [loading,setLoading]=useState(true), [error,setError]=useState(''), [page,setPage]=useState(1)
  const [severity,setSeverity]=useState(searchParams.get('severity')||''), [type,setType]=useState(searchParams.get('alert_type')||''), [status,setStatus]=useState(searchParams.get('status')||''), [institution,setInstitution]=useState(searchParams.get('institution_id')||''), [q,setQ]=useState('')
  const ruleKey=searchParams.get('rule_key')||''
  const [remarks,setRemarks]=useState(''), [resolving,setResolving]=useState<string|null>(null), [saving,setSaving]=useState(false)
  const canManage=Boolean(user?.permissions.includes('alert.manage'))
  const load=useCallback(async()=>{
    setLoading(true);setError('')
    const query=new URLSearchParams({page:String(page),page_size:'20',sort_by:'created_at',sort_order:'desc'})
    if(severity)query.set('severity',severity);if(type)query.set('alert_type',type);if(status)query.set('status',status);if(institution && user?.role!=='institution_admin')query.set('institution_id',institution);if(q.trim())query.set('q',q.trim())
    if(ruleKey)query.set('rule_key',ruleKey)
    const response=await apiFetch(`/api/v1/alerts?${query}`)
    if(!response.ok)throw new Error(await responseError(response))
    setData(await response.json() as Page)
  },[apiFetch,page,severity,type,status,institution,q,ruleKey,user?.role])
  useEffect(()=>{void load().catch((reason:unknown)=>setError(reason instanceof Error?reason.message:'Alerts could not be loaded.')).finally(()=>setLoading(false))},[load])
  function filtersChanged(update:()=>void){update();setPage(1);setDetail(null)}
  async function inspect(row:AlertRow){
    if(detail?.id===row.id){setDetail(null);return}
    const response=await apiFetch(`/api/v1/alerts/${row.id}`)
    if(!response.ok){setError(await responseError(response));return}
    setDetail(await response.json() as AlertDetail)
  }
  async function acknowledge(row:AlertRow){
    const response=await apiFetch(`/api/v1/alerts/${row.id}/acknowledge`,{method:'POST'})
    if(!response.ok){setError(await responseError(response));return}
    await load()
  }
  async function resolve(event:FormEvent<HTMLFormElement>){
    event.preventDefault();if(!resolving||!remarks.trim())return
    setSaving(true)
    try{const response=await apiFetch(`/api/v1/alerts/${resolving}/resolve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({remarks:remarks.trim()})});if(!response.ok)throw new Error(await responseError(response));setResolving(null);setRemarks('');await load()}
    catch(reason){setError(reason instanceof Error?reason.message:'Alert could not be resolved.')}
    finally{setSaving(false)}
  }
  return <section className="space-y-5"><PageHeading title="Alert Centre" description="Review stored alerts and the maturity rule that explains each monitoring alert."/><p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{BRANDING.policyCaution}</p>
    <Card><CardContent><div className="grid gap-3 py-3 sm:grid-cols-2 lg:grid-cols-5">
      <label className="text-xs">Search internal FDR ID<Input aria-label="Search internal FDR ID" value={q} onChange={(e)=>filtersChanged(()=>setQ(e.target.value))}/></label>
      <label className="text-xs">Severity<select aria-label="Filter severity" value={severity} onChange={(e)=>filtersChanged(()=>setSeverity(e.target.value))} className="mt-1 h-9 w-full rounded-lg border bg-white px-2"><option value="">All severities</option>{['low','medium','high','critical'].map(v=><option key={v}>{v}</option>)}</select></label>
      <label className="text-xs">Alert type<select aria-label="Filter alert type" value={type} onChange={(e)=>filtersChanged(()=>setType(e.target.value))} className="mt-1 h-9 w-full rounded-lg border bg-white px-2"><option value="">All types</option>{['maturity_upcoming','maturity_attention_required','maturity_urgent','maturity_overdue_date_review','amount_mismatch','fdr_number_mismatch','maturity_date_mismatch','duplicate_identifier'].map(v=><option key={v}>{v}</option>)}</select></label>
      <label className="text-xs">Status<select aria-label="Filter status" value={status} onChange={(e)=>filtersChanged(()=>setStatus(e.target.value))} className="mt-1 h-9 w-full rounded-lg border bg-white px-2"><option value="">All statuses</option>{['unresolved','open','acknowledged','resolved','superseded'].map(v=><option key={v}>{v}</option>)}</select></label>
      {user?.role!=='institution_admin'&&<label className="text-xs">Institution ID<Input aria-label="Filter institution ID" value={institution} onChange={(e)=>filtersChanged(()=>setInstitution(e.target.value))}/></label>}
    </div></CardContent></Card>
    {error&&<StateMessage kind="error">{error}</StateMessage>}
    <Card><CardContent className="p-0">{loading?<StateMessage kind="loading">Loading alerts…</StateMessage>:!data?.items.length?<StateMessage kind="empty">No alerts match these filters.</StateMessage>:<div className="divide-y">{data.items.map((row)=><article key={row.id} className="space-y-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><span className={`${badge} ${row.severity==='critical'||row.severity==='high'?'bg-rose-100 text-rose-800':'bg-amber-100 text-amber-900'}`}>{row.severity}</span><span className={`${badge} bg-slate-100 text-slate-700`}>{row.status}</span><span className="text-sm font-semibold">{row.alert_type.replaceAll('_',' ')}</span></div><p className="mt-2 text-sm">{row.explanation}</p><p className="mt-1 text-xs text-slate-500">{row.fdr.institution_name} · created {new Date(row.created_at).toLocaleString('en-IN')}</p></div><div className="flex flex-wrap gap-2"><Link className="text-sm text-blue-800 underline" to={`/fdrs/${row.fdr.record_id}`}>{row.fdr.internal_fdr_id}</Link><Button variant="outline" size="sm" onClick={()=>void inspect(row)}>{detail?.id===row.id?'Hide details':'Why this alert?'}</Button>{canManage&&row.status==='open'&&<Button variant="outline" size="sm" onClick={()=>void acknowledge(row)}>Acknowledge</Button>}{canManage&&(row.status==='open'||row.status==='acknowledged')&&<Button size="sm" onClick={()=>{setResolving(row.id);setRemarks('')}}>Resolve</Button>}</div></div>
      {detail?.id===row.id&&<div className="rounded-lg bg-slate-50 p-3 text-sm"><p><strong>Stored maturity date:</strong> {formatDate(detail.details.maturity_date||row.fdr.maturity_date)} {detail.details.days_remaining!==null&&detail.details.days_remaining!==undefined&&`(${detail.details.days_remaining} days from evaluation)`}</p><h3 className="mt-3 font-semibold">Lifecycle history</h3><ol className="mt-1 space-y-1">{detail.history.map((item,index)=><li key={`${item.at}-${index}`}>{new Date(item.at).toLocaleString('en-IN')} · {item.event.replaceAll('_',' ')}{item.remarks&&`: ${item.remarks}`}</li>)}</ol></div>}
    </article>)}</div>}{data&&<Pager page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage}/>}</CardContent></Card>
    {resolving&&<div role="dialog" aria-modal="true" aria-labelledby="resolve-alert-title" className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4"><form onSubmit={(e)=>void resolve(e)} className="w-full max-w-md space-y-4 rounded-xl bg-white p-5 shadow-xl"><h2 id="resolve-alert-title" className="text-lg font-semibold">Resolve alert</h2><label htmlFor="resolve-remarks" className="text-sm">Resolution remarks</label><textarea id="resolve-remarks" required minLength={1} maxLength={1000} value={remarks} onChange={(e)=>setRemarks(e.target.value)} className="min-h-28 w-full rounded-lg border p-3"/><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={()=>setResolving(null)}>Cancel</Button><Button type="submit" disabled={saving||!remarks.trim()}>{saving?'Saving…':'Confirm resolution'}</Button></div></form></div>}
  </section>
}
