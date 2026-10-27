import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useAuth } from '../auth/AuthContext'
import { PageHeading, StateMessage } from '../components/RegistryPrimitives'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import MonitoringAdminPanel from '../components/MonitoringAdminPanel'
import { responseError } from '../lib/registry'

type Summary = { total_institutions: number; total_fdr_records: number; active_records: number; upcoming_maturities: number; overdue_date_review: number; pending_verification_cases: number; unresolved_alerts: number }
type Point = { label: string; count: number; id?: string | null }
type Charts = { records_by_status: Point[]; maturities_by_month: Point[]; institution_distribution: Point[]; cases_by_status: Point[] }
type Monitoring = { counts_by_status: Record<string,number>; upcoming_maturities_by_band: Record<string,number> }
const colors = ['#1d4ed8', '#0f766e', '#b45309', '#be123c', '#475569', '#7e22ce']

function appDate(offsetDays = 0) {
  const now = new Date()
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now)
  const year = Number(parts.find((part) => part.type === 'year')?.value)
  const month = Number(parts.find((part) => part.type === 'month')?.value)
  const day = Number(parts.find((part) => part.type === 'day')?.value)
  return new Date(Date.UTC(year, month - 1, day + offsetDays)).toISOString().slice(0, 10)
}

export default function DashboardPage() {
  const { apiFetch, user } = useAuth()
  const navigate = useNavigate()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [charts, setCharts] = useState<Charts | null>(null)
  const [monitoring, setMonitoring] = useState<Monitoring | null>(null)
  const [summaryState, setSummaryState] = useState<'loading'|'error'|'ready'>('loading')
  const [chartState, setChartState] = useState<'loading'|'error'|'ready'>('loading')
  useEffect(() => {
    let active = true
    void apiFetch('/api/v1/dashboard/summary').then(async (r) => { if (!r.ok) throw new Error(await responseError(r)); return r.json() as Promise<Summary> }).then((v) => { if (active) { setSummary(v); setSummaryState('ready') } }).catch(() => { if (active) setSummaryState('error') })
    void apiFetch('/api/v1/dashboard/charts').then(async (r) => { if (!r.ok) throw new Error(await responseError(r)); return r.json() as Promise<Charts> }).then((v) => { if (active) { setCharts(v); setChartState('ready') } }).catch(() => { if (active) setChartState('error') })
    void apiFetch('/api/v1/monitoring/summary').then(async (r) => { if (!r.ok) throw new Error(await responseError(r)); return r.json() as Promise<Monitoring> }).then((v) => { if (active) setMonitoring(v) }).catch(() => { if (active) setMonitoring(null) })
    return () => { active = false }
  }, [apiFetch])
  const today = appDate()
  const upcomingTo = appDate(90)
  const nearTerm = monitoring ? ['maturity_urgent','maturity_attention_required','maturity_upcoming'].reduce((total,key)=>total+(monitoring.upcoming_maturities_by_band[key]||0),0) : 0
  const unresolved = monitoring ? (monitoring.counts_by_status.open||0)+(monitoring.counts_by_status.acknowledged||0) : 0
  const overdue = monitoring?.upcoming_maturities_by_band.maturity_overdue_date_review || 0
  const cards = summary ? [
    ['Total institutions', summary.total_institutions, '/institutions'], ['Total FDR records', summary.total_fdr_records, '/fdrs'], ['Active records', summary.active_records, '/fdrs?record_status=active'], ['Upcoming maturities (90 days)', monitoring ? nearTerm : '—', `/fdrs?maturity_from=${today}&maturity_to=${upcomingTo}`], ['Overdue-date review', monitoring ? overdue : '—', '/alerts?rule_key=maturity_overdue_date_review&status=unresolved'], ['Pending verification cases', summary.pending_verification_cases, '/fdrs'], ['Unresolved alerts / discrepancies', monitoring ? unresolved : '—', '/alerts?status=unresolved'],
  ] as const : []
  function chartCard(title: string, data: Point[] | undefined, onClick?: (point: Point) => void) {
    return <Card key={title}><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent>
      {chartState === 'loading' ? <p role="status" className="py-10 text-center text-sm text-slate-500">Loading chart…</p> : chartState === 'error' ? <p role="alert" className="py-10 text-center text-sm text-rose-700">Chart data could not be loaded.</p> : !data?.some((point) => point.count > 0) ? <p className="py-10 text-center text-sm text-slate-500">No data to display.</p> : <><div role="img" aria-label={`${title}. ${data.map((item) => `${item.label}: ${item.count}`).join(', ')}`} className="h-64 w-full">
        <ResponsiveContainer><BarChart data={data} onClick={(event) => { const item = (event as unknown as { activePayload?: Array<{ payload: Point }> })?.activePayload?.[0]?.payload; if (item) onClick?.(item) }}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="label" tick={{fontSize: 11}}/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="count" cursor={onClick ? 'pointer' : 'default'}>{data.map((entry, i) => <Cell key={entry.label} fill={colors[i % colors.length]}/>)}</Bar></BarChart></ResponsiveContainer>
      </div><div className="sr-only"><table><caption>{title} data</caption><tbody>{data.map((d)=><tr key={d.label}><th>{d.label}</th><td>{d.count}</td></tr>)}</tbody></table></div></>}
    </CardContent></Card>
  }
  return <section className="space-y-6"><PageHeading title="Dashboard" description="A current view of synthetic FDR registry data."/><p className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">Synthetic demo data. Dashboard values reflect records currently present; alert and verification-case generation is not performed here.</p>
    {summaryState === 'loading' ? <StateMessage kind="loading">Loading dashboard metrics…</StateMessage> : summaryState === 'error' ? <StateMessage kind="error">Dashboard metrics could not be loaded.</StateMessage> : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([label, value, to]) => <button key={label} onClick={() => navigate(to)} className="text-left"><Card className="h-full transition hover:ring-blue-300"><CardContent><p className="text-sm text-slate-600">{label}</p><p className="mt-2 text-2xl font-semibold">{typeof value === 'number' ? value.toLocaleString('en-IN') : value}</p></CardContent></Card></button>)}</div>}
    {!monitoring && <p role="alert" className="text-sm text-rose-700">Monitoring summary could not be loaded; maturity and alert counts are unavailable.</p>}
    {summary && <p className="text-xs text-slate-500">All monetary values use Indian rupees (INR). Overdue-date review means only that a stored maturity date is in the past.</p>}
    <div className="grid gap-5 xl:grid-cols-2">{chartCard('FDR records by status', charts?.records_by_status, (point) => navigate(`/fdrs?record_status=${encodeURIComponent(point.label)}`))}{chartCard('Upcoming maturities by month', charts?.maturities_by_month, (point) => navigate(`/fdrs?maturity_from=${point.label}-01&maturity_to=${point.label}-${new Date(Number(point.label.slice(0,4)),Number(point.label.slice(5,7)),0).getDate()}`))}{chartCard('Institution-wise record distribution (top 10 plus Others)', charts?.institution_distribution, (point) => point.id && navigate(`/fdrs?institution_id=${encodeURIComponent(point.id)}`))}{chartCard('Verification cases by status', charts?.cases_by_status)}</div>
    {user?.permissions.includes('monitoring.run') && <MonitoringAdminPanel />}
  </section>
}
