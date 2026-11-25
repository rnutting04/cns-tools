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
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import type { AccountingJobResult, FdicAccount, FdicSectionResult } from '../../types'
import { money } from './helpers'
import JobRunner from './JobRunner'

type Filter = 'all' | 'over' | 'unknown' | 'problems'

const fdic = (r: AccountingJobResult): FdicSectionResult | null =>
  'problem' in r.result ? null : (r.result as FdicSectionResult)

function AccountLine({ a }: { a: FdicAccount }) {
  const doubt = a.source.verified === false
  return (
    <Box display="flex" justifyContent="space-between" gap={2}>
      <Typography variant="body2" color="text.secondary">
        {a.label}
        {a.network && (
          <Chip
            size="small"
            variant="outlined"
            label="ICS/CDARS"
            sx={{ ml: 1, height: 18, fontSize: 11 }}
          />
        )}
        {doubt && (
          <Tooltip title="The balance sheet's own totals didn't add up on this row — possible OCR misread">
            <ErrorOutlineIcon
              sx={{ fontSize: 15, color: 'warning.main', ml: 0.5, verticalAlign: 'middle' }}
            />
          </Tooltip>
        )}
      </Typography>
      <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
        {money(a.amount)}
      </Typography>
    </Box>
  )
}

function Row({ r }: { r: AccountingJobResult }) {
  const [open, setOpen] = useState(false)
  const v = fdic(r)
  const over = v?.institutions.filter((i) => i.over_limit) ?? []
  return (
    <Fragment>
      <TableRow
        hover
        onClick={() => v && setOpen((o) => !o)}
        sx={{ cursor: v ? 'pointer' : 'default' }}
      >
        <TableCell sx={{ verticalAlign: 'top' }}>
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
        <TableCell sx={{ verticalAlign: 'top' }}>
          {over.length ? (
            <Box display="flex" gap={0.75} flexWrap="wrap">
              {over.map((i) => (
                <Chip
                  key={i.name}
                  size="small"
                  color="warning"
                  label={`${i.name} ${money(i.total)}`}
                />
              ))}
            </Box>
          ) : v ? (
            <Typography variant="body2" color="text.secondary">
              —
            </Typography>
          ) : null}
        </TableCell>
        <TableCell sx={{ verticalAlign: 'top' }}>
          {v && (
            <Typography variant="body2" color="text.secondary">
              {v.institutions.map((i) => `${i.name} ${money(i.total)}`).join(' · ') ||
                'No deposits found'}
            </Typography>
          )}
          {v && v.unrecognized.length > 0 && (
            <Typography variant="caption" color="warning.main" display="block">
              {v.unrecognized.length} account{v.unrecognized.length === 1 ? '' : 's'} at an
              unrecognized bank
            </Typography>
          )}
        </TableCell>
        <TableCell sx={{ verticalAlign: 'top', width: 40 }}>
          {v && (
            <IconButton size="small" aria-label={open ? 'Hide accounts' : 'Show accounts'}>
              <ExpandMoreIcon
                fontSize="small"
                sx={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}
              />
            </IconButton>
          )}
        </TableCell>
      </TableRow>
      {v && (
        <TableRow>
          <TableCell colSpan={4} sx={{ py: 0, borderBottom: open ? undefined : 'none' }}>
            <Collapse in={open} unmountOnExit>
              <Box
                py={1.5}
                display="grid"
                gap={1.5}
                gridTemplateColumns={{ md: 'repeat(2, minmax(0, 1fr))' }}
              >
                {v.institutions.map((i) => (
                  <Box key={i.name}>
                    <Box display="flex" justifyContent="space-between" mb={0.25}>
                      <Typography variant="body2" fontWeight={700}>
                        {i.name}
                      </Typography>
                      <Typography
                        variant="body2"
                        fontWeight={700}
                        color={i.over_limit ? 'warning.main' : undefined}
                        sx={{ fontVariantNumeric: 'tabular-nums' }}
                      >
                        {money(i.total)}
                      </Typography>
                    </Box>
                    {i.accounts.map((a) => (
                      <AccountLine key={a.label} a={a} />
                    ))}
                    {i.notes.map((n) => (
                      <Typography key={n} variant="caption" color="text.secondary" display="block">
                        {n}
                      </Typography>
                    ))}
                  </Box>
                ))}
                {v.unrecognized.length > 0 && (
                  <Box>
                    <Typography variant="body2" fontWeight={700} color="warning.main">
                      Bank not recognized (not in totals)
                    </Typography>
                    {v.unrecognized.map((a) => (
                      <AccountLine key={a.label} a={a} />
                    ))}
                  </Box>
                )}
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
    const c = { all: results.length, over: 0, unknown: 0, problems: 0 }
    for (const r of results) {
      const v = fdic(r)
      if (!v) c.problems++
      else {
        if (v.institutions.some((i) => i.over_limit)) c.over++
        if (v.unrecognized.length) c.unknown++
      }
    }
    return c
  }, [results])

  const shown = results.filter((r) => {
    if (q && !r.association.toLowerCase().includes(q.toLowerCase())) return false
    const v = fdic(r)
    if (filter === 'problems') return !v
    if (filter === 'over') return Boolean(v?.institutions.some((i) => i.over_limit))
    if (filter === 'unknown') return Boolean(v?.unrecognized.length)
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
    ['over', `$250k or more at a bank ${counts.over}`],
    ['unknown', `Unrecognized bank ${counts.unknown}`],
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
            color={filter === f ? 'primary' : f === 'over' && counts.over ? 'warning' : 'default'}
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
              <TableCell>At or over $250,000</TableCell>
              <TableCell>All banks</TableCell>
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

function toCsv(results: AccountingJobResult[]) {
  const rows: (string | number | null)[][] = [
    ['Association', 'Pages', 'Bank', 'Total at bank', 'At or over $250k', 'Accounts', 'Notes'],
  ]
  for (const r of results) {
    const pages = `${r.first_page}-${r.last_page}`
    const v = fdic(r)
    if (!v) {
      rows.push([
        r.association,
        pages,
        null,
        null,
        null,
        null,
        (r.result as { problem: string }).problem,
      ])
      continue
    }
    for (const i of v.institutions) {
      rows.push([
        r.association,
        pages,
        i.name,
        i.total,
        i.over_limit ? 'Yes' : 'No',
        i.accounts.map((a) => `${a.label} (${money(a.amount)})`).join('; '),
        i.notes.join(' '),
      ])
    }
    for (const a of v.unrecognized) {
      rows.push([
        r.association,
        pages,
        'Unrecognized',
        a.amount,
        null,
        a.label,
        'Bank not recognized',
      ])
    }
  }
  return rows
}

export default function FdicTool() {
  return (
    <JobRunner
      tool="fdic"
      title="FDIC exposure"
      csvName="fdic-exposure.csv"
      toCsv={toCsv}
      hint="The combined Balance Sheet for all associations — or a single association's"
      description="Adds up every association's bank and CD balances at each bank from its balance sheet and flags any bank holding $250,000 or more."
    >
      {(results, running) => <ResultsTable results={results} running={running} />}
    </JobRunner>
  )
}
