import { describe, it, expect, vi, type Mock } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChangePasswordSection from './ChangePasswordSection'

vi.mock('../../api/client', () => ({
  default: { post: vi.fn() },
}))

import apiClient from '../../api/client'
const mockClient = apiClient as unknown as { post: Mock }

const VALID_NEW = 'BrandNewSecret9!'

describe('ChangePasswordSection', () => {
  it('disables submit until the form is valid', () => {
    render(<ChangePasswordSection />)
    expect(screen.getByRole('button', { name: /update password/i })).toBeDisabled()
  })

  it('warns when the new password is too short', async () => {
    const user = userEvent.setup()
    render(<ChangePasswordSection />)
    await user.type(screen.getByLabelText('New password'), 'short')
    expect(screen.getByText('Must be at least 12 characters')).toBeInTheDocument()
  })

  it('warns when the confirmation does not match', async () => {
    const user = userEvent.setup()
    render(<ChangePasswordSection />)
    await user.type(screen.getByLabelText('New password'), VALID_NEW)
    await user.type(screen.getByLabelText('Confirm new password'), 'somethingElse9!')
    expect(screen.getByText('Passwords do not match')).toBeInTheDocument()
  })

  it('submits and reports success', async () => {
    mockClient.post.mockResolvedValue({})
    const onSuccess = vi.fn()
    const user = userEvent.setup()
    render(<ChangePasswordSection onSuccess={onSuccess} />)

    await user.type(screen.getByLabelText('Current password'), 'OldPassw0rd!!')
    await user.type(screen.getByLabelText('New password'), VALID_NEW)
    await user.type(screen.getByLabelText('Confirm new password'), VALID_NEW)

    const submit = screen.getByRole('button', { name: /update password/i })
    await waitFor(() => expect(submit).toBeEnabled())
    await user.click(submit)

    await waitFor(() =>
      expect(mockClient.post).toHaveBeenCalledWith('/api/users/me/change-password', {
        current_password: 'OldPassw0rd!!',
        new_password: VALID_NEW,
      }),
    )
    expect(await screen.findByText('Password updated successfully.')).toBeInTheDocument()
    expect(onSuccess).toHaveBeenCalled()
  })

  it('shows the API error message on failure', async () => {
    mockClient.post.mockRejectedValue({
      response: { data: { detail: 'Current password is incorrect' } },
    })
    const user = userEvent.setup()
    render(<ChangePasswordSection />)

    await user.type(screen.getByLabelText('Current password'), 'WrongPassw0rd!')
    await user.type(screen.getByLabelText('New password'), VALID_NEW)
    await user.type(screen.getByLabelText('Confirm new password'), VALID_NEW)
    await user.click(screen.getByRole('button', { name: /update password/i }))

    expect(await screen.findByText('Current password is incorrect')).toBeInTheDocument()
  })
})
