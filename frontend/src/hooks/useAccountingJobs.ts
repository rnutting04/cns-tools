/**
 * Background accounting-tool runs (FDIC exposure, audit threshold, AR &
 * prepaid) over combined multi-association PDFs. Jobs live on the server, so they survive
 * leaving the page or refreshing.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import apiClient from '../api/client'
import type {
  AccountingJobDetail,
  AccountingJobResult,
  AccountingJobSummary,
  AccountingTool,
} from '../types'

const POLL_MS = 2000

function errorText(e: unknown, fallback: string): string {
  const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
  return typeof detail === 'string' ? detail : fallback
}

export const isActive = (j: Pick<AccountingJobSummary, 'status'>) =>
  j.status === 'pending' || j.status === 'processing'

/** Recent runs of one tool, and starting new ones. */
export function useAccountingJobs(tool: AccountingTool) {
  const [jobs, setJobs] = useState<AccountingJobSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    apiClient
      .get<AccountingJobSummary[]>('/api/accounting/jobs', { params: { tool } })
      .then((res) => {
        if (!cancelled) setJobs(res.data)
      })
      .catch((e) => {
        if (!cancelled) setError(errorText(e, 'Could not load recent runs.'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tool])

  /** One combined PDF, or (multi-file tools) the files by role. */
  const start = useCallback(
    async (input: File | Partial<Record<string, File>>): Promise<AccountingJobSummary | null> => {
      const form = new FormData()
      form.append('tool', tool)
      const files = input instanceof File ? { report: input } : input
      for (const [role, file] of Object.entries(files)) {
        if (file) form.append(role, file)
      }
      const names = Object.values(files)
        .filter((f): f is File => Boolean(f))
        .map((f) => f.name)
        .join(', ')
      try {
        // Upload only; the work happens in the background.
        const res = await apiClient.post<AccountingJobSummary>('/api/accounting/jobs', form, {
          timeout: 300_000,
        })
        setJobs((js) => [res.data, ...js.filter((j) => j.id !== res.data.id)])
        return res.data
      } catch (e) {
        setError(errorText(e, `Could not upload ${names}.`))
        return null
      }
    },
    [tool],
  )

  /** Fold a fresher summary (from the detail poll) into the list. */
  const update = useCallback((s: AccountingJobSummary) => {
    setJobs((js) => js.map((j) => (j.id === s.id ? { ...j, ...s } : j)))
  }, [])

  return { jobs, loading, error, clearError: () => setError(null), start, update }
}

interface Followed {
  id: string | null
  summary: AccountingJobSummary | null
  results: AccountingJobResult[]
  error: string | null
}

/**
 * Follow one job: poll its progress and accumulate results, fetching only
 * associations finished since the last poll. Stops when the job ends.
 */
export function useAccountingJob(
  jobId: string | null,
  onSummary?: (s: AccountingJobSummary) => void,
) {
  // Tagged with the job it belongs to, so switching jobs never shows the
  // previous job's data (no reset-in-effect needed).
  const [state, setState] = useState<Followed>({
    id: null,
    summary: null,
    results: [],
    error: null,
  })
  const onSummaryRef = useRef(onSummary)
  useEffect(() => {
    onSummaryRef.current = onSummary
  })

  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    let have = 0

    const tick = async () => {
      try {
        const res = await apiClient.get<AccountingJobDetail>(`/api/accounting/jobs/${jobId}`, {
          params: { since: have },
        })
        if (cancelled) return
        const { results: fresh, ...summary } = res.data
        have += fresh.length
        setState((prev) => ({
          id: jobId,
          summary,
          results: prev.id === jobId ? [...prev.results, ...fresh] : fresh,
          error: null,
        }))
        onSummaryRef.current?.(summary)
        if (!isActive(summary)) return
      } catch (e) {
        if (cancelled) return
        const error = errorText(e, 'Lost contact with this run; refresh to retry.')
        setState((prev) =>
          prev.id === jobId ? { ...prev, error } : { ...EMPTY, id: jobId, error },
        )
        return
      }
      timer = setTimeout(tick, POLL_MS)
    }
    void tick()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [jobId])

  return state.id === jobId ? state : EMPTY
}

const EMPTY: Followed = { id: null, summary: null, results: [], error: null }
