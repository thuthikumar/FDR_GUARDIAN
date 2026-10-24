import { useEffect, useState } from 'react'

type ApiStatus = 'checking' | 'connected' | 'unavailable'
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export default function SystemStatusPanel() {
  const [status, setStatus] = useState<ApiStatus>('checking')
  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 5000)
    fetch(`${apiBaseUrl}/api/v1/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Health check failed')
        return response.json() as Promise<{ status?: string }>
      })
      .then((body) => setStatus(body.status === 'ok' ? 'connected' : 'unavailable'))
      .catch(() => setStatus('unavailable'))
      .finally(() => window.clearTimeout(timeout))
    return () => {
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [])

  const label = {
    checking: 'Checking backend…',
    connected: 'Backend connected',
    unavailable: 'Backend unavailable',
  }[status]
  return (
    <aside aria-label="System status" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">System status</p>
      <p className={`mt-2 text-sm font-semibold ${status === 'connected' ? 'text-green-700' : status === 'unavailable' ? 'text-amber-700' : 'text-slate-600'}`}>
        {label}
      </p>
      <p className="mt-2 text-xs leading-5 text-slate-500">Phase 1 health monitoring remains available. No production AICTE data is connected.</p>
    </aside>
  )
}
