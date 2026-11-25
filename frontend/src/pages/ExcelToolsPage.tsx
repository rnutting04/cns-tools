import { useMemo, useRef, useState } from 'react'
import type { DragEvent } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Paper from '@mui/material/Paper'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Typography from '@mui/material/Typography'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import axios from 'axios'
import apiClient from '../api/client'
import ErrorAlert from '../components/layout/ErrorAlert'
import type { ReserveScheduleIssue, ReserveScheduleReport } from '../types'
import { ToolHeader } from './accounting/shared'

const money = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
function fmt(n: number | null): string {
  if (n === null) return '—'
  return n < 0 ? `(${money.format(-n)})` : money.format(n)
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

/** Flagged items for one association (one workbook tab). */
function AssociationIssues({ sheet, issues }: { sheet: string; issues: ReserveScheduleIssue[] }) {
  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden', mb: 2 }}>
      <Box
        display="flex"
        alignItems="center"
        gap={1}
        px={2}
        py={1.25}
        bgcolor="action.hover"
        flexWrap="wrap"
      >
        <Typography variant="subtitle1" fontWeight={700}>
          {sheet}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          association tab
        </Typography>
        <Chip
          size="small"
          color="error"
          label={plural(issues.length, 'flagged item')}
          sx={{ ml: 'auto' }}
        />
      </Box>
      <Box sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Code</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Cell</TableCell>
              <TableCell align="right">Balance</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {issues.map((i) => (
              <TableRow key={i.cell}>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{i.code || '—'}</TableCell>
                <TableCell>
                  {i.description}
                  {i.group && (
                    <Typography variant="caption" color="text.secondary" display="block">
                      {i.group}
                    </Typography>
                  )}
                </TableCell>
                <TableCell sx={{ fontFamily: 'monospace' }}>{i.cell}</TableCell>
                <TableCell
                  align="right"
                  sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}
                >
                  {i.problem === 'negative' ? (
                    <Typography variant="body2" color="error.main" component="span">
                      {fmt(i.balance)}
                    </Typography>
                  ) : (
                    <Chip size="small" color="warning" label="Not a number" />
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </Paper>
  )
}

function ReserveScheduleCheck() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [report, setReport] = useState<ReserveScheduleReport | null>(null)
  const [running, setRunning] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  const run = async (file: File) => {
    if (!/\.xls[xm]$/i.test(file.name)) {
      setError('Choose an .xlsx workbook.')
      return
    }
    setRunning(file.name)
    setError(null)
    setReport(null)
    const form = new FormData()
    form.append('workbook', file)
    try {
      const res = await apiClient.post<ReserveScheduleReport>(
        '/api/excel/reserve-schedule/check',
        form,
        { timeout: 60_000 },
      )
      setReport(res.data)
    } catch (e) {
      const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
      setError(typeof detail === 'string' ? detail : 'Could not check this workbook. Try again.')
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

  // Issues grouped by association, in workbook tab order.
  const byAssociation = useMemo(() => {
    const groups = new Map<string, ReserveScheduleIssue[]>()
    for (const i of report?.issues ?? []) {
      groups.set(i.sheet, [...(groups.get(i.sheet) ?? []), i])
    }
    return [...groups.entries()]
  }, [report])

  const unchecked = report?.sheets.filter((s) => !s.checked) ?? []
  const negatives = report?.issues.filter((i) => i.problem === 'negative').length ?? 0
  const nonNumbers = (report?.issues.length ?? 0) - negatives

  return (
    <Box>
      <ToolHeader title="Reserve schedule">
        Checks every association tab of the MASS Reserve Schedule workbook. No reserve
        component&apos;s Balance can be negative (totals aren&apos;t checked).
      </ToolHeader>

      <Box
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        sx={{
          p: 2,
          mb: 2,
          border: 1,
          borderRadius: 2,
          borderStyle: 'dashed',
          borderColor: dragging ? 'primary.main' : 'divider',
          bgcolor: dragging ? 'action.hover' : 'transparent',
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
          {running ? 'Checking…' : 'Choose workbook'}
        </Button>
        <Typography variant="body2" color="text.secondary" sx={{ minWidth: 0 }} noWrap>
          {running ? `Reading ${running}` : 'or drop the .xlsx here'}
        </Typography>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void run(f)
          }}
        />
      </Box>

      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

      {report && (
        <>
          <Box display="flex" alignItems="baseline" gap={1} mb={1.5} flexWrap="wrap">
            <Typography variant="subtitle1" fontWeight={600} sx={{ wordBreak: 'break-all' }}>
              {report.filename}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {plural(report.sheet_count, 'association')} · {plural(report.line_items, 'line item')}
            </Typography>
          </Box>

          {report.issues.length === 0 ? (
            <Alert severity="success" sx={{ mb: 2 }}>
              No negative balances.
            </Alert>
          ) : (
            <Alert severity="error" sx={{ mb: 2 }}>
              {[
                negatives > 0 && `${plural(negatives, 'negative balance')}`,
                nonNumbers > 0 && `${plural(nonNumbers, 'balance')} that aren't numbers`,
              ]
                .filter(Boolean)
                .join(' · ')}{' '}
              across {plural(byAssociation.length, 'association')}:{' '}
              {byAssociation.map(([sheet]) => sheet).join(', ')}
            </Alert>
          )}

          {unchecked.length > 0 && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Couldn&apos;t find the Balance header on {unchecked.map((s) => s.name).join(', ')}, so{' '}
              {unchecked.length === 1 ? 'that tab was' : 'those tabs were'} not checked.
            </Alert>
          )}

          {byAssociation.map(([sheet, issues]) => (
            <AssociationIssues key={sheet} sheet={sheet} issues={issues} />
          ))}
        </>
      )}
    </Box>
  )
}

/** Accounting tools → Reserve schedule (MASS workbook check). */
export default ReserveScheduleCheck
