import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import GeneratedLettersPage from './GeneratedLettersPage'
import { downloadFromUrl } from '../utils/download'
import type { LetterJob, LetterJobDetail } from '../types'

// Force the mobile list layout so we exercise the lightweight rows rather than
// the virtualized DataGrid (which does not lay out in jsdom).
vi.mock('@mui/material/useMediaQuery', () => ({ default: () => true }))

vi.mock('../api/client', () => ({
  default: { get: vi.fn() },
}))

vi.mock('../utils/download', () => ({ downloadFromUrl: vi.fn() }))

// Isolate the page from the app-wide tracker; no live overrides by default.
vi.mock('../context/LetterJobsContext', () => ({
  useLetterJobs: () => ({ jobs: {}, trackJob: vi.fn(), inFlightCount: 0 }),
}))

// Default to a non-super-admin user; individual tests override as needed.
const mockUser = { role: 'admin' as string }
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}))

import apiClient from '../api/client'
const mockClient = apiClient as unknown as { get: Mock }

function makeJob(overrides: Partial<LetterJob> = {}): LetterJob {
  return {
    id: 'job-1',
    template_id: 't1',
    template_name: 'Annual Notice',
    association_id: 'a1',
    association_name: 'Sunset Ridge HOA',
    created_by: 'u1',
    created_by_name: 'Jane Doe',
    status: 'complete',
    output_path: 'outputs/job-1/letter.docx',
    created_at: '2026-06-14T10:00:00Z',
    ...overrides,
  }
}

function makeDetail(overrides: Partial<LetterJobDetail> = {}): LetterJobDetail {
  return {
    id: 'job-1',
    template_name: 'Annual Notice',
    association_name: 'Sunset Ridge HOA',
    created_by_name: 'Jane Doe',
    status: 'complete',
    created_at: '2026-06-14T10:00:00Z',
    entries: [{ key: 'meeting_date', label: 'Meeting date', value: '2026-07-15' }],
    derived: [{ label: 'Legal name', value: 'Sunset Ridge HOA, Inc.' }],
    ...overrides,
  }
}

beforeEach(() => {
  mockUser.role = 'admin'
  mockClient.get.mockReset()
  mockClient.get.mockResolvedValue({ data: [makeJob()] })
})

describe('GeneratedLettersPage', () => {
  it('renders a row per letter with template and association names', async () => {
    render(<GeneratedLettersPage />)

    await screen.findByText('Annual Notice')
    expect(screen.getByText('Sunset Ridge HOA')).toBeInTheDocument()
    expect(screen.getByText('Complete')).toBeInTheDocument()
  })

  it('renders a formatted local time for the created timestamp', async () => {
    render(<GeneratedLettersPage />)

    await screen.findByText('Annual Notice')
    // 2026 should appear in the localized date string (exact format is locale-dependent).
    expect(screen.getByText(/2026/)).toBeInTheDocument()
  })

  it('enables Download for completed jobs and disables it otherwise', async () => {
    mockClient.get.mockResolvedValue({
      data: [
        makeJob({ id: 'done', status: 'complete' }),
        makeJob({ id: 'busy', status: 'processing' }),
      ],
    })
    render(<GeneratedLettersPage />)

    await screen.findAllByText('Annual Notice')
    const buttons = screen.getAllByRole('button', { name: /download/i })
    expect(buttons[0]).toBeEnabled()
    expect(buttons[1]).toBeDisabled()
  })

  it('fetches a fresh presigned URL on download click', async () => {
    const user = userEvent.setup()
    mockClient.get.mockImplementation((url: string) =>
      url === '/api/letters/job-1'
        ? Promise.resolve({
            data: { job_id: 'job-1', status: 'complete', download_url: 'http://x/fresh' },
          })
        : Promise.resolve({ data: [makeJob()] }),
    )
    render(<GeneratedLettersPage />)

    await screen.findByText('Annual Notice')
    await user.click(screen.getByRole('button', { name: /download/i }))

    await waitFor(() =>
      expect(downloadFromUrl).toHaveBeenCalledWith('http://x/fresh', 'Annual Notice.docx'),
    )
  })

  it('shows an empty state when there are no letters', async () => {
    mockClient.get.mockResolvedValue({ data: [] })
    render(<GeneratedLettersPage />)

    await screen.findByText('No letters generated yet.')
  })

  it('opens the detail dialog and shows entries + resolved details', async () => {
    const user = userEvent.setup()
    mockClient.get.mockImplementation((url: string) =>
      url.endsWith('/details')
        ? Promise.resolve({ data: makeDetail() })
        : Promise.resolve({ data: [makeJob()] }),
    )
    render(<GeneratedLettersPage />)

    await screen.findByText('Annual Notice')
    await user.click(screen.getByTestId('InfoOutlinedIcon').closest('button')!)

    expect(await screen.findByText('Your entries')).toBeInTheDocument()
    expect(screen.getByText('Meeting date')).toBeInTheDocument()
    expect(screen.getByText('2026-07-15')).toBeInTheDocument()
    expect(screen.getByText('Resolved details')).toBeInTheDocument()
    expect(screen.getByText('Sunset Ridge HOA, Inc.')).toBeInTheDocument()
  })

  it('hides the creator filter for non-super-admins', async () => {
    render(<GeneratedLettersPage />)

    await screen.findByText('Annual Notice')
    expect(screen.queryByLabelText('Created by')).not.toBeInTheDocument()
  })

  it('shows a creator filter for super-admins', async () => {
    mockUser.role = 'super_admin'
    render(<GeneratedLettersPage />)

    await screen.findByText('Annual Notice')
    expect(screen.getByLabelText('Created by')).toBeInTheDocument()
  })
})
