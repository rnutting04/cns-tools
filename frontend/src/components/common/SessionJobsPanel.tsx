import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import DownloadIcon from '@mui/icons-material/Download'
import { Link } from 'react-router-dom'
import { keyframes } from '@mui/system'
import apiClient from '../../api/client'
import { useJobs } from '../../context/JobsContext'
import { downloadFromUrl } from '../../utils/download'
import JobStatusChip from './JobStatusChip'
import type { Job, JobDetail, JobStatus, JobType } from '../../types'

const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000
const MAX_VISIBLE = 10
const HIGHLIGHT_DURATION_MS = 2500

const rowHighlight = keyframes`
  0%   { background-color: rgba(25, 118, 210, 0.12); }
  60%  { background-color: rgba(25, 118, 210, 0.08); }
  100% { background-color: transparent; }
`

interface DisplayJob {
  id: string
  job_type: JobType
  title: string
  association_name: string
  status: JobStatus
  created_at: string
  current_step: string | null
  download_url: string | null
}

export default function SessionJobsPanel({ jobType }: { jobType: JobType }) {
  const { jobs: liveJobs, inFlightCount } = useJobs()
  const [apiJobs, setApiJobs] = useState<Job[]>([])
  const [downloading, setDownloading] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set())
  const prevInFlight = useRef(inFlightCount)
  const knownIds = useRef<Set<string>>(new Set())
  const isFirstLoad = useRef(true)

  const fetchRecentJobs = useCallback(async () => {
    try {
      const { data } = await apiClient.get<Job[]>('/api/jobs')
      const cutoff = Date.now() - TWENTY_FOUR_HOURS_MS
      const filtered = data.filter(
        (j) => j.job_type === jobType && new Date(j.created_at).getTime() > cutoff,
      )
      setApiJobs(filtered)

      if (isFirstLoad.current) {
        // Populate known IDs on first load — don't highlight existing rows.
        isFirstLoad.current = false
        knownIds.current = new Set(filtered.map((j) => j.id))
      } else {
        const newIds = filtered.filter((j) => !knownIds.current.has(j.id)).map((j) => j.id)
        filtered.forEach((j) => knownIds.current.add(j.id))

        if (newIds.length > 0) {
          setHighlightedIds((prev) => new Set([...prev, ...newIds]))
          setTimeout(() => {
            setHighlightedIds((prev) => {
              const next = new Set(prev)
              newIds.forEach((id) => next.delete(id))
              return next
            })
          }, HIGHLIGHT_DURATION_MS)
        }
      }
    } catch {
      // fail silently — don't block the main form
    }
  }, [jobType])

  useEffect(() => {
    fetchRecentJobs()
  }, [fetchRecentJobs])

  // Re-fetch when a job is submitted (inFlightCount increases) or completes (decreases).
  useEffect(() => {
    if (inFlightCount !== prevInFlight.current) {
      prevInFlight.current = inFlightCount
      fetchRecentJobs()
    }
  }, [inFlightCount, fetchRecentJobs])

  // Merge live polling status (current_step, download_url) into API rows.
  const rows = useMemo((): DisplayJob[] => {
    return apiJobs.map((job) => {
      const live = liveJobs[job.id]
      return {
        id: job.id,
        job_type: job.job_type,
        title: job.title,
        association_name: job.association_name,
        status: live ? live.status : job.status,
        created_at: job.created_at,
        current_step: live?.current_step ?? null,
        download_url: live?.download_url ?? null,
      }
    })
  }, [apiJobs, liveJobs])

  if (rows.length === 0) return null

  const visible = rows.slice(0, MAX_VISIBLE)
  const overflow = rows.length - MAX_VISIBLE

  const handleDownload = async (job: DisplayJob) => {
    setDownloading(job.id)
    setDownloadError(null)
    try {
      let url = job.download_url
      if (!url) {
        const { data } = await apiClient.get<JobDetail>(`/api/jobs/${job.id}`)
        url = data.download_url
      }
      if (!url) throw new Error('No download URL')
      const ext = job.job_type === 'budget' ? 'xlsx' : 'docx'
      const filename = job.title ? `${job.title}.${ext}` : `download.${ext}`
      await downloadFromUrl(url, filename)
    } catch {
      setDownloadError('Download failed — try from My Jobs.')
    } finally {
      setDownloading(null)
    }
  }

  const heading = jobType === 'letter' ? 'Recent letters' : 'Recent budgets'

  return (
    <Box mt={3}>
      <Typography variant="subtitle2" color="text.secondary" mb={1}>
        {heading} — last 24 hours
      </Typography>

      {downloadError && (
        <Typography variant="caption" color="error" display="block" mb={1}>
          {downloadError}
        </Typography>
      )}

      <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
        {visible.map((job, i) => {
          const inFlight = job.status === 'pending' || job.status === 'processing'
          const isLast = i === visible.length - 1
          const isHighlighted = highlightedIds.has(job.id)

          return (
            <Box key={job.id}>
              <Box
                sx={{
                  px: 2,
                  py: 1.5,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.5,
                  animation: isHighlighted
                    ? `${rowHighlight} ${HIGHLIGHT_DURATION_MS}ms ease-out forwards`
                    : undefined,
                }}
              >
                <Box flexShrink={0}>
                  <JobStatusChip status={job.status} />
                </Box>

                <Box flex={1} minWidth={0}>
                  <Typography variant="body2" noWrap>
                    {job.title || (inFlight ? 'Processing…' : 'Job')}
                  </Typography>
                  {job.association_name && (
                    <Typography variant="caption" color="text.secondary" noWrap display="block">
                      {job.association_name}
                    </Typography>
                  )}
                  {inFlight && job.current_step && (
                    <Typography variant="caption" color="text.secondary" noWrap display="block">
                      {job.current_step}
                    </Typography>
                  )}
                </Box>

                {job.status === 'complete' && (
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={
                      downloading === job.id ? (
                        <CircularProgress size={12} color="inherit" />
                      ) : (
                        <DownloadIcon fontSize="small" />
                      )
                    }
                    disabled={downloading === job.id}
                    onClick={() => handleDownload(job)}
                    sx={{ flexShrink: 0 }}
                  >
                    {downloading === job.id ? 'Downloading…' : 'Download'}
                  </Button>
                )}
              </Box>
              {!isLast && <Divider />}
            </Box>
          )
        })}
      </Paper>

      {overflow > 0 && (
        <Box mt={1} display="flex" justifyContent="flex-end">
          <Typography
            variant="caption"
            color="text.secondary"
            component={Link}
            to="/jobs"
            sx={{ textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
          >
            +{overflow} more — view all in My Jobs
          </Typography>
        </Box>
      )}
    </Box>
  )
}
