import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import FormControl from '@mui/material/FormControl'
import IconButton from '@mui/material/IconButton'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Select from '@mui/material/Select'
import Skeleton from '@mui/material/Skeleton'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import DownloadIcon from '@mui/icons-material/Download'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import { DataGrid } from '@mui/x-data-grid'
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import apiClient from '../api/client'
import { useAuth } from '../context/AuthContext'
import ErrorAlert from '../components/layout/ErrorAlert'
import LetterStatusChip from '../components/letters/LetterStatusChip'
import LetterDetailDialog from '../components/letters/LetterDetailDialog'
import { useLetterJobs } from '../context/LetterJobsContext'
import { downloadFromUrl } from '../utils/download'
import { formatDateTime } from '../utils/formatDate'
import type { LetterJob, LetterJobStatus } from '../types'

const ALL_CREATORS = 'all'

interface RowActionProps {
  job: LetterJob
  downloadingId: string | null
  onDownload: (job: LetterJob) => void
}

function DownloadButton({ job, downloadingId, onDownload }: RowActionProps) {
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

interface LetterRowProps extends RowActionProps {
  isLast: boolean
  showCreator: boolean
  onDetails: (id: string) => void
}

// Mobile list item — mirrors the responsive list used by Users/Templates pages.
function LetterRow({
  job,
  isLast,
  showCreator,
  downloadingId,
  onDownload,
  onDetails,
}: LetterRowProps) {
  return (
    <>
      <Box sx={{ p: 2 }}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={1}>
          <Box minWidth={0}>
            <Typography variant="subtitle2" noWrap>
              {job.template_name}
            </Typography>
            <Typography variant="body2" color="text.secondary" noWrap>
              {job.association_name}
            </Typography>
            {showCreator && (
              <Typography variant="caption" color="text.secondary">
                {job.created_by_name}
              </Typography>
            )}
            <Box mt={0.5}>
              <LetterStatusChip status={job.status} />
            </Box>
            <Typography variant="caption" color="text.secondary" display="block" mt={0.5}>
              {formatDateTime(job.created_at)}
            </Typography>
          </Box>
          <Box display="flex" flexDirection="column" alignItems="flex-end" gap={1}>
            <Tooltip title="View details">
              <IconButton size="small" onClick={() => onDetails(job.id)}>
                <InfoOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <DownloadButton job={job} downloadingId={downloadingId} onDownload={onDownload} />
          </Box>
        </Box>
      </Box>
      {!isLast && <Divider />}
    </>
  )
}

function GeneratedLettersSkeleton() {
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
            <Skeleton variant="rounded" width={80} height={24} />
            <Skeleton variant="rounded" width={96} height={32} />
          </Box>
        </Box>
      ))}
    </Paper>
  )
}

export default function GeneratedLettersPage() {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const { user } = useAuth()
  const isSuperAdmin = user?.role === 'super_admin'
  const [letters, setLetters] = useState<LetterJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [detailJobId, setDetailJobId] = useState<string | null>(null)
  const [creatorFilter, setCreatorFilter] = useState<string>(ALL_CREATORS)
  const { jobs, inFlightCount } = useLetterJobs()

  const fetchHistory = useCallback(async () => {
    try {
      const { data } = await apiClient.get<LetterJob[]>('/api/letters/history')
      setLetters(data)
    } catch {
      setError('Failed to load generated letters.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  // Refetch when the set of in-flight tracked jobs changes — a job finishing
  // brings a fresh status + download URL, and a newly-queued one a new row.
  const prevInFlight = useRef(inFlightCount)
  useEffect(() => {
    if (inFlightCount !== prevInFlight.current) {
      prevInFlight.current = inFlightCount
      fetchHistory()
    }
  }, [inFlightCount, fetchHistory])

  // Presigned URLs are minted on demand to keep the history list cheap — fetch
  // a fresh one when the user actually clicks Download.
  const handleDownload = useCallback(async (job: LetterJob) => {
    setDownloadingId(job.id)
    try {
      const { data } = await apiClient.get<LetterJobStatus>(`/api/letters/${job.id}`)
      if (!data.download_url) throw new Error('No download URL')
      await downloadFromUrl(data.download_url, `${job.template_name || 'letter'}.docx`)
    } catch {
      setError('Failed to download file.')
    } finally {
      setDownloadingId(null)
    }
  }, [])

  // Distinct creators for the super-admin filter, derived from the loaded jobs.
  const creators = useMemo(() => {
    const byId = new Map<string, string>()
    for (const job of letters) byId.set(job.created_by, job.created_by_name)
    return [...byId.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [letters])

  // Merge live polling status/URL into each row and apply the creator filter.
  const rows = useMemo(
    () =>
      letters
        .filter((job) => creatorFilter === ALL_CREATORS || job.created_by === creatorFilter)
        .map((job) => {
          const live = jobs[job.id]
          return { ...job, status: live?.status ?? job.status }
        }),
    [letters, jobs, creatorFilter],
  )

  const columns = useMemo<GridColDef<LetterJob>[]>(() => {
    const cols: GridColDef<LetterJob>[] = [
      { field: 'template_name', headerName: 'Template', flex: 1, minWidth: 160 },
      { field: 'association_name', headerName: 'Association', flex: 1, minWidth: 160 },
    ]

    if (isSuperAdmin) {
      cols.push({
        field: 'created_by_name',
        headerName: 'Created by',
        flex: 0.8,
        minWidth: 140,
      })
    }

    cols.push(
      {
        field: 'status',
        headerName: 'Status',
        width: 130,
        renderCell: (params: GridRenderCellParams<LetterJob>) => (
          <LetterStatusChip status={params.row.status} />
        ),
      },
      {
        field: 'created_at',
        headerName: 'Created',
        width: 180,
        renderCell: (params: GridRenderCellParams<LetterJob>) =>
          formatDateTime(params.row.created_at),
      },
      {
        field: 'details',
        headerName: 'Details',
        width: 90,
        sortable: false,
        filterable: false,
        renderCell: (params: GridRenderCellParams<LetterJob>) => (
          <Tooltip title="View details">
            <IconButton size="small" onClick={() => setDetailJobId(params.row.id)}>
              <InfoOutlinedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ),
      },
      {
        field: 'download',
        headerName: 'Download',
        width: 140,
        sortable: false,
        filterable: false,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params: GridRenderCellParams<LetterJob>) => (
          <DownloadButton
            job={params.row}
            downloadingId={downloadingId}
            onDownload={handleDownload}
          />
        ),
      },
    )

    return cols
  }, [isSuperAdmin, downloadingId, handleDownload])

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2} gap={2}>
        <Typography variant="h5">Generated letters</Typography>
        {isSuperAdmin && creators.length > 0 && (
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel id="creator-filter-label">Created by</InputLabel>
            <Select
              labelId="creator-filter-label"
              label="Created by"
              value={creatorFilter}
              onChange={(e) => setCreatorFilter(e.target.value)}
            >
              <MenuItem value={ALL_CREATORS}>All users</MenuItem>
              {creators.map(([id, name]) => (
                <MenuItem key={id} value={id}>
                  {name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </Box>

      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

      {loading ? (
        <GeneratedLettersSkeleton />
      ) : rows.length === 0 ? (
        <Typography color="text.secondary" textAlign="center" py={6}>
          No letters generated yet.
        </Typography>
      ) : isMobile ? (
        <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
          {rows.map((job, i) => (
            <LetterRow
              key={job.id}
              job={job}
              isLast={i === rows.length - 1}
              showCreator={isSuperAdmin}
              downloadingId={downloadingId}
              onDownload={handleDownload}
              onDetails={setDetailJobId}
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
    </Box>
  )
}
