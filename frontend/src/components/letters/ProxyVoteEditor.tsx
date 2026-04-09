import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import FormControl from '@mui/material/FormControl'
import IconButton from '@mui/material/IconButton'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Select from '@mui/material/Select'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import type { ProxyVote, ProxyVoteType } from '../../types'

const VOTE_OPTIONS: { value: ProxyVoteType; label: string }[] = [
  { value: 'waive_financial_one_year', label: 'Waiving the financial reporting requirement for one year' },
  { value: 'lower_financial_level', label: 'Lowering the financial reporting requirement level' },
  { value: 'cross_utilization_reserves', label: 'Cross utilization of reserves' },
  { value: 'straight_line_to_pooled', label: 'Changing reserves from Straight Line to Pooled' },
  { value: 'partial_reserve_funding', label: 'Partially Funding the Reserves as one vote' },
  { value: 'waive_reserves', label: 'Waiving Reserves' },
  { value: 'use_reserves_other_purpose', label: 'Using reserves for other than intended purposes' },
  { value: 'move_reserve_line_items', label: 'Moving Reserve Funds from One Line Item to Another Line Item' },
  { value: 'irs_rollover', label: 'IRS Rollover surplus Funds' },
]

const REPORT_LEVEL_OPTIONS = ['Audit', 'Compilation', 'Review']

const EMPTY_VOTE: ProxyVote = {
  type: 'waive_financial_one_year',
}

function resetVoteForType(type: ProxyVoteType): ProxyVote {
  return { type }
}

function voteNeedsField(vote: ProxyVote, field: keyof ProxyVote): boolean {
  switch (vote.type) {
    case 'waive_financial_one_year':
      return field === 'fiscal_year'

    case 'lower_financial_level':
      return field === 'from_level' || field === 'to_level' || field === 'fiscal_year'

    case 'cross_utilization_reserves':
      return field === 'fiscal_year'

    case 'straight_line_to_pooled':
      return false

    case 'partial_reserve_funding':
      return field === 'percentage' || field === 'fiscal_year'

    case 'waive_reserves':
      return field === 'fiscal_year'

    case 'use_reserves_other_purpose':
      return field === 'amount' || field === 'reserve_from' || field === 'purpose'

    case 'move_reserve_line_items':
      return field === 'amount' || field === 'reserve_from' || field === 'reserve_to'

    case 'irs_rollover':
      return field === 'tax_year'

    default:
      return false
  }
}

export default function ProxyVoteEditor({
  votes,
  onChange,
}: {
  votes: ProxyVote[]
  onChange: (votes: ProxyVote[]) => void
}) {
  const safeVotes = votes.length > 0 ? votes : []

  const addVote = () => {
    onChange([...safeVotes, { ...EMPTY_VOTE }])
  }

  const removeVote = (index: number) => {
    onChange(safeVotes.filter((_, i) => i !== index))
  }

  const updateVote = (index: number, patch: Partial<ProxyVote>) => {
    onChange(safeVotes.map((vote, i) => (i === index ? { ...vote, ...patch } : vote)))
  }

  const changeVoteType = (index: number, type: ProxyVoteType) => {
    onChange(safeVotes.map((vote, i) => (i === index ? resetVoteForType(type) : vote)))
  }

  return (
    <Box display="flex" flexDirection="column" gap={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography variant="subtitle2">Proxy vote items</Typography>
          <Typography variant="body2" color="text.secondary">
            Add the matters to be included in the proxy table.
          </Typography>
        </Box>

        <Button variant="outlined" startIcon={<AddIcon />} onClick={addVote}>
          Add vote
        </Button>
      </Box>

      {safeVotes.length === 0 && (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography color="text.secondary">
            No vote items added yet.
          </Typography>
        </Paper>
      )}

      {safeVotes.map((vote, index) => (
        <Paper key={index} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Box display="flex" flexDirection="column" gap={2}>
            <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={2}>
              <FormControl size="small" fullWidth>
                <InputLabel>Vote type</InputLabel>
                <Select
                  value={vote.type}
                  label="Vote type"
                  onChange={(e) => changeVoteType(index, e.target.value as ProxyVoteType)}
                >
                  {VOTE_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <IconButton onClick={() => removeVote(index)} sx={{ mt: 0.25 }}>
                <DeleteIcon />
              </IconButton>
            </Box>

            {voteNeedsField(vote, 'fiscal_year') && (
              <TextField
                label="Fiscal year"
                size="small"
                fullWidth
                value={vote.fiscal_year ?? ''}
                onChange={(e) => updateVote(index, { fiscal_year: e.target.value })}
              />
            )}

            {voteNeedsField(vote, 'from_level') && (
              <FormControl size="small" fullWidth>
                <InputLabel>From level</InputLabel>
                <Select
                  value={vote.from_level ?? ''}
                  label="From level"
                  onChange={(e) => updateVote(index, { from_level: e.target.value })}
                >
                  {REPORT_LEVEL_OPTIONS.map((option) => (
                    <MenuItem key={option} value={option}>
                      {option}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            {voteNeedsField(vote, 'to_level') && (
              <FormControl size="small" fullWidth>
                <InputLabel>To level</InputLabel>
                <Select
                  value={vote.to_level ?? ''}
                  label="To level"
                  onChange={(e) => updateVote(index, { to_level: e.target.value })}
                >
                  {REPORT_LEVEL_OPTIONS.map((option) => (
                    <MenuItem key={option} value={option}>
                      {option}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            {voteNeedsField(vote, 'percentage') && (
              <TextField
                label="Percentage"
                size="small"
                fullWidth
                value={vote.percentage ?? ''}
                onChange={(e) => updateVote(index, { percentage: e.target.value })}
                helperText="Example: 50"
              />
            )}

            {voteNeedsField(vote, 'amount') && (
              <TextField
                label="Amount"
                size="small"
                fullWidth
                value={vote.amount ?? ''}
                onChange={(e) => updateVote(index, { amount: e.target.value })}
                helperText="Enter only the amount value, e.g. 25,000"
              />
            )}

            {voteNeedsField(vote, 'reserve_from') && (
              <TextField
                label="Reserve line item"
                size="small"
                fullWidth
                value={vote.reserve_from ?? ''}
                onChange={(e) => updateVote(index, { reserve_from: e.target.value })}
              />
            )}

            {voteNeedsField(vote, 'reserve_to') && (
              <TextField
                label="To reserve line item"
                size="small"
                fullWidth
                value={vote.reserve_to ?? ''}
                onChange={(e) => updateVote(index, { reserve_to: e.target.value })}
              />
            )}

            {voteNeedsField(vote, 'purpose') && (
              <TextField
                label="Purpose / cost type"
                size="small"
                fullWidth
                value={vote.purpose ?? ''}
                onChange={(e) => updateVote(index, { purpose: e.target.value })}
                helperText="Example: roofing, paving, deferred maintenance"
              />
            )}

            {voteNeedsField(vote, 'tax_year') && (
              <TextField
                label="Tax year ended"
                size="small"
                fullWidth
                value={vote.tax_year ?? ''}
                onChange={(e) => updateVote(index, { tax_year: e.target.value })}
              />
            )}
          </Box>
        </Paper>
      ))}
    </Box>
  )
}