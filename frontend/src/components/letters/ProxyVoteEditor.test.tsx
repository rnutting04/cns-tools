import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ProxyVoteEditor from './ProxyVoteEditor'
import type { ProxyVote } from '../../types'

describe('ProxyVoteEditor', () => {
  it('shows an empty state when there are no votes', () => {
    render(<ProxyVoteEditor votes={[]} onChange={vi.fn()} />)
    expect(screen.getByText('No vote items added yet.')).toBeInTheDocument()
  })

  it('adds a vote when "Add vote" is clicked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<ProxyVoteEditor votes={[]} onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: /add vote/i }))
    expect(onChange).toHaveBeenCalledWith([{ type: 'waive_financial_one_year' }])
  })

  it('renders only the fiscal year field for waive_financial_one_year', () => {
    const votes: ProxyVote[] = [{ type: 'waive_financial_one_year' }]
    render(<ProxyVoteEditor votes={votes} onChange={vi.fn()} />)
    expect(screen.getByLabelText('Fiscal year')).toBeInTheDocument()
    expect(screen.queryByLabelText('Percentage')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Amount')).not.toBeInTheDocument()
  })

  it('renders from/to level and fiscal year for lower_financial_level', () => {
    const votes: ProxyVote[] = [{ type: 'lower_financial_level' }]
    render(<ProxyVoteEditor votes={votes} onChange={vi.fn()} />)
    // The two report-level dropdowns plus the vote-type select => 3 comboboxes.
    expect(screen.getAllByRole('combobox')).toHaveLength(3)
    expect(screen.getAllByText('From level').length).toBeGreaterThan(0)
    expect(screen.getAllByText('To level').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Fiscal year')).toBeInTheDocument()
  })

  it('renders amount/reserve/purpose for use_reserves_other_purpose', () => {
    const votes: ProxyVote[] = [{ type: 'use_reserves_other_purpose' }]
    render(<ProxyVoteEditor votes={votes} onChange={vi.fn()} />)
    expect(screen.getByLabelText('Amount')).toBeInTheDocument()
    expect(screen.getByLabelText('Reserve line item')).toBeInTheDocument()
    expect(screen.getByLabelText('Purpose / cost type')).toBeInTheDocument()
  })

  it('renders no extra fields for straight_line_to_pooled', () => {
    const votes: ProxyVote[] = [{ type: 'straight_line_to_pooled' }]
    render(<ProxyVoteEditor votes={votes} onChange={vi.fn()} />)
    expect(screen.queryByLabelText('Fiscal year')).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('removes a vote via the delete button', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    const votes: ProxyVote[] = [{ type: 'waive_financial_one_year' }]
    render(<ProxyVoteEditor votes={votes} onChange={onChange} />)

    const deleteButton = screen.getByTestId('DeleteIcon').closest('button')!
    await user.click(deleteButton)
    expect(onChange).toHaveBeenCalledWith([])
  })

  it('emits an update when typing in the fiscal year field', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    const votes: ProxyVote[] = [{ type: 'waive_financial_one_year' }]
    render(<ProxyVoteEditor votes={votes} onChange={onChange} />)

    await user.type(screen.getByRole('textbox'), '2026')
    expect(onChange).toHaveBeenCalledWith([{ type: 'waive_financial_one_year', fiscal_year: '2' }])
  })
})
