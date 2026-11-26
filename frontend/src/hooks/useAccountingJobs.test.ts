import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('../api/client', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

import apiClient from '../api/client'
import { useAccountingJob, useAccountingJobs } from './useAccountingJobs'

const get = (apiClient as unknown as { get: Mock }).get
const post = (apiClient as unknown as { post: Mock }).post

describe('useAccountingJobs.start', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: [] })
    post.mockReset()
  })

  it('sends each file of a multi-file run under its role', async () => {
    post.mockResolvedValue({ data: { id: 'j9', status: 'pending' } })
    const { result: hook } = renderHook(() => useAccountingJobs('receivables'))
    const pdf = (name: string) => new File(['%PDF'], name, { type: 'application/pdf' })
    await hook.current.start({ balance_sheet: pdf('Bal Sheet.pdf'), ar: pdf('AR.pdf') })

    const form = post.mock.calls[0][1] as FormData
    expect(form.get('tool')).toBe('receivables')
    expect((form.get('balance_sheet') as File).name).toBe('Bal Sheet.pdf')
    expect((form.get('ar') as File).name).toBe('AR.pdf')
    expect(form.get('report')).toBeNull()
    await waitFor(() => expect(hook.current.jobs.map((j) => j.id)).toEqual(['j9']))
  })

  it('sends a single PDF as the report', async () => {
    post.mockResolvedValue({ data: { id: 'j1', status: 'pending' } })
    const { result: hook } = renderHook(() => useAccountingJobs('fdic'))
    await hook.current.start(new File(['%PDF'], 'Bal Sheet.pdf'))
    expect(((post.mock.calls[0][1] as FormData).get('report') as File).name).toBe('Bal Sheet.pdf')
  })
})

const summary = (status: string, done: number) => ({
  id: 'j1',
  tool: 'fdic',
  filename: 'Bal Sheet.pdf',
  status,
  total_pages: 3,
  pages_done: done,
  current_association: status === 'processing' ? 'Bay Club' : null,
  associations_done: done,
  flagged_count: 0,
  error_detail: null,
  created_at: null,
  finished_at: null,
})
const result = (name: string) => ({
  association: name,
  first_page: 1,
  last_page: 1,
  flagged: false,
  result: { problem: 'x' },
})

describe('useAccountingJob', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    get.mockReset()
  })

  it('fetches only new results each poll and stops when the job ends', async () => {
    get
      .mockResolvedValueOnce({ data: { ...summary('processing', 1), results: [result('A')] } })
      .mockResolvedValueOnce({
        data: { ...summary('complete', 3), results: [result('B'), result('C')] },
      })

    const { result: hook } = renderHook(() => useAccountingJob('j1'))
    await waitFor(() => expect(hook.current.results).toHaveLength(1))
    expect(hook.current.summary?.current_association).toBe('Bay Club')

    await vi.advanceTimersByTimeAsync(2100)
    await waitFor(() =>
      expect(hook.current.results.map((r) => r.association)).toEqual(['A', 'B', 'C']),
    )
    expect(get.mock.calls.map((c) => c[1].params.since)).toEqual([0, 1])

    await vi.advanceTimersByTimeAsync(5000)
    expect(get).toHaveBeenCalledTimes(2) // stopped polling once complete
    vi.useRealTimers()
  })
})
