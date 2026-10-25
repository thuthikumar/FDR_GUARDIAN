import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import FdrFormPage from './FdrFormPage'
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

function record(id: string, internalId: string) {
  return {
    id, institution_id: 'institution-id', internal_fdr_id: internalId, bank_name: 'Synthetic Bank',
    branch_name: null, fdr_number: `SYN-${id}`, amount: '12500.50', currency: 'INR',
    issue_date: '2025-01-01', maturity_date: '2027-01-01', record_status: 'active',
    verification_status: 'not_submitted', source_system: 'MANUAL_ENTRY', is_synthetic: true,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  }
}

describe('Phase 4 registry pages', () => {
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
