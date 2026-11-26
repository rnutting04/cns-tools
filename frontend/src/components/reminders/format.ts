/** Display helpers for reminders (times are always shown in Eastern). */
import type { ReminderRepeat } from '../../types'

const ET = 'America/New_York'

/** "Mon, Dec 22, 8:00 AM ET" from a UTC timestamp. */
export function etDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  const s = d.toLocaleString('en-US', {
    timeZone: ET,
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
  return `${s} ET`
}

/** "Thu, Dec 25, 2026" from "2026-12-25", with no timezone shift. */
export function longDate(isoDate: string | null): string {
  if (!isoDate) return '—'
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-US', {
    timeZone: 'UTC',
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export const REPEAT_LABELS: Record<ReminderRepeat, string> = {
  none: "Doesn't repeat",
  weekly: 'Every week',
  monthly: 'Every month',
  yearly: 'Every year',
}

export const LEAD_OPTIONS = [0, 1, 2, 3, 5, 7, 14, 30]

export const leadLabel = (n: number) =>
  n === 0 ? 'On the day' : `${n} day${n === 1 ? '' : 's'} before`

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export const isEmail = (s: string) => EMAIL.test(s.trim())

/** The API's error message: a string, or FastAPI's validation list. */
export function apiError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string; loc?: unknown[] }
    const field = Array.isArray(first.loc) ? first.loc.at(-1) : null
    return [field, first.msg].filter(Boolean).join(': ') || fallback
  }
  return fallback
}
