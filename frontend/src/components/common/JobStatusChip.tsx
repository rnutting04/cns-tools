import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import type { JobStatus } from '../../types'

const STATUS_COLOR: Record<JobStatus, 'default' | 'info' | 'success' | 'error'> = {
  pending: 'default',
  processing: 'info',
  complete: 'success',
  failed: 'error',
}

const STATUS_LABEL: Record<JobStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  complete: 'Complete',
  failed: 'Failed',
}

export default function JobStatusChip({ status }: { status: JobStatus }) {
  const inFlight = status === 'pending' || status === 'processing'
  return (
    <Chip
      label={STATUS_LABEL[status]}
      size="small"
      color={STATUS_COLOR[status]}
      icon={inFlight ? <CircularProgress size={12} color="inherit" /> : undefined}
    />
  )
}
