import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import VisibilityIcon from '@mui/icons-material/Visibility'
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff'
import apiClient from '../../api/client'
import ErrorAlert from '../../components/layout/ErrorAlert'

const emptyForm = { current_password: '', new_password: '', confirm_password: '' }

interface Props {
  onSuccess?: () => void | Promise<void>
}

export default function ChangePasswordSection({ onSuccess }: Props) {
  const [form, setForm] = useState(emptyForm)
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const mismatch = form.confirm_password.length > 0 && form.new_password !== form.confirm_password
  const tooShort = form.new_password.length > 0 && form.new_password.length < 12
  const canSubmit =
    form.current_password.length > 0 &&
    form.new_password.length >= 12 &&
    form.new_password === form.confirm_password

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    setLoading(true)
    setError(null)
    setSuccess(false)
    try {
      await apiClient.post('/api/users/me/change-password', {
        current_password: form.current_password,
        new_password: form.new_password,
      })
      setForm(emptyForm)
      setSuccess(true)
      await onSuccess?.()
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Failed to change password.',
      )
    } finally {
      setLoading(false)
    }
  }

  function field(
    id: keyof typeof form,
    label: string,
    show: boolean,
    toggle: () => void,
  ) {
    return (
      <TextField
        id={id}
        label={label}
        type={show ? 'text' : 'password'}
        value={form[id]}
        fullWidth
        autoComplete={id === 'current_password' ? 'current-password' : 'new-password'}
        error={
          (id === 'confirm_password' && mismatch) ||
          (id === 'new_password' && tooShort)
        }
        helperText={
          id === 'new_password' && tooShort
            ? 'Must be at least 12 characters'
            : id === 'confirm_password' && mismatch
              ? 'Passwords do not match'
              : undefined
        }
        onChange={(e) => {
          setForm((p) => ({ ...p, [id]: e.target.value }))
          setSuccess(false)
          setError(null)
        }}
        slotProps={{
          input: {
            endAdornment: (
              <InputAdornment position="end">
                <IconButton size="small" edge="end" onClick={toggle} tabIndex={-1}>
                  {show ? <VisibilityOffIcon fontSize="small" /> : <VisibilityIcon fontSize="small" />}
                </IconButton>
              </InputAdornment>
            ),
          },
        }}
      />
    )
  }

  return (
    <Card variant="outlined" sx={{ borderRadius: 2 }}>
      <CardContent sx={{ p: 3 }}>
        <Typography variant="h6" fontWeight={600} mb={2}>
          Change password
        </Typography>
        <Divider sx={{ mb: 2 }} />

        <Box component="form" onSubmit={handleSubmit} display="flex" flexDirection="column" gap={2}>
          {error && <ErrorAlert message={error} onClose={() => setError(null)} />}
          {success && (
            <Alert
              severity="success"
              icon={<CheckCircleOutlineIcon fontSize="inherit" />}
              onClose={() => setSuccess(false)}
            >
              Password updated successfully.
            </Alert>
          )}

          {field('current_password', 'Current password', showCurrent, () => setShowCurrent((v) => !v))}
          {field('new_password', 'New password', showNew, () => setShowNew((v) => !v))}
          {field('confirm_password', 'Confirm new password', showNew, () => setShowNew((v) => !v))}

          <Box display="flex" justifyContent="flex-end">
            <Button
              type="submit"
              variant="contained"
              disabled={!canSubmit || loading}
              startIcon={loading ? <CircularProgress size={16} color="inherit" /> : undefined}
            >
              {loading ? 'Saving…' : 'Update password'}
            </Button>
          </Box>
        </Box>
      </CardContent>
    </Card>
  )
}
