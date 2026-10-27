import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import ProtectedRoute from './auth/ProtectedRoute'
import AppShell from './components/AppShell'
import InstitutionDetailPage from './pages/InstitutionDetailPage'
import InstitutionFormPage from './pages/InstitutionFormPage'
import InstitutionsPage from './pages/InstitutionsPage'
import FdrDetailPage from './pages/FdrDetailPage'
import FdrFormPage from './pages/FdrFormPage'
import FdrsPage from './pages/FdrsPage'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ReportsPage from './pages/ReportsPage'
import AlertsPage from './pages/AlertsPage'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="alerts" element={<AlertsPage />} />
              <Route path="institutions" element={<InstitutionsPage />} />
              <Route path="institutions/new" element={<InstitutionFormPage />} />
              <Route path="institutions/:institutionId" element={<InstitutionDetailPage />} />
              <Route path="fdrs" element={<FdrsPage />} />
              <Route path="fdrs/new" element={<FdrFormPage />} />
              <Route path="fdrs/:recordId" element={<FdrDetailPage />} />
              <Route path="fdrs/:recordId/edit" element={<FdrFormPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
