import Chip from '@mui/material/Chip'
import type { JobKind, JobRow } from './jobRows'

const KIND_COLOR: Record<JobKind, 'primary' | 'secondary' | 'success'> = {
  letter: 'primary',
  budget: 'secondary',
  accounting: 'success',
}

export default function JobTypeChip({ row }: { row: JobRow }) {
  return (
    <Chip
      label={row.typeLabel}
      size="small"
      color={KIND_COLOR[row.kind]}
      variant="outlined"
      sx={{ flexShrink: 0 }}
    />
  )
}
