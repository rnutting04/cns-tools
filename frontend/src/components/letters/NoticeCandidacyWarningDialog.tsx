import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Typography from '@mui/material/Typography'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import Box from '@mui/material/Box'

interface Props {
  open: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function NoticeCandidacyWarningDialog({ open, onConfirm, onCancel }: Props) {
  return (
    <Dialog open={open} onClose={onCancel} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <WarningAmberIcon color="warning" />
          Notice period warning
        </Box>
      </DialogTitle>
      <DialogContent>
        <Typography>
          The meeting date is inside the required 60-day notice period. Would you like to proceed
          anyway?
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="contained" color="warning" onClick={onConfirm}>
          Proceed anyway
        </Button>
      </DialogActions>
    </Dialog>
  )
}
