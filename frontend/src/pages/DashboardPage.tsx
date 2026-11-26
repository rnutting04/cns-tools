import { Fragment, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import ButtonBase from '@mui/material/ButtonBase'
import Divider from '@mui/material/Divider'
import Grid from '@mui/material/Grid'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import Paper from '@mui/material/Paper'
import Skeleton from '@mui/material/Skeleton'
import Typography from '@mui/material/Typography'
import { alpha } from '@mui/material/styles'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import CalculateIcon from '@mui/icons-material/Calculate'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import DescriptionIcon from '@mui/icons-material/Description'
import FolderIcon from '@mui/icons-material/Folder'
import InboxOutlinedIcon from '@mui/icons-material/InboxOutlined'
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import ReminderDialog from '../components/reminders/ReminderDialog'
import { etDateTime } from '../components/reminders/format'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useJobs } from '../context/JobsContext'
import { hasRole } from '../utils/auth'
import {
  REFERENCE_STALE_TIME,
  fetchAccountingJobs,
  fetchAssociations,
  fetchJobs,
  fetchUsers,
  queryKeys,
} from '../api/queries'
import JobStatusChip from '../components/common/JobStatusChip'
import { byNewest, fromJob, fromRun } from '../components/common/jobRows'
import JobTypeChip from '../components/common/JobTypeChip'
import type { JobRow } from '../components/common/jobRows'
import { ACCOUNTING_TOOLS } from './accounting/tools'
import { jobLink } from './accounting/jobTools'
import { formatDateTime } from '../utils/formatDate'

const RECENT = 6

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
    year: 'numeric',
  })
}

const roleLabel = (role: string) => role.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

/** Small uppercase heading used for panel sections. */
function Overline({ children }: { children: ReactNode }) {
  return (
    <Typography
      variant="overline"
      color="text.secondary"
      sx={{ fontWeight: 600, letterSpacing: '0.08em', lineHeight: 1.6 }}
    >
      {children}
    </Typography>
  )
}

function PanelHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <Box
      sx={{
        px: 2.5,
        py: 1.5,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: 1,
        borderColor: 'divider',
      }}
    >
      <Typography variant="subtitle1" fontWeight={600}>
        {title}
      </Typography>
      {action}
    </Box>
  )
}

interface Metric {
  label: string
  value: number | null
  caption: string
  to: string
}

/** One figure in the overview strip. */
function MetricCell({ m }: { m: Metric }) {
  return (
    <ButtonBase
      component={Link}
      to={m.to}
      sx={(theme) => ({
        display: 'block',
        textAlign: 'left',
        width: '100%',
        height: '100%',
        px: 2.5,
        py: 2,
        transition: theme.transitions.create('background-color'),
        '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.04) },
        '&:focus-visible': { outline: `2px solid ${theme.palette.primary.main}` },
      })}
    >
      <Overline>{m.label}</Overline>
      <Typography
        sx={{
          fontSize: 30,
          fontWeight: 700,
          lineHeight: 1.15,
          fontVariantNumeric: 'tabular-nums',
          color: 'text.primary',
        }}
      >
        {m.value ?? <Skeleton width={56} />}
      </Typography>
      <Typography variant="body2" color="text.secondary" noWrap>
        {m.caption}
      </Typography>
    </ButtonBase>
  )
}

interface ToolLink {
  label: string
  description: string
  to: string
  icon: ReactNode
}

function ToolItem({ t }: { t: ToolLink }) {
  return (
    <ListItemButton
      component={Link}
      to={t.to}
      sx={{ px: 2.5, py: 1, gap: 1.5, alignItems: 'center' }}
    >
      <Box
        sx={(theme) => ({
          width: 32,
          height: 32,
          borderRadius: 1,
          flexShrink: 0,
          display: 'grid',
          placeItems: 'center',
          color: 'primary.main',
          bgcolor: alpha(theme.palette.primary.main, 0.08),
          '& svg': { fontSize: 18 },
        })}
      >
        {t.icon}
      </Box>
      <Box minWidth={0} flex={1}>
        <Typography variant="body2" fontWeight={600} noWrap>
          {t.label}
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" noWrap>
          {t.description}
        </Typography>
      </Box>
      <ChevronRightIcon fontSize="small" sx={{ color: 'text.disabled' }} />
    </ListItemButton>
  )
}

function ActivityRow({ row, onOpen }: { row: JobRow; onOpen: (row: JobRow) => void }) {
  return (
    <ListItemButton
      onClick={() => onOpen(row)}
      sx={{ px: 2.5, py: 1.25, gap: 2, alignItems: 'center' }}
    >
      <Box sx={{ width: 112, flexShrink: 0, display: { xs: 'none', sm: 'block' } }}>
        <JobTypeChip row={row} />
      </Box>
      <Box minWidth={0} flex={1}>
        <Typography variant="body2" fontWeight={500} noWrap>
          {row.title || 'Untitled'}
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" noWrap>
          {row.detail}
        </Typography>
      </Box>
      <JobStatusChip status={row.status} />
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ width: 150, flexShrink: 0, textAlign: 'right', display: { xs: 'none', md: 'block' } }}
      >
        {formatDateTime(row.created_at)}
      </Typography>
    </ListItemButton>
  )
}

function ActivitySkeleton() {
  return (
    <>
      {[0, 1, 2, 3].map((i) => (
        <Box key={i} sx={{ px: 2.5, py: 1.5, display: 'flex', alignItems: 'center', gap: 2 }}>
          <Skeleton variant="rounded" width={80} height={22} />
          <Box flex={1}>
            <Skeleton variant="text" width="45%" />
            <Skeleton variant="text" width="30%" />
          </Box>
          <Skeleton variant="rounded" width={80} height={22} />
        </Box>
      ))}
    </>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { jobs: liveJobs, accountingJobs: liveRuns, inFlightCount } = useJobs()

  const isManagerUp = user ? hasRole(user, ['manager', 'admin', 'super_admin']) : false
  const isAdmin = user ? hasRole(user, ['admin', 'super_admin']) : false
  const queryClient = useQueryClient()
  const [reminderOpen, setReminderOpen] = useState(false)

  // Shared query keys, so navigating between the dashboard and the pages that
  // use these lists reuses one cache entry instead of refetching.
  const associationsQuery = useQuery({
    queryKey: queryKeys.associations,
    queryFn: fetchAssociations,
    enabled: isManagerUp,
    staleTime: REFERENCE_STALE_TIME,
  })
  const usersQuery = useQuery({
    queryKey: queryKeys.users,
    queryFn: fetchUsers,
    enabled: isAdmin,
    staleTime: REFERENCE_STALE_TIME,
  })
  const jobsQuery = useQuery({ queryKey: queryKeys.jobs, queryFn: fetchJobs })
  const runsQuery = useQuery({ queryKey: queryKeys.accountingJobs, queryFn: fetchAccountingJobs })

  const recent = useMemo(
    () =>
      [
        ...(jobsQuery.data ?? []).map((j) => {
          const live = liveJobs[j.id]
          return fromJob(live ? { ...j, status: live.status } : j)
        }),
        ...(runsQuery.data ?? []).map((r) => fromRun({ ...r, ...liveRuns[r.id] })),
      ]
        .sort(byNewest)
        .slice(0, RECENT),
    [jobsQuery.data, runsQuery.data, liveJobs, liveRuns],
  )

  if (!user) return null

  const associations = associationsQuery.data
  const activeAssociations = associations?.filter((a) => a.is_active).length ?? null
  const inactiveAssociations = associations ? associations.length - (activeAssociations ?? 0) : 0
  const users = usersQuery.data
  const activeUsers = users?.filter((u) => u.is_active).length ?? null
  const inactiveUsers = users ? users.length - (activeUsers ?? 0) : 0

  const metrics: Metric[] = [
    ...(isManagerUp
      ? [
          {
            label: 'Active associations',
            value: activeAssociations,
            caption: inactiveAssociations
              ? `${inactiveAssociations} inactive · ${associations?.length} total`
              : 'All associations active',
            to: '/associations',
          },
        ]
      : []),
    ...(isAdmin
      ? [
          {
            label: 'Active users',
            value: activeUsers,
            caption: inactiveUsers ? `${inactiveUsers} deactivated` : 'All accounts active',
            to: '/users',
          },
        ]
      : []),
    {
      label: 'Jobs in progress',
      value: inFlightCount,
      caption: inFlightCount ? 'Letters, budgets and accounting runs' : 'Nothing running',
      to: '/jobs',
    },
  ]

  const correspondence: ToolLink[] = [
    {
      label: 'Letter generator',
      description: 'Correspondence letters from templates',
      to: '/letters',
      icon: <DescriptionIcon />,
    },
    ...(isAdmin
      ? [
          {
            label: 'Template manager',
            description: 'Upload and maintain letter templates',
            to: '/templates',
            icon: <FolderIcon />,
          },
          {
            label: 'Reminders',
            description: 'Scheduled emails for mailing days and deadlines',
            to: '/reminders',
            icon: <NotificationsActiveIcon />,
          },
        ]
      : []),
  ]
  const finance: ToolLink[] = [
    ...(isAdmin
      ? [
          {
            label: 'Budget generator',
            description: 'Draft an operating budget from financials',
            to: '/ai/budget',
            icon: <AccountBalanceIcon />,
          },
        ]
      : []),
    ...ACCOUNTING_TOOLS.map((t) => ({
      label: t.title,
      description: t.input,
      to: `/accounting/${t.path}`,
      icon: t.icon,
    })),
  ]

  const openRow = (row: JobRow) => navigate(row.run ? jobLink(row.run) : '/jobs')
  const loadingActivity = jobsQuery.isLoading || runsQuery.isLoading

  return (
    <Box>
      {/* Header */}
      <Box
        display="flex"
        alignItems={{ xs: 'flex-start', sm: 'flex-end' }}
        justifyContent="space-between"
        flexDirection={{ xs: 'column', sm: 'row' }}
        gap={2}
        pb={2.5}
        mb={3}
        sx={{ borderBottom: 1, borderColor: 'divider' }}
      >
        <Box minWidth={0}>
          <Typography variant="h4" component="h1">
            {greeting()}, {user.fname}
          </Typography>
          <Typography variant="body2" color="text.secondary" mt={0.5}>
            {todayLabel()} · {user.title || roleLabel(user.role)}
          </Typography>
        </Box>
        <Box display="flex" gap={1} flexShrink={0} flexWrap="wrap">
          {isAdmin && (
            <Button
              variant="outlined"
              startIcon={<NotificationsActiveIcon />}
              onClick={() => setReminderOpen(true)}
            >
              New reminder
            </Button>
          )}
          <Button
            component={Link}
            to="/accounting"
            variant="outlined"
            startIcon={<CalculateIcon />}
          >
            Accounting tools
          </Button>
          <Button
            component={Link}
            to="/letters"
            variant="contained"
            startIcon={<DescriptionIcon />}
          >
            New letter
          </Button>
        </Box>
      </Box>

      {/* Overview */}
      <Paper variant="outlined" sx={{ borderRadius: 2, mb: 3, overflow: 'hidden' }}>
        <Box
          display="grid"
          gridTemplateColumns={{
            xs: '1fr',
            sm: `repeat(${Math.min(metrics.length, 3)}, minmax(0, 1fr))`,
          }}
          sx={{
            '& > *:not(:last-child)': {
              borderRight: { sm: 1 },
              borderBottom: { xs: 1, sm: 0 },
              borderColor: { xs: 'divider', sm: 'divider' },
            },
          }}
        >
          {metrics.map((m) => (
            <Box key={m.label}>
              <MetricCell m={m} />
            </Box>
          ))}
        </Box>
      </Paper>

      <Grid container spacing={3}>
        {/* Recent activity */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
            <PanelHeader
              title="Recent activity"
              action={
                <Button component={Link} to="/jobs" size="small" endIcon={<ChevronRightIcon />}>
                  All jobs
                </Button>
              }
            />
            {loadingActivity ? (
              <ActivitySkeleton />
            ) : recent.length === 0 ? (
              <Box textAlign="center" py={6} px={2}>
                <InboxOutlinedIcon sx={{ fontSize: 36, color: 'text.disabled', mb: 1 }} />
                <Typography color="text.secondary" variant="body2">
                  No activity yet. Letters, budgets and accounting runs you start will appear here.
                </Typography>
              </Box>
            ) : (
              <List disablePadding>
                {recent.map((row, i) => (
                  <Fragment key={row.id}>
                    {i > 0 && <Divider />}
                    <ActivityRow row={row} onOpen={openRow} />
                  </Fragment>
                ))}
              </List>
            )}
          </Paper>
        </Grid>

        {/* Tools */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
            <PanelHeader title="Tools" />
            <Box px={2.5} pt={1.5}>
              <Overline>Correspondence</Overline>
            </Box>
            <List disablePadding>
              {correspondence.map((t) => (
                <ToolItem key={t.to} t={t} />
              ))}
            </List>
            <Divider sx={{ mt: 1 }} />
            <Box px={2.5} pt={1.5}>
              <Overline>Finance & accounting</Overline>
            </Box>
            <List disablePadding sx={{ pb: 1 }}>
              {finance.map((t) => (
                <ToolItem key={t.to} t={t} />
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>

      {isAdmin && (
        <ReminderDialog
          open={reminderOpen}
          onClose={() => setReminderOpen(false)}
          onSaved={(r) => {
            setReminderOpen(false)
            void queryClient.invalidateQueries({ queryKey: queryKeys.reminders })
            toast.success(
              r.next_send_at
                ? `Reminder set. Next email ${etDateTime(r.next_send_at)}.`
                : 'Reminder saved.',
              { action: { label: 'View', onClick: () => navigate('/reminders') } },
            )
          }}
        />
      )}
    </Box>
  )
}
