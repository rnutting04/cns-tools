import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import DescriptionIcon from '@mui/icons-material/Description'

export default function LetterGeneratorPage() {
  return (
    <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" minHeight="60vh" gap={2}>
      <DescriptionIcon sx={{ fontSize: 56, color: 'text.disabled' }} />
      <Typography variant="h5">Letter generator</Typography>
      <Typography color="text.secondary">Coming soon</Typography>
    </Box>
  )
}
