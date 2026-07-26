import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardActionArea from '@mui/material/CardActionArea'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import Grid from '@mui/material/Grid'
import Paper from '@mui/material/Paper'
import Skeleton from '@mui/material/Skeleton'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import { alpha, useTheme } from '@mui/material/styles'
import ApartmentIcon from '@mui/icons-material/Apartment'
import PeopleIcon from '@mui/icons-material/People'
import DescriptionIcon from '@mui/icons-material/Description'
import TableChartIcon from '@mui/icons-material/TableChart'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import WorkHistoryIcon from '@mui/icons-material/WorkHistory'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import InboxOutlinedIcon from '@mui/icons-material/InboxOutlined'
import type { SvgIconProps } from '@mui/material/SvgIcon'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useJobs } from '../context/JobsContext'
import { hasRole } from '../utils/auth'
import apiClient from '../api/client'
import type { Association, Job, JobType, User } from '../types'
import JobStatusChip from '../components/common/JobStatusChip'
import { formatDateTime } from '../utils/formatDate'

type BrandColor = 'primary' | 'secondary' | 'warning'

const TYPE_LABEL: Record<JobType, string> = { letter: 'Letter', budget: 'Budget' }
const TYPE_COLOR: Record<JobType, 'primary' | 'secondary'> = {
  letter: 'primary',
  budget: 'secondary',
}

function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

function todayLabel(): string {
  return new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })
}

// A tinted, rounded icon badge — the shared visual motif across the app's cards.
function IconBadge({
  color,
  children,
}: {
  color: BrandColor
  children: React.ReactElement<SvgIconProps>
}) {
  return (
    <Box
      sx={(theme) => ({
        width: 48,
        height: 48,
        flexShrink: 0,
        borderRadius: 2,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: alpha(theme.palette[color].main, 0.12),
        color: `${color}.main`,
      })}
    >
      {children}
    </Box>
  )
}

interface StatCardProps {
  icon: React.ReactElement<SvgIconProps>
  label: string
  value: string | number
  color: BrandColor
  to?: string
}

function StatCard({ icon, label, value, color, to }: StatCardProps) {
  const inner = (
    <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      <IconBadge color={color}>{icon}</IconBadge>
      <Box flex={1} minWidth={0}>
        <Typography variant="h5" fontWeight={700} lineHeight={1.2}>
          {value}
        </Typography>
        <Typography variant="body2" color="text.secondary" noWrap>
          {label}
        </Typography>
      </Box>
      {to && <ChevronRightIcon fontSize="small" sx={{ color: 'text.disabled' }} />}
    </CardContent>
  )

  return (
    <Card
      variant="outlined"
      sx={(theme) => ({
        borderRadius: 2.5,
        height: '100%',
        transition: theme.transitions.create(['box-shadow', 'transform', 'border-color'], {
          duration: theme.transitions.duration.shorter,
        }),
        ...(to && {
          '&:hover': {
            borderColor: `${color}.main`,
            boxShadow: `0 6px 16px ${alpha(theme.palette[color].main, 0.16)}`,
            transform: 'translateY(-2px)',
          },
        }),
      })}
    >
      {to ? (
        <CardActionArea component={Link} to={to} sx={{ height: '100%' }}>
          {inner}
        </CardActionArea>
      ) : (
        inner
      )}
    </Card>
  )
}

interface QuickLinkProps {
  icon: React.ReactElement<SvgIconProps>
  label: string
  description: string
  to: string
  color: BrandColor
}

function QuickLink({ icon, label, description, to, color }: QuickLinkProps) {
  return (
    <Card
      variant="outlined"
      sx={(theme) => ({
        borderRadius: 2.5,
        height: '100%',
        transition: theme.transitions.create(['box-shadow', 'transform', 'border-color'], {
          duration: theme.transitions.duration.shorter,
        }),
        '&:hover': {
          borderColor: `${color}.main`,
          boxShadow: `0 6px 16px ${alpha(theme.palette[color].main, 0.16)}`,
          transform: 'translateY(-2px)',
        },
      })}
    >
      <CardActionArea component={Link} to={to} sx={{ height: '100%' }}>
        <CardContent sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
          <IconBadge color={color}>{icon}</IconBadge>
          <Box minWidth={0}>
            <Typography variant="subtitle1" fontWeight={600} lineHeight={1.3}>
              {label}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {description}
            </Typography>
          </Box>
        </CardContent>
      </CardActionArea>
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
  const theme = useTheme()
  const { user } = useAuth()
  const { inFlightCount } = useJobs()
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

  const isManagerUp = hasRole(user, ['manager', 'admin', 'super_admin'])
  const isAdmin = hasRole(user, ['admin', 'super_admin'])

  return (
    <Box>
      {/* Welcome banner */}
      <Paper
        elevation={0}
        sx={{
          position: 'relative',
          overflow: 'hidden',
          borderRadius: 3,
          p: { xs: 3, sm: 4 },
          mb: 4,
          border: 'none',
          color: '#fff',
          background: `linear-gradient(135deg, ${theme.palette.primary.dark} 0%, ${theme.palette.primary.main} 60%, ${theme.palette.secondary.dark} 135%)`,
          '&::after': {
            content: '""',
            position: 'absolute',
            inset: 0,
            background:
              'radial-gradient(50% 60% at 90% 15%, rgba(255,255,255,0.14), transparent 60%)',
            pointerEvents: 'none',
          },
        }}
      >
        <Box position="relative">
          <Typography variant="h4" fontWeight={700}>
            {greeting()}, {user.fname}
          </Typography>
          <Box display="flex" alignItems="center" gap={1.25} mt={1} flexWrap="wrap">
            {user.title && (
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.85)' }}>
                {user.title}
              </Typography>
            )}
            <Chip
              label={user.role.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())}
              size="small"
              sx={{
                height: 22,
                fontWeight: 600,
                color: '#fff',
                bgcolor: 'rgba(255,255,255,0.22)',
              }}
            />
            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.7)', ml: { sm: 0.5 } }}>
              · {todayLabel()}
            </Typography>
          </Box>
        </Box>
      </Paper>

      {/* Overview stats */}
      <Typography variant="subtitle1" fontWeight={600} mb={1.5} color="text.secondary">
        Overview
      </Typography>
      <Grid container spacing={2} mb={4}>
        {isManagerUp && (
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <StatCard
              icon={<ApartmentIcon />}
              label="Associations"
              value={assocCount ?? '—'}
              color="primary"
              to="/associations"
            />
          </Grid>
        )}
        {isAdmin && (
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <StatCard
              icon={<PeopleIcon />}
              label="Users"
              value={userCount ?? '—'}
              color="secondary"
              to="/users"
            />
          </Grid>
        )}
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <StatCard
            icon={<WorkHistoryIcon />}
            label="Active jobs"
            value={inFlightCount}
            color="warning"
            to="/jobs"
          />
        </Grid>
      </Grid>

      {/* Recent jobs */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
        <Typography variant="subtitle1" fontWeight={600} color="text.secondary">
          Recent jobs
        </Typography>
        <Button component={Link} to="/jobs" size="small">
          View all
        </Button>
      </Box>
      <Card variant="outlined" sx={{ mb: 4, borderRadius: 2.5 }}>
        {recentJobs === null ? (
          <RecentJobsSkeleton />
        ) : recentJobs.length === 0 ? (
          <Box textAlign="center" py={5} px={2}>
            <InboxOutlinedIcon sx={{ fontSize: 40, color: 'text.disabled', mb: 1 }} />
            <Typography color="text.secondary" variant="body2">
              No jobs yet. Generate a letter or budget to get started.
            </Typography>
          </Box>
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

      {/* Quick actions */}
      <Typography variant="subtitle1" fontWeight={600} mb={1.5} color="text.secondary">
        Tools
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <QuickLink
            icon={<DescriptionIcon />}
            label="Letter generator"
            description="Generate correspondence letters"
            to="/letters"
            color="primary"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <QuickLink
            icon={<AccountBalanceIcon />}
            label="Budget generator"
            description="Draft an HOA operating budget from financial reports"
            to="/ai/budget"
            color="secondary"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <QuickLink
            icon={<TableChartIcon />}
            label="Excel tools"
            description="Process and export spreadsheet data"
            to="/excel"
            color="warning"
          />
        </Grid>
      </Grid>
    </Box>
  )
}
