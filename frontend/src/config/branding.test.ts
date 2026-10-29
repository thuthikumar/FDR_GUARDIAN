import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('government branding environment setting', () => {
  it.each([
    ['unset', undefined, false],
    ['true', 'true', true],
    ['TRUE', 'TRUE', true],
    ['false', 'false', false],
    ['empty', '', false],
    ['junk', 'junk', false],
  ])('uses the expected mode for %s', async (_name, value, expected) => {
    vi.stubEnv('VITE_SHOW_GOV_BRANDING', value)
    vi.resetModules()
    const { SHOW_GOV_BRANDING } = await import('./branding')
    expect(SHOW_GOV_BRANDING).toBe(expected)
  })
})
