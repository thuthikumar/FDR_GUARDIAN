import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'

export default function ProtectedRoute() {
  const { user, loading } = useAuth()
  if (loading) return <p className="p-8 text-sm text-slate-600">Restoring your session…</p>
  if (!user) return <Navigate to="/login" replace />
  // Route guards improve UX only; the backend enforces authentication and permissions.
  return <Outlet />
}
