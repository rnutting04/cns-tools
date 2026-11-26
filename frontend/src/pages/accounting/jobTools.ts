/** The background accounting tools, as named and linked outside their own page. */
import type { AccountingJobSummary, AccountingTool } from '../../types'

export const JOB_TOOLS: Record<AccountingTool, { label: string; path: string }> = {
  fdic: { label: 'FDIC exposure', path: 'fdic' },
  revenue_threshold: { label: 'Audit threshold', path: 'audit-threshold' },
  receivables: { label: 'AR & prepaid', path: 'ar-prepaid' },
  cd_maturity: { label: 'CD maturity', path: 'cd-maturity' },
}

/** The tool page, showing this run. */
export const jobLink = (job: Pick<AccountingJobSummary, 'id' | 'tool'>) =>
  `/accounting/${JOB_TOOLS[job.tool].path}?job=${job.id}`

/** Accounting timestamps are stored as naive UTC. */
export const utc = (iso: string | null) =>
  iso && !/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? `${iso}Z` : (iso ?? '')

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** A waiting run's place in line: "Queued · 2 jobs ahead of yours · 3 running". */
export function queuePosition(
  j: Pick<AccountingJobSummary, 'queue_ahead' | 'queue_running'>,
): string {
  const ahead = j.queue_ahead
  const running = j.queue_running ?? 0
  if (ahead === null || ahead === undefined) return 'Waiting for the background worker'
  const busy = running ? ` · ${plural(running, 'job', 'jobs')} running` : ''
  if (ahead === 0) return running ? `Queued · next in line${busy}` : 'Starting…'
  return `Queued · ${plural(ahead, 'job', 'jobs')} ahead of yours${busy}`
}

/** "Working on X · page 40 of 604", or the finished run's counts. */
export function jobProgress(j: AccountingJobSummary): string {
  if (j.status === 'pending') return queuePosition(j)
  if (j.status === 'failed') return j.error_detail ?? 'Failed'
  const counts = `${j.associations_done} association${j.associations_done === 1 ? '' : 's'}${
    j.flagged_count ? ` · ${j.flagged_count} flagged` : ''
  }`
  if (j.status === 'complete') return counts
  const page = `page ${j.pages_done} of ${j.total_pages ?? '…'}`
  return j.current_association ? `Working on ${j.current_association} · ${page}` : page
}
