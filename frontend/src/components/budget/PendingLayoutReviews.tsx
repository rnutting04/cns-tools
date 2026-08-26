import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import apiClient from '../../api/client'
import { useJobs } from '../../context/JobsContext'
import LayoutReviewPanel from './LayoutReviewPanel'
import { AWAITING_LAYOUT_REVIEW } from '../../types'
import type { BudgetJobStatus, LayoutCorrections } from '../../types'

interface Parked {
  jobId: string
  associationName: string
  priorBudgetFilename: string
  status: BudgetJobStatus
}

/**
 * Surfaces any budget run that is parked waiting for its workbook layout to be
 * confirmed, and resumes it once the reviewer approves.
 *
 * Parked jobs still report status "processing" — the pause is signalled by
 * current_step, so JobsContext keeps polling them and this panel appears without
 * any extra plumbing.
 */
export default function PendingLayoutReviews() {
  const { jobs } = useJobs()
  const [parked, setParked] = useState<Record<string, Parked>>({})
  const [submitting, setSubmitting] = useState<string | null>(null)
  const seenRef = useRef<Set<string>>(new Set())

  // Ids of tracked budget jobs currently reporting the parked step.
  const awaitingIds = useMemo(
    () =>
      Object.values(jobs)
        .filter((j) => j.job_type === 'budget' && j.current_step === AWAITING_LAYOUT_REVIEW)
        .map((j) => j.id)
        .sort()
        .join(','),
    [jobs],
  )

  useEffect(() => {
    if (!awaitingIds) {
      setParked({})
      return
    }
    const ids = awaitingIds.split(',')
    let cancelled = false

    ;(async () => {
      const next: Record<string, Parked> = {}
      await Promise.all(
        ids.map(async (id) => {
          try {
            const [status, details] = await Promise.all([
              apiClient.get<BudgetJobStatus>(`/api/budget/jobs/${id}`),
              apiClient.get<{ association_name: string; prior_budget_filename: string }>(
                `/api/budget/jobs/${id}/details`,
              ),
            ])
            if (!status.data.layout_review) return
            next[id] = {
              jobId: id,
              associationName: details.data.association_name,
              priorBudgetFilename: details.data.prior_budget_filename,
              status: status.data,
            }
            if (!seenRef.current.has(id)) {
              seenRef.current.add(id)
              toast.info('A budget needs its workbook layout confirmed before it can continue.')
            }
          } catch {
            // Transient fetch failure — the next poll will pick it up.
          }
        }),
      )
      if (!cancelled) setParked(next)
    })()

    return () => {
      cancelled = true
    }
  }, [awaitingIds])

  const handleConfirm = useCallback(
    async (jobId: string, corrections: LayoutCorrections | null) => {
      setSubmitting(jobId)
      try {
        await apiClient.post(`/api/budget/jobs/${jobId}/confirm-layout`, {
          corrections: corrections ?? null,
        })
        setParked((prev) => {
          const next = { ...prev }
          delete next[jobId]
          return next
        })
        toast.success('Layout confirmed — the budget is generating. Future runs skip this step.')
      } catch {
        toast.error('Could not confirm the layout. Try again.')
      } finally {
        setSubmitting(null)
      }
    },
    [],
  )

  const items = Object.values(parked)
  if (items.length === 0) return null

  return (
    <Box mt={3}>
      <Stack spacing={2}>
        {items.map((item) => (
          <LayoutReviewPanel
            key={item.jobId}
            review={item.status.layout_review!}
            associationName={item.associationName}
            priorBudgetFilename={item.priorBudgetFilename}
            submitting={submitting === item.jobId}
            onConfirm={(corrections) => handleConfirm(item.jobId, corrections)}
          />
        ))}
      </Stack>
    </Box>
  )
}
