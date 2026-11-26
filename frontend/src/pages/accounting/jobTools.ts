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

/** "Working on X · page 40 of 604", or the finished run's counts. */
export function jobProgress(j: AccountingJobSummary): string {
  if (j.status === 'pending') return 'Waiting for the background worker'
  if (j.status === 'failed') return j.error_detail ?? 'Failed'
  const counts = `${j.associations_done} association${j.associations_done === 1 ? '' : 's'}${
    j.flagged_count ? ` · ${j.flagged_count} flagged` : ''
  }`
  if (j.status === 'complete') return counts
  const page = `page ${j.pages_done} of ${j.total_pages ?? '…'}`
  return j.current_association ? `Working on ${j.current_association} · ${page}` : page
}
