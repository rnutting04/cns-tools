/** Upload queues for the PDF accounting tools (kept across tab switches). */
import { createUploadStore } from '../../hooks/createUploadStore'
import type { FdicReport, RevenueThresholdReport } from '../../types'

export const revenueStore = createUploadStore<RevenueThresholdReport>({
  url: '/api/accounting/revenue-threshold',
  field: 'report',
  accept: ['.pdf'],
})

export const fdicStore = createUploadStore<FdicReport>({
  url: '/api/accounting/fdic',
  field: 'report',
  accept: ['.pdf'],
})
