import { useCallback, useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Divider from '@mui/material/Divider'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import apiClient from '../../api/client'
import { formatDateTime } from '../../utils/formatDate'
import ErrorAlert from '../layout/ErrorAlert'
import LetterStatusChip from '../letters/LetterStatusChip'
import type { BudgetJobDetail } from '../../types'

interface Props {
  jobId: string | null
  onClose: () => void
  onRetried?: () => void
}

function FieldRows({ rows }: { rows: { label: string; value: string }[] }) {
  return (
    <Box>
      {rows.map((row, i) => (
        <Box
          key={`${row.label}-${i}`}
          display="flex"
          justifyContent="space-between"
          gap={2}
          py={0.75}
        >
          <Typography variant="body2" color="text.secondary" sx={{ flexShrink: 0 }}>
            {row.label}
          </Typography>
          <Typography variant="body2" sx={{ textAlign: 'right', wordBreak: 'break-word' }}>
            {row.value}
          </Typography>
        </Box>
      ))}
    </Box>
  )
}

export default function BudgetDetailDialog({ jobId, onClose, onRetried }: Props) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  const [detail, setDetail] = useState<BudgetJobDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDetail = useCallback(async (id: string) => {
    setLoading(true)
    setError(null)
    setDetail(null)
    try {
      const { data } = await apiClient.get<BudgetJobDetail>(`/api/budget/jobs/${id}/details`)
      setDetail(data)
    } catch {
      setError('Failed to load budget job details.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (jobId) fetchDetail(jobId)
  }, [jobId, fetchDetail])

  const handleRetry = async () => {
    if (!detail) return
    setRetrying(true)
    setError(null)
    try {
      await apiClient.post(`/api/budget/jobs/${detail.job_id}/retry`)
      onRetried?.()
      onClose()
    } catch {
      setError('Failed to retry job.')
    } finally {
      setRetrying(false)
    }
  }

  const isStuck = detail?.status === 'pending' || detail?.status === 'processing'

  return (
    <Dialog open={jobId !== null} onClose={onClose} fullScreen={fullScreen} maxWidth="sm" fullWidth>
      <DialogTitle>Budget job details</DialogTitle>
      <DialogContent dividers>
        {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

        {loading ? (
          <Box display="flex" justifyContent="center" py={6}>
            <CircularProgress size={28} />
          </Box>
        ) : detail ? (
          <Box display="flex" flexDirection="column" gap={2}>
            <Box>
              <Box display="flex" justifyContent="space-between" alignItems="center" gap={2}>
                <Typography variant="h6">
                  {detail.association_name} {detail.budget_year}
                </Typography>
                <LetterStatusChip status={detail.status} />
              </Box>
              <Typography variant="body2" color="text.secondary">
                Submitted by {detail.created_by_name} · {formatDateTime(detail.created_at)}
              </Typography>
            </Box>

            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Uploaded files
              </Typography>
              <Divider sx={{ mb: 1 }} />
              <FieldRows
                rows={[
                  { label: 'Financial report', value: detail.financial_report_filename },
                  { label: 'Prior budget', value: detail.prior_budget_filename },
                ]}
              />
            </Box>

            {detail.status === 'complete' && detail.review_flag_count !== null && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Results
                </Typography>
                <Divider sx={{ mb: 1 }} />
                <FieldRows
                  rows={[
                    {
                      label: 'Review flags',
                      value:
                        detail.review_flag_count === 0
                          ? 'None'
                          : String(detail.review_flag_count),
                    },
                  ]}
                />
              </Box>
            )}

            {detail.status === 'failed' && detail.error_code && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Failure
                </Typography>
                <Divider sx={{ mb: 1 }} />
                <FieldRows
                  rows={[
                    { label: 'Error', value: detail.error_code },
                    ...(detail.error_detail?.message
                      ? [{ label: 'Detail', value: String(detail.error_detail.message) }]
                      : []),
                  ]}
                />
              </Box>
            )}
          </Box>
        ) : null}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        {isStuck && (
          <Button
            onClick={handleRetry}
            disabled={retrying}
            startIcon={retrying ? <CircularProgress size={14} color="inherit" /> : undefined}
          >
            Retry
          </Button>
        )}
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}
