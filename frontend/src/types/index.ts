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

export interface BudgetJobDetail {
  job_id: string
  association_name: string
  budget_year: number
  financial_report_filename: string
  prior_budget_filename: string
  status: JobStatus
  current_step: string | null
  review_flag_count: number | null
  error_code: string | null
  error_detail: Record<string, unknown> | null
  created_by_name: string
  created_at: string
}

/** current_step value set while a run is parked for workbook-layout confirmation. */
export const AWAITING_LAYOUT_REVIEW = 'awaiting_layout_review'

export interface LayoutValueColumn {
  col: number
  year: number | null
  role: 'adopted' | 'projected' | 'actual'
  header: string
}

export interface LayoutSectionSummary {
  /** Normalized budget section used for the pipeline's arithmetic. */
  section: string
  /** The heading as written in the workbook, when it has one. */
  source_section: string | null
  /** What to display: the sheet's own heading, else the normalized name. */
  label: string
  count: number
  total: number
  sample: { label: string; amount: number | null; note: string | null }[]
}

/**
 * What the backend detected about an association's workbook, shown to a
 * reviewer when detection was not confident enough to run unattended.
 */
export interface LayoutReview {
  signature: string
  sheet_title: string
  all_sheets: string[]
  header_row: number
  data_start_row: number
  label_col: number
  gl_col: number | null
  prior_col: number | null
  prior_col_header: string | null
  projected_col: number | null
  projected_col_header: string | null
  proposed_col: number | null
  proposed_col_header: string | null
  notes_col: number | null
  reserve_sheet: string | null
  reserve_items: number
  /** subtotal group -> the sheet row that prints that subtotal. */
  subtotal_rows: Record<string, number>
  value_cols: LayoutValueColumn[]
  line_count: number
  sections: LayoutSectionSummary[]
  revenue_total: number
  expense_total: number
  balanced: boolean
  notes_captured: number
  warnings: string[]
}

export interface LayoutCorrections {
  sheet_title?: string
  prior_col?: number
}

export interface BudgetJobStatus {
  job_id: string
  status: JobStatus
  current_step: string | null
  review_flag_count: number | null
  download_url: string | null
  error_code: string | null
  error_detail: Record<string, unknown> | null
  layout_review: LayoutReview | null
}

export interface LayoutProfile {
  id: string
  signature: string
  sheet_title: string
  confirmed: boolean
  use_count: number
  example_association: string | null
  example_filename: string | null
  warnings: string[] | null
  confirmed_at: string | null
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

// ── Financial packet checks ───────────────────────────────────────────────

export type FinancialCheckStatus = 'pass' | 'fail' | 'review' | 'missing' | 'not_applicable'

export interface FinancialCheckSide {
  source: string
  label: string
  amount: number | null
  page: number | null
  /** true = confirmed by the report's own arithmetic; false = that arithmetic failed (likely OCR) */
  verified: boolean | null
  /** amount was picked by its position on the page (line didn't parse cleanly) — confirm it */
  guessed: boolean
  /** [x0, top, x1, bottom] in PDF points on `page` — sent to /evidence to render the screenshot */
  bbox: number[] | null
  /** data: URL of the highlighted region (or where the figure should be); null when the
   * report was fetched without images */
  image: string | null
}

export interface FinancialCheckResult {
  id: string
  title: string
  status: FinancialCheckStatus
  difference: number | null
  tolerance: number
  notes: string[]
  left: FinancialCheckSide | null
  right: FinancialCheckSide | null
}

/** Response from POST /api/financials/check */
export interface FinancialCheckReport {
  filename: string
  page_count: number
  reports_found: string[]
  summary: Record<FinancialCheckStatus, number>
  checks: FinancialCheckResult[]
}

/** A reserve component on the MASS Reserve Schedule whose Balance breaks the no-negative rule */
export interface ReserveScheduleIssue {
  /** association code — one tab per association */
  sheet: string
  /** heading the component sits under, e.g. "SIRS Non-Waivable"; "" if none */
  group: string
  /** e.g. "H10" */
  cell: string
  row: number
  /** GL code, e.g. "7061" */
  code: string
  description: string
  /** null when the cell isn't a number */
  balance: number | null
  problem: 'negative' | 'not_a_number'
}

export interface ReserveScheduleSheet {
  name: string
  line_items: number
  issue_count: number
  /** false: no Balance header found, so the tab couldn't be checked */
  checked: boolean
}

/** Response from POST /api/excel/reserve-schedule/check */
export interface ReserveScheduleReport {
  filename: string
  sheet_count: number
  line_items: number
  issues: ReserveScheduleIssue[]
  sheets: ReserveScheduleSheet[]
}

/** A figure read from a PDF, with where it came from */
export interface SourceFigure {
  label: string
  amount: number
  page: number
  bbox: number[]
  /** true: confirmed by the report's own arithmetic */
  verified: boolean | null
  /** read by column position because the line was damaged */
  guessed: boolean
}

export type ReportTier = 'none' | 'compilation' | 'review' | 'audit'

export interface RevenueBasis {
  operating: SourceFigure | null
  reserve: SourceFigure | null
  total: number | null
  tier: ReportTier | null
  notes: string[]
}

/** Response from POST /api/accounting/revenue-threshold */
export interface RevenueThresholdReport {
  filename: string
  page_count: number
  /** pages read with OCR because the PDF had no text layer */
  ocr_pages: number
  ytd_actual: RevenueBasis
  annual: RevenueBasis
}

export interface FdicAccount {
  label: string
  amount: number
  /** ICS / CDARS reciprocal deposit */
  network: boolean
  source: SourceFigure
}

export interface FdicInstitution {
  name: string
  total: number
  over_limit: boolean
  accounts: FdicAccount[]
  notes: string[]
}

export type AccountingTool = 'fdic' | 'revenue_threshold' | 'receivables' | 'cd_maturity'

/** The combined files a receivables run compares */
export type ReceivablesRole = 'balance_sheet' | 'ar' | 'prepaid'

/** A background run over a combined multi-association PDF */
export interface AccountingJobSummary {
  id: string
  tool: AccountingTool
  filename: string
  status: 'pending' | 'processing' | 'complete' | 'failed'
  total_pages: number | null
  pages_done: number
  current_association: string | null
  associations_done: number
  flagged_count: number
  error_detail: string | null
  created_at: string | null
  finished_at: string | null
}

export interface FdicSectionResult {
  limit: number
  institutions: FdicInstitution[]
  unrecognized: FdicAccount[]
}

export interface RevenueSectionResult {
  ytd_actual: RevenueBasis
  annual: RevenueBasis
}

/** One side of a receivables comparison, as read from its PDF */
export interface ReceivablesSide {
  source: string
  label: string
  amount: number | null
  page: number | null
  bbox: number[] | null
  verified: boolean | null
  guessed: boolean
}

export interface ReceivablesCheck {
  id: 'ar' | 'prepaid_assessments'
  title: string
  status: FinancialCheckStatus
  balance_sheet: ReceivablesSide | null
  report: ReceivablesSide | null
  difference: number | null
  notes: string[]
  /** Page regions behind a non-passing check (absent on older runs) */
  shots?: ReceivablesShot[]
}

/** A highlighted strip of one uploaded file's page, saved during the run */
export interface Shot {
  /** which uploaded file: a receivables role, or "report" for single-file tools */
  role: string
  page: number
  bbox: number[]
  caption: string
  /** JPEG data URL; missing if the page couldn't be rendered */
  image?: string
}

export type ReceivablesShot = Shot

/**
 * How soon a CD matures, from the day the check ran. `investment` rows sit
 * in the CD section but have no maturity (brokerage, money market).
 */
export type CdTier = 'matured' | 'due_30' | 'due_60' | 'due_90' | 'later' | 'no_date' | 'investment'

export interface CdAccount {
  label: string
  amount: number
  tier: CdTier
  /** ISO date read from the account name */
  maturity: string | null
  /** days from the run date; negative once matured */
  days: number | null
  /** term as written ("13m", "52w") */
  term: string | null
  notes: string[]
  source: SourceFigure
  /** the CD's line on the balance sheet, for flagged CDs */
  shots: Shot[]
}

export interface CdSectionResult {
  /** the day the check ran (tiers count from it) */
  as_of: string
  /** the balance sheet's own date */
  period_end: string | null
  /** soonest first, then undated CDs, then investment accounts */
  cds: CdAccount[]
}

/** Pages ([first, last]) of this association in each uploaded file */
export type ReceivablesPages = Partial<Record<ReceivablesRole, number[] | null>>

export interface ReceivablesSectionResult {
  pages: ReceivablesPages
  /** where a report printed the name differently (paired despite OCR) */
  names: Partial<Record<ReceivablesRole, string>>
  checks: ReceivablesCheck[]
}

/** An association only found in the AR / prepaid files */
export interface ReceivablesUnmatched {
  problem: string
  pages: ReceivablesPages
  reports: Partial<Record<ReceivablesRole, ReceivablesSide | null>>
  shots?: ReceivablesShot[]
}

/** `problem` is set when the association's section couldn't be processed */
export type SectionResult =
  | { problem: string }
  | FdicSectionResult
  | RevenueSectionResult
  | ReceivablesSectionResult
  | ReceivablesUnmatched
  | CdSectionResult

export interface AccountingJobResult {
  association: string
  first_page: number
  last_page: number
  flagged: boolean
  result: SectionResult
}

export interface AccountingJobDetail extends AccountingJobSummary {
  results: AccountingJobResult[]
}

/** Response from POST /api/accounting/fdic */
export interface FdicReport {
  filename: string
  page_count: number
  ocr_pages: number
  limit: number
  balance_sheet_found: boolean
  institutions: FdicInstitution[]
  unrecognized: FdicAccount[]
}
