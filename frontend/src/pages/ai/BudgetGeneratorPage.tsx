import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Autocomplete from '@mui/material/Autocomplete'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ClearIcon from '@mui/icons-material/Clear'
import DownloadIcon from '@mui/icons-material/Download'
import RestartAltIcon from '@mui/icons-material/RestartAlt'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import apiClient from '../../api/client'
import { usePolling } from '../../hooks/usePolling'
import { useJobs } from '../../context/JobsContext'
import type { Association } from '../../types'

// --- Types -------------------------------------------------------------------

const PIPELINE_STEPS: Array<{ key: string; label: string }> = [
  { key: 'reading_excel', label: 'Copying current-year budget to prior-year column' },
  { key: 'extracting', label: 'Extracting from Income & Expense Report' },
  { key: 'cross_check', label: 'Verifying totals' },
  { key: 'calculating', label: 'Calculating projections' },
  { key: 'assembling', label: 'Building output' },
  { key: 'rendering', label: 'Rendering spreadsheet' },
]

interface BudgetJobStatus {
  job_id: string
  status: 'pending' | 'processing' | 'complete' | 'failed'
  current_step: string | null
  review_flag_count: number | null
  download_url: string | null
  error_code: string | null
  error_detail: {
    message?: string
    mismatches?: string[]
    errors?: string[]
  } | null
}

interface JobError {
  error_code: string | null
  error_detail: BudgetJobStatus['error_detail']
}

// --- File upload field -------------------------------------------------------

function FileField({
  label,
  accept,
  file,
  onChange,
  helperText,
}: {
  label: string
  accept: string
  file: File | null
  onChange: (f: File | null) => void
  helperText?: string
}) {
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
        {label}
      </Typography>

      <Box display="flex" alignItems="center" gap={1}>
        <Button
          variant="outlined"
          size="small"
          startIcon={<AttachFileIcon />}
          onClick={() => inputRef.current?.click()}
          sx={{ flexShrink: 0 }}
        >
          Choose file
        </Button>

        {file ? (
          <Box display="flex" alignItems="center" gap={0.5} minWidth={0}>
            <Typography variant="body2" noWrap title={file.name}>
              {file.name}
            </Typography>
            <IconButton size="small" onClick={() => onChange(null)}>
              <ClearIcon fontSize="small" />
            </IconButton>
          </Box>
        ) : (
          <Typography variant="body2" color="text.disabled">
            No file chosen
          </Typography>
        )}
      </Box>

      {helperText && (
        <Typography variant="caption" color="text.secondary">
          {helperText}
        </Typography>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        style={{ display: 'none' }}
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
    </Box>
  )
}

// --- Error detail renderer ---------------------------------------------------

function PipelineError({ detail }: { detail: JobError }) {
  const { error_code, error_detail } = detail

  if (error_code === 'cross_check_failed') {
    return (
      <Alert severity="error" icon={<WarningAmberIcon />}>
        <Typography variant="body2" fontWeight={600} gutterBottom>
          Extraction cross-check failed — AI may have missed lines in the PDF
        </Typography>
        {error_detail?.mismatches?.map((m, i) => (
          <Typography key={i} variant="body2" sx={{ fontFamily: 'monospace', fontSize: 12 }}>
            • {m}
          </Typography>
        ))}
      </Alert>
    )
  }

  if (error_code === 'validation_failed') {
    return (
      <Alert severity="error">
        <Typography variant="body2" fontWeight={600} gutterBottom>
          Budget validation failed
        </Typography>
        {error_detail?.errors?.map((e, i) => (
          <Typography key={i} variant="body2" sx={{ fontFamily: 'monospace', fontSize: 12 }}>
            • {e}
          </Typography>
        ))}
      </Alert>
    )
  }

  return (
    <Alert severity="error">
      {error_detail?.message ?? 'Budget generation failed. Check the uploaded files and try again.'}
    </Alert>
  )
}

// --- Main page ---------------------------------------------------------------

const isTerminal = (data: BudgetJobStatus) =>
  data.status === 'complete' || data.status === 'failed'

export default function BudgetGeneratorPage() {
  const navigate = useNavigate()
  const { trackJob } = useJobs()

  const [associations, setAssociations] = useState<Association[]>([])
  const [selectedAssoc, setSelectedAssoc] = useState<Association | null>(null)
  const [budgetYear, setBudgetYear] = useState(new Date().getFullYear() + 1)
  const [financialReport, setFinancialReport] = useState<File | null>(null)
  const [priorBudget, setPriorBudget] = useState<File | null>(null)

  const [jobId, setJobId] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [reviewFlagCount, setReviewFlagCount] = useState<number | null>(null)
  const [error, setError] = useState<JobError | null>(null)
  const [done, setDone] = useState(false)

  // Capture the filename at submit time so the download effect doesn't depend
  // on selectedAssoc / budgetYear state (which could change while polling).
  const downloadFilenameRef = useRef<string>('')

  useEffect(() => {
    apiClient
      .get<Association[]>('/api/associations')
      .then((res) => setAssociations(res.data.filter((a) => a.is_active)))
      .catch(() => {})
  }, [])

  const fetchJobStatus = useCallback(
    (id: string) =>
      apiClient.get<BudgetJobStatus>(`/api/budget/jobs/${id}`).then((r) => r.data),
    [],
  )

  const { data: pollData } = usePolling(jobId, fetchJobStatus, isTerminal)

  const currentStep = pollData?.current_step ?? null

  useEffect(() => {
    if (!pollData) return

    if (pollData.status === 'complete') {
      if (pollData.download_url) {
        const a = document.createElement('a')
        a.href = pollData.download_url
        a.download = downloadFilenameRef.current
        document.body.appendChild(a)
        a.click()
        a.remove()
      }
      setReviewFlagCount(pollData.review_flag_count)
      setDone(true)
      setGenerating(false)
      setJobId(null)
    } else if (pollData.status === 'failed') {
      setError({ error_code: pollData.error_code, error_detail: pollData.error_detail })
      setGenerating(false)
      setJobId(null)
    }
  }, [pollData])

  const canGenerate =
    selectedAssoc !== null && financialReport !== null && priorBudget !== null && !generating

  const handleGenerate = async () => {
    if (!canGenerate || !selectedAssoc) return

    const formData = new FormData()
    formData.append('association_name', selectedAssoc.legal_name)
    formData.append('budget_year', String(budgetYear))
    formData.append('financial_report', financialReport!)
    formData.append('prior_budget', priorBudget!)

    downloadFilenameRef.current = `${selectedAssoc.filter_name}_${budgetYear}_budget.xlsx`

    setGenerating(true)
    setError(null)
    setDone(false)
    setReviewFlagCount(null)

    try {
      const res = await apiClient.post<{ job_id: string }>('/api/budget/generate', formData)
      setJobId(res.data.job_id)
      trackJob(res.data.job_id, 'budget')
    } catch {
      setError({
        error_code: 'unexpected_error',
        error_detail: { message: 'Failed to submit budget generation job. Please try again.' },
      })
      setGenerating(false)
    }
  }

  const handleReset = () => {
    setSelectedAssoc(null)
    setFinancialReport(null)
    setPriorBudget(null)
    setDone(false)
    setError(null)
    setReviewFlagCount(null)
    setJobId(null)
  }

  return (
    <Box>
      <Box display="flex" alignItems="center" gap={1} mb={3}>
        <IconButton size="small" onClick={() => navigate('/ai')}>
          <ArrowBackIcon fontSize="small" />
        </IconButton>
        <Typography variant="h5" fontWeight={700}>
          Budget generator
        </Typography>
      </Box>

      <Paper variant="outlined" sx={{ p: 3, maxWidth: 560, borderRadius: 2 }}>
        <Box display="flex" flexDirection="column" gap={3}>

          <Autocomplete
            options={associations}
            value={selectedAssoc}
            onChange={(_, v) => setSelectedAssoc(v)}
            getOptionLabel={(a) => `${a.legal_name} (${a.filter_name} · ${a.location_name})`}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Association"
                size="small"
                helperText="The HOA this budget is for"
              />
            )}
          />

          <TextField
            label="Budget year"
            type="number"
            size="small"
            value={budgetYear}
            onChange={(e) => setBudgetYear(parseInt(e.target.value, 10))}
            slotProps={{ htmlInput: { min: 2020, max: 2100 } }}
          />

          <Divider />

          <FileField
            label="Income & Expense report"
            accept=".pdf"
            file={financialReport}
            onChange={setFinancialReport}
            helperText="CSC Income & Expense report PDF — source for the Projected column"
          />

          <FileField
            label="Previous year's budget"
            accept=".xlsx,.xls"
            file={priorBudget}
            onChange={setPriorBudget}
            helperText="Last year's budget xlsx — will be edited in place with the new year's values"
          />

          <Divider />

          {error && <PipelineError detail={error} />}

          {done && (
            <Box display="flex" flexDirection="column" gap={1.5}>
              <Box display="flex" flexDirection="column" gap={0.75} sx={{ pl: 0.5 }}>
                {PIPELINE_STEPS.map((step) => (
                  <Box key={step.key} display="flex" alignItems="center" gap={1}>
                    <CheckCircleIcon color="success" sx={{ fontSize: 14, flexShrink: 0 }} />
                    <Typography variant="body2" color="text.secondary">
                      {step.label}
                    </Typography>
                  </Box>
                ))}
              </Box>

              <Box display="flex" alignItems="center" gap={1}>
                <CheckCircleIcon color="success" fontSize="small" />
                <Typography color="success.main" fontWeight={600} variant="body2">
                  Budget generated — download started automatically
                </Typography>
              </Box>

              {reviewFlagCount !== null && reviewFlagCount > 0 && (
                <Alert severity="warning">
                  <Typography variant="body2">
                    {reviewFlagCount} review {reviewFlagCount === 1 ? 'flag' : 'flags'} — check
                    the Notes column in the workbook for lines that need human review before
                    finalizing.
                  </Typography>
                </Alert>
              )}

              <Box display="flex" gap={2}>
                <Button
                  variant="outlined"
                  startIcon={<RestartAltIcon />}
                  onClick={handleReset}
                  size="small"
                >
                  Generate another
                </Button>
              </Box>
            </Box>
          )}

          {!done && (
            <Box display="flex" flexDirection="column" gap={1.5}>
              <Button
                variant="contained"
                onClick={handleGenerate}
                disabled={!canGenerate}
                startIcon={
                  generating ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    <DownloadIcon />
                  )
                }
              >
                {generating ? 'Generating…' : 'Generate budget'}
              </Button>
              {generating && (
                <Box display="flex" flexDirection="column" gap={0.75} sx={{ pl: 0.5 }}>
                  {PIPELINE_STEPS.map((step) => {
                    const currentIdx = PIPELINE_STEPS.findIndex((s) => s.key === currentStep)
                    const stepIdx = PIPELINE_STEPS.findIndex((s) => s.key === step.key)
                    const isDone = currentIdx > stepIdx
                    const isCurrent = step.key === currentStep || (currentStep === null && stepIdx === 0)
                    return (
                      <Box key={step.key} display="flex" alignItems="center" gap={1}>
                        {isDone ? (
                          <CheckCircleIcon color="success" sx={{ fontSize: 14, flexShrink: 0 }} />
                        ) : isCurrent ? (
                          <CircularProgress size={12} sx={{ flexShrink: 0 }} />
                        ) : (
                          <Box
                            sx={{
                              width: 12,
                              height: 12,
                              borderRadius: '50%',
                              border: '1.5px solid',
                              borderColor: 'divider',
                              flexShrink: 0,
                            }}
                          />
                        )}
                        <Typography
                          variant="body2"
                          color={isDone ? 'text.secondary' : isCurrent ? 'text.primary' : 'text.disabled'}
                          fontWeight={isCurrent ? 500 : 400}
                        >
                          {step.label}
                        </Typography>
                      </Box>
                    )
                  })}
                </Box>
              )}
            </Box>
          )}
        </Box>
      </Paper>
    </Box>
  )
}
