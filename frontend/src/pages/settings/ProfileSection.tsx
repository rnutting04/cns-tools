import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Divider from '@mui/material/Divider'
import Typography from '@mui/material/Typography'
import EmailIcon from '@mui/icons-material/Email'
import WorkIcon from '@mui/icons-material/Work'
import { useAuth } from '../../hooks/useAuth'
import RoleBadge from '../../components/layout/RoleBadge'

export default function ProfileSection() {
  const { user } = useAuth()
  if (!user) return null

  return (
    <Card variant="outlined" sx={{ borderRadius: 2 }}>
      <CardContent sx={{ p: 3 }}>
        <Typography variant="h6" fontWeight={600} mb={2}>
          Profile
        </Typography>
        <Divider sx={{ mb: 2 }} />

        <Typography variant="subtitle1" fontWeight={500}>
          {user.fname} {user.lname}
        </Typography>

        <Box display="flex" alignItems="center" gap={0.75} mt={1}>
          <EmailIcon sx={{ fontSize: 15, color: 'text.disabled' }} />
          <Typography variant="body2" color="text.secondary">
            {user.email}
          </Typography>
        </Box>

        <Box display="flex" alignItems="center" gap={0.75} mt={0.5}>
          <WorkIcon sx={{ fontSize: 15, color: 'text.disabled' }} />
          <Typography variant="body2" color="text.secondary">
            {user.title}
          </Typography>
        </Box>

        <Box mt={1.5}>
          <RoleBadge role={user.role} />
        </Box>
      </CardContent>
    </Card>
  )
}
