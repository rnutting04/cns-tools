import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Skeleton from '@mui/material/Skeleton'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import DownloadIcon from '@mui/icons-material/Download'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import { DataGrid } from '@mui/x-data-grid'
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import { useNavigate } from 'react-router-dom'
import apiClient from '../api/client'
import { useJobs } from '../context/JobsContext'
import ErrorAlert from '../components/layout/ErrorAlert'
import JobStatusChip from '../components/common/JobStatusChip'
import LetterDetailDialog from '../components/letters/LetterDetailDialog'
import BudgetDetailDialog from '../components/budget/BudgetDetailDialog'
import { downloadFromUrl } from '../utils/download'
import { formatDateTime } from '../utils/formatDate'
import { jobLink } from './accounting/jobTools'
import {
  byNewest,
  fromJob,
  fromRun,
  type JobKind as Kind,
  type JobRow as Row,
} from '../components/common/jobRows'
import TypeChip from '../components/common/JobTypeChip'
import type { AccountingJobSummary, Job, JobDetail } from '../types'

type TabValue = 'all' | Kind

const TAB_NOUN: Record<Kind, string> = {
  letter: 'letter',
  budget: 'budget',
  accounting: 'accounting',
}

function JobsSkeleton() {
  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
      {[0, 1, 2, 3].map((i) => (
        <Box key={i}>
          {i > 0 && <Divider />}
          <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', gap: 2 }}>
            <Box flexGrow={1}>
              <Skeleton variant="text" width="40%" height={22} />
              <Skeleton variant="text" width="55%" height={18} sx={{ mt: 0.5 }} />
            </Box>
            <Skeleton variant="rounded" width={60} height={24} />
            <Skeleton variant="rounded" width={80} height={24} />
            <Skeleton variant="rounded" width={96} height={32} />
          </Box>
        </Box>
      ))}
    </Paper>
  )
}

interface ActionProps {
  row: Row
  downloadingId: string | null
  onDownload: (job: Job) => void
  onOpen: (run: AccountingJobSummary) => void
}

/** Download a letter / budget, or open an accounting run's results. */
function RowAction({ row, downloadingId, onDownload, onOpen }: ActionProps) {
  if (row.run) {
    const run = row.run
    return (
      <Button
        variant="outlined"
        size="small"
        startIcon={<OpenInNewIcon />}
        disabled={run.status === 'pending'}
        onClick={() => onOpen(run)}
      >
        {run.status === 'processing' ? 'Follow' : 'Results'}
      </Button>
    )
  }
  const job = row.job as Job
  return (
    <Button
      variant="outlined"
      size="small"
      startIcon={
        downloadingId === job.id ? <CircularProgress size={14} color="inherit" /> : <DownloadIcon />
      }
      disabled={job.status !== 'complete' || downloadingId === job.id}
      onClick={() => onDownload(job)}
    >
      Download
    </Button>
  )
}

interface MobileRowProps extends ActionProps {
  isLast: boolean
  onDetails: (job: Job) => void
}

function MobileRow({ row, isLast, onDetails, ...action }: MobileRowProps) {
  return (
    <>
      <Box sx={{ p: 2 }}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={1}>
          <Box minWidth={0}>
            <Box display="flex" alignItems="center" gap={1} mb={0.5}>
              <TypeChip row={row} />
            </Box>
            <Typography variant="subtitle2" noWrap>
              {row.title}
            </Typography>
            <Typography variant="body2" color="text.secondary" noWrap>
              {row.detail}
            </Typography>
            <Box mt={0.5}>
              <JobStatusChip status={row.status} />
            </Box>
            <Typography variant="caption" color="text.secondary" display="block" mt={0.5}>
              {formatDateTime(row.created_at)}
            </Typography>
          </Box>
          <Box display="flex" flexDirection="column" alignItems="flex-end" gap={1}>
            {row.job && (
              <Tooltip title="View details">
                <IconButton size="small" onClick={() => onDetails(row.job as Job)}>
                  <InfoOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            <RowAction row={row} {...action} />
          </Box>
        </Box>
      </Box>
      {!isLast && <Divider />}
    </>
  )
}

export default function JobsPage() {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const navigate = useNavigate()
  const [allJobs, setAllJobs] = useState<Job[]>([])
  const [runs, setRuns] = useState<AccountingJobSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [detailJobId, setDetailJobId] = useState<string | null>(null)
  const [detailBudgetJobId, setDetailBudgetJobId] = useState<string | null>(null)
  const [tab, setTab] = useState<TabValue>('all')
  const { jobs: liveJobs, accountingJobs: liveRuns, inFlightCount } = useJobs()

  const fetchJobs = useCallback(async () => {
    const [jobs, accounting] = await Promise.allSettled([
      apiClient.get<Job[]>('/api/jobs'),
      apiClient.get<AccountingJobSummary[]>('/api/accounting/jobs'),
    ])
    if (jobs.status === 'fulfilled') setAllJobs(jobs.value.data)
    if (accounting.status === 'fulfilled') setRuns(accounting.value.data)
    if (jobs.status === 'rejected' || accounting.status === 'rejected')
      setError('Failed to load jobs.')
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchJobs()
  }, [fetchJobs])

  // Re-fetch whenever a tracked job completes or a new one is queued.
  const prevInFlight = useRef(inFlightCount)
  useEffect(() => {
    if (inFlightCount !== prevInFlight.current) {
      prevInFlight.current = inFlightCount
      fetchJobs()
    }
  }, [inFlightCount, fetchJobs])

  const handleDownload = useCallback(async (job: Job) => {
    setDownloadingId(job.id)
    try {
      const { data } = await apiClient.get<JobDetail>(`/api/jobs/${job.id}`)
      if (!data.download_url) throw new Error('No download URL')
      const ext = job.job_type === 'budget' ? 'xlsx' : 'docx'
      await downloadFromUrl(data.download_url, `${job.title}.${ext}`)
    } catch {
      setError('Failed to download file.')
    } finally {
      setDownloadingId(null)
    }
  }, [])

  const openRun = useCallback((run: AccountingJobSummary) => navigate(jobLink(run)), [navigate])
  const openDetails = useCallback((job: Job) => {
    if (job.job_type === 'letter') setDetailJobId(job.id)
    else setDetailBudgetJobId(job.id)
  }, [])

  // Merge live polling status into each row, newest first, then apply the tab filter.
  const rows = useMemo(() => {
    const merged = [
      ...allJobs.map((job) => {
        const live = liveJobs[job.id]
        return fromJob(live ? { ...job, status: live.status } : job)
      }),
      ...runs.map((run) => fromRun({ ...run, ...liveRuns[run.id] })),
    ].sort(byNewest)
    return tab === 'all' ? merged : merged.filter((r) => r.kind === tab)
  }, [allJobs, liveJobs, runs, liveRuns, tab])

  const columns = useMemo<GridColDef<Row>[]>(
    () => [
      {
        field: 'kind',
        headerName: 'Type',
        width: 130,
        renderCell: (p: GridRenderCellParams<Row>) => <TypeChip row={p.row} />,
      },
      { field: 'title', headerName: 'Job', flex: 1, minWidth: 160 },
      { field: 'detail', headerName: 'Association / progress', flex: 1, minWidth: 200 },
      {
        field: 'status',
        headerName: 'Status',
        width: 130,
        renderCell: (p: GridRenderCellParams<Row>) => <JobStatusChip status={p.row.status} />,
      },
      {
        field: 'created_at',
        headerName: 'Created',
        width: 180,
        renderCell: (p: GridRenderCellParams<Row>) => formatDateTime(p.row.created_at),
      },
      {
        field: 'details',
        headerName: '',
        width: 56,
        sortable: false,
        filterable: false,
        renderCell: (p: GridRenderCellParams<Row>) =>
          p.row.job ? (
            <Tooltip title="View details">
              <IconButton size="small" onClick={() => openDetails(p.row.job as Job)}>
                <InfoOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          ) : null,
      },
      {
        field: 'action',
        headerName: '',
        width: 130,
        sortable: false,
        filterable: false,
        align: 'right',
        headerAlign: 'right',
        renderCell: (p: GridRenderCellParams<Row>) => (
          <RowAction
            row={p.row}
            downloadingId={downloadingId}
            onDownload={handleDownload}
            onOpen={openRun}
          />
        ),
      },
    ],
    [downloadingId, handleDownload, openRun, openDetails],
  )

  return (
    <Box>
      <Typography variant="h5" mb={2}>
        My Jobs
      </Typography>

      <Tabs
        value={tab}
        onChange={(_, v: TabValue) => setTab(v)}
        variant="scrollable"
        allowScrollButtonsMobile
        sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab label="All" value="all" />
        <Tab label="Letters" value="letter" />
        <Tab label="Budgets" value="budget" />
        <Tab label="Accounting" value="accounting" />
      </Tabs>

      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

      {loading ? (
        <JobsSkeleton />
      ) : rows.length === 0 ? (
        <Paper variant="outlined" sx={{ borderRadius: 2, px: 2, py: 6, textAlign: 'center' }}>
          <Typography color="text.secondary">
            {tab === 'all' ? 'No jobs yet.' : `No ${TAB_NOUN[tab]} jobs yet.`}
          </Typography>
        </Paper>
      ) : isMobile ? (
        <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
          {rows.map((row, i) => (
            <MobileRow
              key={row.id}
              row={row}
              isLast={i === rows.length - 1}
              downloadingId={downloadingId}
              onDownload={handleDownload}
              onOpen={openRun}
              onDetails={openDetails}
            />
          ))}
        </Paper>
      ) : (
        <DataGrid
          rows={rows}
          columns={columns}
          getRowId={(row) => row.id}
          autoHeight
          pageSizeOptions={[25, 50, 100]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          disableRowSelectionOnClick
          sx={{ bgcolor: 'background.paper', borderRadius: 2 }}
        />
      )}

      <LetterDetailDialog jobId={detailJobId} onClose={() => setDetailJobId(null)} />
      <BudgetDetailDialog
        jobId={detailBudgetJobId}
        onClose={() => setDetailBudgetJobId(null)}
        onRetried={fetchJobs}
      />
    </Box>
  )
}
