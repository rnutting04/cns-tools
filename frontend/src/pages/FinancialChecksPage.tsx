import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Collapse from '@mui/material/Collapse'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import CancelIcon from '@mui/icons-material/Cancel'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import VerifiedIcon from '@mui/icons-material/Verified'
import axios from 'axios'
import apiClient from '../api/client'
import ErrorAlert from '../components/layout/ErrorAlert'
import type {
  FinancialCheckReport,
  FinancialCheckResult,
  FinancialCheckSide,
  FinancialCheckStatus,
} from '../types'

const STATUS: Record<
  FinancialCheckStatus,
  {
    label: string
    color: 'success' | 'error' | 'warning' | 'default'
    icon: React.ReactElement
    hint: string
  }
> = {
  fail: {
    label: 'Mismatch',
    color: 'error',
    icon: <CancelIcon fontSize="small" />,
    hint: 'The figures disagree and both were read with confidence.',
  },
  review: {
    label: 'Needs review',
    color: 'warning',
    icon: <ErrorOutlineIcon fontSize="small" />,
    hint: 'A figure could not be read reliably. Compare the highlighted areas.',
  },
  missing: {
    label: 'Report missing',
    color: 'warning',
    icon: <HelpOutlineIcon fontSize="small" />,
    hint: 'The supporting report is not in this packet.',
  },
  pass: {
    label: 'Matches',
    color: 'success',
    icon: <CheckCircleIcon fontSize="small" />,
    hint: 'The figures agree.',
  },
  not_applicable: {
    label: 'N/A',
    color: 'default',
    icon: <RemoveCircleOutlineIcon fontSize="small" />,
    hint: 'Account not on the balance sheet and the report is empty.',
  },
}

const ORDER: FinancialCheckStatus[] = ['fail', 'review', 'missing', 'pass', 'not_applicable']

const money = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return n < 0 ? `(${money.format(-n)})` : money.format(n)
}

function SideView({ side, heading }: { side: FinancialCheckSide | null; heading: string }) {
  if (!side) {
    return (
      <Box flex={1} minWidth={0}>
        <Typography variant="caption" color="text.secondary">
          {heading}
        </Typography>
        <Typography variant="body2" color="text.disabled">
          Not found
        </Typography>
      </Box>
    )
  }
  return (
    <Box flex={1} minWidth={0}>
      <Typography variant="caption" color="text.secondary" display="block">
        {heading} · {side.source}
        {side.page ? ` · page ${side.page}` : ''}
      </Typography>
      <Box display="flex" alignItems="center" gap={0.5}>
        <Typography variant="body2" fontWeight={600} sx={{ fontVariantNumeric: 'tabular-nums' }}>
          {fmt(side.amount)}
        </Typography>
        {side.verified === true && (
          <Tooltip title="Confirmed by the report's own totals">
            <VerifiedIcon sx={{ fontSize: 16, color: 'success.main' }} />
          </Tooltip>
        )}
        {side.verified === false && (
          <Tooltip title="The report's own totals didn't add up when read — possible OCR misread">
            <ErrorOutlineIcon sx={{ fontSize: 16, color: 'warning.main' }} />
          </Tooltip>
        )}
      </Box>
      <Typography
        variant="caption"
        color="text.secondary"
        display="block"
        noWrap
        title={side.label}
      >
        {side.label}
      </Typography>
      {side.image && (
        <Box
          component="img"
          src={side.image}
          alt={`${side.source} page ${side.page}`}
          sx={{
            display: 'block',
            width: '100%',
            mt: 1,
            border: 1,
            borderColor: 'divider',
            borderRadius: 1,
          }}
        />
      )}
    </Box>
  )
}

function CheckRow({ check }: { check: FinancialCheckResult }) {
  const [open, setOpen] = useState(check.status === 'fail' || check.status === 'review')
  const s = STATUS[check.status]
  const hasDetail = Boolean(check.left?.image || check.right?.image || check.notes.length)
  return (
    <Box sx={{ borderTop: 1, borderColor: 'divider' }}>
      <Box
        display="grid"
        gridTemplateColumns={{ xs: '1fr auto', md: '150px 1fr 130px 130px 110px 40px' }}
        alignItems="center"
        columnGap={2}
        rowGap={0.5}
        px={2}
        py={1.25}
        onClick={() => hasDetail && setOpen((o) => !o)}
        sx={{ cursor: hasDetail ? 'pointer' : 'default', '&:hover': { bgcolor: 'action.hover' } }}
      >
        <Tooltip title={s.hint}>
          <Chip
            size="small"
            icon={s.icon}
            label={s.label}
            color={s.color}
            variant={check.status === 'pass' ? 'outlined' : 'filled'}
            sx={{ justifySelf: 'start' }}
          />
        </Tooltip>
        <Typography variant="body2" sx={{ gridColumn: { xs: '1 / -1', md: 'auto' } }}>
          {check.title}
        </Typography>
        {[check.left?.amount, check.right?.amount].map((a, i) => (
          <Typography
            key={i}
            variant="body2"
            textAlign="right"
            sx={{ display: { xs: 'none', md: 'block' }, fontVariantNumeric: 'tabular-nums' }}
          >
            {fmt(a)}
          </Typography>
        ))}
        <Typography
          variant="body2"
          textAlign="right"
          color={check.status === 'fail' ? 'error.main' : 'text.secondary'}
          sx={{ display: { xs: 'none', md: 'block' }, fontVariantNumeric: 'tabular-nums' }}
        >
          {check.difference ? fmt(check.difference) : ''}
        </Typography>
        <Box sx={{ gridRow: { xs: 1, md: 'auto' }, gridColumn: { xs: 2, md: 'auto' } }}>
          {hasDetail && (
            <IconButton size="small" aria-label={open ? 'Hide detail' : 'Show detail'}>
              <ExpandMoreIcon
                fontSize="small"
                sx={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}
              />
            </IconButton>
          )}
        </Box>
      </Box>
      <Collapse in={open} unmountOnExit>
        <Box px={2} pb={2}>
          {check.notes.map((n) => (
            <Typography key={n} variant="body2" color="text.secondary" mb={1}>
              {n}
            </Typography>
          ))}
          <Box display="flex" flexDirection={{ xs: 'column', md: 'row' }} gap={2}>
            <SideView side={check.left} heading="Balance sheet" />
            <SideView side={check.right} heading="Supporting report" />
          </Box>
        </Box>
      </Collapse>
    </Box>
  )
}

export default function FinancialChecksPage() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [report, setReport] = useState<FinancialCheckReport | null>(null)
  const [running, setRunning] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FinancialCheckStatus | null>(null)
  const [dragging, setDragging] = useState(false)

  const run = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Choose a PDF financial packet.')
      return
    }
    setRunning(file.name)
    setError(null)
    setReport(null)
    setFilter(null)
    const form = new FormData()
    form.append('financial_report', file)
    try {
      // Scanned packets are several MB and take a few seconds to read.
      const res = await apiClient.post<FinancialCheckReport>('/api/financials/check', form, {
        timeout: 120_000,
      })
      setReport(res.data)
    } catch (e) {
      const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
      setError(typeof detail === 'string' ? detail : 'Could not check this packet. Try again.')
    } finally {
      setRunning(null)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file && !running) void run(file)
  }

  const shown = report?.checks.filter((c) => !filter || c.status === filter) ?? []
  const issues = report ? report.summary.fail + report.summary.review + report.summary.missing : 0

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={0.5}>
        Financial review
      </Typography>
      <Typography color="text.secondary" mb={3}>
        Upload a monthly financial packet to tie the balance sheet to the bank reconciliations and
        supporting reports.
      </Typography>

      <Paper
        variant="outlined"
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        sx={{
          p: 3,
          mb: 3,
          borderRadius: 2,
          borderStyle: 'dashed',
          borderColor: dragging ? 'primary.main' : 'divider',
          bgcolor: dragging ? 'action.hover' : 'background.paper',
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          flexWrap: 'wrap',
        }}
      >
        <Button
          variant="contained"
          startIcon={running ? <CircularProgress size={16} color="inherit" /> : <UploadFileIcon />}
          onClick={() => inputRef.current?.click()}
          disabled={Boolean(running)}
        >
          {running ? 'Checking…' : 'Choose PDF'}
        </Button>
        <Typography variant="body2" color="text.secondary" sx={{ minWidth: 0 }} noWrap>
          {running ? `Reading ${running}` : 'or drop the packet here'}
        </Typography>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void run(f)
          }}
        />
      </Paper>

      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

      {report && (
        <>
          <Box display="flex" alignItems="baseline" gap={1} mb={1.5} flexWrap="wrap">
            <Typography variant="subtitle1" fontWeight={600} sx={{ wordBreak: 'break-all' }}>
              {report.filename}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {report.page_count} pages
            </Typography>
          </Box>

          {report.checks.length > 0 && issues === 0 && (
            <Alert severity="success" sx={{ mb: 2 }}>
              Everything ties out.
            </Alert>
          )}

          <Box display="flex" gap={1} mb={2} flexWrap="wrap">
            <Chip
              label={`All ${report.checks.length}`}
              onClick={() => setFilter(null)}
              color={filter === null ? 'primary' : 'default'}
              variant={filter === null ? 'filled' : 'outlined'}
            />
            {ORDER.filter((s) => report.summary[s] > 0).map((s) => (
              <Chip
                key={s}
                icon={STATUS[s].icon}
                label={`${STATUS[s].label} ${report.summary[s]}`}
                onClick={() => setFilter(filter === s ? null : s)}
                color={filter === s ? 'primary' : STATUS[s].color}
                variant={filter === s ? 'filled' : 'outlined'}
              />
            ))}
          </Box>

          <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
            <Box
              display={{ xs: 'none', md: 'grid' }}
              gridTemplateColumns="150px 1fr 130px 130px 110px 40px"
              columnGap={2}
              px={2}
              py={1}
              bgcolor="action.hover"
            >
              {['Status', 'Check', 'Balance sheet', 'Report', 'Difference', ''].map((h, i) => (
                <Typography
                  key={i}
                  variant="caption"
                  fontWeight={600}
                  color="text.secondary"
                  textAlign={i >= 2 && i <= 4 ? 'right' : 'left'}
                >
                  {h}
                </Typography>
              ))}
            </Box>
            {shown.map((c) => (
              <CheckRow key={c.id} check={c} />
            ))}
          </Paper>
        </>
      )}
    </Box>
  )
}
