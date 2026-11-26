import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RemindersPage from './RemindersPage'
import type { Reminder, User } from '../types'

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn() } }))

import apiClient from '../api/client'
import { toast } from 'sonner'
const api = apiClient as unknown as Record<'get' | 'post' | 'put' | 'patch' | 'delete', Mock>

const reminder: Reminder = {
  id: 'r1',
  title: 'Mailing day',
  message: 'Letters go out Thursday.',
  recipients: ['ryan@example.com', 'team@example.com'],
  start_date: '2026-12-25',
  repeat: 'monthly',
  lead_days: 3,
  send_time: '08:00:00',
  active: true,
  schedule: 'Every month on the 25th · 3 days before · 8:00 AM ET',
  next_event_date: '2026-12-25',
  next_send_at: '2026-12-22T13:00:00Z',
  last_sent_at: null,
  created_by_name: 'Ryan N',
  created_at: '2026-11-26T12:00:00Z',
}

const users = [
  { id: 'u1', fname: 'Ryan', lname: 'N', email: 'ryan@example.com', is_active: true },
] as User[]

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockImplementation((url: string) =>
    Promise.resolve({ data: url === '/api/users' ? users : [reminder] }),
  )
})

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <RemindersPage />
    </QueryClientProvider>,
  )
}

describe('RemindersPage', () => {
  it('lists reminders with their schedule and next email in Eastern time', async () => {
    renderPage()
    expect(await screen.findByText('Mailing day')).toBeInTheDocument()
    expect(screen.getByText(reminder.schedule)).toBeInTheDocument()
    expect(screen.getByText('Tue, Dec 22, 8:00 AM ET')).toBeInTheDocument()
    expect(screen.getByText('team@example.com')).toBeInTheDocument()
  })

  it('creates a reminder', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValue({ data: reminder })
    renderPage()
    await screen.findByText('Mailing day')
    await user.click(screen.getAllByRole('button', { name: /new reminder/i })[0])

    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/title/i), 'Budget season')
    await user.type(within(dialog).getByLabelText(/send to/i), 'dl@example.com{Enter}')
    await user.click(within(dialog).getByRole('button', { name: /create reminder/i }))

    await waitFor(() => expect(api.post).toHaveBeenCalled())
    const [url, body] = api.post.mock.calls[0]
    expect(url).toBe('/api/reminders')
    expect(body).toMatchObject({ title: 'Budget season', recipients: ['dl@example.com'] })
  })

  it('will not save an address that is not an email', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Mailing day')
    await user.click(screen.getAllByRole('button', { name: /new reminder/i })[0])
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/title/i), 'Oops')
    await user.type(within(dialog).getByLabelText(/send to/i), 'not-an-email{Enter}')
    expect(within(dialog).getByText(/not an email address/i)).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: /create reminder/i })).toBeDisabled()
  })

  it('sends a test to yourself', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValue({ data: { sent_to: 'ryan@example.com' } })
    renderPage()
    await screen.findByText('Mailing day')
    await user.click(screen.getByRole('button', { name: /send me a test/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/reminders/r1/test'))
    expect(toast.success).toHaveBeenCalledWith('Test sent to ryan@example.com')
  })
})
