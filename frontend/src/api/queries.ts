import apiClient from './client'
import type { Association, Job, Template, User } from '../types'

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
  jobs: ['jobs'] as const,
}

// Reference data (associations, managers, templates, users) changes rarely.
// Keeping it fresh for 5 minutes avoids refetching these lists every time a
// page that uses them is revisited, while the 30s global default still governs
// more volatile data like jobs.
export const REFERENCE_STALE_TIME = 5 * 60_000

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

export async function fetchJobs(): Promise<Job[]> {
  const { data } = await apiClient.get<Job[]>('/api/jobs')
  return data
}
