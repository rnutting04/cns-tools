import { useState } from 'react'
import type React from 'react'
import { useNavigate } from 'react-router-dom'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CircularProgress from '@mui/material/CircularProgress'
import Collapse from '@mui/material/Collapse'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import { alpha, useTheme } from '@mui/material/styles'
import EmailOutlinedIcon from '@mui/icons-material/EmailOutlined'
import LockOutlinedIcon from '@mui/icons-material/LockOutlined'
import LoginIcon from '@mui/icons-material/Login'
import Visibility from '@mui/icons-material/Visibility'
import VisibilityOff from '@mui/icons-material/VisibilityOff'
import { useAuth } from '../context/AuthContext'
import CnsLogo from '../components/common/CnsLogo'

export default function LoginPage() {
  const theme = useTheme()
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
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
        position: 'relative',
        overflow: 'hidden',
        px: 2,
        background: 'linear-gradient(145deg, #0F2057 0%, #1E3D8F 45%, #1D7834 100%)',
        // Subtle depth glows over the flat gradient.
        '&::before': {
          content: '""',
          position: 'absolute',
          inset: 0,
          background:
            'radial-gradient(60% 55% at 15% 10%, rgba(255,255,255,0.10), transparent 60%),' +
            'radial-gradient(50% 50% at 90% 90%, rgba(46,155,78,0.22), transparent 60%)',
          pointerEvents: 'none',
        },
      }}
    >
      <Card
        sx={{
          position: 'relative',
          width: '100%',
          maxWidth: 420,
          borderRadius: 3.5,
          overflow: 'hidden',
          border: 'none',
          boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
        }}
      >
        {/* Brand header bar */}
        <Box
          sx={{
            position: 'relative',
            background: `linear-gradient(160deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
            pt: 4.5,
            pb: 3.5,
            px: 4,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 1.5,
          }}
        >
          <CnsLogo height={56} showText={false} />
          <Typography
            variant="subtitle2"
            sx={{
              color: 'rgba(255,255,255,0.9)',
              letterSpacing: '1.5px',
              fontSize: '0.7rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              textAlign: 'center',
            }}
          >
            Community Management Services, Inc.
          </Typography>
          {/* Brand accent bar (green arc color) */}
          <Box
            sx={{
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: 0,
              height: 4,
              background: `linear-gradient(90deg, ${theme.palette.secondary.dark}, ${theme.palette.secondary.main}, ${theme.palette.secondary.light})`,
            }}
          />
        </Box>

        <CardContent sx={{ p: 4 }}>
          <Typography variant="h6" fontWeight={700} mb={0.5} color="text.primary">
            Sign in
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={3}>
            Enter your credentials to access your account
          </Typography>

          <Collapse in={!!error} unmountOnExit>
            <Alert
              severity="error"
              variant="filled"
              onClose={() => setError(null)}
              sx={{ mb: 2.5, borderRadius: 2, alignItems: 'center', fontWeight: 500 }}
            >
              {error}
            </Alert>
          </Collapse>

          <Box
            component="form"
            onSubmit={handleSubmit}
            display="flex"
            flexDirection="column"
            gap={2}
          >
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              fullWidth
              autoComplete="email"
              autoFocus
              error={!!error}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <EmailOutlinedIcon fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                },
              }}
            />
            <TextField
              label="Password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              fullWidth
              autoComplete="current-password"
              error={!!error}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <LockOutlinedIcon fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                        onClick={() => setShowPassword((s) => !s)}
                        edge="end"
                        size="small"
                      >
                        {showPassword ? (
                          <VisibilityOff fontSize="small" />
                        ) : (
                          <Visibility fontSize="small" />
                        )}
                      </IconButton>
                    </InputAdornment>
                  ),
                },
              }}
            />
            <Button
              type="submit"
              variant="contained"
              size="large"
              disabled={loading}
              startIcon={loading ? <CircularProgress size={18} color="inherit" /> : <LoginIcon />}
              sx={{
                mt: 1,
                py: 1.25,
                fontWeight: 600,
                borderRadius: 2,
                transition: theme.transitions.create(['box-shadow', 'transform']),
                '&:hover': {
                  boxShadow: `0 8px 20px ${alpha(theme.palette.primary.main, 0.35)}`,
                  transform: 'translateY(-1px)',
                },
              }}
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </Box>

          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', textAlign: 'center', mt: 3 }}
          >
            Trouble signing in? Contact your administrator.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  )
}
