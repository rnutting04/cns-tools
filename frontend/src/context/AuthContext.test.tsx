import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { AuthProvider } from './AuthContext'
import { useAuth } from './AuthContext'
import type { User } from '../types'

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import apiClient from '../api/client'
const mockClient = apiClient as unknown as { get: Mock; post: Mock }

function makeUser(): User {
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
  }
}

beforeEach(() => {
  localStorage.clear()
})

describe('AuthProvider', () => {
  it('finishes loading with no user when there is no token', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.user).toBeNull()
  })

  it('login stores the token and sets the user', async () => {
    mockClient.post.mockResolvedValue({ data: { access_token: 'tok-123', token_type: 'bearer' } })
    mockClient.get.mockResolvedValue({ data: makeUser() })

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.login('test@example.com', 'password123')
    })

    expect(mockClient.post).toHaveBeenCalledWith('/api/auth/login', {
      email: 'test@example.com',
      password: 'password123',
    })
    expect(localStorage.getItem('token')).toBe('tok-123')
    expect(result.current.user?.email).toBe('test@example.com')
  })

  it('logout clears the token and the user', async () => {
    mockClient.post.mockResolvedValue({ data: { access_token: 'tok-123', token_type: 'bearer' } })
    mockClient.get.mockResolvedValue({ data: makeUser() })

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(async () => {
      await result.current.login('test@example.com', 'password123')
    })

    act(() => result.current.logout())

    expect(localStorage.getItem('token')).toBeNull()
    expect(result.current.user).toBeNull()
  })
})
