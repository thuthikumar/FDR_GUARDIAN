import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GovernmentIdentity, HeaderBrand } from './BrandIdentity'

describe('branding modes', () => {
  it('renders the government identity and emblem when enabled', () => {
    render(<><HeaderBrand showGovBranding /><GovernmentIdentity showGovBranding /></>)
    expect(screen.getAllByText('FDR Guardian').length).toBeGreaterThan(0)
    expect(screen.getByText('Government of India')).toBeInTheDocument()
    expect(screen.getByText('Ministry of Education · AICTE')).toBeInTheDocument()
    expect(screen.getAllByAltText('State Emblem of India')).toHaveLength(2)
  })

  it('renders neutral identity without government labels when disabled', () => {
    render(<><HeaderBrand showGovBranding={false} /><GovernmentIdentity showGovBranding={false} /></>)
    expect(screen.getAllByText('FDR Guardian').length).toBeGreaterThan(0)
    expect(screen.getByText('Demo workspace')).toBeInTheDocument()
    expect(screen.queryByText('Government of India')).not.toBeInTheDocument()
    expect(screen.queryByText('Ministry of Education · AICTE')).not.toBeInTheDocument()
    expect(screen.getAllByLabelText('FDR Guardian shield')).toHaveLength(2)
  })
})
