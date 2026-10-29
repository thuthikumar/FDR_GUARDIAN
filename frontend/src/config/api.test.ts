import { describe, expect, it } from 'vitest'
import { API_BASE_URL, apiUrl } from './api'

describe('API base URL', () => {
  it('defaults to the relative same-origin Vercel API prefix', () => {
    expect(API_BASE_URL).toBe('/api/v1')
    expect(apiUrl('/api/v1/auth/refresh')).toBe('/api/v1/auth/refresh')
  })

  it('appends endpoints to a configured API base without duplicating the version path', () => {
    expect(apiUrl('/api/v1/auth/me', 'https://api.example.invalid/api/v1')).toBe('https://api.example.invalid/api/v1/auth/me')
  })
})
