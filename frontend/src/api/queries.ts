import apiClient from './client'
import type { Association, Template, User } from '../types'

// A manager as returned by /api/managers (a lighter shape than the full User).
export type ManagerOption = {
  id: string
  fname: string
  lname: string
  email?: string
  title?: string
  is_active?: boolean
}

// Centralized React Query keys. Sharing these constants keeps cache keys
// identical across pages that read the same endpoint (e.g. the associations
// list is used by both AssociationPage and LetterGeneratorPage), so they share
// one cache entry instead of silently drifting apart.
export const queryKeys = {
  templates: ['templates'] as const,
  associations: ['associations'] as const,
  users: ['users'] as const,
  managers: ['managers'] as const,
}

export async function fetchTemplates(): Promise<Template[]> {
  const { data } = await apiClient.get<Template[]>('/api/templates')
  return data
}

export async function fetchAssociations(): Promise<Association[]> {
  const { data } = await apiClient.get<Association[]>('/api/associations')
  return data
}

export async function fetchUsers(): Promise<User[]> {
  const { data } = await apiClient.get<User[]>('/api/users')
  return data
}

export async function fetchManagers(): Promise<ManagerOption[]> {
  const { data } = await apiClient.get<ManagerOption[]>('/api/managers')
  return data
}
