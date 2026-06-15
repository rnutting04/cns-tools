import Chip from '@mui/material/Chip'
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

export default function LetterStatusChip({ status }: { status: JobStatus }) {
  return <Chip label={STATUS_LABEL[status]} size="small" color={STATUS_COLOR[status]} />
}
