import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
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
import { DataGrid } from '@mui/x-data-grid'
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import apiClient from '../api/client'
import { useJobs } from '../context/JobsContext'
import ErrorAlert from '../components/layout/ErrorAlert'
import JobStatusChip from '../components/common/JobStatusChip'
import LetterDetailDialog from '../components/letters/LetterDetailDialog'
import BudgetDetailDialog from '../components/budget/BudgetDetailDialog'
import { downloadFromUrl } from '../utils/download'
import { formatDateTime } from '../utils/formatDate'
import type { Job, JobDetail, JobType } from '../types'

type TabValue = 'all' | JobType

const TYPE_LABEL: Record<JobType, string> = { letter: 'Letter', budget: 'Budget' }
const TYPE_COLOR: Record<JobType, 'primary' | 'secondary'> = {
  letter: 'primary',
  budget: 'secondary',
}

function TypeChip({ jobType }: { jobType: JobType }) {
  return (
    <Chip label={TYPE_LABEL[jobType]} size="small" color={TYPE_COLOR[jobType]} variant="outlined" />
  )
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

interface MobileRowProps {
  job: Job
  isLast: boolean
  downloadingId: string | null
  onDownload: (job: Job) => void
  onDetails: (id: string) => void
  onBudgetDetails: (id: string) => void
}

function MobileRow({
  job,
  isLast,
  downloadingId,
  onDownload,
  onDetails,
  onBudgetDetails,
}: MobileRowProps) {
  return (
    <>
      <Box sx={{ p: 2 }}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={1}>
          <Box minWidth={0}>
            <Box display="flex" alignItems="center" gap={1} mb={0.5}>
              <TypeChip jobType={job.job_type} />
            </Box>
            <Typography variant="subtitle2" noWrap>
              {job.title}
            </Typography>
            <Typography variant="body2" color="text.secondary" noWrap>
              {job.association_name}
            </Typography>
            <Box mt={0.5}>
              <JobStatusChip status={job.status} />
            </Box>
            <Typography variant="caption" color="text.secondary" display="block" mt={0.5}>
              {formatDateTime(job.created_at)}
            </Typography>
          </Box>
          <Box display="flex" flexDirection="column" alignItems="flex-end" gap={1}>
            <Tooltip title="View details">
              <IconButton
                size="small"
                onClick={() =>
                  job.job_type === 'letter' ? onDetails(job.id) : onBudgetDetails(job.id)
                }
              >
                <InfoOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Button
              variant="outlined"
              size="small"
              startIcon={
                downloadingId === job.id ? (
                  <CircularProgress size={14} color="inherit" />
                ) : (
                  <DownloadIcon />
                )
              }
              disabled={job.status !== 'complete' || downloadingId === job.id}
              onClick={() => onDownload(job)}
            >
              Download
            </Button>
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
  const [allJobs, setAllJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [detailJobId, setDetailJobId] = useState<string | null>(null)
  const [detailBudgetJobId, setDetailBudgetJobId] = useState<string | null>(null)
  const [tab, setTab] = useState<TabValue>('all')
  const { jobs: liveJobs, inFlightCount } = useJobs()

  const fetchJobs = useCallback(async () => {
    try {
      const { data } = await apiClient.get<Job[]>('/api/jobs')
      setAllJobs(data)
    } catch {
      setError('Failed to load jobs.')
    } finally {
      setLoading(false)
    }
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

  // Merge live polling status into each row, then apply tab filter.
  const rows = useMemo(() => {
    const filtered = tab === 'all' ? allJobs : allJobs.filter((j) => j.job_type === tab)
    return filtered.map((job) => {
      const live = liveJobs[job.id]
      return live ? { ...job, status: live.status } : job
    })
  }, [allJobs, liveJobs, tab])

  const columns = useMemo<GridColDef<Job>[]>(
    () => [
      {
        field: 'job_type',
        headerName: 'Type',
        width: 100,
        renderCell: (p: GridRenderCellParams<Job>) => <TypeChip jobType={p.row.job_type} />,
      },
      { field: 'title', headerName: 'Job', flex: 1, minWidth: 160 },
      { field: 'association_name', headerName: 'Association', flex: 1, minWidth: 160 },
      {
        field: 'status',
        headerName: 'Status',
        width: 130,
        renderCell: (p: GridRenderCellParams<Job>) => <JobStatusChip status={p.row.status} />,
      },
      {
        field: 'created_at',
        headerName: 'Created',
        width: 180,
        renderCell: (p: GridRenderCellParams<Job>) => formatDateTime(p.row.created_at),
      },
      {
        field: 'details',
        headerName: '',
        width: 56,
        sortable: false,
        filterable: false,
        renderCell: (p: GridRenderCellParams<Job>) => (
          <Tooltip title="View details">
            <IconButton
              size="small"
              onClick={() =>
                p.row.job_type === 'letter'
                  ? setDetailJobId(p.row.id)
                  : setDetailBudgetJobId(p.row.id)
              }
            >
              <InfoOutlinedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ),
      },
      {
        field: 'download',
        headerName: '',
        width: 130,
        sortable: false,
        filterable: false,
        align: 'right',
        headerAlign: 'right',
        renderCell: (p: GridRenderCellParams<Job>) => (
          <Button
            variant="outlined"
            size="small"
            startIcon={
              downloadingId === p.row.id ? (
                <CircularProgress size={14} color="inherit" />
              ) : (
                <DownloadIcon />
              )
            }
            disabled={p.row.status !== 'complete' || downloadingId === p.row.id}
            onClick={() => handleDownload(p.row)}
          >
            Download
          </Button>
        ),
      },
    ],
    [downloadingId, handleDownload],
  )

  return (
    <Box>
      <Typography variant="h5" mb={2}>
        My Jobs
      </Typography>

      <Tabs
        value={tab}
        onChange={(_, v: TabValue) => setTab(v)}
        sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab label="All" value="all" />
        <Tab label="Letters" value="letter" />
        <Tab label="Budgets" value="budget" />
      </Tabs>

      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

      {loading ? (
        <JobsSkeleton />
      ) : rows.length === 0 ? (
        <Typography color="text.secondary" textAlign="center" py={6}>
          No jobs yet.
        </Typography>
      ) : isMobile ? (
        <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
          {rows.map((job, i) => (
            <MobileRow
              key={job.id}
              job={job}
              isLast={i === rows.length - 1}
              downloadingId={downloadingId}
              onDownload={handleDownload}
              onDetails={setDetailJobId}
              onBudgetDetails={setDetailBudgetJobId}
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
