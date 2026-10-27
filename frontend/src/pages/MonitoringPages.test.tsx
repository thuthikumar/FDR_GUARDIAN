import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import AlertsPage from './AlertsPage'
import MonitoringAdminPanel from '../components/MonitoringAdminPanel'

const admin={id:'u',email:'monitor@synthetic.invalid',full_name:'Synthetic Monitor',role:'system_admin',institution_id:null,permissions:['alert.read','alert.manage','monitoring.run','monitoring.configure']}
const alert={id:'alert-1',alert_type:'maturity_urgent',rule_key:'maturity_urgent',severity:'high',status:'open',explanation:'Stored maturity date is 3 days away (2026-11-30). Urgent per demo rule.',created_at:'2026-11-27T12:00:00Z',fdr:{record_id:'record-1',internal_fdr_id:'SYN-1',fdr_number:'SYN-FDR-1',bank_name:'Synthetic Bank',maturity_date:'2026-11-30',record_status:'active',institution_id:'inst-1',institution_name:'Synthetic Institution'}}
function response(body:unknown,status=200){return{ok:status>=200&&status<300,status,json:async()=>body} as Response}
function bootstrap(url:string){if(url.endsWith('/auth/refresh'))return response({access_token:'test-token'});if(url.endsWith('/auth/me'))return response(admin);return null}

describe('Phase 6 monitoring pages',()=>{
  it('lists alerts, filters, and requires resolution remarks before sending',async()=>{
    let status='open'
    const fetchMock=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
      void init
      const url=String(input),initial=bootstrap(url);if(initial)return initial
      if(url.includes('/api/v1/alerts?'))return response({items:[{...alert,status}],total:1,page:1,page_size:20})
      if(url.endsWith('/resolve')){status='resolved';return response({...alert,status})}
      if(url.endsWith('/acknowledge'))return response({...alert,status:'acknowledged'})
      return response({},404)
    })
    vi.stubGlobal('fetch',fetchMock)
    render(<MemoryRouter><AuthProvider><AlertsPage/></AuthProvider></MemoryRouter>)
    expect(await screen.findByText('Stored maturity date is 3 days away (2026-11-30). Urgent per demo rule.')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'SYN-1'})).toHaveAttribute('href','/fdrs/record-1')
    fireEvent.change(screen.getByLabelText('Filter severity'),{target:{value:'high'}})
    await waitFor(()=>expect(fetchMock.mock.calls.some(([input])=>String(input).includes('severity=high'))).toBe(true))
    fireEvent.click(screen.getByRole('button',{name:'Resolve'}))
    const confirm=screen.getByRole('button',{name:'Confirm resolution'})
    expect(confirm).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Resolution remarks'),{target:{value:'Synthetic review completed'}})
    expect(confirm).toBeEnabled()
    fireEvent.click(confirm)
    await waitFor(()=>expect(fetchMock.mock.calls.some(([input,init])=>String(input).endsWith('/resolve')&&init?.method==='POST'&&String(init.body).includes('Synthetic review completed'))).toBe(true))
  })

  it('hides alert actions when role has read permission only',async()=>{
    const readOnly={...admin,permissions:['alert.read']}
    vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>{const url=String(input);if(url.endsWith('/auth/refresh'))return response({access_token:'test-token'});if(url.endsWith('/auth/me'))return response(readOnly);if(url.includes('/api/v1/alerts?'))return response({items:[alert],total:1,page:1,page_size:20});return response({},404)}))
    render(<MemoryRouter><AuthProvider><AlertsPage/></AuthProvider></MemoryRouter>)
    await screen.findByText(alert.explanation)
    expect(screen.queryByRole('button',{name:'Acknowledge'})).not.toBeInTheDocument()
    expect(screen.queryByRole('button',{name:'Resolve'})).not.toBeInTheDocument()
  })

  it('runs monitoring and displays the result summary',async()=>{
    const fetchMock=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{void init;const url=String(input),initial=bootstrap(url);if(initial)return initial;if(url.endsWith('/monitoring/rules'))return response({items:[{rule_key:'maturity_urgent',label:'Urgent',min_days:0,max_days:7,severity:'high',is_active:true}],demo_default_notice:'Demo defaults, not policy.'});if(url.endsWith('/monitoring/runs?page=1&page_size=5'))return response({items:[],total:0});if(url.endsWith('/monitoring/run'))return response({id:'run-1',status:'success',records_evaluated:9,alerts_created:2,alerts_superseded:1,alerts_resolved:0,alerts_reopened:0});return response({},404)})
    vi.stubGlobal('fetch',fetchMock)
    render(<MemoryRouter><AuthProvider><MonitoringAdminPanel/></AuthProvider></MemoryRouter>)
    const button=await screen.findByRole('button',{name:'Run now'})
    fireEvent.click(button)
    await waitFor(()=>expect(fetchMock.mock.calls.some(([input,init])=>String(input).endsWith('/monitoring/run')&&init?.method==='POST')).toBe(true))
    expect(await screen.findByText(/Run success: evaluated 9/)).toBeInTheDocument()
  })
})
