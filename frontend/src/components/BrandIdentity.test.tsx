import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { GovernmentIdentity, HeaderBrand } from './BrandIdentity'

afterEach(() => vi.unstubAllGlobals())

describe('branding modes', () => {
  it('renders the government identity and emblem when enabled', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, headers: { get: () => null } }))
    render(<><HeaderBrand showGovBranding /><GovernmentIdentity showGovBranding /></>)
    expect(screen.getAllByText('FDR Guardian').length).toBeGreaterThan(0)
    expect(screen.getByText('Government of India')).toBeInTheDocument()
    expect(screen.getByText('Ministry of Education · AICTE')).toBeInTheDocument()
    expect(screen.getAllByAltText('State Emblem of India')).toHaveLength(2)
  })

  it('renders neutral identity without government labels when disabled', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<><HeaderBrand showGovBranding={false} /><GovernmentIdentity showGovBranding={false} /></>)
    expect(screen.getAllByText('FDR Guardian').length).toBeGreaterThan(0)
    expect(screen.getByText('Demo workspace')).toBeInTheDocument()
    expect(screen.queryByText('Government of India')).not.toBeInTheDocument()
    expect(screen.queryByText('Ministry of Education · AICTE')).not.toBeInTheDocument()
    expect(screen.getAllByLabelText('FDR Guardian shield')).toHaveLength(2)
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.queryByAltText('Organization logo')).not.toBeInTheDocument()
  })

  it('shows the optional header logo only after confirming the local PNG exists', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, headers: { get: () => 'image/png' } })
    vi.stubGlobal('fetch', fetchMock)
    render(<HeaderBrand showGovBranding />)

    const logo = await screen.findByAltText('Organization logo')
    expect(logo).toHaveAttribute('src', '/branding/gov-logo.png')
    expect(fetchMock).toHaveBeenCalledWith('/branding/gov-logo.png', { method: 'HEAD' })
  })

  it('renders no broken image when the optional header logo is absent', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, headers: { get: () => 'text/html' } })
    vi.stubGlobal('fetch', fetchMock)
    render(<HeaderBrand showGovBranding />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
    expect(screen.queryByAltText('Organization logo')).not.toBeInTheDocument()
  })
})
