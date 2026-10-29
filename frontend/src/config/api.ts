const configuredApiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const API_BASE_URL = configuredApiBase.replace(/\/$/, '')

export function apiUrl(path: string, baseUrl = API_BASE_URL): string {
  if (/^https?:\/\//i.test(path)) return path
  const suffix = path.startsWith('/api/v1') ? path.slice('/api/v1'.length) : path
  return `${baseUrl.replace(/\/$/, '')}${suffix.startsWith('/') ? suffix : `/${suffix}`}`
}
