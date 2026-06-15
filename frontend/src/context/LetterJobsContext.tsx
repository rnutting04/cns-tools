import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Alert, Button, Snackbar } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import apiClient from '../api/client'
import type { JobStatus, LetterJobStatus } from '../types'

interface LetterJobsContextValue {
  /** Live status (and download URL once ready) for every tracked job, keyed by id. */
  jobs: Record<string, LetterJobStatus>
  /** Start tracking a freshly-queued job so it is polled app-wide. */
  trackJob: (jobId: string) => void
  /** Number of tracked jobs still pending/processing. */
  inFlightCount: number
}

const isInFlight = (status: JobStatus) => status === 'pending' || status === 'processing'

const LetterJobsContext = createContext<LetterJobsContextValue | null>(null)

/**
 * App-wide tracker for background letter-generation jobs.
 *
 * Lives above the routed pages so a job kicked off on the generator keeps being
 * polled after the user navigates elsewhere. It is the single poller for live
 * job status — both the generator and the Generated Letters page read from it —
 * and raises a global toast when a job finishes.
 */
export function LetterJobsProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<Record<string, LetterJobStatus>>({})
  const [notice, setNotice] = useState<{ status: 'complete' | 'failed' } | null>(null)
  const navigate = useNavigate()

  // Jobs we've already toasted, so a transition only notifies once even across
  // polling-loop restarts.
  const notifiedRef = useRef<Set<string>>(new Set())

  const trackJob = useCallback((jobId: string) => {
    setJobs((prev) =>
      prev[jobId]
        ? prev
        : { ...prev, [jobId]: { job_id: jobId, status: 'pending', download_url: null } },
    )
  }, [])

  const inFlightIds = Object.values(jobs)
    .filter((job) => isInFlight(job.status))
    .map((job) => job.job_id)
    .sort()
  // Stable key so the polling effect restarts only when the in-flight set changes.
  const inFlightKey = inFlightIds.join(',')

  useEffect(() => {
    if (!inFlightKey) return
    const ids = inFlightKey.split(',')

    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const tick = async () => {
      const results = await Promise.allSettled(
        ids.map((id) => apiClient.get<LetterJobStatus>(`/api/letters/${id}`).then((r) => r.data)),
      )
      if (cancelled) return

      const updates: Record<string, LetterJobStatus> = {}
      results.forEach((res, i) => {
        if (res.status !== 'fulfilled') return
        const data = res.value
        updates[ids[i]] = data
        if (!isInFlight(data.status) && !notifiedRef.current.has(ids[i])) {
          notifiedRef.current.add(ids[i])
          setNotice({ status: data.status === 'failed' ? 'failed' : 'complete' })
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

  return (
    <LetterJobsContext.Provider value={{ jobs, trackJob, inFlightCount: inFlightIds.length }}>
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
                    navigate('/letters/generated')
                  }}
                >
                  View
                </Button>
              ) : undefined
            }
          >
            {notice.status === 'complete'
              ? 'Your letter is ready to download.'
              : 'A letter failed to generate.'}
          </Alert>
        ) : undefined}
      </Snackbar>
    </LetterJobsContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useLetterJobs() {
  const ctx = useContext(LetterJobsContext)
  if (!ctx) throw new Error('useLetterJobs must be used within LetterJobsProvider')
  return ctx
}
