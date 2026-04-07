import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import IconButton from '@mui/material/IconButton'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'

interface Props {
  candidates: string[]
  onChange: (candidates: string[]) => void
}

export default function BallotCandidateEditor({ candidates, onChange }: Props) {
  const add = () => onChange([...candidates, ''])
  const remove = (i: number) => onChange(candidates.filter((_, idx) => idx !== i))
  const update = (i: number, val: string) =>
    onChange(candidates.map((c, idx) => (idx === i ? val : c)))

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
        <Typography variant="subtitle2" color="text.secondary">
          Candidates
        </Typography>
        <Button size="small" startIcon={<AddIcon />} onClick={add}>
          Add candidate
        </Button>
      </Box>

      {candidates.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          Add at least one candidate to continue.
        </Typography>
      ) : (
        <Box display="flex" flexDirection="column" gap={1}>
          {candidates.map((c, i) => (
            <Box key={i} display="flex" gap={1} alignItems="center">
              <TextField
                label={`Candidate ${i + 1}`}
                size="small"
                fullWidth
                value={c}
                onChange={(e) => update(i, e.target.value)}
                placeholder="Full name"
              />
              <IconButton size="small" onClick={() => remove(i)} aria-label="Remove candidate">
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  )
}
