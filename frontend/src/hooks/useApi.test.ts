import { describe, it, expect } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useApi } from './useApi'

describe('useApi', () => {
  it('starts idle', () => {
    const { result } = renderHook(() => useApi<string>())
    expect(result.current).toMatchObject({ data: null, loading: false, error: null })
  })

  it('stores data on success', async () => {
    const { result } = renderHook(() => useApi<string>())
    await act(async () => {
      await result.current.execute(async () => 'hello')
    })
    expect(result.current.data).toBe('hello')
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('extracts the API detail message on failure', async () => {
    const { result } = renderHook(() => useApi<string>())
    const apiError = { response: { data: { detail: 'Nope.' } } }

    await act(async () => {
      await expect(result.current.execute(async () => Promise.reject(apiError))).rejects.toEqual(
        apiError,
      )
    })

    await waitFor(() => expect(result.current.error).toBe('Nope.'))
    expect(result.current.data).toBeNull()
    expect(result.current.loading).toBe(false)
  })

  it('falls back to a generic error message', async () => {
    const { result } = renderHook(() => useApi<string>())
    await act(async () => {
      await expect(result.current.execute(async () => Promise.reject({}))).rejects.toBeTruthy()
    })
    await waitFor(() => expect(result.current.error).toBe('An unexpected error occurred.'))
  })
})
