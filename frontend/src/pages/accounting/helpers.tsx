/** Non-component helpers shared by the Accounting tools. */

const moneyFmt = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** 1,234.56 — negatives in parentheses, null as an em dash. */
export function money(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return n < 0 ? `(${moneyFmt.format(-n)})` : moneyFmt.format(n)
}

/** Download rows as a CSV file (opens in Excel). */
export function downloadCsv(rows: (string | number | null | undefined)[][], filename: string) {
  const cell = (v: string | number | null | undefined) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const blob = new Blob([rows.map((r) => r.map(cell).join(',')).join('\r\n')], {
    type: 'text/csv;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
