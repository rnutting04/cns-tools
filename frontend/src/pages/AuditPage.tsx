import { useCallback, useEffect, useMemo, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import MenuItem from '@mui/material/MenuItem'
import OutlinedInput from '@mui/material/OutlinedInput'
import Paper from '@mui/material/Paper'
import Select from '@mui/material/Select'
import Stack from '@mui/material/Stack'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import CloseIcon from '@mui/icons-material/Close'
import DownloadIcon from '@mui/icons-material/Download'
import FilterListIcon from '@mui/icons-material/FilterList'
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore'
import NavigateNextIcon from '@mui/icons-material/NavigateNext'
import SearchIcon from '@mui/icons-material/Search'
import apiClient from '../api/client'
import ErrorAlert from '../components/layout/ErrorAlert'
import type { AuditEvent, AuditPage } from '../types'

// ─── Action chip colours ──────────────────────────────────────────────────────

const ACTION_COLOR: Record<string, 'error' | 'warning' | 'info' | 'success' | 'default'> = {
  'auth.login_failed': 'error',
  'auth.login_blocked': 'error',
  'user.deactivated': 'warning',
  'user.role_changed': 'warning',
  'auth.login': 'success',
  'user.created': 'info',
  'user.password_changed': 'info',
  'user.updated': 'default',
}

function actionColor(action: string) {
  return ACTION_COLOR[action] ?? 'default'
}

// ─── Actor display ───────────────────────────────────────────────────────────

const FAILED_LOGIN_ACTIONS = new Set(['auth.login_failed', 'auth.login_blocked'])

function actorLabel(event: AuditEvent): string {
  if (event.actor_email) return event.actor_email
  if (FAILED_LOGIN_ACTIONS.has(event.action) && event.event_metadata?.email) {
    return `${event.event_metadata.email as string} (attempted)`
  }
  return '—'
}

// ─── Detail dialog ────────────────────────────────────────────────────────────

function DetailDialog({ event, onClose }: { event: AuditEvent; onClose: () => void }) {
  const rows: [string, string][] = [
    ['ID', event.id],
    ['Timestamp', new Date(event.created_at).toLocaleString()],
    ['Actor', actorLabel(event)],
    ['Actor ID', event.actor_user_id ?? '—'],
    ['Action', event.action],
    ['Target type', event.target_type ?? '—'],
    ['Target ID', event.target_id ?? '—'],
    ['User agent', event.user_agent ?? '—'],
  ]

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        Event detail
        <IconButton size="small" onClick={onClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        <Table size="small" sx={{ mb: 3 }}>
          <TableBody>
            {rows.map(([label, value]) => (
              <TableRow key={label}>
                <TableCell sx={{ width: 140, color: 'text.secondary', fontWeight: 500, whiteSpace: 'nowrap' }}>
                  {label}
                </TableCell>
                <TableCell sx={{ wordBreak: 'break-all' }}>{value}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <Typography variant="subtitle2" fontWeight={600} mb={1}>
          Metadata
        </Typography>
        <Box
          component="pre"
          sx={{
            m: 0,
            p: 2,
            bgcolor: 'grey.50',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            fontSize: 12,
            fontFamily: 'monospace',
            overflowX: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}
        >
          {JSON.stringify(event.event_metadata, null, 2)}
        </Box>
      </DialogContent>
    </Dialog>
  )
}

// ─── Filters bar ──────────────────────────────────────────────────────────────

interface Filters {
  search: string
  dateFrom: string
  dateTo: string
  actorEmail: string
  actions: string[]
}

const emptyFilters: Filters = {
  search: '',
  dateFrom: '',
  dateTo: '',
  actorEmail: '',
  actions: [],
}

interface FiltersBarProps {
  filters: Filters
  allActions: string[]
  onChange: (f: Filters) => void
  onApply: () => void
}

function FiltersBar({ filters, allActions, onChange, onApply }: FiltersBarProps) {
  function set<K extends keyof Filters>(key: K, value: Filters[K]) {
    onChange({ ...filters, [key]: value })
  }

  return (
    <Stack spacing={1.5} sx={{ mb: 2 }}>
      {/* Row 1: search */}
      <TextField
        placeholder="Search actor, action or target ID…"
        size="small"
        value={filters.search}
        onChange={(e) => set('search', e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && onApply()}
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          },
        }}
        sx={{ maxWidth: 480 }}
      />

      {/* Row 2: date range + actor email + action multi-select */}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} flexWrap="wrap">
        <TextField
          label="From"
          type="date"
          size="small"
          value={filters.dateFrom}
          onChange={(e) => set('dateFrom', e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ width: 180 }}
        />
        <TextField
          label="To"
          type="date"
          size="small"
          value={filters.dateTo}
          onChange={(e) => set('dateTo', e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ width: 180 }}
        />
        <TextField
          label="Actor email"
          size="small"
          value={filters.actorEmail}
          onChange={(e) => set('actorEmail', e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onApply()}
          sx={{ width: 220 }}
        />

        {allActions.length > 0 && (
          <Select
            multiple
            displayEmpty
            size="small"
            value={filters.actions}
            onChange={(e) => set('actions', e.target.value as string[])}
            input={<OutlinedInput />}
            renderValue={(selected) =>
              selected.length === 0 ? (
                <Typography variant="body2" color="text.disabled">
                  All actions
                </Typography>
              ) : (
                <Box display="flex" gap={0.5} flexWrap="wrap">
                  {(selected as string[]).map((v) => (
                    <Chip key={v} label={v} size="small" color={actionColor(v)} />
                  ))}
                </Box>
              )
            }
            sx={{ minWidth: 220, maxWidth: 400 }}
          >
            {allActions.map((a) => (
              <MenuItem key={a} value={a}>
                {a}
              </MenuItem>
            ))}
          </Select>
        )}

        <Button variant="outlined" size="small" startIcon={<FilterListIcon />} onClick={onApply}>
          Apply
        </Button>
        <Button
          size="small"
          onClick={() => {
            onChange(emptyFilters)
            onApply()
          }}
        >
          Clear
        </Button>
      </Stack>
    </Stack>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AuditPage() {
  const [data, setData] = useState<AuditPage | null>(null)
  const [allActions, setAllActions] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const [appliedFilters, setAppliedFilters] = useState<Filters>(emptyFilters)
  const [detailEvent, setDetailEvent] = useState<AuditEvent | null>(null)
  const [exporting, setExporting] = useState(false)

  // Build query string from applied filters
  const queryParams = useMemo(() => {
    const p = new URLSearchParams()
    p.set('page', String(page))
    if (appliedFilters.search) p.set('search', appliedFilters.search)
    if (appliedFilters.dateFrom) p.set('date_from', appliedFilters.dateFrom)
    if (appliedFilters.dateTo) p.set('date_to', appliedFilters.dateTo)
    if (appliedFilters.actorEmail) p.set('actor_email', appliedFilters.actorEmail)
    appliedFilters.actions.forEach((a) => p.append('actions', a))
    return p.toString()
  }, [page, appliedFilters])

  const fetchEvents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data: result } = await apiClient.get<AuditPage>(`/api/audit?${queryParams}`)
      setData(result)
    } catch {
      setError('Failed to load audit events.')
    } finally {
      setLoading(false)
    }
  }, [queryParams])

  useEffect(() => {
    apiClient.get<string[]>('/api/audit/actions').then(({ data }) => setAllActions(data)).catch(() => {})
  }, [])

  useEffect(() => {
    fetchEvents()
  }, [fetchEvents])

  function applyFilters() {
    setPage(1)
    setAppliedFilters(filters)
  }

  async function handleExport() {
    setExporting(true)
    try {
      const p = new URLSearchParams()
      if (appliedFilters.search) p.set('search', appliedFilters.search)
      if (appliedFilters.dateFrom) p.set('date_from', appliedFilters.dateFrom)
      if (appliedFilters.dateTo) p.set('date_to', appliedFilters.dateTo)
      if (appliedFilters.actorEmail) p.set('actor_email', appliedFilters.actorEmail)
      appliedFilters.actions.forEach((a) => p.append('actions', a))

      const response = await apiClient.get(`/api/audit/export?${p.toString()}`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(response.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'audit_export.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('Export failed.')
    } finally {
      setExporting(false)
    }
  }

  const rows = data?.items ?? []

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Audit log</Typography>
        <Tooltip title="Export current filters as CSV">
          <span>
            <Button
              variant="outlined"
              size="small"
              startIcon={exporting ? <CircularProgress size={14} color="inherit" /> : <DownloadIcon />}
              onClick={handleExport}
              disabled={exporting}
            >
              Export CSV
            </Button>
          </span>
        </Tooltip>
      </Box>

      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

      <FiltersBar
        filters={filters}
        allActions={allActions}
        onChange={setFilters}
        onApply={applyFilters}
      />

      {/* Table */}
      <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'grey.50' }}>
                <TableCell sx={{ fontWeight: 600 }}>Timestamp</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Actor</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Action</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Target</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 6 }}>
                    <CircularProgress size={28} />
                  </TableCell>
                </TableRow>
              ) : rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                    No events found.
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((event) => (
                  <TableRow
                    key={event.id}
                    hover
                    onClick={() => setDetailEvent(event)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell sx={{ whiteSpace: 'nowrap', color: 'text.secondary', fontSize: 13 }}>
                      {new Date(event.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell sx={{ fontSize: 13 }}>
                      {actorLabel(event)}
                    </TableCell>
                    <TableCell>
                      <Chip label={event.action} size="small" color={actionColor(event.action)} />
                    </TableCell>
                    <TableCell sx={{ fontSize: 13, color: 'text.secondary' }}>
                      {event.target_type && event.target_id
                        ? `${event.target_type} / ${event.target_id.slice(0, 8)}…`
                        : event.target_type ?? '—'}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Pagination */}
        {data && data.pages > 1 && (
          <>
            <Divider />
            <Box display="flex" justifyContent="space-between" alignItems="center" px={2} py={1}>
              <Typography variant="body2" color="text.secondary">
                {data.total} events · page {data.page} of {data.pages}
              </Typography>
              <Box display="flex" gap={0.5}>
                <IconButton size="small" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
                  <NavigateBeforeIcon fontSize="small" />
                </IconButton>
                <IconButton size="small" disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)}>
                  <NavigateNextIcon fontSize="small" />
                </IconButton>
              </Box>
            </Box>
          </>
        )}
      </Paper>

      {/* Detail dialog */}
      {detailEvent && <DetailDialog event={detailEvent} onClose={() => setDetailEvent(null)} />}
    </Box>
  )
}
