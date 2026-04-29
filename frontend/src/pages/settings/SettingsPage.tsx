import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import LockIcon from '@mui/icons-material/Lock'
import { useAuth } from '../../hooks/useAuth'
import ProfileSection from './ProfileSection'
import ChangePasswordSection from './ChangePasswordSection'

export default function SettingsPage() {
  const { user, refreshUser } = useAuth()
  const mustChange = user?.password_change_required ?? false

  return (
    <Box maxWidth={600}>
      <Typography variant="h5" mb={3}>
        Settings
      </Typography>

      {mustChange && (
        <Alert severity="warning" icon={<LockIcon fontSize="inherit" />} sx={{ mb: 3 }}>
          You must set a new password before you can access the app. Please choose a password
          that is at least 12 characters long.
        </Alert>
      )}

      <Box display="flex" flexDirection="column" gap={3}>
        <ProfileSection />
        <ChangePasswordSection onSuccess={mustChange ? refreshUser : undefined} />
      </Box>
    </Box>
  )
}
