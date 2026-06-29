import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { toast } from 'sonner'
import { useNavigate } from 'react-router-dom'
import apiClient from '../api/client'
import type { JobDetail, JobStatus, JobType } from '../types'

interface JobsContextValue {
  /** Live detail (status, current_step, download_url) for every tracked job. */
  jobs: Record<string, JobDetail>
  /** Register a freshly-queued job so it is polled app-wide. */
  trackJob: (jobId: string, jobType: JobType) => void
  /** Total count of pending/processing tracked jobs. */
  inFlightCount: number
}

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
    () => Object.values(jobs).filter((j) => isInFlight(j.status)).map((j) => j.id).sort(),
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

  return (
    <JobsContext.Provider value={{ jobs, trackJob, inFlightCount: inFlightIds.length }}>
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
