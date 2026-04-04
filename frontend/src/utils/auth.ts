import { jwtDecode } from 'jwt-decode'
import type { TokenPayload, User, UserRole } from '../types'

export function decodeToken(token: string): TokenPayload {
  return jwtDecode<TokenPayload>(token)
}

export function getStoredToken(): string | null {
  return localStorage.getItem('token')
}

export function isTokenExpired(payload: TokenPayload): boolean {
  return payload.exp * 1000 < Date.now()
}

export function hasRole(user: User, roles: UserRole[]): boolean {
  return roles.includes(user.role)
}
