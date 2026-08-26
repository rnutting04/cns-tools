import { useMemo, useState } from 'react'
import Alert from '@mui/material/Alert'
import AlertTitle from '@mui/material/AlertTitle'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Collapse from '@mui/material/Collapse'
import Divider from '@mui/material/Divider'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import TuneIcon from '@mui/icons-material/Tune'
import type { LayoutCorrections, LayoutReview } from '../../types'

const SECTION_LABELS: Record<string, string> = {
  REVENUE_OPERATING: 'Operating revenue',
  REVENUE_RESERVES: 'Reserve revenue',
  ADMINISTRATION: 'Administration',
  MAINTENANCE: 'Maintenance',
  UTILITIES: 'Utilities',
  OTHER: 'Other',
  RESERVES: 'Reserves',
}

const money = (n: number | null | undefined) =>
  n == null
    ? '—'
    : n.toLocaleString(undefined, {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
      })

/** Spreadsheet column letter for a 1-based index: 1 -> A, 27 -> AA. */
function columnLetter(index: number | null): string {
  if (index == null) return '—'
  let n = index
  let out = ''
  while (n > 0) {
    const rem = (n - 1) % 26
    out = String.fromCharCode(65 + rem) + out
    n = Math.floor((n - 1) / 26)
  }
  return out
}

function Fact({
  label,
  value,
  hint,
}: {
  label: string
  value: string
  hint?: string
}) {
  const body = (
    <Box minWidth={0}>
      <Typography variant="caption" color="text.secondary" display="block" noWrap>
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={600} noWrap>
        {value}
      </Typography>
    </Box>
  )
  return hint ? (
    <Tooltip title={hint} arrow>
      {body}
    </Tooltip>
  ) : (
    body
  )
}

interface Props {
  review: LayoutReview
  associationName: string
  priorBudgetFilename: string
  submitting?: boolean
  onConfirm: (corrections: LayoutCorrections | null) => void
}

/**
 * Shown before a budget is built, so a human can confirm the workbook was read
 * correctly.
 *
 * Everything the parser extracted is on screen: which sheet and columns it used,
 * the sections it found under the workbook's own headings, which row each
 * subtotal writes into, and every line item with its amount. The balance check
 * leads because it is the strongest single tell that a parse went wrong — a
 * mis-sectioned workbook almost never balances.
 *
 * Confirming stores the decision against the workbook's structural signature. In
 * this mode the panel appears on every run; when ALWAYS_CONFIRM_TEMPLATE is
 * switched off server-side, a stored confirmation covers every association
 * sharing that template instead.
 */
export default function LayoutReviewPanel({
  review,
  associationName,
  priorBudgetFilename,
  submitting = false,
  onConfirm,
}: Props) {
  const [adjusting, setAdjusting] = useState(false)
  const [sheet, setSheet] = useState(review.sheet_title)
  const [priorCol, setPriorCol] = useState<number | ''>(review.prior_col ?? '')
  const [showLines, setShowLines] = useState(false)

  const changed = sheet !== review.sheet_title || priorCol !== (review.prior_col ?? '')

  const corrections = useMemo<LayoutCorrections | null>(() => {
    if (!changed) return null
    const out: LayoutCorrections = {}
    if (sheet !== review.sheet_title) out.sheet_title = sheet
    if (priorCol !== '' && priorCol !== review.prior_col) out.prior_col = priorCol
    return out
  }, [changed, sheet, priorCol, review.sheet_title, review.prior_col])

  const difference = Math.abs(review.revenue_total - review.expense_total)

  // Sections are keyed "SECTION::Sheet Heading" in subtotal_rows.
  const subtotalRow = (s: LayoutReview['sections'][number]) =>
    review.subtotal_rows[
      s.source_section ? `${s.section}::${s.source_section}` : s.section
    ] ?? null

  return (
    <Paper variant="outlined" sx={{ p: 2.5, borderColor: 'warning.main' }}>
      <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
        <TuneIcon fontSize="small" color="warning" />
        <Typography variant="subtitle1" fontWeight={700}>
          Confirm how this workbook was read
        </Typography>
      </Stack>
      <Typography variant="body2" color="text.secondary" mb={2}>
        {associationName} — {priorBudgetFilename}. Below is everything the parser read out of
        this workbook. Check it against the spreadsheet before the budget is built on it.
      </Typography>

      {/* The balance check: the fastest signal that a parse is wrong. */}
      <Alert
        severity={review.balanced ? 'success' : 'error'}
        icon={review.balanced ? <CheckCircleIcon /> : <ErrorOutlineIcon />}
        sx={{ mb: 2 }}
      >
        <AlertTitle sx={{ mb: 0.25 }}>
          {review.balanced ? 'The budget balances' : "The budget doesn't balance"}
        </AlertTitle>
        <Typography variant="body2">
          Revenue {money(review.revenue_total)} vs expenses {money(review.expense_total)}
          {review.balanced
            ? ' — revenue and expenses agree, which is what a correctly read budget should do.'
            : ` — ${money(difference)} apart. That usually means a line landed in the wrong section, or the wrong column was read.`}
        </Typography>
      </Alert>

      {review.warnings.length > 0 ? (
        <Alert severity="warning" sx={{ mb: 2 }}>
          <AlertTitle sx={{ mb: 0.25 }}>Worth a closer look</AlertTitle>
          <Stack component="ul" sx={{ m: 0, pl: 2.5 }} spacing={0.5}>
            {review.warnings.map((w) => (
              <Typography component="li" variant="body2" key={w}>
                {w}
              </Typography>
            ))}
          </Stack>
        </Alert>
      ) : (
        // Most confirmations are routine. Say so plainly rather than leaving a
        // blank space that implies something is wrong.
        <Alert severity="info" sx={{ mb: 2 }}>
          <Typography variant="body2">
            No problems detected — the automated checks all passed. Confirm the figures below
            match the spreadsheet and the run will continue.
          </Typography>
        </Alert>
      )}

      {/* What was read. */}
      <Box
        display="grid"
        gridTemplateColumns={{ xs: '1fr 1fr', sm: 'repeat(4, 1fr)' }}
        gap={2}
        mb={2}
      >
        <Fact
          label="Sheet read"
          value={review.sheet_title}
          hint={`Workbook contains: ${review.all_sheets.join(', ')}`}
        />
        <Fact
          label="Prior-year column"
          value={
            review.prior_col
              ? `${columnLetter(review.prior_col)} — ${review.prior_col_header ?? 'unlabelled'}`
              : 'not found'
          }
          hint="The column holding last year's adopted budget amounts."
        />
        <Fact label="Line items" value={String(review.line_count)} />
        <Fact
          label="Reserve study"
          value={review.reserve_sheet ? `${review.reserve_items} items` : 'none in workbook'}
          hint={review.reserve_sheet ? `Read from sheet "${review.reserve_sheet}"` : undefined}
        />
        <Fact
          label="Projected column"
          value={
            review.projected_col
              ? `${columnLetter(review.projected_col)} — ${review.projected_col_header ?? 'unlabelled'}`
              : 'none'
          }
          hint="Annualised YTD actuals are written here."
        />
        <Fact
          label="New budget column"
          value={
            review.proposed_col
              ? `${columnLetter(review.proposed_col)} — ${review.proposed_col_header ?? 'unlabelled'}`
              : 'none'
          }
          hint="Left untouched for the manager to fill in."
        />
        <Fact
          label="Labels / GL codes"
          value={
            review.gl_col
              ? `${columnLetter(review.label_col)} / ${columnLetter(review.gl_col)}`
              : `${columnLetter(review.label_col)} (no GL column)`
          }
        />
        <Fact
          label="Notes column"
          value={review.notes_col ? columnLetter(review.notes_col) : 'none'}
          hint={
            review.notes_captured
              ? `${review.notes_captured} analyst notes carried across`
              : 'No comments column detected'
          }
        />
      </Box>

      {/* Every column the parser saw, so the reviewer can confirm nothing was
          picked up as a budget column that shouldn't have been. */}
      <Box mb={2}>
        <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
          All value columns found on this sheet
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {review.value_cols.map((c) => (
            <Chip
              key={c.col}
              size="small"
              variant={c.col === review.prior_col ? 'filled' : 'outlined'}
              color={c.col === review.prior_col ? 'primary' : 'default'}
              label={`${columnLetter(c.col)}: ${c.header} (${c.role})`}
            />
          ))}
        </Stack>
      </Box>

      <Divider sx={{ mb: 1.5 }} />

      {/* Section breakdown — compare these against the workbook's own subtotals. */}
      <Typography variant="caption" color="text.secondary" display="block" mb={1}>
        Sections read from the workbook — each keeps its own subtotal row, so these
        should match the subtotals printed in your spreadsheet line for line
      </Typography>
      <Stack spacing={0.5} mb={1}>
        {review.sections.map((s) => (
          <Box
            key={s.label}
            display="flex"
            alignItems="center"
            justifyContent="space-between"
            gap={1}
          >
            <Stack direction="row" spacing={1} alignItems="center" minWidth={0}>
              {/* The sheet's own heading leads, so the reviewer can compare
                  against Excel directly rather than translating our names. */}
              <Typography variant="body2" noWrap>
                {s.label}
              </Typography>
              {s.source_section && SECTION_LABELS[s.section] && (
                <Tooltip
                  title={`Treated as ${SECTION_LABELS[s.section]} for budget totals`}
                  arrow
                >
                  <Chip
                    label={SECTION_LABELS[s.section]}
                    size="small"
                    variant="outlined"
                    sx={{ opacity: 0.7 }}
                  />
                </Tooltip>
              )}
              <Chip label={`${s.count} lines`} size="small" variant="outlined" />
            </Stack>
            <Stack direction="row" spacing={1.5} alignItems="center">
              {subtotalRow(s) != null && (
                <Typography variant="caption" color="text.secondary">
                  subtotal → row {subtotalRow(s)}
                </Typography>
              )}
              <Typography variant="body2" fontWeight={600} fontFamily="ui-monospace, monospace">
                {money(s.total)}
              </Typography>
            </Stack>
          </Box>
        ))}
      </Stack>

      <Button
        size="small"
        onClick={() => setShowLines((v) => !v)}
        endIcon={
          <ExpandMoreIcon
            sx={{ transform: showLines ? 'rotate(180deg)' : 'none', transition: '.2s' }}
          />
        }
      >
        {showLines ? 'Hide' : 'Show'} all {review.line_count} line items
      </Button>
      <Collapse in={showLines}>
        <Box mt={1}>
          {review.sections.map((s) => (
            <Box key={s.label} mb={1.5}>
              <Typography variant="caption" color="text.secondary" fontWeight={700}>
                {s.label}
              </Typography>
              {s.sample.map((line, i) => (
                <Box
                  key={`${line.label}-${i}`}
                  display="flex"
                  justifyContent="space-between"
                  gap={2}
                  pl={1}
                >
                  <Typography variant="body2" color="text.secondary" noWrap>
                    {line.label}
                    {line.note ? ` — ${line.note}` : ''}
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    fontFamily="ui-monospace, monospace"
                  >
                    {money(line.amount)}
                  </Typography>
                </Box>
              ))}
            </Box>
          ))}
        </Box>
      </Collapse>

      {/* Corrections — deliberately behind a click; most reviews need no edits. */}
      <Collapse in={adjusting}>
        <Box
          mt={1.5}
          p={2}
          bgcolor="action.hover"
          borderRadius={1}
          display="grid"
          gridTemplateColumns={{ xs: '1fr', sm: '1fr 1fr' }}
          gap={2}
        >
          <TextField
            select
            size="small"
            label="Sheet to read"
            value={sheet}
            onChange={(e) => setSheet(e.target.value)}
            disabled={submitting}
          >
            {review.all_sheets.map((s) => (
              <MenuItem key={s} value={s}>
                {s}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Prior-year column"
            value={priorCol}
            onChange={(e) => setPriorCol(Number(e.target.value))}
            disabled={submitting}
            helperText="The column holding last year's adopted amounts"
          >
            {review.value_cols.map((c) => (
              <MenuItem key={c.col} value={c.col}>
                {columnLetter(c.col)} — {c.header} ({c.role})
              </MenuItem>
            ))}
          </TextField>
        </Box>
      </Collapse>

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} mt={2}>
        <Button
          variant="contained"
          onClick={() => onConfirm(corrections)}
          disabled={submitting}
          startIcon={
            submitting ? <CircularProgress size={16} color="inherit" /> : <CheckCircleIcon />
          }
        >
          {submitting
            ? 'Resuming…'
            : changed
              ? 'Save changes and continue'
              : 'Looks right — continue'}
        </Button>
        <Button
          variant="outlined"
          onClick={() => setAdjusting((v) => !v)}
          disabled={submitting}
          startIcon={<TuneIcon />}
        >
          {adjusting ? 'Cancel changes' : 'Change sheet or column'}
        </Button>
      </Stack>
    </Paper>
  )
}
