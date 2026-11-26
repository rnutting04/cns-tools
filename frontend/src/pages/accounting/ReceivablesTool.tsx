/**
 * AR & prepaid: ties each association's balance sheet Accounts Receivable
 * (1100) and Prepaid Member Assessments (2100) to the combined CSC AR Names
 * and CSC_Prepaid reports.
 */
import { Fragment, useMemo, useState } from 'react'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Collapse from '@mui/material/Collapse'
import IconButton from '@mui/material/IconButton'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import type {
  AccountingJobResult,
  FinancialCheckStatus,
  ReceivablesCheck,
  ReceivablesPages,
  ReceivablesRole,
  ReceivablesSectionResult,
  ReceivablesShot,
  ReceivablesSide,
  ReceivablesUnmatched,
} from '../../types'
import { money } from './helpers'
import JobRunner from './JobRunner'
import type { JobInput } from './JobRunner'

const INPUTS: JobInput[] = [
  {
    role: 'balance_sheet',
    label: 'Balance sheets',
    hint: 'Every association’s balance sheet in one PDF',
    required: true,
    match: /bal|balance/i,
  },
  {
    role: 'ar',
    label: 'AR report',
    hint: 'The combined CSC AR Names report',
    match: /(^|[^a-z])ar([^a-z]|$)|receivable|aging/i,
  },
  {
    role: 'prepaid',
    label: 'Prepaid report',
    hint: 'The combined CSC_Prepaid report',
    match: /prepaid/i,
  },
]

const FILE_LABEL: Record<ReceivablesRole, string> = {
  balance_sheet: 'Balance sheet',
  ar: 'AR',
  prepaid: 'Prepaid',
}

const STATUS: Record<
  FinancialCheckStatus,
  { label: string; color: 'success' | 'error' | 'warning' | 'default' }
> = {
  pass: { label: 'Matches', color: 'success' },
  fail: { label: 'Mismatch', color: 'error' },
  review: { label: 'Needs review', color: 'warning' },
  missing: { label: 'Report missing', color: 'warning' },
  not_applicable: { label: 'N/A', color: 'default' },
}

type Filter = 'all' | 'mismatch' | 'review' | 'unmatched' | 'na' | 'ok'

const matched = (r: AccountingJobResult): ReceivablesSectionResult | null =>
  'checks' in r.result ? (r.result as ReceivablesSectionResult) : null

const statuses = (r: AccountingJobResult): FinancialCheckStatus[] =>
  matched(r)?.checks.map((c) => c.status) ?? []

function category(r: AccountingJobResult): Exclude<Filter, 'all'> {
  if (!matched(r)) return 'unmatched'
  const s = statuses(r)
  if (s.includes('fail')) return 'mismatch'
  if (s.some((x) => x === 'review' || x === 'missing')) return 'review'
  if (s.includes('not_applicable')) return 'na'
  return 'ok'
}

function pagesText(pages: ReceivablesPages): string {
  return (Object.entries(pages) as [ReceivablesRole, number[] | null][])
    .filter(([, p]) => p)
    .map(([role, p]) => {
      const [a, b] = p as number[]
      return `${FILE_LABEL[role]} p.${a === b ? a : `${a}–${b}`}`
    })
    .join(' · ')
}

function Amount({ side }: { side: ReceivablesSide | null }) {
  if (!side || side.amount === null) {
    return (
      <Typography component="span" variant="body2" color="text.secondary">
        —
      </Typography>
    )
  }
  const doubt = side.guessed || side.verified === false
  const text = (
    <Typography
      component="span"
      variant="body2"
      sx={{
        fontVariantNumeric: 'tabular-nums',
        whiteSpace: 'nowrap',
        textDecoration: doubt ? 'underline dotted' : undefined,
      }}
    >
      {money(side.amount)}
    </Typography>
  )
  return doubt ? (
    <Tooltip
      title={
        side.guessed
          ? 'Best-guess read — confirm on the page'
          : 'The report’s own totals didn’t add up — possible OCR misread'
      }
    >
      {text}
    </Tooltip>
  ) : (
    text
  )
}

function CheckCell({ c }: { c: ReceivablesCheck | undefined }) {
  if (!c) return null
  const meta = STATUS[c.status]
  return (
    <Box>
      <Chip
        size="small"
        label={meta.label}
        color={meta.color}
        variant={c.status === 'pass' ? 'outlined' : 'filled'}
        sx={{ mb: 0.5 }}
      />
      {c.status === 'not_applicable' ? (
        <Typography variant="caption" color="text.secondary" display="block">
          {c.report
            ? 'Not on balance sheet · report total 0.00'
            : `${c.balance_sheet ? 'Zero' : 'Not'} on balance sheet · no report`}
        </Typography>
      ) : (
        <Typography variant="body2" color="text.secondary" component="div">
          BS <Amount side={c.balance_sheet} /> · report <Amount side={c.report} />
        </Typography>
      )}
      {c.difference !== null && Math.abs(c.difference) >= 0.005 && (
        <Typography variant="caption" color="error.main" display="block">
          Off by {money(Math.abs(c.difference))}
        </Typography>
      )}
    </Box>
  )
}

/** Highlighted strips of the pages, saved when the run read the PDFs. */
function Shots({ shots }: { shots: ReceivablesShot[] | undefined }) {
  if (!shots?.length) return null
  return (
    <Box display="flex" flexDirection="column" gap={1} mt={1}>
      {shots.map((s) => (
        <Box key={`${s.role}-${s.page}-${s.bbox.join(',')}`}>
          <Typography variant="caption" color="text.secondary" display="block" mb={0.25}>
            {s.caption}
          </Typography>
          {s.image ? (
            <Box
              component="img"
              src={s.image}
              alt={s.caption}
              sx={{
                display: 'block',
                maxWidth: '100%',
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
                bgcolor: '#fff',
              }}
            />
          ) : (
            <Typography variant="caption" color="text.secondary">
              (screenshot unavailable)
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  )
}

/** Why one check came out as it did: its notes, then the page regions. */
function CheckDetail({ c }: { c: ReceivablesCheck }) {
  const meta = STATUS[c.status]
  return (
    <Box mb={2}>
      <Box display="flex" alignItems="center" gap={1} mb={0.5}>
        <Typography variant="subtitle2">{c.title}</Typography>
        <Chip size="small" label={meta.label} color={meta.color} variant="outlined" />
      </Box>
      {c.notes.map((n) => (
        <Typography key={n} variant="body2" color="text.secondary">
          {n}
        </Typography>
      ))}
      <Shots shots={c.shots} />
    </Box>
  )
}

function Row({ r }: { r: AccountingJobResult }) {
  const [open, setOpen] = useState(false)
  const v = matched(r)
  const unmatched = v ? null : (r.result as ReceivablesUnmatched)
  const byId = (id: ReceivablesCheck['id']) => v?.checks.find((c) => c.id === id)
  // Passing checks only have something to say if they carry a note.
  const explained = v ? v.checks.filter((c) => c.status !== 'pass' || c.notes.length) : []
  const renamed = v ? (Object.entries(v.names) as [ReceivablesRole, string][]) : []
  const expandable = explained.length > 0 || renamed.length > 0 || Boolean(unmatched?.shots?.length)

  return (
    <Fragment>
      <TableRow
        hover
        onClick={() => expandable && setOpen((o) => !o)}
        sx={{ cursor: expandable ? 'pointer' : 'default', '& > td': { verticalAlign: 'top' } }}
      >
        <TableCell>
          <Typography variant="body2" fontWeight={600}>
            {r.association}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {pagesText((v ?? unmatched)?.pages ?? {})}
          </Typography>
          {unmatched && (
            <Typography variant="caption" color="warning.main" display="block">
              {unmatched.problem}
            </Typography>
          )}
        </TableCell>
        {v ? (
          <>
            <TableCell>
              <CheckCell c={byId('ar')} />
            </TableCell>
            <TableCell>
              <CheckCell c={byId('prepaid_assessments')} />
            </TableCell>
          </>
        ) : (
          <TableCell colSpan={2}>
            <Typography variant="body2" color="text.secondary">
              {(Object.entries(unmatched?.reports ?? {}) as [ReceivablesRole, ReceivablesSide][])
                .map(([role, s]) => `${FILE_LABEL[role]} report ${money(s?.amount)}`)
                .join(' · ')}
            </Typography>
          </TableCell>
        )}
        <TableCell sx={{ width: 40 }}>
          {expandable && (
            <IconButton size="small" aria-label={open ? 'Hide details' : 'Show details'}>
              <ExpandMoreIcon
                fontSize="small"
                sx={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}
              />
            </IconButton>
          )}
        </TableCell>
      </TableRow>
      {expandable && (
        <TableRow>
          <TableCell colSpan={4} sx={{ py: 0, borderBottom: open ? undefined : 'none' }}>
            <Collapse in={open} unmountOnExit>
              <Box py={1.5}>
                {renamed.map(([role, name]) => (
                  <Typography key={role} variant="body2" color="text.secondary" mb={1}>
                    Printed as “{name}” in the {FILE_LABEL[role]} report — paired by name; confirm
                    it’s the same association.
                  </Typography>
                ))}
                {explained.map((c) => (
                  <CheckDetail key={c.id} c={c} />
                ))}
                <Shots shots={unmatched?.shots} />
              </Box>
            </Collapse>
          </TableCell>
        </TableRow>
      )}
    </Fragment>
  )
}

function ResultsTable({ results, running }: { results: AccountingJobResult[]; running: boolean }) {
  const [filter, setFilter] = useState<Filter>('all')
  const [q, setQ] = useState('')

  const counts = useMemo(() => {
    const c: Record<Filter, number> = {
      all: results.length,
      mismatch: 0,
      review: 0,
      unmatched: 0,
      na: 0,
      ok: 0,
    }
    for (const r of results) c[category(r)]++
    return c
  }, [results])

  if (!results.length) {
    return running ? (
      <Typography variant="body2" color="text.secondary">
        Each file is read first; associations appear here once all of them are done.
      </Typography>
    ) : null
  }

  const shown = results.filter(
    (r) =>
      (!q || r.association.toLowerCase().includes(q.toLowerCase())) &&
      (filter === 'all' || category(r) === filter),
  )

  const FILTERS: [Filter, string, 'error' | 'warning' | 'default'][] = [
    ['all', `All ${counts.all}`, 'default'],
    ['mismatch', `Mismatch ${counts.mismatch}`, 'error'],
    ['review', `Needs review ${counts.review}`, 'warning'],
    ['unmatched', `No balance sheet match ${counts.unmatched}`, 'warning'],
    ['na', `N/A ${counts.na}`, 'default'],
    ['ok', `Matches ${counts.ok}`, 'default'],
  ]

  return (
    <>
      <Box display="flex" gap={1} flexWrap="wrap" alignItems="center" mb={1.5}>
        {FILTERS.map(([f, label, color]) => (
          <Chip
            key={f}
            label={label}
            onClick={() => setFilter(f)}
            color={filter === f ? 'primary' : counts[f] && f !== 'all' ? color : 'default'}
            variant={filter === f ? 'filled' : 'outlined'}
          />
        ))}
        <TextField
          size="small"
          placeholder="Find association"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          sx={{ ml: { sm: 'auto' }, minWidth: 200 }}
        />
      </Box>
      <Box sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Association</TableCell>
              <TableCell>Accounts Receivable (1100)</TableCell>
              <TableCell>Prepaid Assessments (2100)</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {shown.map((r) => (
              <Row key={`${r.association}-${r.first_page}`} r={r} />
            ))}
          </TableBody>
        </Table>
      </Box>
    </>
  )
}

function pagesCsv(pages: ReceivablesPages, role: ReceivablesRole): string {
  const p = pages[role]
  return p ? (p[0] === p[1] ? `${p[0]}` : `${p[0]}-${p[1]}`) : ''
}

function toCsv(results: AccountingJobResult[]) {
  const rows: (string | number | null)[][] = [
    [
      'Association',
      'Balance sheet pages',
      'AR pages',
      'Prepaid pages',
      'AR (1100) balance sheet',
      'AR report',
      'AR difference',
      'AR status',
      'Prepaid (2100) balance sheet',
      'Prepaid report',
      'Prepaid difference',
      'Prepaid status',
      'Notes',
    ],
  ]
  for (const r of results) {
    const v = matched(r)
    const u = v ? null : (r.result as ReceivablesUnmatched)
    const pages = (v ?? u)?.pages ?? {}
    const check = (id: ReceivablesCheck['id']) => v?.checks.find((c) => c.id === id)
    const cols = (c: ReceivablesCheck | undefined, role: ReceivablesRole) =>
      c
        ? [
            c.balance_sheet?.amount ?? null,
            c.report?.amount ?? null,
            c.difference,
            STATUS[c.status].label,
          ]
        : [null, u?.reports?.[role]?.amount ?? null, null, u ? 'No balance sheet match' : null]
    rows.push([
      r.association,
      pagesCsv(pages, 'balance_sheet'),
      pagesCsv(pages, 'ar'),
      pagesCsv(pages, 'prepaid'),
      ...cols(check('ar'), 'ar'),
      ...cols(check('prepaid_assessments'), 'prepaid'),
      v ? v.checks.flatMap((c) => c.notes).join(' ') : (u?.problem ?? ''),
    ])
  }
  return rows
}

export default function ReceivablesTool() {
  return (
    <JobRunner
      tool="receivables"
      title="AR & prepaid"
      csvName="ar-prepaid.csv"
      toCsv={toCsv}
      inputs={INPUTS}
      minFiles={2}
      description="Ties every association’s Accounts Receivable (1100) and Prepaid Member Assessments (2100) on the balance sheet to the combined AR and prepaid reports. Associations are paired by name across the files."
    >
      {(results, running) => <ResultsTable results={results} running={running} />}
    </JobRunner>
  )
}
