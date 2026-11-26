/**
 * CD maturity: every CD on each association's balance sheet, by how soon
 * it comes due. The date is read from the account name ("R-CD OZK 2/13/27").
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
import Typography from '@mui/material/Typography'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import type { AccountingJobResult, CdAccount, CdSectionResult, CdTier } from '../../types'
import { money } from './helpers'
import JobRunner from './JobRunner'
import { Shots } from './shared'

type ChipColor = 'error' | 'warning' | 'info' | 'success' | 'default'

const TIERS: Record<CdTier, { label: string; color: ChipColor; filled?: boolean }> = {
  matured: { label: 'Matured', color: 'error', filled: true },
  due_30: { label: 'Within 30 days', color: 'error' },
  due_60: { label: '31–60 days', color: 'warning' },
  due_90: { label: '61–90 days', color: 'info' },
  later: { label: 'Over 90 days', color: 'success' },
  no_date: { label: 'No date', color: 'warning', filled: true },
  investment: { label: 'Investment', color: 'default' },
}

const FLAGGED: CdTier[] = ['matured', 'due_30', 'due_60', 'due_90', 'no_date']

type Filter = 'all' | 'flagged' | CdTier | 'problems'

const cdResult = (r: AccountingJobResult): CdSectionResult | null =>
  'problem' in r.result ? null : (r.result as CdSectionResult)

/** "2027-02-13" → "2/13/2027", without a timezone shift. */
function usDate(iso: string | null): string {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-').map(Number)
  return `${m}/${d}/${y}`
}

function relative(days: number | null): string {
  if (days === null) return ''
  if (days === 0) return 'today'
  const n = Math.abs(days)
  const unit = `${n} day${n === 1 ? '' : 's'}`
  return days < 0 ? `${unit} ago` : `in ${unit}`
}

function TierChip({ tier }: { tier: CdTier }) {
  const t = TIERS[tier]
  return (
    <Chip
      size="small"
      label={t.label}
      color={t.color}
      variant={t.filled ? 'filled' : 'outlined'}
      sx={{ fontWeight: 600 }}
    />
  )
}

function CdLine({ cd }: { cd: CdAccount }) {
  const showNotes = cd.notes.length > 0 || cd.shots.length > 0
  return (
    <TableRow sx={{ '& > td': { verticalAlign: 'top', borderBottomColor: 'divider' } }}>
      <TableCell sx={{ width: 140 }}>
        <TierChip tier={cd.tier} />
      </TableCell>
      <TableCell>
        <Typography variant="body2">{cd.label}</Typography>
        {showNotes && (
          <>
            {cd.notes.map((n) => (
              <Typography key={n} variant="caption" color="text.secondary" display="block">
                {n}
              </Typography>
            ))}
            <Shots shots={cd.shots} />
          </>
        )}
      </TableCell>
      <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
        {money(cd.amount)}
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums' }}>
          {usDate(cd.maturity)}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {relative(cd.days)}
        </Typography>
      </TableCell>
    </TableRow>
  )
}

function Row({ r }: { r: AccountingJobResult }) {
  const [open, setOpen] = useState(false)
  const v = cdResult(r)
  const cds = v?.cds ?? []
  const flagged = cds.filter((c) => FLAGGED.includes(c.tier))
  const soonest = flagged[0] ?? cds.find((c) => c.tier === 'later')
  const total = cds.reduce((s, c) => s + c.amount, 0)
  const byTier = FLAGGED.map((t) => [t, flagged.filter((c) => c.tier === t).length] as const)

  return (
    <Fragment>
      <TableRow
        hover
        onClick={() => cds.length && setOpen((o) => !o)}
        sx={{ cursor: cds.length ? 'pointer' : 'default', '& > td': { verticalAlign: 'top' } }}
      >
        <TableCell>
          <Typography variant="body2" fontWeight={600}>
            {r.association}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {r.first_page === r.last_page
              ? `page ${r.first_page}`
              : `pages ${r.first_page}–${r.last_page}`}
          </Typography>
          {!v && (
            <Typography variant="caption" color="warning.main" display="block">
              {(r.result as { problem: string }).problem}
            </Typography>
          )}
        </TableCell>
        <TableCell>
          {soonest ? (
            <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
              <TierChip tier={soonest.tier} />
              <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                {soonest.maturity ? `${usDate(soonest.maturity)} · ${relative(soonest.days)}` : ''}
              </Typography>
            </Box>
          ) : v ? (
            <Typography variant="body2" color="text.secondary">
              {cds.length ? 'No dated CDs' : 'No CDs'}
            </Typography>
          ) : null}
        </TableCell>
        <TableCell>
          {cds.length > 0 && (
            <>
              <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                {cds.length} account{cds.length === 1 ? '' : 's'} · {money(total)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {byTier
                  .filter(([, n]) => n)
                  .map(([t, n]) => `${n} ${TIERS[t].label.toLowerCase()}`)
                  .join(' · ') || 'Nothing due within 90 days'}
              </Typography>
            </>
          )}
        </TableCell>
        <TableCell sx={{ width: 40 }}>
          {cds.length > 0 && (
            <IconButton size="small" aria-label={open ? 'Hide CDs' : 'Show CDs'}>
              <ExpandMoreIcon
                fontSize="small"
                sx={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}
              />
            </IconButton>
          )}
        </TableCell>
      </TableRow>
      {cds.length > 0 && (
        <TableRow>
          <TableCell colSpan={4} sx={{ py: 0, borderBottom: open ? undefined : 'none' }}>
            <Collapse in={open} unmountOnExit>
              <Box py={1.5} sx={{ overflowX: 'auto' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Status</TableCell>
                      <TableCell>Account</TableCell>
                      <TableCell align="right">Balance</TableCell>
                      <TableCell>Matures</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {cds.map((c, i) => (
                      <CdLine key={`${c.label}-${i}`} cd={c} />
                    ))}
                  </TableBody>
                </Table>
              </Box>
            </Collapse>
          </TableCell>
        </TableRow>
      )}
    </Fragment>
  )
}

function ResultsTable({ results, running }: { results: AccountingJobResult[]; running: boolean }) {
  const [filter, setFilter] = useState<Filter>('flagged')
  const [q, setQ] = useState('')

  const counts = useMemo(() => {
    const c: Record<Filter, number> = {
      all: results.length,
      flagged: 0,
      problems: 0,
      matured: 0,
      due_30: 0,
      due_60: 0,
      due_90: 0,
      later: 0,
      no_date: 0,
      investment: 0,
    }
    for (const r of results) {
      const v = cdResult(r)
      if (!v) {
        c.problems++
        continue
      }
      if (r.flagged) c.flagged++
      for (const t of new Set(v.cds.map((cd) => cd.tier))) c[t]++
    }
    return c
  }, [results])

  const shown = results.filter((r) => {
    if (q && !r.association.toLowerCase().includes(q.toLowerCase())) return false
    const v = cdResult(r)
    if (filter === 'all') return true
    if (filter === 'problems') return !v
    if (filter === 'flagged') return r.flagged
    return Boolean(v?.cds.some((c) => c.tier === filter))
  })

  if (!results.length) {
    return running ? (
      <Typography variant="body2" color="text.secondary">
        Results appear here as each association is finished.
      </Typography>
    ) : null
  }

  const asOf = results.map(cdResult).find(Boolean)?.as_of ?? null
  const FILTERS: [Filter, string][] = [
    ['flagged', `Needs attention ${counts.flagged}`],
    ['matured', `Matured ${counts.matured}`],
    ['due_30', `Within 30 days ${counts.due_30}`],
    ['due_60', `31–60 days ${counts.due_60}`],
    ['due_90', `61–90 days ${counts.due_90}`],
    ['no_date', `No date ${counts.no_date}`],
    ['problems', `Couldn't read ${counts.problems}`],
    ['all', `All ${counts.all}`],
  ]

  return (
    <>
      {asOf && (
        <Typography variant="body2" color="text.secondary" mb={1.5}>
          Days are counted from {usDate(asOf)}, the day this check ran.
        </Typography>
      )}
      <Box display="flex" gap={1} flexWrap="wrap" alignItems="center" mb={1.5}>
        {FILTERS.filter(([f]) => f === 'all' || f === 'flagged' || counts[f] > 0).map(
          ([f, label]) => (
            <Chip
              key={f}
              label={label}
              onClick={() => setFilter(f)}
              color={filter === f ? 'primary' : 'default'}
              variant={filter === f ? 'filled' : 'outlined'}
            />
          ),
        )}
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
              <TableCell>Soonest</TableCell>
              <TableCell>CDs</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {shown.map((r) => (
              <Row key={`${r.association}-${r.first_page}`} r={r} />
            ))}
          </TableBody>
        </Table>
        {!shown.length && (
          <Typography variant="body2" color="text.secondary" py={2}>
            No associations match.
          </Typography>
        )}
      </Box>
    </>
  )
}

function toCsv(results: AccountingJobResult[]) {
  const rows: (string | number | null)[][] = [
    ['Association', 'Pages', 'Account', 'Balance', 'Matures', 'Days left', 'Status', 'Notes'],
  ]
  for (const r of results) {
    const pages = `${r.first_page}-${r.last_page}`
    const v = cdResult(r)
    if (!v) {
      rows.push([
        r.association,
        pages,
        null,
        null,
        null,
        null,
        'Couldn’t read',
        (r.result as { problem: string }).problem,
      ])
      continue
    }
    for (const c of v.cds) {
      rows.push([
        r.association,
        pages,
        c.label,
        c.amount,
        c.maturity ? usDate(c.maturity) : null,
        c.days,
        TIERS[c.tier].label,
        c.notes.join(' '),
      ])
    }
  }
  return rows
}

export default function CdMaturityTool() {
  return (
    <JobRunner
      tool="cd_maturity"
      title="CD maturity"
      csvName="cd-maturity.csv"
      toCsv={toCsv}
      hint="The combined Balance Sheet for all associations — or a single association's"
      description="Lists every CD on each association's balance sheet by when it matures, reading the date from the account name. Flags CDs that have matured, mature within 90 days, or have no date."
    >
      {(results, running) => <ResultsTable results={results} running={running} />}
    </JobRunner>
  )
}
