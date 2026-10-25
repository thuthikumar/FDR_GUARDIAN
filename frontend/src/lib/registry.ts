export type PageResult<T> = { items: T[]; total: number; page: number; page_size: number }

export type Institution = {
  id: string
  institution_code: string
  institution_name: string
  institution_type: string | null
  state: string | null
  contact_email: string | null
  status: string
  is_synthetic: boolean
  created_at: string
  updated_at: string
}

export type InstitutionDetail = Institution & {
  stats: {
    total_fdrs: number
    active_fdrs: number
    total_principal_amount: string
    nearest_upcoming_maturity_date: string | null
  }
}

export type FdrRecord = {
  id: string
  institution_id: string
  internal_fdr_id: string
  bank_name: string
  branch_name: string | null
  fdr_number: string
  amount: string
  currency: string
  issue_date: string
  maturity_date: string
  record_status: string
  verification_status: string
  source_system: string
  is_synthetic: boolean
  created_at: string
  updated_at: string
}

export type FdrHistoryItem = {
  id: string
  action: string
  actor_name: string
  timestamp: string
  changed_fields: Record<string, { old: unknown; new: unknown }>
  remarks: string | null
}

export async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail.map((item) => item.msg || 'Invalid value').join(' ')
  } catch {
    // Use the safe generic message below when the response is not JSON.
  }
  return `Request failed (${response.status}).`
}

export function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

export function formatInr(value: string | number, currency = 'INR'): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return `${currency} ${value}`
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount)
}
