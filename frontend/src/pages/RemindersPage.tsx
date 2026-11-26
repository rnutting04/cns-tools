/**
 * Reminders: scheduled emails to staff ("mailing day is Thursday"). Admins
 * only for now. Reminders live in the database; the server checks every few
 * minutes for ones that are due and sends them.
 */
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Collapse from '@mui/material/Collapse'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Skeleton from '@mui/material/Skeleton'
import Switch from '@mui/material/Switch'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import EditIcon from '@mui/icons-material/Edit'
import HistoryIcon from '@mui/icons-material/History'
import SendIcon from '@mui/icons-material/Send'
import { toast } from 'sonner'
import apiClient from '../api/client'
import { fetchReminders, queryKeys } from '../api/queries'
import ConfirmDialog from '../components/layout/ConfrimDialog'
import ErrorAlert from '../components/layout/ErrorAlert'
import ReminderDialog from '../components/reminders/ReminderDialog'
import { apiError, etDateTime, longDate } from '../components/reminders/format'
import type { Reminder, ReminderDelivery } from '../types'

function status(r: Reminder): { label: string; color: 'success' | 'default' | 'warning' } {
  if (r.next_send_at) return { label: 'On', color: 'success' }
  if (!r.active && r.repeat === 'none' && r.last_sent_at) return { label: 'Sent', color: 'default' }
  return { label: 'Paused', color: 'warning' }
}

function History({ id }: { id: string }) {
  const { data, isLoading } = useQuery({
    queryKey: [...queryKeys.reminders, id, 'deliveries'],
    queryFn: async () =>
      (await apiClient.get<ReminderDelivery[]>(`/api/reminders/${id}/deliveries`)).data,
  })
  if (isLoading) return <Skeleton width="60%" />
  if (!data?.length)
    return (
      <Typography variant="body2" color="text.secondary">
        Nothing sent yet.
      </Typography>
    )
  // One line per occurrence: "Thu, Dec 25, 2026 — sent Mon, Dec 22, 8:00 AM ET to 3 people"
  const byEvent = new Map<string, ReminderDelivery[]>()
  for (const d of data) byEvent.set(d.event_date, [...(byEvent.get(d.event_date) ?? []), d])
  return (
    <Box display="flex" flexDirection="column" gap={0.5}>
      {[...byEvent.entries()].map(([event, ds]) => (
        <Typography key={event} variant="body2" color="text.secondary">
          <strong>{longDate(event)}</strong> · sent {etDateTime(ds[0].sent_at)} to{' '}
          <Tooltip title={ds.map((d) => d.recipient).join(', ')}>
            <span style={{ textDecoration: 'underline dotted' }}>
              {ds.length} {ds.length === 1 ? 'person' : 'people'}
            </span>
          </Tooltip>
        </Typography>
      ))}
    </Box>
  )
}

interface RowProps {
  r: Reminder
  onEdit: () => void
  onDelete: () => void
  onToggle: (active: boolean) => void
  onTest: () => void
  busy: boolean
}

function ReminderRow({ r, onEdit, onDelete, onToggle, onTest, busy }: RowProps) {
  const [showHistory, setShowHistory] = useState(false)
  const s = status(r)
  const finished = s.label === 'Sent'
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, md: 2.5 }, borderRadius: 2 }}>
      <Box display="flex" gap={2} alignItems="flex-start" flexWrap="wrap">
        <Box flex={1} minWidth={240}>
          <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
            <Typography variant="subtitle1" fontWeight={700}>
              {r.title}
            </Typography>
            <Chip size="small" label={s.label} color={s.color} variant="outlined" />
          </Box>
          <Typography variant="body2" color="text.secondary">
            {r.schedule}
          </Typography>
          {r.message && (
            <Typography
              variant="body2"
              mt={0.75}
              sx={{
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                whiteSpace: 'pre-line',
              }}
            >
              {r.message}
            </Typography>
          )}
          <Box display="flex" gap={0.5} flexWrap="wrap" mt={1}>
            {r.recipients.map((e) => (
              <Chip key={e} size="small" label={e} variant="outlined" />
            ))}
          </Box>
        </Box>

        <Box minWidth={200}>
          <Typography variant="overline" color="text.secondary" display="block" lineHeight={1.6}>
            Next email
          </Typography>
          <Typography variant="body2" fontWeight={600}>
            {r.next_send_at ? etDateTime(r.next_send_at) : finished ? 'None, it went out' : '—'}
          </Typography>
          {r.next_event_date && (
            <Typography variant="caption" color="text.secondary" display="block">
              for {longDate(r.next_event_date)}
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary" display="block" mt={0.5}>
            Last sent: {r.last_sent_at ? etDateTime(r.last_sent_at) : 'never'}
            {r.created_by_name && ` · by ${r.created_by_name}`}
          </Typography>
        </Box>

        <Box display="flex" alignItems="center" gap={0.5}>
          {!finished && (
            <Tooltip title={r.active ? 'Pause' : 'Switch on'}>
              <Switch
                checked={r.active}
                disabled={busy}
                onChange={(e) => onToggle(e.target.checked)}
                inputProps={{ 'aria-label': r.active ? 'Pause reminder' : 'Switch reminder on' }}
              />
            </Tooltip>
          )}
          <Tooltip title="Send me a test">
            <span>
              <IconButton aria-label="Send me a test" onClick={onTest} disabled={busy}>
                <SendIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="What was sent">
            <IconButton
              aria-label="What was sent"
              onClick={() => setShowHistory((v) => !v)}
              color={showHistory ? 'primary' : 'default'}
            >
              <HistoryIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit">
            <IconButton aria-label="Edit" onClick={onEdit}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton aria-label="Delete" onClick={onDelete}>
              <DeleteOutlineIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
      <Collapse in={showHistory} unmountOnExit>
        <Box mt={1.5} pt={1.5} borderTop={1} borderColor="divider">
          <History id={r.id} />
        </Box>
      </Collapse>
    </Paper>
  )
}

export default function RemindersPage() {
  const qc = useQueryClient()
  const {
    data: reminders,
    isLoading,
    error,
  } = useQuery({
    queryKey: queryKeys.reminders,
    queryFn: fetchReminders,
  })
  const [editing, setEditing] = useState<Reminder | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<Reminder | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const refresh = () => qc.invalidateQueries({ queryKey: queryKeys.reminders })

  const run = async (id: string, fn: () => Promise<unknown>, failed: string) => {
    setBusyId(id)
    setActionError(null)
    try {
      await fn()
    } catch (err) {
      setActionError(apiError(err, failed))
    } finally {
      setBusyId(null)
    }
  }

  const toggle = (r: Reminder, active: boolean) =>
    run(
      r.id,
      async () => {
        await apiClient.patch(`/api/reminders/${r.id}/active`, { active })
        await refresh()
      },
      'Could not update the reminder.',
    )

  const test = (r: Reminder) =>
    run(
      r.id,
      async () => {
        const { data } = await apiClient.post<{ sent_to: string }>(`/api/reminders/${r.id}/test`)
        toast.success(`Test sent to ${data.sent_to}`)
      },
      'Could not send the test.',
    )

  const remove = async () => {
    if (!deleting) return
    const r = deleting
    await run(
      r.id,
      async () => {
        await apiClient.delete(`/api/reminders/${r.id}`)
        await refresh()
      },
      'Could not delete the reminder.',
    )
    setDeleting(null)
  }

  return (
    <Box>
      <Box
        display="flex"
        alignItems={{ sm: 'flex-end' }}
        justifyContent="space-between"
        flexDirection={{ xs: 'column', sm: 'row' }}
        gap={2}
        mb={3}
      >
        <Box>
          <Typography variant="h5">Reminders</Typography>
          <Typography variant="body2" color="text.secondary" maxWidth={640}>
            Scheduled emails to staff, such as mailing days and upcoming deadlines. Times are
            Eastern. Admins only for now.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreating(true)}>
          New reminder
        </Button>
      </Box>

      {error && <ErrorAlert message="Could not load reminders." />}
      {actionError && <ErrorAlert message={actionError} onClose={() => setActionError(null)} />}

      {isLoading ? (
        <Box display="flex" flexDirection="column" gap={1.5}>
          {[0, 1].map((i) => (
            <Skeleton key={i} variant="rounded" height={110} />
          ))}
        </Box>
      ) : reminders?.length ? (
        <Box display="flex" flexDirection="column" gap={1.5}>
          {reminders.map((r) => (
            <ReminderRow
              key={r.id}
              r={r}
              busy={busyId === r.id}
              onEdit={() => setEditing(r)}
              onDelete={() => setDeleting(r)}
              onToggle={(active) => void toggle(r, active)}
              onTest={() => void test(r)}
            />
          ))}
        </Box>
      ) : (
        !error && (
          <Paper variant="outlined" sx={{ borderRadius: 2, px: 2, py: 6, textAlign: 'center' }}>
            <Typography fontWeight={600}>No reminders yet</Typography>
            <Typography variant="body2" color="text.secondary" mb={2}>
              Create one to email people ahead of a mailing day or deadline.
            </Typography>
            <Button variant="outlined" startIcon={<AddIcon />} onClick={() => setCreating(true)}>
              New reminder
            </Button>
          </Paper>
        )
      )}

      <ReminderDialog
        open={creating || Boolean(editing)}
        reminder={editing}
        onClose={() => {
          setCreating(false)
          setEditing(null)
        }}
        onSaved={(r) => {
          toast.success(
            r.next_send_at ? `Saved. Next email ${etDateTime(r.next_send_at)}.` : 'Saved.',
          )
          setCreating(false)
          setEditing(null)
          void refresh()
        }}
      />
      <ConfirmDialog
        open={Boolean(deleting)}
        title="Delete reminder?"
        description={`“${deleting?.title ?? ''}” will stop sending and be removed, along with its send history.`}
        confirmLabel="Delete"
        loading={busyId === deleting?.id}
        onConfirm={() => void remove()}
        onCancel={() => setDeleting(null)}
      />
    </Box>
  )
}
