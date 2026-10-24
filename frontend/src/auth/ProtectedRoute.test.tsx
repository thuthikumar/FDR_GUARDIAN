import { StrictMode } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from './AuthContext'
import ProtectedRoute from './ProtectedRoute'

function fakeResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/refresh')) return fakeResponse({ detail: 'no session' }, 401)
      return fakeResponse({ status: 'ok' })
    }))
  })

  it('redirects an unauthenticated user to login', async () => {
    render(
      <StrictMode>
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <Routes>
            <Route element={<ProtectedRoute />}><Route path="/" element={<p>Protected home</p>} /></Route>
            <Route path="/login" element={<p>Sign in page</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
      </StrictMode>,
    )

    await waitFor(() => expect(screen.getByText('Sign in page')).toBeInTheDocument())
    expect(screen.queryByText('Protected home')).not.toBeInTheDocument()
    expect(vi.mocked(fetch).mock.calls.filter(([input]) => String(input).endsWith('/auth/refresh'))).toHaveLength(1)
  })

  it('loads the user after a successful single StrictMode bootstrap refresh', async () => {
    const user = {
      id: 'synthetic-user-id',
      email: 'system-admin@synthetic.invalid',
      full_name: 'Synthetic System Administrator',
      role: 'system_admin',
      institution_id: null,
      permissions: ['user.manage'],
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/refresh')) return fakeResponse({ access_token: 'in-memory-test-access-token' })
      if (url.endsWith('/auth/me')) return fakeResponse(user)
      return fakeResponse({})
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/']}>
          <AuthProvider>
            <Routes>
              <Route element={<ProtectedRoute />}><Route path="/" element={<p>Welcome, {user.full_name}</p>} /></Route>
              <Route path="/login" element={<p>Sign in page</p>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </StrictMode>,
    )

    await waitFor(() => expect(screen.getByText(`Welcome, ${user.full_name}`)).toBeInTheDocument())
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/auth/refresh'))).toHaveLength(1)
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith('/auth/me'))).toBe(true)
  })
})
