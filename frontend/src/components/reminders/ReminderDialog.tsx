/** Create or edit a reminder: what it says, who gets it, and when. */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Alert from '@mui/material/Alert'
import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import FormControlLabel from '@mui/material/FormControlLabel'
import MenuItem from '@mui/material/MenuItem'
import Switch from '@mui/material/Switch'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import apiClient from '../../api/client'
import { REFERENCE_STALE_TIME, fetchUsers, queryKeys } from '../../api/queries'
import type { Reminder, ReminderInput, ReminderRepeat } from '../../types'
import { LEAD_OPTIONS, REPEAT_LABELS, apiError, isEmail, leadLabel } from './format'

function todayIso(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function blank(): ReminderInput {
  return {
    title: '',
    message: '',
    recipients: [],
    start_date: todayIso(),
    repeat: 'none',
    lead_days: 0,
    send_time: '08:00',
    active: true,
  }
}

function fromReminder(r: Reminder): ReminderInput {
  return {
    title: r.title,
    message: r.message,
    recipients: r.recipients,
    start_date: r.start_date,
    repeat: r.repeat,
    lead_days: r.lead_days,
    send_time: r.send_time.slice(0, 5),
    active: r.active,
  }
}

interface Props {
  open: boolean
  /** the reminder being edited; omit to create one */
  reminder?: Reminder | null
  onClose: () => void
  onSaved: (r: Reminder) => void
}

export default function ReminderDialog({ open, reminder, onClose, onSaved }: Props) {
  // Remount per reminder so the form starts from its values.
  return open ? (
    <Form key={reminder?.id ?? 'new'} reminder={reminder} onClose={onClose} onSaved={onSaved} />
  ) : null
}

function Form({ reminder, onClose, onSaved }: Omit<Props, 'open'>) {
  const [form, setForm] = useState<ReminderInput>(() =>
    reminder ? fromReminder(reminder) : blank(),
  )
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: users = [] } = useQuery({
    queryKey: queryKeys.users,
    queryFn: fetchUsers,
    staleTime: REFERENCE_STALE_TIME,
  })
  const people = useMemo(
    () =>
      users
        .filter((u) => u.is_active)
        .map((u) => ({ email: u.email.toLowerCase(), name: `${u.fname} ${u.lname}` })),
    [users],
  )
  const nameOf = (email: string) => people.find((p) => p.email === email)?.name

  const set = <K extends keyof ReminderInput>(k: K, v: ReminderInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  const bad = form.recipients.filter((r) => !isEmail(r))
  const ready =
    form.title.trim() && form.recipients.length > 0 && !bad.length && form.start_date && !saving

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const { data } = reminder
        ? await apiClient.put<Reminder>(`/api/reminders/${reminder.id}`, form)
        : await apiClient.post<Reminder>('/api/reminders', form)
      onSaved(data)
    } catch (err) {
      setError(apiError(err, 'Could not save the reminder.'))
    } finally {
      setSaving(false)
    }
  }

  const eventLabel = form.repeat === 'none' ? 'Date' : 'First date'

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{reminder ? 'Edit reminder' : 'New reminder'}</DialogTitle>
      <DialogContent>
        <Box display="flex" flexDirection="column" gap={2} pt={1}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="Title"
            helperText="Also the email subject, e.g. “Mailing day Thursday”"
            value={form.title}
            onChange={(e) => set('title', e.target.value)}
            inputProps={{ maxLength: 200 }}
            required
            autoFocus
          />
          <TextField
            label="Message"
            value={form.message}
            onChange={(e) => set('message', e.target.value)}
            multiline
            minRows={3}
            inputProps={{ maxLength: 5000 }}
            helperText="Leave a blank line between paragraphs."
          />
          <Autocomplete
            multiple
            freeSolo
            options={people.map((p) => p.email)}
            value={form.recipients}
            inputValue={draft}
            onInputChange={(_, v) => setDraft(v)}
            onChange={(_, v) =>
              set(
                'recipients',
                Array.from(new Set(v.map((s) => s.trim().toLowerCase()).filter(Boolean))),
              )
            }
            onBlur={() => {
              // Keep an address that was typed but not confirmed with Enter.
              const s = draft.trim().toLowerCase()
              if (s && !form.recipients.includes(s)) set('recipients', [...form.recipients, s])
              setDraft('')
            }}
            getOptionLabel={(o) => o}
            renderOption={(props, option) => {
              const { key, ...rest } = props as typeof props & { key: string }
              return (
                <li key={key} {...rest}>
                  <Box>
                    <Typography variant="body2">{nameOf(option) ?? option}</Typography>
                    {nameOf(option) && (
                      <Typography variant="caption" color="text.secondary">
                        {option}
                      </Typography>
                    )}
                  </Box>
                </li>
              )
            }}
            renderValue={(value, getItemProps) =>
              value.map((email, index) => {
                const { key, ...rest } = getItemProps({ index })
                return (
                  <Chip
                    key={key}
                    size="small"
                    label={nameOf(email) ?? email}
                    color={isEmail(email) ? 'default' : 'error'}
                    {...rest}
                  />
                )
              })
            }
            renderInput={(params) => (
              <TextField
                {...params}
                label="Send to"
                required
                error={bad.length > 0}
                helperText={
                  bad.length
                    ? `Not an email address: ${bad.join(', ')}`
                    : 'Pick people, or type any address (e.g. a distribution list) and press Enter.'
                }
              />
            )}
          />
          <Box display="grid" gridTemplateColumns={{ xs: '1fr', sm: '1fr 1fr' }} gap={2}>
            <TextField
              label={eventLabel}
              type="date"
              value={form.start_date}
              onChange={(e) => set('start_date', e.target.value)}
              InputLabelProps={{ shrink: true }}
              required
            />
            <TextField
              select
              label="Repeats"
              value={form.repeat}
              onChange={(e) => set('repeat', e.target.value as ReminderRepeat)}
            >
              {(Object.keys(REPEAT_LABELS) as ReminderRepeat[]).map((k) => (
                <MenuItem key={k} value={k}>
                  {REPEAT_LABELS[k]}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Send"
              value={form.lead_days}
              onChange={(e) => set('lead_days', Number(e.target.value))}
            >
              {LEAD_OPTIONS.map((n) => (
                <MenuItem key={n} value={n}>
                  {leadLabel(n)}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="At (Eastern)"
              type="time"
              value={form.send_time}
              onChange={(e) => set('send_time', e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Box>
          <FormControlLabel
            control={
              <Switch checked={form.active} onChange={(e) => set('active', e.target.checked)} />
            }
            label={form.active ? 'On' : 'Paused: nothing is sent until it’s switched back on'}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={!ready}
          onClick={() => void save()}
          startIcon={saving ? <CircularProgress size={14} color="inherit" /> : undefined}
        >
          {reminder ? 'Save' : 'Create reminder'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
