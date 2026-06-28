import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import DownloadIcon from '@mui/icons-material/Download'
import apiClient from '../../api/client'
import { useJobs } from '../../context/JobsContext'
import { downloadFromUrl } from '../../utils/download'
import type { JobDetail } from '../../types'

export default function JobStatusBanner({
  jobId,
  onDismiss,
}: {
  jobId: string | null
  onDismiss: () => void
}) {
  const { jobs } = useJobs()
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  if (!jobId) return null
  const job = jobs[jobId]
  if (!job) return null

  const handleDownload = async () => {
    setDownloading(true)
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
      setDownloadError('Download failed — try again from My Jobs.')
    } finally {
      setDownloading(false)
    }
  }

  if (job.status === 'pending' || job.status === 'processing') {
    return (
      <Alert
        severity="info"
        icon={<CircularProgress size={18} color="inherit" />}
        onClose={onDismiss}
        sx={{ mt: 2 }}
      >
        {job.current_step ?? 'Processing your document…'}
      </Alert>
    )
  }

  if (job.status === 'complete') {
    return (
      <Alert severity="success" onClose={onDismiss} sx={{ mt: 2 }}>
        <Box display="flex" alignItems="center" gap={2} flexWrap="wrap">
          <span>{downloadError ?? 'Your document is ready.'}</span>
          <Button
            size="small"
            color="inherit"
            startIcon={
              downloading ? (
                <CircularProgress size={14} color="inherit" />
              ) : (
                <DownloadIcon fontSize="small" />
              )
            }
            onClick={handleDownload}
            disabled={downloading}
          >
            {downloading ? 'Downloading…' : 'Download'}
          </Button>
        </Box>
      </Alert>
    )
  }

  if (job.status === 'failed') {
    return (
      <Alert severity="error" onClose={onDismiss} sx={{ mt: 2 }}>
        Generation failed — check My Jobs for details.
      </Alert>
    )
  }

  return null
}
