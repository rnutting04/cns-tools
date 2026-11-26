/**
 * Letters, budgets and accounting tool runs as one kind of list row, shared
 * by My Jobs and the dashboard.
 */
import { JOB_TOOLS, jobProgress, utc } from '../../pages/accounting/jobTools'
import type { AccountingJobSummary, Job, JobStatus, JobType } from '../../types'

export type JobKind = JobType | 'accounting'

/** A letter / budget job or an accounting tool run, as one list row. */
export interface JobRow {
  id: string
  kind: JobKind
  typeLabel: string
  title: string
  /** association (letters, budgets) or progress (accounting runs) */
  detail: string
  status: JobStatus
  created_at: string
  job?: Job
  run?: AccountingJobSummary
}

export const fromJob = (job: Job): JobRow => ({
  id: job.id,
  kind: job.job_type,
  typeLabel: job.job_type === 'budget' ? 'Budget' : 'Letter',
  title: job.title,
  detail: job.association_name,
  status: job.status,
  created_at: job.created_at,
  job,
})

export const fromRun = (run: AccountingJobSummary): JobRow => ({
  id: run.id,
  kind: 'accounting',
  typeLabel: JOB_TOOLS[run.tool]?.label ?? 'Accounting',
  title: run.filename,
  detail: jobProgress(run),
  status: run.status,
  created_at: utc(run.created_at),
  run,
})

/** Newest first. */
export const byNewest = (a: JobRow, b: JobRow) =>
  Date.parse(b.created_at) - Date.parse(a.created_at)
