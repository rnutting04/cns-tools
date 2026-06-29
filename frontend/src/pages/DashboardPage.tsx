import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import Grid from '@mui/material/Grid'
import Skeleton from '@mui/material/Skeleton'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import ApartmentIcon from '@mui/icons-material/Apartment'
import PeopleIcon from '@mui/icons-material/People'
import DescriptionIcon from '@mui/icons-material/Description'
import TableChartIcon from '@mui/icons-material/TableChart'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { hasRole } from '../utils/auth'
import apiClient from '../api/client'
import type { Association, Job, JobType, User } from '../types'
import RoleBadge from '../components/layout/RoleBadge'
import JobStatusChip from '../components/common/JobStatusChip'
import { formatDateTime } from '../utils/formatDate'

const TYPE_LABEL: Record<JobType, string> = { letter: 'Letter', budget: 'Budget' }
const TYPE_COLOR: Record<JobType, 'primary' | 'secondary'> = {
  letter: 'primary',
  budget: 'secondary',
}

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string | number
  to?: string
}

function StatCard({ icon, label, value, to }: StatCardProps) {
  return (
    <Card>
      <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box
          sx={{
            width: 48,
            height: 48,
            borderRadius: 2,
            bgcolor: 'primary.main',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            flexShrink: 0,
          }}
        >
          {icon}
        </Box>
        <Box flex={1}>
          <Typography variant="h5" fontWeight={700}>
            {value}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
        </Box>
        {to && (
          <Button component={Link} to={to} size="small" variant="outlined">
            View
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

interface QuickLinkProps {
  icon: React.ReactNode
  label: string
  description: string
  to: string
}

function QuickLink({ icon, label, description, to }: QuickLinkProps) {
  return (
    <Card
      component={Link}
      to={to}
      sx={{
        textDecoration: 'none',
        transition: 'box-shadow 0.2s',
        '&:hover': { boxShadow: '0 4px 16px rgba(0,0,0,0.12)' },
      }}
    >
      <CardContent sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
        <Box sx={{ color: 'primary.main', mt: 0.5 }}>{icon}</Box>
        <Box>
          <Typography variant="subtitle1">{label}</Typography>
          <Typography variant="body2" color="text.secondary">
            {description}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  )
}

function RecentJobsSkeleton() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <Box key={i}>
          {i > 0 && <Divider />}
          <Box sx={{ px: 2, py: 1.5, display: 'flex', alignItems: 'center', gap: 2 }}>
            <Skeleton variant="rounded" width={56} height={22} />
            <Box flex={1}>
              <Skeleton variant="text" width="50%" height={20} />
            </Box>
            <Skeleton variant="rounded" width={72} height={22} />
            <Skeleton variant="text" width={90} height={18} />
          </Box>
        </Box>
      ))}
    </>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [assocCount, setAssocCount] = useState<number | null>(null)
  const [userCount, setUserCount] = useState<number | null>(null)
  const [recentJobs, setRecentJobs] = useState<Job[] | null>(null)

  useEffect(() => {
    apiClient
      .get<Association[]>('/api/associations')
      .then((r) => setAssocCount(r.data.length))
      .catch(() => setAssocCount(0))
    apiClient
      .get<Job[]>('/api/jobs')
      .then((r) => setRecentJobs(r.data.slice(0, 5)))
      .catch(() => setRecentJobs([]))
    if (user && hasRole(user, ['admin', 'super_admin'])) {
      apiClient
        .get<User[]>('/api/users')
        .then((r) => setUserCount(r.data.length))
        .catch(() => setUserCount(0))
    }
  }, [user])

  if (!user) return null

  const isAdmin = hasRole(user, ['admin', 'super_admin'])

  return (
    <Box>
      <Box display="flex" alignItems="center" gap={1.5} mb={3}>
        <Box>
          <Typography variant="h5">Welcome back, {user.fname}</Typography>
          <Box display="flex" alignItems="center" gap={1} mt={0.5}>
            <Typography variant="body2" color="text.secondary">
              {user.title}
            </Typography>
            <RoleBadge role={user.role} />
          </Box>
        </Box>
      </Box>

      <Typography variant="subtitle1" mb={1.5} color="text.secondary">
        Overview
      </Typography>
      <Grid container spacing={2} mb={4}>
        {hasRole(user, ['manager', 'admin', 'super_admin']) && (
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <StatCard
              icon={<ApartmentIcon />}
              label="Associations"
              value={assocCount ?? '—'}
              to="/associations"
            />
          </Grid>
        )}
        {isAdmin && (
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <StatCard icon={<PeopleIcon />} label="Users" value={userCount ?? '—'} to="/users" />
          </Grid>
        )}
      </Grid>

      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
        <Typography variant="subtitle1" color="text.secondary">
          Recent jobs
        </Typography>
        <Button component={Link} to="/jobs" size="small">
          View all
        </Button>
      </Box>
      <Card variant="outlined" sx={{ mb: 4 }}>
        {recentJobs === null ? (
          <RecentJobsSkeleton />
        ) : recentJobs.length === 0 ? (
          <Typography color="text.secondary" textAlign="center" py={3} variant="body2">
            No jobs yet.
          </Typography>
        ) : (
          recentJobs.map((job, i) => (
            <Box key={job.id}>
              {i > 0 && <Divider />}
              <Box
                sx={{
                  px: 2,
                  py: 1.5,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                  flexWrap: 'wrap',
                }}
              >
                <Chip
                  label={TYPE_LABEL[job.job_type]}
                  size="small"
                  color={TYPE_COLOR[job.job_type]}
                  variant="outlined"
                  sx={{ flexShrink: 0 }}
                />
                <Typography variant="body2" flex={1} noWrap>
                  {job.title}
                </Typography>
                <JobStatusChip status={job.status} />
                <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
                  {formatDateTime(job.created_at)}
                </Typography>
              </Box>
            </Box>
          ))
        )}
      </Card>

      <Typography variant="subtitle1" mb={1.5} color="text.secondary">
        Tools
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <QuickLink
            icon={<DescriptionIcon />}
            label="Letter generator"
            description="Generate correspondence letters"
            to="/letters"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <QuickLink
            icon={<TableChartIcon />}
            label="Excel tools"
            description="Process and export spreadsheet data"
            to="/excel"
          />
        </Grid>
      </Grid>
    </Box>
  )
}
