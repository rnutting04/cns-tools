import { useState } from 'react'
import type React from 'react'
import { useNavigate } from 'react-router-dom'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CircularProgress from '@mui/material/CircularProgress'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import { useAuth } from '../hooks/useAuth'
import ErrorAlert from '../components/layout/ErrorAlert'
import CnsLogo from '../components/common/CnsLogo'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.SyntheticEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Login failed. Please check your credentials.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="100vh"
      sx={{
        background: 'linear-gradient(145deg, #0F2057 0%, #1E3D8F 45%, #1D7834 100%)',
      }}
    >
      <Card sx={{ width: '100%', maxWidth: 420, mx: 2, borderRadius: 3, overflow: 'hidden', boxShadow: '0 8px 40px rgba(0,0,0,0.28)' }}>
        {/* Brand header bar */}
        <Box
          sx={{
            bgcolor: '#1E3D8F',
            pt: 4,
            pb: 3,
            px: 4,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 1.5,
          }}
        >
          <CnsLogo height={56} showText={false} />
          <Box textAlign="center">
            <Typography
              variant="subtitle2"
              sx={{
                color: 'rgba(255,255,255,0.9)',
                letterSpacing: '1.5px',
                fontSize: '0.7rem',
                fontWeight: 600,
                textTransform: 'uppercase',
              }}
            >
              Community Management Services, Inc.
            </Typography>
          </Box>
        </Box>

        <CardContent sx={{ p: 4 }}>
          <Typography variant="h6" fontWeight={600} mb={0.5} color="text.primary">
            Sign in
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={3}>
            Enter your credentials to access your account
          </Typography>

          {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

          <Box component="form" onSubmit={handleSubmit} display="flex" flexDirection="column" gap={2}>
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              fullWidth
              autoComplete="email"
              autoFocus
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              fullWidth
              autoComplete="current-password"
            />
            <Button
              type="submit"
              variant="contained"
              size="large"
              disabled={loading}
              startIcon={loading ? <CircularProgress size={18} color="inherit" /> : undefined}
              sx={{ mt: 1 }}
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  )
}
