import { useEffect, useRef, useState } from 'react'
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
import SessionJobsPanel from '../../components/common/SessionJobsPanel'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import ClearIcon from '@mui/icons-material/Clear'
import SendIcon from '@mui/icons-material/Send'
import apiClient from '../../api/client'
import { useJobs } from '../../context/JobsContext'
import type { Association } from '../../types'

function FileField({
  label,
  accept,
  file,
  onChange,
  helperText,
  disabled,
}: {
  label: string
  accept: string
  file: File | null
  onChange: (f: File | null) => void
  helperText?: string
  disabled?: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)

  // Clear the hidden input when the parent resets file to null so that
  // re-selecting the same file still fires onChange.
  useEffect(() => {
    if (!file && inputRef.current) {
      inputRef.current.value = ''
    }
  }, [file])

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
          disabled={disabled}
          sx={{ flexShrink: 0 }}
        >
          Choose file
        </Button>
        {file ? (
          <Box display="flex" alignItems="center" gap={0.5} minWidth={0}>
            <Typography variant="body2" noWrap title={file.name}>
              {file.name}
            </Typography>
            <IconButton size="small" onClick={() => onChange(null)} disabled={disabled}>
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

export default function BudgetGeneratorPage() {
  const navigate = useNavigate()
  const { trackJob } = useJobs()

  const [associations, setAssociations] = useState<Association[]>([])
  const [selectedAssoc, setSelectedAssoc] = useState<Association | null>(null)
  const [budgetYear, setBudgetYear] = useState(new Date().getFullYear() + 1)
  const [financialReport, setFinancialReport] = useState<File | null>(null)
  const [priorBudget, setPriorBudget] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    apiClient
      .get<Association[]>('/api/associations')
      .then((res) => setAssociations(res.data.filter((a) => a.is_active)))
      .catch(() => {})
  }, [])

  const canSubmit =
    selectedAssoc !== null && financialReport !== null && priorBudget !== null && !submitting

  const handleGenerate = async () => {
    if (!canSubmit || !selectedAssoc) return

    const formData = new FormData()
    formData.append('association_name', selectedAssoc.legal_name)
    formData.append('budget_year', String(budgetYear))
    formData.append('financial_report', financialReport!)
    formData.append('prior_budget', priorBudget!)

    setSubmitting(true)
    setSubmitError(null)

    try {
      const res = await apiClient.post<{ job_id: string }>('/api/budget/generate', formData)
      trackJob(res.data.job_id, 'budget')

      // Reset immediately so another job can be submitted without waiting.
      setSelectedAssoc(null)
      setFinancialReport(null)
      setPriorBudget(null)
    } catch {
      setSubmitError('Failed to submit. Check your connection and try again.')
    } finally {
      setSubmitting(false)
    }
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
            disabled={submitting}
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
            disabled={submitting}
            slotProps={{ htmlInput: { min: 2020, max: 2100 } }}
          />

          <Divider />

          <FileField
            label="Income & Expense report"
            accept=".pdf"
            file={financialReport}
            onChange={setFinancialReport}
            helperText="Current Year CSC Income & Expense report PDF — source for the Projected column"
            disabled={submitting}
          />

          <FileField
            label="Previous year's budget"
            accept=".xlsx,.xls"
            file={priorBudget}
            onChange={setPriorBudget}
            helperText="Last year's budget xlsx — will be edited in place with the new year's values"
            disabled={submitting}
          />

          <Divider />

          {submitError && (
            <Alert severity="error" onClose={() => setSubmitError(null)}>
              {submitError}
            </Alert>
          )}

          <Button
            variant="contained"
            onClick={handleGenerate}
            disabled={!canSubmit}
            startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : <SendIcon />}
          >
            {submitting ? 'Submitting…' : 'Generate budget'}
          </Button>
        </Box>
      </Paper>

      <SessionJobsPanel jobType="budget" />
    </Box>
  )
}
