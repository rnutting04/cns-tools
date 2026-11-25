import { useMemo, useState } from 'react'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import type {
  AccountingJobResult,
  ReportTier,
  RevenueBasis,
  RevenueSectionResult,
} from '../../types'
import { money } from './helpers'
import JobRunner from './JobRunner'

const TIER: Record<
  ReportTier,
  { label: string; color: 'default' | 'info' | 'warning' | 'primary'; range: string }
> = {
  none: { label: 'None needed', color: 'default', range: 'Under $150,000' },
  compilation: { label: 'Compilation', color: 'info', range: '$150,000 – $299,999' },
  review: { label: 'Review', color: 'warning', range: '$300,000 – $499,999' },
  audit: { label: 'Audit', color: 'primary', range: '$500,000 and over' },
}

type Filter = 'all' | 'needs' | 'differ' | 'problems'

const revenue = (r: AccountingJobResult): RevenueSectionResult | null =>
  'problem' in r.result ? null : (r.result as RevenueSectionResult)

function TierChip({ tier }: { tier: ReportTier | null }) {
  if (!tier) return <Chip size="small" variant="outlined" label="Couldn't read" />
  return <Chip size="small" color={TIER[tier].color} label={TIER[tier].label} />
}

/** Notes for one basis: unread figures, best guesses, reserve missing. */
function doubts(b: RevenueBasis): string[] {
  const out = [...b.notes]
  for (const f of [b.operating, b.reserve]) {
    if (f && f.verified === false) out.push(`${f.label}: report's own totals didn't add up`)
  }
  return out
}

function Amount({ basis }: { basis: RevenueBasis }) {
  return (
    <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
      {money(basis.total)}
    </Typography>
  )
}

function ResultsTable({ results, running }: { results: AccountingJobResult[]; running: boolean }) {
  const [filter, setFilter] = useState<Filter>('all')
  const [q, setQ] = useState('')

  const counts = useMemo(() => {
    const c = { all: results.length, needs: 0, differ: 0, problems: 0 }
    for (const r of results) {
      const v = revenue(r)
      if (!v) c.problems++
      else {
        if (v.ytd_actual.tier && v.ytd_actual.tier !== 'none') c.needs++
        if (v.ytd_actual.tier !== v.annual.tier) c.differ++
      }
    }
    return c
  }, [results])

  const shown = results.filter((r) => {
    if (q && !r.association.toLowerCase().includes(q.toLowerCase())) return false
    const v = revenue(r)
    if (filter === 'problems') return !v
    if (filter === 'needs') return Boolean(v?.ytd_actual.tier && v.ytd_actual.tier !== 'none')
    if (filter === 'differ') return Boolean(v && v.ytd_actual.tier !== v.annual.tier)
    return true
  })

  if (!results.length) {
    return running ? (
      <Typography variant="body2" color="text.secondary">
        Results appear here as each association is finished.
      </Typography>
    ) : null
  }

  const FILTERS: [Filter, string][] = [
    ['all', `All ${counts.all}`],
    ['needs', `Needs a report ${counts.needs}`],
    ['differ', `YTD and annual differ ${counts.differ}`],
    ['problems', `Needs a person ${counts.problems}`],
  ]

  return (
    <>
      <Box display="flex" gap={1} flexWrap="wrap" alignItems="center" mb={1.5}>
        {FILTERS.map(([f, label]) => (
          <Chip
            key={f}
            label={label}
            onClick={() => setFilter(f)}
            color={
              filter === f ? 'primary' : f === 'problems' && counts.problems ? 'warning' : 'default'
            }
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
              <TableCell align="right">YTD actual revenues</TableCell>
              <TableCell>Report (YTD)</TableCell>
              <TableCell align="right">Annual revenues</TableCell>
              <TableCell>Report (annual)</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {shown.map((r) => {
              const v = revenue(r)
              const notes = v ? [...new Set([...doubts(v.ytd_actual), ...doubts(v.annual)])] : []
              return (
                <TableRow key={`${r.association}-${r.first_page}`} hover>
                  <TableCell>
                    <Box display="flex" alignItems="center" gap={0.75}>
                      <Typography variant="body2" fontWeight={600}>
                        {r.association}
                      </Typography>
                      {notes.length > 0 && (
                        <Tooltip title={notes.join(' · ')}>
                          <ErrorOutlineIcon sx={{ fontSize: 16, color: 'warning.main' }} />
                        </Tooltip>
                      )}
                    </Box>
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
                  {v ? (
                    <>
                      <TableCell align="right">
                        <Amount basis={v.ytd_actual} />
                      </TableCell>
                      <TableCell>
                        <TierChip tier={v.ytd_actual.tier} />
                      </TableCell>
                      <TableCell align="right">
                        <Amount basis={v.annual} />
                      </TableCell>
                      <TableCell>
                        <TierChip tier={v.annual.tier} />
                      </TableCell>
                    </>
                  ) : (
                    <TableCell colSpan={4} />
                  )}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </Box>
    </>
  )
}

function toCsv(results: AccountingJobResult[]) {
  const rows: (string | number | null)[][] = [
    [
      'Association',
      'Pages',
      'YTD operating revenues',
      'YTD reserve revenues',
      'YTD total revenues',
      'Report needed (YTD)',
      'Annual operating revenues',
      'Annual reserve revenues',
      'Annual total revenues',
      'Report needed (annual)',
      'Notes',
    ],
  ]
  const tier = (t: ReportTier | null) => (t ? TIER[t].label : "Couldn't read")
  for (const r of results) {
    const pages = `${r.first_page}-${r.last_page}`
    const v = revenue(r)
    if (!v) {
      const problem = (r.result as { problem: string }).problem
      rows.push([r.association, pages, null, null, null, null, null, null, null, null, problem])
      continue
    }
    rows.push([
      r.association,
      pages,
      v.ytd_actual.operating?.amount ?? null,
      v.ytd_actual.reserve?.amount ?? null,
      v.ytd_actual.total,
      tier(v.ytd_actual.tier),
      v.annual.operating?.amount ?? null,
      v.annual.reserve?.amount ?? null,
      v.annual.total,
      tier(v.annual.tier),
      [...new Set([...doubts(v.ytd_actual), ...doubts(v.annual)])].join('; '),
    ])
  }
  return rows
}

export default function RevenueThresholdTool() {
  const legend = (Object.keys(TIER) as ReportTier[])
    .map((t) => `${TIER[t].range}: ${TIER[t].label}`)
    .join(' · ')
  return (
    <JobRunner
      tool="revenue_threshold"
      title="Audit threshold"
      csvName="audit-threshold.csv"
      toCsv={toCsv}
      hint="The combined Income & Expense report for all associations — or a single association's"
      description={
        <>
          Adds operating and reserve TOTAL REVENUES for every association and shows which year-end
          report it needs, by year-to-date actual and by the annual budget. {legend}.
        </>
      }
    >
      {(results, running) => <ResultsTable results={results} running={running} />}
    </JobRunner>
  )
}
