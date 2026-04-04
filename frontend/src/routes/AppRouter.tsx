import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './ProtectedRoute'
import AppShell from '../components/common/AppShell'
import LoginPage from '../pages/LoginPage'
import DashboardPage from '../pages/DashboardPage'
import AssociationPage from '../pages/AssociationPage'
import UsersPage from '../pages/UsersPage'
import LetterGeneratorPage from '../pages/LetterGeneratorPage'
import ExcelToolsPage from '../pages/ExcelToolsPage'
import NotFoundPage from '../pages/NotFoundPage'

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route
            path="associations"
            element={
              <ProtectedRoute allowedRoles={['manager', 'admin', 'super_admin']}>
                <AssociationPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="users"
            element={
              <ProtectedRoute allowedRoles={['admin', 'super_admin']}>
                <UsersPage />
              </ProtectedRoute>
            }
          />
          <Route path="letters" element={<LetterGeneratorPage />} />
          <Route path="excel" element={<ExcelToolsPage />} />
        </Route>
        <Route path="/404" element={<NotFoundPage />} />
        <Route path="*" element={<Navigate to="/404" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
