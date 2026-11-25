/**
 * Shared screen for the background accounting tools: upload a combined
 * (or single-association) PDF, pick a recent run, follow its progress, see
 * and download the per-association results.
 */
import { useState } from 'react'
import type { ReactNode } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import LinearProgress from '@mui/material/LinearProgress'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import DownloadIcon from '@mui/icons-material/Download'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import ErrorAlert from '../../components/layout/ErrorAlert'
import { isActive, useAccountingJob, useAccountingJobs } from '../../hooks/useAccountingJobs'
import type { AccountingJobResult, AccountingJobSummary, AccountingTool } from '../../types'
import { downloadCsv } from './helpers'
import { DropZone, ToolHeader } from './shared'

function when(iso: string | null): string {
  if (!iso) return ''
  // Stored as naive UTC.
  const d = new Date(iso.endsWith('Z') ? iso : `${iso}Z`)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function RunChip({
  job,
  selected,
  onClick,
}: {
  job: AccountingJobSummary
  selected: boolean
  onClick: () => void
}) {
  const icon = isActive(job) ? (
    <CircularProgress size={12} sx={{ ml: 1 }} />
  ) : job.status === 'failed' ? (
    <ErrorOutlineIcon />
  ) : (
    <CheckCircleIcon />
  )
  return (
    <Chip
      icon={icon}
      label={`${job.filename} · ${when(job.created_at)}`}
      onClick={onClick}
      color={selected ? 'primary' : job.status === 'failed' ? 'error' : 'default'}
      variant={selected ? 'filled' : 'outlined'}
      sx={{ maxWidth: 360 }}
    />
  )
}

export default function JobRunner({
  tool,
  title,
  description,
  hint,
  csvName,
  toCsv,
  children,
}: {
  tool: AccountingTool
  title: string
  description: ReactNode
  hint: string
  csvName: string
  /** header row + one row per association (or per association × bank) */
  toCsv: (results: AccountingJobResult[]) => (string | number | null)[][]
  /** renders the results table */
  children: (results: AccountingJobResult[], running: boolean) => ReactNode
}) {
  const { jobs, loading, error, clearError, start, update } = useAccountingJobs(tool)
  const [chosen, setChosen] = useState<string | null>(null)
  const [uploading, setUploading] = useState(0)
  const [rejected, setRejected] = useState<string | null>(null)
  const selectedId = chosen ?? jobs[0]?.id ?? null
  const { summary, results, error: pollError } = useAccountingJob(selectedId, update)

  const add = async (files: File[]) => {
    const pdfs = files.filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    const skipped = files.filter((f) => !pdfs.includes(f)).map((f) => f.name)
    setRejected(skipped.length ? `Skipped (not a PDF): ${skipped.join(', ')}` : null)
    for (const f of pdfs) {
      setUploading((n) => n + 1)
      const job = await start(f)
      setUploading((n) => n - 1)
      if (job) setChosen(job.id)
    }
  }

  const s = summary
  const running = Boolean(s && isActive(s))
  const pct = s?.total_pages ? Math.round((100 * s.pages_done) / s.total_pages) : 0

  return (
    <Box>
      <ToolHeader title={title}>{description}</ToolHeader>
      <DropZone
        accept=".pdf,application/pdf"
        buttonLabel={uploading ? 'Uploading…' : 'Choose PDF'}
        hint={hint}
        onFiles={(f) => void add(f)}
      />
      {rejected && <ErrorAlert message={rejected} onClose={() => setRejected(null)} />}
      {error && <ErrorAlert message={error} onClose={clearError} />}

      {loading ? (
        <CircularProgress size={20} />
      ) : (
        jobs.length > 0 && (
          <Box mb={2}>
            <Typography variant="caption" color="text.secondary" display="block" mb={0.75}>
              Recent runs
            </Typography>
            <Box display="flex" gap={1} flexWrap="wrap">
              {jobs.map((j) => (
                <RunChip
                  key={j.id}
                  job={j}
                  selected={j.id === selectedId}
                  onClick={() => setChosen(j.id)}
                />
              ))}
            </Box>
          </Box>
        )
      )}

      {s && (
        <Paper variant="outlined" sx={{ borderRadius: 2, p: { xs: 2, md: 2.5 } }}>
          <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap" mb={1.5}>
            <Typography
              variant="subtitle1"
              fontWeight={700}
              sx={{ wordBreak: 'break-all', flex: 1 }}
            >
              {s.filename}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {s.associations_done} association{s.associations_done === 1 ? '' : 's'}
              {s.flagged_count > 0 && ` · ${s.flagged_count} flagged`}
            </Typography>
            <Button
              size="small"
              startIcon={<DownloadIcon />}
              disabled={!results.length}
              onClick={() => downloadCsv(toCsv(results), csvName)}
            >
              Download CSV
            </Button>
          </Box>

          {s.status === 'pending' && (
            <Alert severity="info" icon={<CircularProgress size={18} />} sx={{ mb: 2 }}>
              Waiting for the background worker to pick this up…
            </Alert>
          )}
          {s.status === 'processing' && (
            <Box mb={2}>
              <LinearProgress
                variant="determinate"
                value={pct}
                sx={{ borderRadius: 1, mb: 0.75 }}
              />
              <Typography variant="body2" color="text.secondary">
                {s.current_association ? (
                  <>
                    Working on <strong>{s.current_association}</strong> ·{' '}
                  </>
                ) : null}
                page {s.pages_done} of {s.total_pages ?? '…'} · you can leave this page; the run
                continues in the background.
              </Typography>
            </Box>
          )}
          {s.status === 'failed' && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {s.error_detail ?? 'This run failed.'}
            </Alert>
          )}
          {pollError && <ErrorAlert message={pollError} />}

          {children(results, running)}
        </Paper>
      )}
    </Box>
  )
}
