import { useEffect } from 'react'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { LetterJobsProvider, useLetterJobs } from './LetterJobsContext'

vi.mock('../api/client', () => ({
  default: { get: vi.fn() },
}))

import apiClient from '../api/client'
const mockClient = apiClient as unknown as { get: Mock }

// A child that immediately starts tracking a job on mount.
function TrackOnMount({ jobId }: { jobId: string }) {
  const { trackJob, inFlightCount } = useLetterJobs()
  useEffect(() => {
    trackJob(jobId)
  }, [trackJob, jobId])
  return <span data-testid="in-flight">{inFlightCount}</span>
}

function renderProvider(jobId: string) {
  return render(
    <MemoryRouter>
      <LetterJobsProvider>
        <TrackOnMount jobId={jobId} />
      </LetterJobsProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockClient.get.mockReset()
})

describe('LetterJobsContext', () => {
  it('toasts when a tracked job completes', async () => {
    mockClient.get.mockResolvedValue({
      data: { job_id: 'job-1', status: 'complete', download_url: 'http://x/url' },
    })

    renderProvider('job-1')

    await waitFor(() => expect(screen.getByText(/your letter is ready/i)).toBeInTheDocument())
  })

  it('shows an error toast when a tracked job fails', async () => {
    mockClient.get.mockResolvedValue({
      data: { job_id: 'job-2', status: 'failed', download_url: null },
    })

    renderProvider('job-2')

    await waitFor(() =>
      expect(screen.getByText(/a letter failed to generate/i)).toBeInTheDocument(),
    )
  })
})
