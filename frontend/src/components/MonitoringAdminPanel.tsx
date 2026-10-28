import { useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { BRANDING } from '../config/branding'
import { Button } from './ui/button'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { responseError } from '../lib/registry'

type Rule = { rule_key:string;label:string;min_days:number|null;max_days:number|null;severity:string;is_active:boolean }
type Run = { id:string;status:string;trigger:string;started_at:string;records_evaluated:number;alerts_created:number;alerts_superseded:number;alerts_resolved:number;alerts_reopened:number;alerts_unchanged:number }
type RunPage = { items:Run[];total:number }
export default function MonitoringAdminPanel(){
  const {apiFetch}=useAuth()
  const [rules,setRules]=useState<Rule[]>([]),[runs,setRuns]=useState<Run[]>([]),[notice,setNotice]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(true)
  async function load(showDemoNotice=true){
    const [ruleResponse,runResponse]=await Promise.all([apiFetch('/api/v1/monitoring/rules'),apiFetch('/api/v1/monitoring/runs?page=1&page_size=5')])
    if(!ruleResponse.ok)throw new Error(await responseError(ruleResponse));if(!runResponse.ok)throw new Error(await responseError(runResponse))
    const [ruleBody,runBody]=await Promise.all([ruleResponse.json() as Promise<{items:Rule[];demo_default_notice:string}>,runResponse.json() as Promise<RunPage>])
    setRules(ruleBody.items);if(showDemoNotice)setNotice(ruleBody.demo_default_notice);setRuns(runBody.items)
  }
  useEffect(()=>{let active=true;void load().catch((reason:unknown)=>{if(active)setError(reason instanceof Error?reason.message:'Monitoring information could not be loaded.')}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[apiFetch])
  async function runNow(){
    setLoading(true);setError('')
    try{const response=await apiFetch('/api/v1/monitoring/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});if(!response.ok)throw new Error(await responseError(response));const result=await response.json() as Run;setNotice(`Run ${result.status}: evaluated ${result.records_evaluated}, created ${result.alerts_created}, superseded ${result.alerts_superseded}, resolved ${result.alerts_resolved}, reopened ${result.alerts_reopened}.`);await load(false)}
    catch(reason){setError(reason instanceof Error?reason.message:'Monitoring run failed.')}finally{setLoading(false)}
  }
  return <Card><CardHeader><div className="flex items-center justify-between gap-3"><CardTitle>Monitoring administration</CardTitle><Button onClick={()=>void runNow()} disabled={loading}>{loading?'Running…':'Run now'}</Button></div></CardHeader><CardContent className="space-y-4">
    {error&&<p role="alert" className="text-sm text-rose-700">{error}</p>}<p className="text-sm text-amber-900">{notice||BRANDING.policyCaution}</p>
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">{rules.map((rule)=><div key={rule.rule_key} className="rounded-lg border p-3"><p className="font-semibold">{rule.label}</p><p className="text-xs capitalize text-slate-600">{rule.min_days===null?'Past':`${rule.min_days} days`} – {rule.max_days===null?'and beyond':`${rule.max_days} days`} · {rule.severity}</p></div>)}</div>
    <h3 className="font-semibold">Recent runs</h3>{runs.length===0?<p className="text-sm text-slate-500">No monitoring runs yet.</p>:<div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-2">Started</th><th className="p-2">Trigger</th><th className="p-2">Status</th><th className="p-2">Evaluated</th><th className="p-2">Created</th><th className="p-2">Other changes</th></tr></thead><tbody>{runs.map(run=><tr key={run.id} className="border-t"><td className="p-2">{new Date(run.started_at).toLocaleString('en-IN')}</td><td className="p-2 capitalize">{run.trigger}</td><td className="p-2 capitalize">{run.status}</td><td className="p-2">{run.records_evaluated}</td><td className="p-2">{run.alerts_created}</td><td className="p-2">S {run.alerts_superseded} · R {run.alerts_resolved} · O {run.alerts_reopened} · U {run.alerts_unchanged}</td></tr>)}</tbody></table></div>}
  </CardContent></Card>
}
