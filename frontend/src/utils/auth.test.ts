import { describe, it, expect } from 'vitest'
import { decodeToken, getStoredToken, hasRole, isTokenExpired } from './auth'
import type { TokenPayload, User } from '../types'

function makeJwt(payload: Record<string, unknown>): string {
  const b64 = (obj: unknown) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64(payload)}.signature`
}

describe('decodeToken', () => {
  it('decodes the JWT payload', () => {
    const token = makeJwt({ sub: 'u1', email: 'a@b.com', role: 'admin', exp: 123 })
    const payload = decodeToken(token)
    expect(payload.sub).toBe('u1')
    expect(payload.email).toBe('a@b.com')
    expect(payload.role).toBe('admin')
  })
})

describe('isTokenExpired', () => {
  it('returns true for a past expiry', () => {
    const payload = { exp: Math.floor(Date.now() / 1000) - 60 } as TokenPayload
    expect(isTokenExpired(payload)).toBe(true)
  })

  it('returns false for a future expiry', () => {
    const payload = { exp: Math.floor(Date.now() / 1000) + 3600 } as TokenPayload
    expect(isTokenExpired(payload)).toBe(false)
  })
})

describe('hasRole', () => {
  const user = { role: 'manager' } as User

  it('is true when the role is allowed', () => {
    expect(hasRole(user, ['admin', 'manager'])).toBe(true)
  })

  it('is false when the role is not allowed', () => {
    expect(hasRole(user, ['admin', 'super_admin'])).toBe(false)
  })
})

describe('getStoredToken', () => {
  it('returns the token from localStorage, or null', () => {
    expect(getStoredToken()).toBeNull()
    localStorage.setItem('token', 'abc')
    expect(getStoredToken()).toBe('abc')
  })
})
