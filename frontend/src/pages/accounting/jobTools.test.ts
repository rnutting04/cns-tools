import { describe, expect, it } from 'vitest'
import { queuePosition } from './jobTools'

describe('queuePosition', () => {
  it.each([
    [{ queue_ahead: 2, queue_running: 3 }, 'Queued · 2 jobs ahead of yours · 3 jobs running'],
    [{ queue_ahead: 1, queue_running: 0 }, 'Queued · 1 job ahead of yours'],
    [{ queue_ahead: 0, queue_running: 4 }, 'Queued · next in line · 4 jobs running'],
    [{ queue_ahead: 0, queue_running: 0 }, 'Starting…'],
    // Older API responses without queue fields
    [{}, 'Waiting for the background worker'],
  ])('%o → %s', (job, text) => {
    expect(queuePosition(job)).toBe(text)
  })
})
