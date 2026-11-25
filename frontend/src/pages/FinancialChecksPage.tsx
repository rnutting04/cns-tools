import { useEffect, useRef, useState } from 'react'
import type { DragEvent } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Collapse from '@mui/material/Collapse'
import IconButton from '@mui/material/IconButton'
import LinearProgress from '@mui/material/LinearProgress'
import Paper from '@mui/material/Paper'
import Skeleton from '@mui/material/Skeleton'
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
import CloseIcon from '@mui/icons-material/Close'
import ReplayIcon from '@mui/icons-material/Replay'
import RestartAltIcon from '@mui/icons-material/RestartAlt'
import ErrorAlert from '../components/layout/ErrorAlert'
import { ToolHeader } from './accounting/shared'
import {
  addPackets,
  clearSession,
  evidenceKey,
  loadEvidence,
  removePacket,
  retryPacket,
  useReviewSession,
} from '../hooks/useReviewSession'
import type { PacketEvidence, SessionPacket } from '../hooks/useReviewSession'
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

/** Screenshot for a side: inline (single-packet reports) or fetched lazily. */
interface Evidence {
  image: string | null
  loading: boolean
  failed: boolean
}

function SideView({
  side,
  heading,
  evidence,
}: {
  side: FinancialCheckSide | null
  heading: string
  evidence: Evidence
}) {
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
        {side.amount === null ? (
          <Typography variant="body2" color="text.disabled">
            {side.bbox ? 'Not read — see highlighted area' : 'Not found'}
          </Typography>
        ) : (
          <Typography variant="body2" fontWeight={600} sx={{ fontVariantNumeric: 'tabular-nums' }}>
            {fmt(side.amount)}
          </Typography>
        )}
        {side.guessed && side.verified !== true && (
          <Tooltip title="This line didn't read cleanly, so the amount was picked by its position on the page. Confirm it against the image.">
            <Chip size="small" label="Best guess" color="warning" variant="outlined" />
          </Tooltip>
        )}
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
      {evidence.image ? (
        <Box
          component="img"
          src={evidence.image}
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
      ) : evidence.loading ? (
        <Skeleton variant="rounded" height={84} sx={{ mt: 1 }} />
      ) : evidence.failed ? (
        <Typography variant="caption" color="error.main" display="block" mt={1}>
          Couldn&apos;t load the screenshot.
        </Typography>
      ) : null}
    </Box>
  )
}

function CheckRow({
  check,
  evidence,
}: {
  check: FinancialCheckResult
  evidence: PacketEvidence | null
}) {
  const [open, setOpen] = useState(check.status === 'fail' || check.status === 'review')
  const s = STATUS[check.status]
  const hasDetail = Boolean(check.left?.bbox || check.right?.bbox || check.notes.length)
  const evidenceFor = (side: 'left' | 'right'): Evidence => {
    const inline = check[side]?.image ?? null
    const wanted = Boolean(check[side]?.bbox)
    return {
      image: inline ?? evidence?.images[evidenceKey(check.id, side)] ?? null,
      loading: !inline && wanted && evidence?.status === 'loading',
      failed: !inline && wanted && evidence?.status === 'error',
    }
  }
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
        {[check.left, check.right].map((side, i) => {
          const guess = Boolean(side?.guessed && side.verified !== true)
          return (
            <Typography
              key={i}
              variant="body2"
              textAlign="right"
              title={guess ? 'Best guess — confirm against the image' : undefined}
              sx={{
                display: { xs: 'none', md: 'block' },
                fontVariantNumeric: 'tabular-nums',
                fontStyle: guess ? 'italic' : 'normal',
              }}
            >
              {fmt(side?.amount)}
              {guess ? '?' : ''}
            </Typography>
          )
        })}
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
            <SideView side={check.left} heading="Balance sheet" evidence={evidenceFor('left')} />
            <SideView
              side={check.right}
              heading="Supporting report"
              evidence={evidenceFor('right')}
            />
          </Box>
        </Box>
      </Collapse>
    </Box>
  )
}

/** One packet's checks, with status filter chips. */
function ReportView({
  report,
  evidence,
}: {
  report: FinancialCheckReport
  evidence: PacketEvidence | null
}) {
  const [filter, setFilter] = useState<FinancialCheckStatus | null>(null)
  const shown = report.checks.filter((c) => !filter || c.status === filter)
  const issues = report.summary.fail + report.summary.review + report.summary.missing
  return (
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
          <CheckRow key={c.id} check={c} evidence={evidence} />
        ))}
      </Paper>
    </>
  )
}

/** Counts of the actionable statuses for a packet row, most urgent first. */
function PacketCounts({ report }: { report: FinancialCheckReport }) {
  const shown = ORDER.filter((s) => s !== 'not_applicable' && report.summary[s] > 0)
  return (
    <Box display="flex" gap={0.5} flexWrap="wrap" justifyContent={{ md: 'flex-end' }}>
      {shown.map((s) => (
        <Tooltip key={s} title={STATUS[s].label}>
          <Chip
            size="small"
            icon={STATUS[s].icon}
            label={report.summary[s]}
            color={STATUS[s].color}
            variant={s === 'pass' ? 'outlined' : 'filled'}
          />
        </Tooltip>
      ))}
    </Box>
  )
}

function PacketRow({
  packet,
  selected,
  onSelect,
}: {
  packet: SessionPacket
  selected: boolean
  onSelect: () => void
}) {
  const r = packet.report
  const clean = r !== null && r.summary.fail + r.summary.review + r.summary.missing === 0
  return (
    <Box
      display="grid"
      gridTemplateColumns={{ xs: '1fr auto', md: '1fr auto 40px' }}
      alignItems="center"
      columnGap={2}
      rowGap={0.5}
      px={2}
      py={1}
      onClick={() => packet.status === 'done' && onSelect()}
      sx={{
        borderTop: 1,
        borderColor: 'divider',
        cursor: packet.status === 'done' ? 'pointer' : 'default',
        bgcolor: selected ? 'action.selected' : 'transparent',
        '&:hover': { bgcolor: selected ? 'action.selected' : 'action.hover' },
      }}
    >
      <Box minWidth={0}>
        <Typography variant="body2" fontWeight={selected ? 700 : 500} noWrap title={packet.name}>
          {packet.name}
        </Typography>
        {packet.status === 'error' && (
          <Typography variant="caption" color="error.main">
            {packet.error}
          </Typography>
        )}
        {clean && (
          <Typography variant="caption" color="success.main">
            Everything ties out
          </Typography>
        )}
      </Box>
      <Box>
        {packet.status === 'queued' && (
          <Typography variant="caption" color="text.secondary">
            Waiting…
          </Typography>
        )}
        {packet.status === 'checking' && (
          <Box display="flex" alignItems="center" gap={1}>
            <CircularProgress size={14} />
            <Typography variant="caption" color="text.secondary">
              Checking…
            </Typography>
          </Box>
        )}
        {packet.status === 'error' && (
          <Button
            size="small"
            startIcon={<ReplayIcon fontSize="small" />}
            onClick={(e) => {
              e.stopPropagation()
              retryPacket(packet.id)
            }}
          >
            Retry
          </Button>
        )}
        {r && <PacketCounts report={r} />}
      </Box>
      <Box display={{ xs: 'none', md: 'block' }}>
        {packet.status !== 'checking' && (
          <Tooltip title="Remove from session">
            <IconButton
              size="small"
              aria-label={`Remove ${packet.name}`}
              onClick={(e) => {
                e.stopPropagation()
                removePacket(packet.id)
              }}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Box>
    </Box>
  )
}

export default function FinancialChecksPage() {
  const inputRef = useRef<HTMLInputElement>(null)
  const packets = useReviewSession()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  const add = (files: File[]) => {
    const { rejected } = addPackets(files)
    setError(rejected.length ? `Skipped (not a PDF): ${rejected.join(', ')}` : null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    add(Array.from(e.dataTransfer.files ?? []))
  }

  const done = packets.filter((p) => p.status === 'done')
  const finished = packets.filter((p) => p.status === 'done' || p.status === 'error').length
  const busy = finished < packets.length
  const withIssues = done.filter((p) => {
    const s = p.report?.summary
    return s ? s.fail + s.review + s.missing > 0 : false
  }).length

  // Show the chosen packet; until one is chosen (or if it was removed), the first finished one.
  const selected = done.find((p) => p.id === selectedId) ?? done[0]

  // Fetch the open packet's screenshots (cached for the last few opened).
  const openId = selected?.id
  useEffect(() => {
    if (openId) void loadEvidence(openId)
  }, [openId])

  // A refresh loses the session; warn while packets are still being checked.
  useEffect(() => {
    if (!busy) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [busy])

  return (
    <Box>
      <ToolHeader title="Financial review">
        Upload monthly financial packets to tie each balance sheet to its bank reconciliations and
        supporting reports. Add as many as you like; they&apos;re checked two at a time.
      </ToolHeader>

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
          startIcon={<UploadFileIcon />}
          onClick={() => inputRef.current?.click()}
        >
          {packets.length ? 'Add packets' : 'Choose PDFs'}
        </Button>
        <Typography variant="body2" color="text.secondary" sx={{ minWidth: 0 }}>
          or drop one or more packets here
        </Typography>
        {packets.length > 0 && (
          <Button
            color="inherit"
            startIcon={<RestartAltIcon />}
            onClick={() => {
              if (window.confirm('Start a new review session? Current results will be cleared.')) {
                clearSession()
                setSelectedId(null)
              }
            }}
            sx={{ ml: 'auto' }}
          >
            New session
          </Button>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          hidden
          onChange={(e) => add(Array.from(e.target.files ?? []))}
        />
      </Paper>

      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

      {packets.length > 0 && (
        <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden', mb: 3 }}>
          <Box px={2} py={1.25} bgcolor="action.hover">
            <Box display="flex" alignItems="baseline" gap={1.5} flexWrap="wrap">
              <Typography variant="subtitle2" fontWeight={700}>
                Review session
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {finished} of {packets.length} checked
                {done.length > 0 &&
                  ` · ${withIssues} with issues · ${done.length - withIssues} tie out`}
              </Typography>
            </Box>
            {busy && (
              <LinearProgress
                variant="determinate"
                value={(finished / packets.length) * 100}
                sx={{ mt: 1, borderRadius: 1 }}
              />
            )}
          </Box>
          {packets.map((p) => (
            <PacketRow
              key={p.id}
              packet={p}
              selected={p.id === selected?.id}
              onSelect={() => setSelectedId(p.id)}
            />
          ))}
        </Paper>
      )}

      {selected?.report && (
        <ReportView key={selected.id} report={selected.report} evidence={selected.evidence} />
      )}
    </Box>
  )
}
