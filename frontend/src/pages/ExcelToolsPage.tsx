import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import TableChartIcon from '@mui/icons-material/TableChart'

export default function ExcelToolsPage() {
  return (
    <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" minHeight="60vh" gap={2}>
      <TableChartIcon sx={{ fontSize: 56, color: 'text.disabled' }} />
      <Typography variant="h5">Excel tools</Typography>
      <Typography color="text.secondary">Coming soon</Typography>
    </Box>
  )
}
