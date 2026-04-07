export type UserRole = 'super_admin' | 'admin' | 'manager' | 'employee'
export type RendererType = 'simple' | 'proxy' | 'ballot' | 'electronic_ballot' | 'notice_candidacy'
export type FieldType = 'text' | 'date' | 'dropdown' | 'association' | 'manager' | 'time'

export interface FieldDefinition {
  key: string
  label: string
  type: FieldType
  options: string[]
  auto_populate: boolean
}

export interface FieldRow {
    key: string
    label: string
    type: FieldType
    options: string
    auto_populate: boolean
  }

export interface Template {
  id: string
  name: string
  category: string
  docx_path: string
  fields: FieldDefinition[]
  renderer_type?: RendererType
  is_active: boolean
  created_at?: string
  updated_at?: string
}

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

export interface LetterJob {
  id: string
  template_id: string
  association_id: string
  status: 'pending' | 'complete' | 'failed'
  output_path: string | null
  created_at: string
}

export interface LetterGenerateRequest {
  template_id: string
  association_id: string
  field_values: Record<string, string>
}
