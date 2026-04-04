import Alert from '@mui/material/Alert'
import AlertTitle from '@mui/material/AlertTitle'

interface Props {
  message: string
  title?: string
  onClose?: () => void
}

export default function ErrorAlert({ message, title, onClose }: Props) {
  return (
    <Alert severity="error" onClose={onClose} sx={{ mb: 2 }}>
      {title && <AlertTitle>{title}</AlertTitle>}
      {message}
    </Alert>
  )
}
