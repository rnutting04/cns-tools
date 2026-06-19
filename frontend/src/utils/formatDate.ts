/**
 * Format an ISO 8601 timestamp for display in the user's local timezone.
 *
 * Backend timestamps are emitted as UTC-aware ISO strings (with a `Z`/offset),
 * so `new Date()` parses them as UTC and `toLocaleString` converts to local.
 */
export function formatDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
