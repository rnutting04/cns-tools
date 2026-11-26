import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkingText from './WorkingText'

describe('WorkingText', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('shows a status word and swaps it for a different one', () => {
    render(<WorkingText />)
    const first = screen.getByRole('status').textContent
    expect(first).toMatch(/…$/)
    act(() => {
      vi.advanceTimersByTime(3000)
    })
    expect(screen.getByRole('status').textContent).not.toBe(first)
  })
})
