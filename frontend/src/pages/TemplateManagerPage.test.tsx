import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TemplateManagerPage from './TemplateManagerPage'
import type { Template } from '../types'

// Force the mobile (TemplateRow) layout so we test the lightweight list rather
// than the heavy DataGrid; the action buttons are identical either way.
vi.mock('@mui/material/useMediaQuery', () => ({ default: () => true }))

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import apiClient from '../api/client'
const mockClient = apiClient as unknown as {
  get: Mock
  post: Mock
  patch: Mock
  delete: Mock
}

function makeTemplate(overrides: Partial<Template> = {}): Template {
  return {
    id: 't1',
    name: 'Annual Notice',
    category: 'Notices',
    docx_path: 'templates/t1/annual.docx',
    fields: [
      { key: 'assoc', label: 'Association', type: 'text', options: [], auto_populate: false },
    ],
    renderer_type: 'simple',
    is_active: true,
    created_at: '',
    updated_at: '',
    ...overrides,
  }
}

beforeEach(() => {
  mockClient.get.mockResolvedValue({ data: [makeTemplate()] })
})

describe('TemplateManagerPage', () => {
  it('renders rows with edit, duplicate, and deactivate actions', async () => {
    render(<TemplateManagerPage />)
    await screen.findByText('Annual Notice')

    expect(screen.getByTestId('EditIcon')).toBeInTheDocument()
    expect(screen.getByTestId('ContentCopyIcon')).toBeInTheDocument()
    expect(screen.getByTestId('BlockIcon')).toBeInTheDocument()
  })

  it('opens the edit dialog prefilled with the existing values', async () => {
    const user = userEvent.setup()
    render(<TemplateManagerPage />)
    await screen.findByText('Annual Notice')

    await user.click(screen.getByTestId('EditIcon').closest('button')!)

    expect(await screen.findByText('Edit template')).toBeInTheDocument()
    expect((screen.getByLabelText('Template name') as HTMLInputElement).value).toBe('Annual Notice')
    expect((screen.getByLabelText('Category') as HTMLInputElement).value).toBe('Notices')
    // Field rows are prefilled too.
    expect((screen.getByLabelText('Key (placeholder)') as HTMLInputElement).value).toBe('assoc')
  })

  it('saves an edit via PATCH and updates the row', async () => {
    const user = userEvent.setup()
    mockClient.patch.mockResolvedValue({ data: makeTemplate({ name: 'Updated Name' }) })

    render(<TemplateManagerPage />)
    await screen.findByText('Annual Notice')

    await user.click(screen.getByTestId('EditIcon').closest('button')!)
    const nameInput = await screen.findByLabelText('Template name')
    await user.clear(nameInput)
    await user.type(nameInput, 'Updated Name')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(mockClient.patch).toHaveBeenCalled())
    expect(mockClient.patch.mock.calls[0][0]).toBe('/api/templates/t1')
    expect(await screen.findByText('Updated Name')).toBeInTheDocument()
  })

  it('opens the duplicate dialog prefilled with "(Copy)" and posts to the duplicate endpoint', async () => {
    const user = userEvent.setup()
    mockClient.post.mockResolvedValue({
      data: makeTemplate({ id: 't2', name: 'Annual Notice (Copy)' }),
    })

    render(<TemplateManagerPage />)
    await screen.findByText('Annual Notice')

    await user.click(screen.getByTestId('ContentCopyIcon').closest('button')!)

    expect(await screen.findByText('Duplicate template')).toBeInTheDocument()
    expect((screen.getByLabelText('Template name') as HTMLInputElement).value).toBe(
      'Annual Notice (Copy)',
    )

    await user.click(screen.getByRole('button', { name: 'Create duplicate' }))
    await waitFor(() => expect(mockClient.post).toHaveBeenCalled())
    expect(mockClient.post.mock.calls[0][0]).toBe('/api/templates/t1/duplicate')
  })
})
