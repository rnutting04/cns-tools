/** Non-component helpers shared by the Accounting tools. */
import { useState } from 'react'
import ErrorAlert from '../../components/layout/ErrorAlert'
import type { UploadStore } from '../../hooks/createUploadStore'

const moneyFmt = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** 1,234.56 — negatives in parentheses, null as an em dash. */
export function money(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return n < 0 ? `(${moneyFmt.format(-n)})` : moneyFmt.format(n)
}

/** Items from an upload store, an add() that reports rejected files, and its error banner. */
export function useStoreUpload<T>(store: UploadStore<T>, kind: string) {
  const items = store.useItems()
  const [error, setError] = useState<string | null>(null)
  const add = (files: File[]) => {
    const { rejected } = store.add(files)
    setError(rejected.length ? `Skipped (not ${kind}): ${rejected.join(', ')}` : null)
  }
  const errorBanner = error ? <ErrorAlert message={error} onClose={() => setError(null)} /> : null
  return { items, add, errorBanner }
}
