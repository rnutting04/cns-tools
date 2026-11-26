import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { toast } from 'sonner'
import { useNavigate } from 'react-router-dom'
import apiClient from '../api/client'
import { JOB_TOOLS, jobLink } from '../pages/accounting/jobTools'
import type { AccountingJobSummary, JobDetail, JobStatus, JobType } from '../types'

interface JobsContextValue {
  /** Live detail (status, current_step, download_url) for every tracked job. */
  jobs: Record<string, JobDetail>
  /** Register a freshly-queued job so it is polled app-wide. */
  trackJob: (jobId: string, jobType: JobType) => void
  /** Accounting tool runs (FDIC, audit threshold, AR & prepaid) being followed. */
  accountingJobs: Record<string, AccountingJobSummary>
  /** Follow a freshly-started accounting run app-wide (badge + toast when done). */
  trackAccountingJob: (job: AccountingJobSummary) => void
  /** Total count of pending/processing tracked jobs, of every kind. */
  inFlightCount: number
}

const ACCOUNTING_POLL_MS = 3000

const isInFlight = (status: JobStatus) => status === 'pending' || status === 'processing'

const JobsContext = createContext<JobsContextValue | null>(null)

export function JobsProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<Record<string, JobDetail>>({})
  const navigate = useNavigate()

  const notifiedRef = useRef<Set<string>>(new Set())

  const trackJob = useCallback((jobId: string, jobType: JobType) => {
    setJobs((prev) => {
      if (prev[jobId]) return prev
      return {
        ...prev,
        [jobId]: {
          id: jobId,
          job_type: jobType,
          title: '',
          association_name: '',
          status: 'pending',
          created_at: new Date().toISOString(),
          current_step: null,
          download_url: null,
        },
      }
    })
  }, [])

  const inFlightIds = useMemo(
    () =>
      Object.values(jobs)
        .filter((j) => isInFlight(j.status))
        .map((j) => j.id)
        .sort(),
    [jobs],
  )
  const inFlightKey = inFlightIds.join(',')

  useEffect(() => {
    if (!inFlightKey) return
    const ids = inFlightKey.split(',')
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const tick = async () => {
      const params = new URLSearchParams(ids.map((id) => ['ids', id]))
      let fetched: JobDetail[]
      try {
        const res = await apiClient.get<JobDetail[]>(`/api/jobs/status?${params}`)
        fetched = res.data
      } catch {
        timer = setTimeout(tick, 2000)
        return
      }
      if (cancelled) return

      const updates: Record<string, JobDetail> = {}
      for (const data of fetched) {
        updates[data.id] = data
        if (!isInFlight(data.status) && !notifiedRef.current.has(data.id)) {
          notifiedRef.current.add(data.id)
          const label = data.job_type === 'budget' ? 'budget' : 'letter'
          if (data.status === 'failed') {
            toast.error(`Your ${label} failed.`, {
              description: 'Check My Jobs for details.',
              action: { label: 'View jobs', onClick: () => navigate('/jobs') },
            })
          } else {
            toast.success(`Your ${label} is ready to download.`, {
              action: { label: 'View jobs', onClick: () => navigate('/jobs') },
            })
          }
        }
      }

      if (Object.keys(updates).length > 0) {
        setJobs((prev) => ({ ...prev, ...updates }))
      }
      timer = setTimeout(tick, 2000)
    }

    tick()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [inFlightKey])

  // ---- Accounting runs: long (minutes), so follow them across pages and
  // pick up any still running after a refresh.
  const [accountingJobs, setAccountingJobs] = useState<Record<string, AccountingJobSummary>>({})

  const trackAccountingJob = useCallback((job: AccountingJobSummary) => {
    setAccountingJobs((prev) => ({ ...prev, [job.id]: { ...prev[job.id], ...job } }))
  }, [])

  useEffect(() => {
    let cancelled = false
    apiClient
      .get<AccountingJobSummary[]>('/api/accounting/jobs')
      .then((res) => {
        if (cancelled) return
        const running = res.data.filter((j) => isInFlight(j.status))
        if (running.length)
          setAccountingJobs((prev) => ({
            ...Object.fromEntries(running.map((j) => [j.id, j])),
            ...prev,
          }))
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const accountingInFlight = useMemo(
    () =>
      Object.values(accountingJobs)
        .filter((j) => isInFlight(j.status))
        .map((j) => j.id)
        .sort(),
    [accountingJobs],
  )
  const accountingKey = accountingInFlight.join(',')

  useEffect(() => {
    if (!accountingKey) return
    const ids = new Set(accountingKey.split(','))
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const tick = async () => {
      try {
        // The list carries every recent run's progress in one request.
        const res = await apiClient.get<AccountingJobSummary[]>('/api/accounting/jobs')
        if (cancelled) return
        const fresh = res.data.filter((j) => ids.has(j.id))
        for (const j of fresh) {
          if (isInFlight(j.status) || notifiedRef.current.has(j.id)) continue
          notifiedRef.current.add(j.id)
          const label = JOB_TOOLS[j.tool]?.label ?? 'Accounting'
          const action = { label: 'View results', onClick: () => navigate(jobLink(j)) }
          if (j.status === 'failed') {
            toast.error(`${label} run failed.`, {
              description: j.error_detail ?? undefined,
              action,
            })
          } else {
            const flagged = j.flagged_count ? ` · ${j.flagged_count} flagged` : ''
            toast.success(`${label} run finished.`, {
              description: `${j.associations_done} associations${flagged}`,
              action,
            })
          }
        }
        if (fresh.length)
          setAccountingJobs((prev) => ({
            ...prev,
            ...Object.fromEntries(fresh.map((j) => [j.id, j])),
          }))
      } catch {
        // retry on the next tick
      }
      if (!cancelled) timer = setTimeout(tick, ACCOUNTING_POLL_MS)
    }

    tick()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [accountingKey, navigate])

  return (
    <JobsContext.Provider
      value={{
        jobs,
        trackJob,
        accountingJobs,
        trackAccountingJob,
        inFlightCount: inFlightIds.length + accountingInFlight.length,
      }}
    >
      {children}
    </JobsContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useJobs() {
  const ctx = useContext(JobsContext)
  if (!ctx) throw new Error('useJobs must be used within JobsProvider')
  return ctx
}
