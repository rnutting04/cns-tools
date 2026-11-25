import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'

vi.mock('../api/client', () => ({ default: { post: vi.fn() } }))

import apiClient from '../api/client'
import { createUploadStore } from './createUploadStore'

const post = (apiClient as unknown as { post: Mock }).post
const store = createUploadStore<{ name: string }>({
  url: '/api/accounting/fdic',
  field: 'report',
  accept: ['.pdf'],
})
const pdf = (name: string) => new File(['%PDF'], name)

describe('createUploadStore', () => {
  beforeEach(() => {
    store._reset()
    post.mockReset()
  })

  it('posts each file under the field name and keeps results in order', async () => {
    post.mockImplementation((_url: string, form: FormData) =>
      Promise.resolve({ data: { name: (form.get('report') as File).name } }),
    )
    const { result } = renderHook(() => store.useItems())
    let rejected: string[] = []
    act(() => {
      rejected = store.add([
        pdf('A.pdf'),
        pdf('B.pdf'),
        new File(['x'], 'C.xlsx'),
        pdf('D.pdf'),
      ]).rejected
    })
    expect(rejected).toEqual(['C.xlsx'])
    await waitFor(() => expect(result.current.every((i) => i.status === 'done')).toBe(true))
    expect(result.current.map((i) => i.result?.name)).toEqual(['A.pdf', 'B.pdf', 'D.pdf'])
    expect(post.mock.calls[0][0]).toBe('/api/accounting/fdic')
  })

  it('shows the server error and retries', async () => {
    post
      .mockRejectedValueOnce({ isAxiosError: true, response: { data: { detail: 'No text' } } })
      .mockResolvedValueOnce({ data: { name: 'A.pdf' } })
    const { result } = renderHook(() => store.useItems())
    act(() => {
      store.add([pdf('A.pdf')])
    })
    await waitFor(() => expect(result.current[0].status).toBe('error'))
    act(() => store.retry(result.current[0].id))
    await waitFor(() => expect(result.current[0].status).toBe('done'))
  })
})
