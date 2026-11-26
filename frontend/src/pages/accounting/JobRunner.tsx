/**
 * Shared screen for the background accounting tools: upload a combined
 * (or single-association) PDF, pick a recent run, follow its progress, see
 * and download the per-association results.
 */
import { useRef, useState } from 'react'
import type { ReactNode } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import IconButton from '@mui/material/IconButton'
import LinearProgress from '@mui/material/LinearProgress'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import DownloadIcon from '@mui/icons-material/Download'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import CloseIcon from '@mui/icons-material/Close'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import { useSearchParams } from 'react-router-dom'
import ErrorAlert from '../../components/layout/ErrorAlert'
import WorkingText from '../../components/common/WorkingText'
import { useJobs } from '../../context/JobsContext'
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

/** One file a multi-file tool needs. */
export interface JobInput {
  role: string
  label: string
  hint: string
  required?: boolean
  /** filename pattern used to sort files dropped together into their slot */
  match: RegExp
}

const isPdf = (f: File) => f.name.toLowerCase().endsWith('.pdf')

/** A labelled slot per file, then Start (for tools that compare files). */
function MultiFileForm({
  inputs,
  minFiles,
  uploading,
  onStart,
}: {
  inputs: JobInput[]
  minFiles: number
  uploading: boolean
  onStart: (files: Record<string, File>) => Promise<boolean>
}) {
  const [files, setFiles] = useState<Record<string, File>>({})
  const [dragging, setDragging] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  const assign = (dropped: File[], role?: string) => {
    const pdfs = dropped.filter(isPdf)
    const skipped = dropped.filter((f) => !isPdf(f)).map((f) => f.name)
    const next = { ...files }
    const placed = new Set<string>()
    const unplaced: string[] = []
    for (const f of pdfs) {
      // Files dropped together go one per slot, by name.
      const slot = role ?? inputs.find((i) => !placed.has(i.role) && i.match.test(f.name))?.role
      if (slot) {
        next[slot] = f
        placed.add(slot)
      } else unplaced.push(f.name)
    }
    setFiles(next)
    const msgs = [
      skipped.length ? `Not a PDF: ${skipped.join(', ')}` : '',
      unplaced.length
        ? `Couldn't tell which box ${unplaced.join(', ')} belongs in — choose it below.`
        : '',
    ].filter(Boolean)
    setNote(msgs.length ? msgs.join(' ') : null)
  }

  const missingRequired = inputs.some((i) => i.required && !files[i.role])
  const ready = !missingRequired && Object.keys(files).length >= minFiles

  return (
    <Paper
      variant="outlined"
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        assign(Array.from(e.dataTransfer.files ?? []))
      }}
      sx={{
        p: { xs: 2, md: 2.5 },
        mb: 3,
        borderRadius: 2,
        borderStyle: 'dashed',
        borderColor: dragging ? 'primary.main' : 'divider',
        bgcolor: dragging ? 'action.hover' : 'background.paper',
      }}
    >
      <Box display="grid" gap={1.5} gridTemplateColumns={{ md: `repeat(${inputs.length}, 1fr)` }}>
        {inputs.map((i) => (
          <FileSlot
            key={i.role}
            input={i}
            file={files[i.role] ?? null}
            onFile={(f) => assign([f], i.role)}
            onClear={() =>
              setFiles(({ [i.role]: _removed, ...rest }) => {
                void _removed
                return rest
              })
            }
          />
        ))}
      </Box>
      {note && (
        <Typography variant="body2" color="warning.main" mt={1.5}>
          {note}
        </Typography>
      )}
      <Box display="flex" alignItems="center" gap={2} mt={2} flexWrap="wrap">
        <Button
          variant="contained"
          startIcon={<PlayArrowIcon />}
          disabled={!ready || uploading}
          onClick={() => {
            void onStart(files).then((ok) => ok && setFiles({}))
          }}
        >
          {uploading ? 'Uploading…' : 'Start'}
        </Button>
        <Typography variant="body2" color="text.secondary">
          Drop all the files here at once, or choose each one.
        </Typography>
      </Box>
    </Paper>
  )
}

function FileSlot({
  input,
  file,
  onFile,
  onClear,
}: {
  input: JobInput
  file: File | null
  onFile: (f: File) => void
  onClear: () => void
}) {
  const ref = useRef<HTMLInputElement>(null)
  return (
    <Box
      sx={{
        border: 1,
        borderColor: file ? 'success.light' : 'divider',
        borderRadius: 1.5,
        p: 1.5,
        minWidth: 0,
      }}
    >
      <Typography variant="body2" fontWeight={700}>
        {input.label}
        {!input.required && (
          <Typography component="span" variant="caption" color="text.secondary" ml={0.75}>
            optional
          </Typography>
        )}
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block" mb={1}>
        {input.hint}
      </Typography>
      {file ? (
        <Box display="flex" alignItems="center" gap={0.5} minWidth={0}>
          <InsertDriveFileOutlinedIcon fontSize="small" color="action" />
          <Typography variant="body2" noWrap sx={{ flex: 1, minWidth: 0 }} title={file.name}>
            {file.name}
          </Typography>
          <IconButton size="small" aria-label={`Remove ${input.label}`} onClick={onClear}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      ) : (
        <Button size="small" variant="outlined" onClick={() => ref.current?.click()}>
          Choose PDF
        </Button>
      )}
      <input
        ref={ref}
        type="file"
        accept=".pdf,application/pdf"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) onFile(f)
          e.target.value = ''
        }}
      />
    </Box>
  )
}

export default function JobRunner({
  tool,
  title,
  description,
  hint,
  inputs,
  minFiles = 1,
  csvName,
  toCsv,
  children,
}: {
  tool: AccountingTool
  title: string
  description: ReactNode
  /** what to upload (single-file tools) */
  hint?: string
  /** several files compared in one run (otherwise: one PDF per run) */
  inputs?: JobInput[]
  minFiles?: number
  csvName: string
  /** header row + one row per association (or per association × bank) */
  toCsv: (results: AccountingJobResult[]) => (string | number | null)[][]
  /** renders the results table */
  children: (results: AccountingJobResult[], running: boolean) => ReactNode
}) {
  const { jobs, loading, error, clearError, start, update } = useAccountingJobs(tool)
  const { trackAccountingJob } = useJobs()
  // The run shown is in the URL (?job=), so My Jobs and the "finished"
  // pop-up can link straight to it.
  const [params, setParams] = useSearchParams()
  const chosen = params.get('job')
  const setChosen = (id: string) => setParams({ job: id }, { replace: true })
  const [uploading, setUploading] = useState(0)
  const [rejected, setRejected] = useState<string | null>(null)
  const selectedId = chosen ?? jobs[0]?.id ?? null
  const { summary, results, error: pollError } = useAccountingJob(selectedId, update)

  const run = async (input: File | Record<string, File>) => {
    setUploading((n) => n + 1)
    const job = await start(input)
    setUploading((n) => n - 1)
    if (job) {
      trackAccountingJob(job)
      setChosen(job.id)
    }
    return Boolean(job)
  }

  const add = async (files: File[]) => {
    const pdfs = files.filter(isPdf)
    const skipped = files.filter((f) => !pdfs.includes(f)).map((f) => f.name)
    setRejected(skipped.length ? `Skipped (not a PDF): ${skipped.join(', ')}` : null)
    for (const f of pdfs) await run(f)
  }

  const s = summary
  const running = Boolean(s && isActive(s))
  const pct = s?.total_pages ? Math.round((100 * s.pages_done) / s.total_pages) : 0

  return (
    <Box>
      <ToolHeader title={title}>{description}</ToolHeader>
      {inputs ? (
        <MultiFileForm
          inputs={inputs}
          minFiles={minFiles}
          uploading={uploading > 0}
          onStart={run}
        />
      ) : (
        <DropZone
          accept=".pdf,application/pdf"
          buttonLabel={uploading ? 'Uploading…' : 'Choose PDF'}
          hint={hint ?? ''}
          onFiles={(f) => void add(f)}
        />
      )}
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
              <LinearProgress variant="determinate" value={pct} sx={{ borderRadius: 1, mb: 1 }} />
              <Box display="flex" alignItems="center" columnGap={1.5} rowGap={0.5} flexWrap="wrap">
                <Typography variant="body2" component="div">
                  <WorkingText />
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {s.current_association ? (
                    <>
                      <strong>{s.current_association}</strong> ·{' '}
                    </>
                  ) : null}
                  page {s.pages_done} of {s.total_pages ?? '…'}
                </Typography>
              </Box>
              <Typography variant="caption" color="text.secondary" display="block" mt={0.5}>
                You can leave this page; the run continues in the background and shows up in My
                Jobs.
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
