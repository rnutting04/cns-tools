import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../api/client', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import apiClient from '../api/client'
import { toast } from 'sonner'
import { JobsProvider, useJobs } from './JobsContext'

const get = (apiClient as unknown as { get: Mock }).get

const run = (status: string, extra = {}) => ({
  id: 'r1',
  tool: 'receivables',
  filename: 'Bal Sheet.pdf + AR.pdf + Prepaid.pdf',
  status,
  total_pages: 604,
  pages_done: status === 'complete' ? 604 : 40,
  current_association: status === 'processing' ? 'Valgo' : null,
  associations_done: status === 'complete' ? 179 : 0,
  flagged_count: status === 'complete' ? 6 : 0,
  error_detail: null,
  created_at: '2026-11-25T20:00:00',
  finished_at: null,
  ...extra,
})

const wrapper = ({ children }: { children: ReactNode }) => (
  <MemoryRouter>
    <JobsProvider>{children}</JobsProvider>
  </MemoryRouter>
)

describe('JobsProvider accounting runs', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    get.mockReset()
    ;(toast.success as Mock).mockReset()
  })

  it('picks up a run still going after a refresh, counts it, and pops up when it ends', async () => {
    get
      .mockResolvedValueOnce({ data: [run('processing')] }) // on load
      .mockResolvedValueOnce({ data: [run('processing')] }) // first poll
      .mockResolvedValue({ data: [run('complete')] })

    const { result } = renderHook(() => useJobs(), { wrapper })
    await waitFor(() => expect(result.current.inFlightCount).toBe(1))
    expect(result.current.accountingJobs.r1.current_association).toBe('Valgo')

    await act(() => vi.advanceTimersByTimeAsync(3100))
    await waitFor(() => expect(result.current.inFlightCount).toBe(0))
    expect(toast.success).toHaveBeenCalledOnce()
    expect((toast.success as Mock).mock.calls[0][0]).toBe('AR & prepaid run finished.')
    expect((toast.success as Mock).mock.calls[0][1].description).toBe(
      '179 associations · 6 flagged',
    )

    await act(() => vi.advanceTimersByTimeAsync(10_000))
    expect(get).toHaveBeenCalledTimes(3) // stops polling once nothing is running
    vi.useRealTimers()
  })
})
