/**
 * Negative bank balances: any deposit account on each association's balance
 * sheet below zero. Associations whose accounts don't sum to Total Bank are
 * flagged too, since a misread sign could hide an overdraft.
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
import type { AccountingJobResult, BankBalance, NegativeBankSectionResult } from '../../types'
import { money } from './helpers'
import JobRunner from './JobRunner'
import { Shots } from './shared'

type Status = 'negative' | 'unbalanced' | 'ok' | 'problem'
type Filter = 'all' | 'flagged' | Status

const bankResult = (r: AccountingJobResult): NegativeBankSectionResult | null =>
  'problem' in r.result ? null : (r.result as NegativeBankSectionResult)

function statusOf(r: AccountingJobResult): Status {
  const v = bankResult(r)
  if (!v) return 'problem'
  if (v.accounts.some((a) => a.negative)) return 'negative'
  if (v.totals_ok === false) return 'unbalanced'
  return 'ok'
}

const STATUS: Record<Status, { label: string; color: 'error' | 'warning' | 'success' }> = {
  negative: { label: 'Negative balance', color: 'error' },
  unbalanced: { label: "Doesn't add up", color: 'warning' },
  ok: { label: 'No negatives', color: 'success' },
  problem: { label: "Couldn't read", color: 'warning' },
}

const COLUMNS: Record<string, string> = {
  operating: 'Operating',
  reserve: 'Reserve',
  total: 'Total',
}
const columnName = (c: string) => COLUMNS[c] ?? c.replace('fund', 'Fund ')

function AccountLine({ a }: { a: BankBalance }) {
  return (
    <TableRow sx={{ '& > td': { verticalAlign: 'top', borderBottomColor: 'divider' } }}>
      <TableCell>
        <Typography variant="body2" fontWeight={a.negative ? 600 : 400}>
          {a.label}
        </Typography>
        {a.notes.map((n) => (
          <Typography key={n} variant="caption" color="text.secondary" display="block">
            {n}
          </Typography>
        ))}
        <Shots shots={a.shots} />
      </TableCell>
      {(['operating', 'reserve', 'total'] as const).map((c) => {
        const amt = a.amounts[c]
        return (
          <TableCell
            key={c}
            align="right"
            sx={{
              fontVariantNumeric: 'tabular-nums',
              whiteSpace: 'nowrap',
              color: amt !== undefined && amt < 0 ? 'error.main' : undefined,
              fontWeight: amt !== undefined && amt < 0 ? 700 : undefined,
            }}
          >
            {amt === undefined ? '' : money(amt)}
          </TableCell>
        )
      })}
    </TableRow>
  )
}

function Row({ r }: { r: AccountingJobResult }) {
  const [open, setOpen] = useState(false)
  const v = bankResult(r)
  const status = statusOf(r)
  const accounts = v?.accounts ?? []
  const negatives = accounts.filter((a) => a.negative)
  const expandable = accounts.length > 0

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
            {r.first_page === r.last_page
              ? `page ${r.first_page}`
              : `pages ${r.first_page}–${r.last_page}`}
          </Typography>
        </TableCell>
        <TableCell sx={{ width: 170 }}>
          <Chip
            size="small"
            label={STATUS[status].label}
            color={STATUS[status].color}
            variant={status === 'ok' ? 'outlined' : 'filled'}
            sx={{ fontWeight: 600 }}
          />
        </TableCell>
        <TableCell>
          {!v ? (
            <Typography variant="body2" color="warning.main">
              {(r.result as { problem: string }).problem}
            </Typography>
          ) : negatives.length ? (
            negatives.map((a) => (
              <Typography key={a.label} variant="body2" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                {a.label} · <b>{money(a.amount)}</b>
              </Typography>
            ))
          ) : v.totals_ok === false ? (
            <Typography variant="body2" color="text.secondary">
              The bank accounts don’t add up to Total Bank, so a sign may have been misread. Check
              the bank section.
            </Typography>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {accounts.length} account{accounts.length === 1 ? '' : 's'}
              {v.totals_ok ? ', tied to Total Bank' : ''}
            </Typography>
          )}
        </TableCell>
        <TableCell sx={{ width: 40 }}>
          {expandable && (
            <IconButton size="small" aria-label={open ? 'Hide accounts' : 'Show accounts'}>
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
              <Box py={1.5} sx={{ overflowX: 'auto' }}>
                {v && v.totals_ok === false && (
                  <Box mb={1.5}>
                    {v.total_checks.map((c) => (
                      <Typography key={c} variant="caption" color="warning.main" display="block">
                        Didn’t add up: {c}
                      </Typography>
                    ))}
                    <Shots shots={v.shots} />
                  </Box>
                )}
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Account</TableCell>
                      {['operating', 'reserve', 'total'].map((c) => (
                        <TableCell key={c} align="right">
                          {columnName(c)}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {accounts.map((a, i) => (
                      <AccountLine key={`${a.label}-${i}`} a={a} />
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
      negative: 0,
      unbalanced: 0,
      ok: 0,
      problem: 0,
    }
    for (const r of results) {
      if (r.flagged) c.flagged++
      c[statusOf(r)]++
    }
    return c
  }, [results])

  const shown = results.filter((r) => {
    if (q && !r.association.toLowerCase().includes(q.toLowerCase())) return false
    if (filter === 'all') return true
    if (filter === 'flagged') return r.flagged
    return statusOf(r) === filter
  })

  if (!results.length) {
    return running ? (
      <Typography variant="body2" color="text.secondary">
        Results appear here as each association is finished.
      </Typography>
    ) : null
  }

  const FILTERS: [Filter, string][] = [
    ['flagged', `Needs attention ${counts.flagged}`],
    ['negative', `Negative ${counts.negative}`],
    ['unbalanced', `Doesn’t add up ${counts.unbalanced}`],
    ['problem', `Couldn't read ${counts.problem}`],
    ['ok', `No negatives ${counts.ok}`],
    ['all', `All ${counts.all}`],
  ]

  return (
    <>
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
              <TableCell>Status</TableCell>
              <TableCell>Details</TableCell>
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
    ['Association', 'Pages', 'Status', 'Account', 'Operating', 'Reserve', 'Total', 'Notes'],
  ]
  for (const r of results) {
    const pages = `${r.first_page}-${r.last_page}`
    const v = bankResult(r)
    const status = STATUS[statusOf(r)].label
    if (!v) {
      rows.push([
        r.association,
        pages,
        status,
        null,
        null,
        null,
        null,
        (r.result as { problem: string }).problem,
      ])
      continue
    }
    const listed = v.accounts.filter((a) => a.negative)
    if (!listed.length) {
      rows.push([r.association, pages, status, null, null, null, null, v.total_checks.join('; ')])
    }
    for (const a of listed) {
      rows.push([
        r.association,
        pages,
        status,
        a.label,
        a.amounts.operating ?? null,
        a.amounts.reserve ?? null,
        a.amounts.total ?? null,
        a.notes.join(' '),
      ])
    }
  }
  return rows
}

export default function NegativeBankTool() {
  return (
    <JobRunner
      tool="negative_bank"
      title="Negative bank balances"
      csvName="negative-bank-balances.csv"
      toCsv={toCsv}
      hint="The combined Balance Sheet for all associations — or a single association's"
      description="Checks every bank, CD and money market account on each association's balance sheet and flags any below zero. Also flags associations whose accounts don't add up to Total Bank, since a misread sign could hide an overdraft."
    >
      {(results, running) => <ResultsTable results={results} running={running} />}
    </JobRunner>
  )
}
