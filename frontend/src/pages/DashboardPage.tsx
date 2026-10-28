import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Bell, CalendarDays, CheckCircle2, ClipboardCheck, FileText, Landmark } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useAuth } from '../auth/AuthContext'
import { useShellAlertCount } from '../components/AppShell'
import { PageHeading, StateMessage } from '../components/RegistryPrimitives'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import MonitoringAdminPanel from '../components/MonitoringAdminPanel'
import { responseError } from '../lib/registry'

type Summary = { total_institutions: number; total_fdr_records: number; active_records: number; upcoming_maturities: number; overdue_date_review: number; pending_verification_cases: number; unresolved_alerts: number }
type Point = { label: string; count: number; id?: string | null }
type Charts = { records_by_status: Point[]; maturities_by_month: Point[]; institution_distribution: Point[]; cases_by_status: Point[] }
type Monitoring = { counts_by_status: Record<string, number>; upcoming_maturities_by_band: Record<string, number> }

const colors = ['#1f4aa8', '#138808', '#b45f06', '#c62828', '#17306b', '#5d6678']
const cardIcons = [Landmark, FileText, CheckCircle2, CalendarDays, AlertTriangle, ClipboardCheck, Bell]

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
  const { setOpenAlertCount } = useShellAlertCount()
  const navigate = useNavigate()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [charts, setCharts] = useState<Charts | null>(null)
  const [monitoring, setMonitoring] = useState<Monitoring | null>(null)
  const [summaryState, setSummaryState] = useState<'loading' | 'error' | 'ready'>('loading')
  const [chartState, setChartState] = useState<'loading' | 'error' | 'ready'>('loading')

  useEffect(() => {
    let active = true
    void apiFetch('/api/v1/dashboard/summary').then(async (response) => {
      if (!response.ok) throw new Error(await responseError(response))
      return response.json() as Promise<Summary>
    }).then((value) => { if (active) { setSummary(value); setSummaryState('ready') } }).catch(() => { if (active) setSummaryState('error') })
    void apiFetch('/api/v1/dashboard/charts').then(async (response) => {
      if (!response.ok) throw new Error(await responseError(response))
      return response.json() as Promise<Charts>
    }).then((value) => { if (active) { setCharts(value); setChartState('ready') } }).catch(() => { if (active) setChartState('error') })
    void apiFetch('/api/v1/monitoring/summary').then(async (response) => {
      if (!response.ok) throw new Error(await responseError(response))
      return response.json() as Promise<Monitoring>
    }).then((value) => { if (active) setMonitoring(value) }).catch(() => { if (active) setMonitoring(null) })
    return () => { active = false }
  }, [apiFetch])

  useEffect(() => { setOpenAlertCount(summary?.unresolved_alerts ?? null) }, [setOpenAlertCount, summary?.unresolved_alerts])

  const today = appDate()
  const upcomingTo = appDate(90)
  const nearTerm = monitoring ? ['maturity_urgent', 'maturity_attention_required', 'maturity_upcoming'].reduce((total, key) => total + (monitoring.upcoming_maturities_by_band[key] || 0), 0) : 0
  const unresolved = monitoring ? (monitoring.counts_by_status.open || 0) + (monitoring.counts_by_status.acknowledged || 0) : 0
  const overdue = monitoring?.upcoming_maturities_by_band.maturity_overdue_date_review || 0
  const cards = summary ? [
    ['Total institutions', summary.total_institutions, '/institutions'],
    ['Total FDR records', summary.total_fdr_records, '/fdrs'],
    ['Active records', summary.active_records, '/fdrs?record_status=active'],
    ['Upcoming maturities (90 days)', monitoring ? nearTerm : '—', `/fdrs?maturity_from=${today}&maturity_to=${upcomingTo}`],
    ['Overdue-date review', monitoring ? overdue : '—', '/alerts?rule_key=maturity_overdue_date_review&status=unresolved'],
    ['Pending verification cases', summary.pending_verification_cases, '/fdrs'],
    ['Unresolved alerts / discrepancies', monitoring ? unresolved : '—', '/alerts?status=unresolved'],
  ] as const : []

  function chartCard(title: string, data: Point[] | undefined, onClick?: (point: Point) => void) {
    return <Card key={title} className="chart-card"><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent>
      {chartState === 'loading' ? <p role="status" className="py-10 text-center text-sm text-slate-500">Loading chart…</p>
        : chartState === 'error' ? <p role="alert" className="py-10 text-center text-sm text-rose-700">Chart data could not be loaded.</p>
          : !data?.some((point) => point.count > 0) ? <p className="py-10 text-center text-sm text-slate-500">No data to display.</p>
            : <>
              <div role="img" aria-label={`${title}. ${data.map((item) => `${item.label}: ${item.count}`).join(', ')}`} className="h-64 w-full">
                <ResponsiveContainer><BarChart data={data} onClick={(event) => {
                  const item = (event as unknown as { activePayload?: Array<{ payload: Point }> })?.activePayload?.[0]?.payload
                  if (item) onClick?.(item)
                }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e3e8f1" />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#5d6678' }} axisLine={{ stroke: '#e3e8f1' }} />
                  <YAxis allowDecimals={false} tick={{ fill: '#5d6678' }} axisLine={{ stroke: '#e3e8f1' }} />
                  <Tooltip contentStyle={{ borderColor: '#e3e8f1', borderRadius: 10 }} />
                  <Bar dataKey="count" cursor={onClick ? 'pointer' : 'default'}>{data.map((entry, index) => <Cell key={entry.label} fill={colors[index % colors.length]} />)}</Bar>
                </BarChart></ResponsiveContainer>
              </div>
              <div className="sr-only"><table><caption>{title} data</caption><tbody>{data.map((point) => <tr key={point.label}><th>{point.label}</th><td>{point.count}</td></tr>)}</tbody></table></div>
            </>}
    </CardContent></Card>
  }

  const dashboardDate = new Intl.DateTimeFormat('en-IN', { dateStyle: 'full', timeZone: 'Asia/Kolkata' }).format(new Date())
  const dashboardSummary = summary
    ? `${summary.total_fdr_records.toLocaleString('en-IN')} FDR records across ${summary.total_institutions.toLocaleString('en-IN')} institutions; ${summary.active_records.toLocaleString('en-IN')} are currently active.`
    : summaryState === 'error' ? 'Dashboard data could not be loaded.' : 'Loading current registry summary…'

  return <section className="dashboard-page">
    <PageHeading title="Dashboard" description="A current view of synthetic FDR registry data." />
    <section className="dashboard-hero" aria-label="Dashboard overview">
      <div className="hero-copy"><span className="hero-date">{dashboardDate}</span><h2>Welcome, {user?.full_name}</h2><p>{dashboardSummary}</p><span className="synthetic-demo-badge">Synthetic demo</span></div>
      <div className="hero-stat"><strong>{summary ? summary.active_records.toLocaleString('en-IN') : '—'}</strong><span>Active FDR records</span></div>
    </section>
    <p className="synthetic-demo-notice">Synthetic demo data. Dashboard values reflect records currently present; alert and verification-case generation is not performed here.</p>
    {summaryState === 'loading' ? <StateMessage kind="loading">Loading dashboard metrics…</StateMessage>
      : summaryState === 'error' ? <StateMessage kind="error">Dashboard metrics could not be loaded.</StateMessage>
        : <div className="dashboard-kpis">{cards.map(([label, value, to], index) => {
          const Icon = cardIcons[index]
          return <button key={label} onClick={() => navigate(to)} className="dashboard-kpi"><Card className="h-full transition hover:ring-blue-300"><CardContent>
            <span className="kpi-icon"><Icon aria-hidden="true" size={24} /></span>
            <strong className="kpi-value">{typeof value === 'number' ? value.toLocaleString('en-IN') : value}</strong>
            <span className="kpi-label">{label}</span>
          </CardContent></Card></button>
        })}</div>}
    {!monitoring && <p role="alert" className="text-sm text-rose-700">Monitoring summary could not be loaded; maturity and alert counts are unavailable.</p>}
    {summary && <p className="text-xs text-slate-500">All monetary values use Indian rupees (INR). Overdue-date review means only that a stored maturity date is in the past.</p>}
    <div className="dashboard-charts">
      {chartCard('FDR records by status', charts?.records_by_status, (point) => navigate(`/fdrs?record_status=${encodeURIComponent(point.label)}`))}
      {chartCard('Upcoming maturities by month', charts?.maturities_by_month, (point) => navigate(`/fdrs?maturity_from=${point.label}-01&maturity_to=${point.label}-${new Date(Number(point.label.slice(0, 4)), Number(point.label.slice(5, 7)), 0).getDate()}`))}
      {chartCard('Institution-wise record distribution (top 10 plus Others)', charts?.institution_distribution, (point) => point.id && navigate(`/fdrs?institution_id=${encodeURIComponent(point.id)}`))}
      {chartCard('Verification cases by status', charts?.cases_by_status)}
    </div>
    {user?.permissions.includes('monitoring.run') && <MonitoringAdminPanel />}
  </section>
}
