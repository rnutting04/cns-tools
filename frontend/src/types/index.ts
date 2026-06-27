export type UserRole = 'super_admin' | 'admin' | 'manager' | 'employee'
export type RendererType = 'simple' | 'proxy' | 'ballot' | 'electronic_ballot' | 'notice_candidacy'
export type FieldType = 'text' | 'date' | 'dropdown' | 'association' | 'manager' | 'time'

export type ProxyVoteType =
  | 'waive_financial_one_year'
  | 'lower_financial_level'
  | 'cross_utilization_reserves'
  | 'straight_line_to_pooled'
  | 'partial_reserve_funding'
  | 'waive_reserves'
  | 'use_reserves_other_purpose'
  | 'move_reserve_line_items'
  | 'irs_rollover'

export type ProxyVote = {
  type: ProxyVoteType
  fiscal_year?: string
  from_level?: string
  to_level?: string
  percentage?: string
  amount?: string
  reserve_from?: string
  reserve_to?: string
  purpose?: string
  tax_year?: string
}

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
  password_change_required: boolean
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

export interface AuditEvent {
  id: string
  created_at: string
  actor_user_id: string | null
  actor_email: string | null
  action: string
  target_type: string | null
  target_id: string | null
  event_metadata: Record<string, unknown>
  ip_address: string | null
  user_agent: string | null
}

export interface AuditPage {
  items: AuditEvent[]
  total: number
  page: number
  pages: number
}

export type JobStatus = 'pending' | 'processing' | 'complete' | 'failed'
export type JobType = 'letter' | 'budget'

export interface Job {
  id: string
  job_type: JobType
  title: string
  association_name: string
  status: JobStatus
  created_at: string
  created_by: string
  created_by_name: string
}

export interface JobDetail {
  id: string
  job_type: JobType
  title: string
  association_name: string
  status: JobStatus
  created_at: string
  current_step: string | null
  download_url: string | null
}

export interface LetterJob {
  id: string
  template_id: string
  template_name: string
  association_id: string
  association_name: string
  created_by: string
  created_by_name: string
  status: JobStatus
  output_path: string | null
  created_at: string
}

/** A single template field the user filled in when generating a letter. */
export interface LetterFieldEntry {
  key: string
  label: string
  value: string
}

/** An auto-resolved field surfaced in the letter detail view. */
export interface LetterDerivedEntry {
  label: string
  value: string
}

/** Response from GET /api/letters/{job_id}/details. */
export interface LetterJobDetail {
  id: string
  template_name: string
  association_name: string
  created_by_name: string
  status: JobStatus
  created_at: string
  entries: LetterFieldEntry[]
  derived: LetterDerivedEntry[]
}

export interface LetterGenerateRequest {
  template_id: string
  association_id: string
  field_values: Record<string, string>
}

/** Response from POST /api/letters/generate — the job is queued. */
export interface GenerateAccepted {
  job_id: string
  status: JobStatus
}

/** Response from GET /api/letters/{job_id} while polling for completion. */
export interface LetterJobStatus {
  job_id: string
  status: JobStatus
  download_url: string | null
}
