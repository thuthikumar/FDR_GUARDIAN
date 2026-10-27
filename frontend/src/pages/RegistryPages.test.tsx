import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import { SourceBadges } from '../components/RegistryPrimitives'
import { formatHistoryAction, formatHistoryChanges, formatInr, formatRecordStatusLabel } from '../lib/registry'
import FdrFormPage from './FdrFormPage'
import FdrDetailPage from './FdrDetailPage'
import FdrsPage from './FdrsPage'

function jsonResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response
}

const syntheticAdmin = {
  id: 'user-id', email: 'institution-admin@synthetic.invalid', full_name: 'Synthetic Institution Admin',
  role: 'institution_admin', institution_id: 'institution-id', permissions: ['institution.read', 'fdr.read', 'fdr.write'],
}

function renderWithAuth(page: ReactNode) {
  return render(<MemoryRouter><AuthProvider>{page}</AuthProvider></MemoryRouter>)
}

function bootstrapResponse(url: string) {
  if (url.endsWith('/auth/refresh')) return jsonResponse({ access_token: 'in-memory-test-access' })
  if (url.endsWith('/auth/me')) return jsonResponse(syntheticAdmin)
  return null
}

function record(id: string, internalId: string, sourceSystem = 'MANUAL_ENTRY') {
  return {
    id, institution_id: 'institution-id', internal_fdr_id: internalId, bank_name: 'Synthetic Bank',
    branch_name: null, fdr_number: `SYN-${id}`, amount: '12500.50', currency: 'INR',
    issue_date: '2025-01-01', maturity_date: '2027-01-01', record_status: 'active',
    verification_status: 'not_submitted', source_system: sourceSystem, is_synthetic: true,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  }
}

describe('Phase 4 registry pages', () => {
  it.each([
    ['MANUAL_ENTRY', 'Manual entry'],
    ['SYNTHETIC_DEMO', 'Synthetic demo'],
  ])('shows exactly one source badge for %s', (sourceSystem, label) => {
    const { container } = render(<SourceBadges sourceSystem={sourceSystem} />)
    expect(container.querySelectorAll('[data-slot="badge"]')).toHaveLength(1)
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('shows the source badges on registry rows based only on source_system', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const bootstrap = bootstrapResponse(url)
      if (bootstrap) return bootstrap
      return jsonResponse({ items: [record('manual', 'SYN-MANUAL', 'MANUAL_ENTRY'), record('demo', 'SYN-DEMO', 'SYNTHETIC_DEMO')], total: 2, page: 1, page_size: 10 })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithAuth(<FdrsPage />)
    const manualRow = (await screen.findByText('SYN-MANUAL')).closest('tr')!
    const demoRow = screen.getByText('SYN-DEMO').closest('tr')!
    expect(within(manualRow).getByText('Manual entry')).toBeInTheDocument()
    expect(within(manualRow).queryByText('Synthetic')).not.toBeInTheDocument()
    expect(within(manualRow).getByLabelText('Record data source').querySelectorAll('[data-slot="badge"]')).toHaveLength(1)
    expect(within(demoRow).getByText('Synthetic demo')).toBeInTheDocument()
    expect(within(demoRow).queryByText('Synthetic')).not.toBeInTheDocument()
    expect(within(demoRow).getByLabelText('Record data source').querySelectorAll('[data-slot="badge"]')).toHaveLength(1)
  })

  it('shows exactly one Manual entry badge on FDR details for a synthetic manual record', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const bootstrap = bootstrapResponse(url)
      if (bootstrap) return bootstrap
      if (url.endsWith('/api/v1/fdrs/manual')) return jsonResponse(record('manual', 'SYN-MANUAL', 'MANUAL_ENTRY'))
      if (url.endsWith('/api/v1/fdrs/manual/history')) return jsonResponse([])
      return jsonResponse({ detail: 'Unexpected request' }, 500)
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/fdrs/manual']}><AuthProvider><Routes><Route path="/fdrs/:recordId" element={<FdrDetailPage />} /></Routes></AuthProvider></MemoryRouter>)
    const badge = await screen.findByText('Manual entry')
    const source = screen.getByLabelText('Record data source')
    expect(badge).toBeInTheDocument()
    expect(within(source).queryByText('Synthetic')).not.toBeInTheDocument()
    expect(source.querySelectorAll('[data-slot="badge"]')).toHaveLength(1)
  })

  it('preserves unknown source_system values verbatim', () => {
    render(<SourceBadges sourceSystem="LEGACY_SOURCE_X" />)
    expect(screen.getByText('LEGACY_SOURCE_X')).toBeInTheDocument()
  })

  it('humanises and formats only business fields in history', () => {
    const item = {
      action: 'fdr_created', actor_name: 'Synthetic Tester', timestamp: '2026-01-01T00:00:00Z', remarks: null,
      changed_fields: {
        internal_fdr_id: { old: null, new: 'INT-001' }, institution_id: { old: null, new: 'institution-id' },
        source_system: { old: null, new: 'MANUAL_ENTRY' }, verification_status: { old: null, new: 'not_submitted' },
        is_synthetic: { old: null, new: true }, branch_name: { old: null, new: null },
        bank_name: { old: null, new: 'Synthetic Bank' }, fdr_number: { old: null, new: 'SYN-001' },
        amount: { old: null, new: '12500.50' }, currency: { old: null, new: 'INR' }, issue_date: { old: null, new: '2025-01-01' },
        maturity_date: { old: null, new: '2027-01-01' }, record_status: { old: null, new: 'draft' },
      },
    }
    expect(formatHistoryAction(item.action)).toBe('Record created')
    expect(formatHistoryAction('fdr_updated')).toBe('Record updated')
    expect(formatHistoryAction('fdr_status_changed')).toBe('Status changed')
    expect(formatHistoryChanges(item)).toEqual([
      { field: 'Bank name', oldValue: '—', newValue: 'Synthetic Bank' },
      { field: 'FDR number', oldValue: '—', newValue: 'SYN-001' },
      { field: 'Amount', oldValue: '—', newValue: formatInr('12500.50') },
      { field: 'Currency', oldValue: '—', newValue: 'INR' },
      { field: 'Issue date', oldValue: '—', newValue: '01 Jan 2025' },
      { field: 'Maturity date', oldValue: '—', newValue: '01 Jan 2027' },
      { field: 'Record status', oldValue: '—', newValue: 'Draft' },
    ])
  })

  it('capitalises record status labels consistently', () => {
    expect(['draft', 'active', 'cancelled'].map(formatRecordStatusLabel)).toEqual(['Draft', 'Active', 'Cancelled'])
  })

  it('shows a humanised status change and its remarks in the history timeline', async () => {
    const changed = {
      action: 'fdr_status_changed', actor_name: 'Synthetic Institution Admin', timestamp: '2026-01-01T00:00:00Z',
      changed_fields: {
        record_status: { old: 'active', new: 'cancelled' }, internal_fdr_id: { old: 'SECRET-ID', new: 'SECRET-ID' },
        institution_id: { old: 'internal-institution', new: 'internal-institution' },
      }, remarks: 'Synthetic cancellation recorded after review',
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const bootstrap = bootstrapResponse(url)
      if (bootstrap) return bootstrap
      if (url.endsWith('/api/v1/fdrs/changed')) return jsonResponse(record('changed', 'SYN-CHANGED'))
      if (url.endsWith('/api/v1/fdrs/changed/history')) return jsonResponse([changed])
      return jsonResponse({ detail: 'Unexpected request' }, 500)
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/fdrs/changed']}><AuthProvider><Routes><Route path="/fdrs/:recordId" element={<FdrDetailPage />} /></Routes></AuthProvider></MemoryRouter>)
    expect(await screen.findByText(/Status changed/)).toBeInTheDocument()
    const historyLabel = screen.getAllByText('Record status').find((element) => element.tagName === 'SPAN')!
    expect(historyLabel.closest('li')).toHaveTextContent('Record status: Active → Cancelled')
    expect(screen.getByText('Synthetic cancellation recorded after review')).toBeInTheDocument()
    expect(screen.queryByText('SECRET-ID')).not.toBeInTheDocument()
    expect(screen.queryByText('internal institution → internal institution')).not.toBeInTheDocument()
  })

  it('validates FDR amounts before sending a create request', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      void init
      const url = String(input)
      const bootstrap = bootstrapResponse(url)
      if (bootstrap) return bootstrap
      return jsonResponse({ id: 'created' }, 201)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithAuth(<FdrFormPage />)
    await screen.findByRole('button', { name: 'Create FDR' })
    fireEvent.change(screen.getByLabelText('Bank name'), { target: { value: 'Synthetic Bank' } })
    fireEvent.change(screen.getByLabelText('FDR number'), { target: { value: 'SYN-001' } })
    fireEvent.change(screen.getByLabelText('Principal amount'), { target: { value: '125.999' } })
    fireEvent.change(screen.getByLabelText('Currency'), { target: { value: 'INR' } })
    fireEvent.change(screen.getByLabelText('Issue date'), { target: { value: '2025-01-01' } })
    fireEvent.change(screen.getByLabelText('Maturity date'), { target: { value: '2027-01-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create FDR' }))
    expect(await screen.findByText('Enter a positive amount with at most 2 decimal places.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([input, init]) => String(input).endsWith('/api/v1/fdrs') && init?.method === 'POST')).toBe(false)
  })

  it('renders FDR results and moves to the next page', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const bootstrap = bootstrapResponse(url)
      if (bootstrap) return bootstrap
      if (url.includes('/api/v1/fdrs?')) {
        const page = new URL(url).searchParams.get('page')
        return jsonResponse({ items: [page === '2' ? record('two', 'SYN-FDR-0002') : record('one', 'SYN-FDR-0001')], total: 11, page: Number(page), page_size: 10 })
      }
      return jsonResponse({ detail: 'Unexpected request' }, 500)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithAuth(<FdrsPage />)
    expect(await screen.findByText('SYN-FDR-0001')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('SYN-FDR-0002')).toBeInTheDocument()
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).includes('page=2'))).toBe(true))
  })

  it('shows server load errors accessibly', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const bootstrap = bootstrapResponse(url)
      if (bootstrap) return bootstrap
      return jsonResponse({ detail: 'Synthetic registry unavailable' }, 503)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderWithAuth(<FdrsPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Synthetic registry unavailable')
  })
})
