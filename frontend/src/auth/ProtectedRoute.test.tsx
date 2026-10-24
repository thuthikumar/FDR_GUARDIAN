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
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <Routes>
            <Route element={<ProtectedRoute />}><Route path="/" element={<p>Protected home</p>} /></Route>
            <Route path="/login" element={<p>Sign in page</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('Sign in page')).toBeInTheDocument())
    expect(screen.queryByText('Protected home')).not.toBeInTheDocument()
  })
})
