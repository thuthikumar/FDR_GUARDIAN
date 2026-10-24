import { useEffect, useState } from 'react'

type ApiStatus = 'checking' | 'connected' | 'unavailable'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')

  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 5000)

    fetch(`${apiBaseUrl}/api/v1/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Health check failed')
        return response.json() as Promise<{ status?: string }>
      })
      .then((data) => setApiStatus(data.status === 'ok' ? 'connected' : 'unavailable'))
      .catch(() => setApiStatus('unavailable'))
      .finally(() => window.clearTimeout(timeout))

    return () => {
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [])

  const apiLabel = {
    checking: 'Checking backend…',
    connected: 'Backend connected',
    unavailable: 'Backend unavailable',
  }[apiStatus]

  return (
    <main className="min-h-screen px-6 py-8 sm:px-10 lg:px-16">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-7xl flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 pb-6">
          <a className="flex items-center gap-3" href="#home" aria-label="FDR Guardian home">
            <span className="brand-mark" aria-hidden="true">F</span>
            <span className="text-sm font-bold tracking-tight text-slate-900">FDR Guardian</span>
          </a>
          <span className="hidden text-xs font-medium tracking-[0.16em] text-slate-500 sm:inline">SECURITY DEPOSIT OPERATIONS</span>
        </header>

        <section id="home" className="grid flex-1 items-center gap-12 py-16 lg:grid-cols-[1.15fr_0.85fr] lg:py-20">
          <div className="max-w-2xl">
            <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-800">
              <span className="h-1.5 w-1.5 rounded-full bg-blue-600" />
              Foundation setup in progress
            </div>
            <p className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-blue-700">FDR lifecycle management</p>
            <h1 className="max-w-xl text-5xl font-semibold leading-[1.08] tracking-tight text-slate-950 sm:text-6xl">
              FDR Guardian
            </h1>
            <p className="mt-5 max-w-xl text-xl leading-8 text-slate-600">
              Intelligent Security Deposit and FDR Lifecycle Management Platform
            </p>
            <p className="mt-6 max-w-xl text-base leading-7 text-slate-500">
              A secure workspace for authorised teams to organise fixed deposit records, track important dates, and coordinate verification and approvals.
            </p>
            <div className="mt-10 flex flex-wrap gap-3">
              <StatusPill label="Development status" value="Phase 1 · Foundation" tone="blue" />
              <StatusPill label="API connection" value={apiLabel} tone={apiStatus === 'connected' ? 'green' : apiStatus === 'unavailable' ? 'amber' : 'slate'} />
            </div>
          </div>

          <aside className="relative overflow-hidden rounded-3xl border border-slate-200 bg-white p-7 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.3)] sm:p-9">
            <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-blue-50 blur-3xl" />
            <div className="relative">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Workspace foundation</p>
                  <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-900">A clear view of every lifecycle</h2>
                </div>
                <span className="rounded-xl bg-slate-100 p-3 text-blue-700" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" stroke="currentColor" strokeWidth="1.8"><path d="M4 19.5h16M6.5 16V9.5m5.5 6.5V4.5m5.5 11.5v-4" strokeLinecap="round"/><path d="m5 7 6-3 6 6 3-2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </span>
              </div>
              <div className="mt-8 space-y-3">
                <FeatureRow number="01" title="Institution-wise records" detail="A structured home for FDR information" />
                <FeatureRow number="02" title="Verification workflows" detail="Documents and review steps in context" />
                <FeatureRow number="03" title="Maturity monitoring" detail="Important dates surfaced for follow-up" />
              </div>
              <div className="mt-7 rounded-2xl border border-amber-100 bg-amber-50/70 p-4">
                <p className="text-sm font-semibold text-amber-950">Development environment</p>
                <p className="mt-1 text-xs leading-5 text-amber-900/75">No production AICTE data is connected. Any sample records added later will be clearly labelled synthetic.</p>
              </div>
            </div>
          </aside>
        </section>

        <footer className="flex flex-col gap-2 border-t border-slate-200 py-5 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>FDR Guardian · Development environment</span>
          <span>Designed for authorised security deposit operations</span>
        </footer>
      </div>
    </main>
  )
}

function StatusPill({ label, value, tone }: { label: string; value: string; tone: 'blue' | 'green' | 'amber' | 'slate' }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 flex items-center gap-2 text-sm font-semibold tone-${tone}`}>
        <span className="h-2 w-2 rounded-full bg-current" />{value}
      </p>
    </div>
  )
}

function FeatureRow({ number, title, detail }: { number: string; title: string; detail: string }) {
  return (
    <div className="flex items-center gap-4 rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white text-xs font-bold text-blue-700 shadow-sm">{number}</span>
      <div>
        <p className="text-sm font-semibold text-slate-800">{title}</p>
        <p className="mt-0.5 text-xs text-slate-500">{detail}</p>
      </div>
    </div>
  )
}
