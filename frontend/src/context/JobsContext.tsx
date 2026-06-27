import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Alert, Button, Snackbar } from '@mui/material'
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
  const [notice, setNotice] = useState<{
    jobType: JobType
    status: 'complete' | 'failed'
  } | null>(null)
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

  const inFlightIds = Object.values(jobs)
    .filter((j) => isInFlight(j.status))
    .map((j) => j.id)
    .sort()
  const inFlightKey = inFlightIds.join(',')

  useEffect(() => {
    if (!inFlightKey) return
    const ids = inFlightKey.split(',')
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const tick = async () => {
      const results = await Promise.allSettled(
        ids.map((id) => apiClient.get<JobDetail>(`/api/jobs/${id}`).then((r) => r.data)),
      )
      if (cancelled) return

      const updates: Record<string, JobDetail> = {}
      results.forEach((res, i) => {
        if (res.status !== 'fulfilled') return
        const data = res.value
        updates[ids[i]] = data
        if (!isInFlight(data.status) && !notifiedRef.current.has(ids[i])) {
          notifiedRef.current.add(ids[i])
          setNotice({
            jobType: data.job_type,
            status: data.status === 'failed' ? 'failed' : 'complete',
          })
        }
      })

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

  const jobLabel = notice?.jobType === 'budget' ? 'budget' : 'letter'

  return (
    <JobsContext.Provider value={{ jobs, trackJob, inFlightCount: inFlightIds.length }}>
      {children}
      <Snackbar
        open={notice !== null}
        autoHideDuration={6000}
        onClose={() => setNotice(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        {notice ? (
          <Alert
            severity={notice.status === 'complete' ? 'success' : 'error'}
            onClose={() => setNotice(null)}
            action={
              notice.status === 'complete' ? (
                <Button
                  color="inherit"
                  size="small"
                  onClick={() => {
                    setNotice(null)
                    navigate('/jobs')
                  }}
                >
                  View
                </Button>
              ) : undefined
            }
          >
            {notice.status === 'complete'
              ? `Your ${jobLabel} is ready to download.`
              : `A ${jobLabel} failed to generate.`}
          </Alert>
        ) : undefined}
      </Snackbar>
    </JobsContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useJobs() {
  const ctx = useContext(JobsContext)
  if (!ctx) throw new Error('useJobs must be used within JobsProvider')
  return ctx
}
