import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import DashboardPage from './DashboardPage'
import ReportsPage from './ReportsPage'

const user = { id: 'u', email: 'auditor@synthetic.invalid', full_name: 'Synthetic Auditor', role: 'read_only_auditor', institution_id: null, permissions: ['report.read', 'report.export'] }
const summary = { total_institutions: 2, total_fdr_records: 18, active_records: 12, upcoming_maturities: 4, overdue_date_review: 1, pending_verification_cases: 3, unresolved_alerts: 2 }
const charts = { records_by_status: [{label:'active',count:12}], maturities_by_month: [], institution_distribution: [], cases_by_status: [] }
const monitor = { counts_by_status:{open:2,acknowledged:1},upcoming_maturities_by_band:{maturity_urgent:1,maturity_attention_required:1,maturity_upcoming:2,maturity_overdue_date_review:1,maturity_normal:5} }
function response(body: unknown, status = 200) { return { ok: status >= 200 && status < 300, status, json: async () => body, blob: async () => new Blob(['csv']) } as Response }
function bootstrap(url: string) { if(url.endsWith('/auth/refresh')) return response({access_token:'test-token'}); if(url.endsWith('/auth/me')) return response(user); return null }

describe('Phase 5 dashboard and reports', () => {
  it('renders dashboard cards from API data and chart empty states', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo|URL) => { const url=String(input), initial=bootstrap(url); if(initial) return initial; if(url.endsWith('/dashboard/summary')) return response(summary); if(url.endsWith('/dashboard/charts')) return response(charts); if(url.endsWith('/monitoring/summary')) return response(monitor); return response({detail:'Unexpected'},500) }))
    render(<MemoryRouter><AuthProvider><DashboardPage/></AuthProvider></MemoryRouter>)
    expect(await screen.findByText('18')).toBeInTheDocument()
    expect(screen.getByText('Synthetic demo data. Dashboard values reflect records currently present; alert and verification-case generation is not performed here.')).toBeInTheDocument()
    expect(await screen.findAllByText('No data to display.')).toHaveLength(3)
  })

  it('shows a chart error when chart API fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo|URL) => { const url=String(input), initial=bootstrap(url); if(initial) return initial; if(url.endsWith('/dashboard/summary')) return response(summary); if(url.endsWith('/dashboard/charts')) return response({detail:'failure'},500); if(url.endsWith('/monitoring/summary')) return response(monitor); return response({},500) }))
    render(<MemoryRouter><AuthProvider><DashboardPage/></AuthProvider></MemoryRouter>)
    expect(await screen.findAllByText('Chart data could not be loaded.')).toHaveLength(4)
  })

  it('paginates maturity rows and exports CSV with authenticated request', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo|URL, init?: RequestInit) => {
      void init
      const url=String(input), initial=bootstrap(url); if(initial) return initial
      if(url.includes('institution-summary')) return response({items:[],total:0,page:1,page_size:10})
      if(url.includes('reports/maturities')) return response({items:[],total:21,page:Number(new URL(url).searchParams.get('page')),page_size:10})
      return response({},500)
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.spyOn(URL,'createObjectURL').mockReturnValue('blob:test')
    vi.spyOn(URL,'revokeObjectURL').mockImplementation(()=>undefined)
    const click = vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>undefined)
    render(<MemoryRouter><AuthProvider><Routes><Route path="/" element={<ReportsPage/>}/></Routes></AuthProvider></MemoryRouter>)
    expect(await screen.findByText('Page 1 of 3')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button',{name:'Next'}).find((button) => !button.hasAttribute('disabled'))!)
    await waitFor(()=>expect(fetchMock.mock.calls.some(([input])=>String(input).includes('reports/maturities?page=2'))).toBe(true))
    fireEvent.click(screen.getAllByRole('button',{name:'Export CSV'})[1])
    await waitFor(()=>expect(fetchMock.mock.calls.some(([input,init])=>String(input).includes('format=csv') && new Headers(init?.headers).get('Authorization')==='Bearer test-token')).toBe(true))
    expect(click).toHaveBeenCalled()
    click.mockRestore()
  })
})
