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
  action: string
  actor_name: string
  timestamp: string
  changed_fields: Record<string, { old: unknown; new: unknown }>
  remarks: string | null
}

export function formatRecordStatusLabel(status: string): string {
  return status.replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase())
}

const historyFieldLabels: Record<string, string> = {
  fdr_number: 'FDR number', bank_name: 'Bank name', branch_name: 'Branch name',
  issue_date: 'Issue date', maturity_date: 'Maturity date', amount: 'Amount',
  currency: 'Currency', record_status: 'Record status',
}

export function formatHistoryAction(action: string): string {
  if (action === 'fdr_created') return 'Record created'
  if (action === 'fdr_updated') return 'Record updated'
  if (action === 'fdr_status_changed') return 'Status changed'
  return action.replaceAll('_', ' ')
}

export function formatHistoryChanges(item: FdrHistoryItem): Array<{ field: string; oldValue: string; newValue: string }> {
  return Object.entries(item.changed_fields).flatMap(([key, change]) => {
    const label = historyFieldLabels[key]
    if (!label) return []
    if (item.action === 'fdr_created' && (change.new === null || change.new === undefined || change.new === '')) return []
    const formatValue = (value: unknown) => {
      if (value === null || value === undefined || value === '') return '—'
      if (key === 'amount') return formatInr(String(value), 'INR')
      if (key === 'issue_date' || key === 'maturity_date') return formatDate(String(value))
      if (key === 'record_status' && typeof value === 'string') return formatRecordStatusLabel(value)
      return String(value)
    }
    return [{ field: label, oldValue: formatValue(change.old), newValue: formatValue(change.new) }]
  })
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
