import { describe, it, expect, vi } from 'vitest'
import type { Mock } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './ProtectedRoute'
import { useAuth } from '../context/AuthContext'
import type { User, UserRole } from '../types'

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'u1',
    fname: 'Test',
    lname: 'User',
    email: 'test@example.com',
    title: 'Manager',
    role: 'manager',
    is_active: true,
    password_change_required: false,
    created_at: '',
    updated_at: '',
    ...overrides,
  }
}

function renderRoute({
  user,
  loading = false,
  allowedRoles,
  path = '/dashboard',
}: {
  user: User | null
  loading?: boolean
  allowedRoles?: UserRole[]
  path?: string
}) {
  ;(useAuth as Mock).mockReturnValue({
    user,
    loading,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  })

  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<div>LOGIN PAGE</div>} />
        <Route path="/settings" element={<div>SETTINGS PAGE</div>} />
        <Route path="/" element={<div>HOME PAGE</div>} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute allowedRoles={allowedRoles}>
              <div>PROTECTED CONTENT</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  it('shows a loading state and not the content while auth is resolving', () => {
    renderRoute({ user: null, loading: true })
    expect(screen.queryByText('PROTECTED CONTENT')).not.toBeInTheDocument()
    expect(screen.queryByText('LOGIN PAGE')).not.toBeInTheDocument()
  })

  it('redirects unauthenticated users to /login', () => {
    renderRoute({ user: null })
    expect(screen.getByText('LOGIN PAGE')).toBeInTheDocument()
  })

  it('renders the content for an authenticated, allowed user', () => {
    renderRoute({ user: makeUser({ role: 'admin' }), allowedRoles: ['admin'] })
    expect(screen.getByText('PROTECTED CONTENT')).toBeInTheDocument()
  })

  it('redirects users who must change their password to /settings', () => {
    renderRoute({ user: makeUser({ password_change_required: true }) })
    expect(screen.getByText('SETTINGS PAGE')).toBeInTheDocument()
  })

  it('redirects users without an allowed role to home', () => {
    renderRoute({ user: makeUser({ role: 'employee' }), allowedRoles: ['admin'] })
    expect(screen.getByText('HOME PAGE')).toBeInTheDocument()
  })
})
