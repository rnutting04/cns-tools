import AppBar from '@mui/material/AppBar'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import IconButton from '@mui/material/IconButton'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import LogoutIcon from '@mui/icons-material/Logout'
import MenuIcon from '@mui/icons-material/Menu'
import { useAuth } from '../../hooks/useAuth'
import { useNavigate } from 'react-router-dom'
import CnsLogo from './CnsLogo'

interface Props {
  onMenuClick: () => void
}

export default function TopBar({ onMenuClick }: Props) {
  const { user, logout } = useAuth()
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const navigate = useNavigate()
  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }
  return (
    <AppBar
      position="fixed"
      sx={{ zIndex: (t) => t.zIndex.drawer + 1, bgcolor: 'primary.main' }}
    >
      <Toolbar>
        {isMobile && (
          <IconButton
            color="inherit"
            edge="start"
            onClick={onMenuClick}
            sx={{ mr: 1 }}
            aria-label="open navigation"
          >
            <MenuIcon />
          </IconButton>
        )}

        {/* Logo + app name */}
        <Box display="flex" alignItems="center" gap={1.5} sx={{ flexShrink: 0 }}>
          <CnsLogo height={32} />
          {!isMobile && (
            <Box>
              <Typography variant="subtitle2" sx={{ color: 'primary.contrastText', fontWeight: 700, lineHeight: 1.1, fontSize: '0.85rem' }}>
                C&amp;S Community Management
              </Typography>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', lineHeight: 1, fontSize: '0.65rem', letterSpacing: '0.5px' }}>
                Services, Inc.
              </Typography>
            </Box>
          )}
        </Box>

        <Box flex={1} />
        {user && (
          <Box display="flex" alignItems="center" gap={{ xs: 1, sm: 2 }}>
            {!isMobile && (
              <Typography variant="body2" sx={{ color: 'primary.contrastText', opacity: 0.85 }}>
                {user.fname} {user.lname}
              </Typography>
            )}
            <Button
              color="inherit"
              size="small"
              startIcon={<LogoutIcon />}
              onClick={handleLogout}
            >
              {isMobile ? '' : 'Log out'}
            </Button>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  )
}
