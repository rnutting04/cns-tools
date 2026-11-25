import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'

vi.mock('../api/client', () => ({ default: { post: vi.fn() } }))

import apiClient from '../api/client'
import {
  _resetSession,
  addPackets,
  clearSession,
  evidenceKey,
  loadEvidence,
  retryPacket,
  useReviewSession,
} from './useReviewSession'

const post = (apiClient as unknown as { post: Mock }).post

const pdf = (name: string) => new File(['%PDF'], name, { type: 'application/pdf' })

function report(filename: string) {
  const side = { source: 'balance sheet', label: 'AR', amount: 1, page: 2, verified: true }
  return {
    filename,
    page_count: 1,
    reports_found: [],
    summary: { fail: 0, review: 0, missing: 0, pass: 1, not_applicable: 0 },
    checks: [
      {
        id: 'ar',
        title: 'AR',
        status: 'pass',
        difference: 0,
        tolerance: 0,
        notes: [],
        left: { ...side, guessed: false, bbox: [1, 2, 3, 4], image: null },
        right: null,
      },
    ],
  }
}

/** Route mocked POSTs: /check returns a report, /evidence one image per region. */
function routePosts() {
  post.mockImplementation((url: string, form: FormData) => {
    if (url.endsWith('/evidence')) {
      const regions = JSON.parse(form.get('regions') as string) as unknown[]
      return Promise.resolve({ data: { images: regions.map(() => 'data:image/png;base64,x') } })
    }
    const name = (form.get('financial_report') as File).name
    return Promise.resolve({ data: report(name) })
  })
}

describe('useReviewSession', () => {
  beforeEach(() => {
    _resetSession()
    post.mockReset()
  })

  it('checks packets two at a time and keeps each report', async () => {
    const pending: Array<() => void> = []
    post.mockImplementation(
      (_url: string, form: FormData) =>
        new Promise((resolve) => {
          const name = (form.get('financial_report') as File).name
          pending.push(() => resolve({ data: report(name) }))
        }),
    )
    const { result } = renderHook(() => useReviewSession())

    act(() => {
      addPackets([pdf('A.pdf'), pdf('B.pdf'), pdf('C.pdf')])
    })
    expect(post).toHaveBeenCalledTimes(2)
    expect(result.current.map((p) => p.status)).toEqual(['checking', 'checking', 'queued'])

    await act(async () => pending.shift()!())
    await waitFor(() => expect(post).toHaveBeenCalledTimes(3))
    await act(async () => pending.splice(0).forEach((r) => r()))

    await waitFor(() => expect(result.current.every((p) => p.status === 'done')).toBe(true))
    expect(result.current.map((p) => p.report?.filename)).toEqual(['A.pdf', 'B.pdf', 'C.pdf'])
  })

  it('rejects non-PDFs, and a failed packet can be retried', async () => {
    post
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ data: report('A.pdf') })
    const { result } = renderHook(() => useReviewSession())

    let rejected: string[] = []
    act(() => {
      rejected = addPackets([pdf('A.pdf'), new File(['x'], 'notes.xlsx')]).rejected
    })
    expect(rejected).toEqual(['notes.xlsx'])
    await waitFor(() => expect(result.current[0].status).toBe('error'))

    act(() => retryPacket(result.current[0].id))
    await waitFor(() => expect(result.current[0].status).toBe('done'))

    act(() => clearSession())
    expect(result.current).toEqual([])
  })

  it('checks without images, then loads screenshots on open, keeping only the last 3', async () => {
    routePosts()
    const { result } = renderHook(() => useReviewSession())
    act(() => {
      addPackets(['A', 'B', 'C', 'D'].map((n) => pdf(`${n}.pdf`)))
    })
    await waitFor(() => expect(result.current.every((p) => p.status === 'done')).toBe(true))
    const checkForm = post.mock.calls[0][1] as FormData
    expect(checkForm.get('images')).toBe('false')

    const key = evidenceKey('ar', 'left')
    for (const p of result.current) {
      await act(() => loadEvidence(p.id))
    }
    const regions = JSON.parse(
      (post.mock.calls.at(-1)![1] as FormData).get('regions') as string,
    ) as { page: number; bbox: number[] }[]
    expect(regions).toEqual([{ page: 2, bbox: [1, 2, 3, 4] }])

    // A (opened first) was evicted; B-D keep their screenshots.
    expect(result.current.map((p) => p.evidence?.images[key] ?? null)).toEqual([
      null,
      'data:image/png;base64,x',
      'data:image/png;base64,x',
      'data:image/png;base64,x',
    ])

    // Re-opening a cached packet doesn't refetch.
    const calls = post.mock.calls.length
    await act(() => loadEvidence(result.current[3].id))
    expect(post.mock.calls.length).toBe(calls)
  })
})
