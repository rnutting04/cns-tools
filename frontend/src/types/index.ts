export type UserRole = 'super_admin' | 'admin' | 'manager' | 'employee'

export interface User {
  id: string
  fname: string
  lname: string
  email: string
  title: string
  role: UserRole
  is_active: boolean
  created_at: string
  updated_at: string
  associations?: Association[]
}

export interface Association {
  id: string
  legal_name: string
  filter_name: string
  location_name: string
  is_active: boolean
  created_at: string
  updated_at: string
  managers: User[]
}

export interface TokenPayload {
  sub: string
  email: string
  role: UserRole
  exp: number
}

export interface ApiError {
  detail: string
  status?: number
}
