import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { usePolling } from './usePolling'

type Job = { status: 'pending' | 'complete' }

describe('usePolling', () => {
  it('stays idle when key is null', () => {
    const fetcher = vi.fn()
    renderHook(() => usePolling<Job>(null, fetcher, (d) => d.status === 'complete', 1))
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('polls until the stop condition is met', async () => {
    const fetcher = vi
      .fn<(id: string) => Promise<Job>>()
      .mockResolvedValueOnce({ status: 'pending' })
      .mockResolvedValueOnce({ status: 'complete' })

    const { result } = renderHook(() =>
      usePolling<Job>('job-1', fetcher, (d) => d.status === 'complete', 1),
    )

    await waitFor(() => expect(result.current.data?.status).toBe('complete'))
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(fetcher).toHaveBeenCalledWith('job-1')

    // No further polling after the stop condition.
    const callsAfterStop = fetcher.mock.calls.length
    await new Promise((r) => setTimeout(r, 10))
    expect(fetcher.mock.calls.length).toBe(callsAfterStop)
  })

  it('reports an error and stops when the fetcher rejects', async () => {
    const fetcher = vi.fn<(id: string) => Promise<Job>>().mockRejectedValue(new Error('boom'))

    const { result } = renderHook(() =>
      usePolling<Job>('job-1', fetcher, (d) => d.status === 'complete', 1),
    )

    await waitFor(() => expect(result.current.error).toBe('Polling failed.'))
    expect(result.current.data).toBeNull()
  })

  it('stops polling after unmount', async () => {
    const fetcher = vi.fn<(id: string) => Promise<Job>>().mockResolvedValue({ status: 'pending' })

    const { unmount } = renderHook(() =>
      usePolling<Job>('job-1', fetcher, (d) => d.status === 'complete', 1),
    )

    await waitFor(() => expect(fetcher).toHaveBeenCalled())
    unmount()
    const callsAtUnmount = fetcher.mock.calls.length
    await new Promise((r) => setTimeout(r, 10))
    expect(fetcher.mock.calls.length).toBe(callsAtUnmount)
  })
})
