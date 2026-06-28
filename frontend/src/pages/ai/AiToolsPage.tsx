import { useNavigate } from 'react-router-dom'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardActionArea from '@mui/material/CardActionArea'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import Typography from '@mui/material/Typography'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'

interface AiTool {
  label: string
  description: string
  to: string
  icon: React.ReactNode
  badge?: string
}

const AI_TOOLS: AiTool[] = [
  {
    label: 'Budget generator',
    description:
      'Upload a monthly financial report and prior-year budget to automatically produce a draft HOA operating budget as a formatted Excel workbook.',
    to: '/ai/budget',
    icon: <AccountBalanceIcon fontSize="large" color="primary" />,
    badge: 'New',
  },
  // Add future AI tools here — each becomes a card automatically.
]

export default function AiToolsPage() {
  const navigate = useNavigate()

  return (
    <Box>
      <Box display="flex" alignItems="center" gap={1} mb={1}>
        <AutoAwesomeIcon color="primary" />
        <Typography variant="h5" fontWeight={700}>
          AI tools
        </Typography>
      </Box>

      <Typography variant="body2" color="text.secondary" mb={4}>
        Automated tools powered by AI. Upload the required files and let the pipeline do the work.
      </Typography>

      <Box display="flex" flexWrap="wrap" gap={3}>
        {AI_TOOLS.map((tool) => (
          <Card key={tool.to} variant="outlined" sx={{ width: { xs: '100%', sm: 280 } }}>
            <CardActionArea onClick={() => navigate(tool.to)} sx={{ height: '100%' }}>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1.5}>
                  {tool.icon}
                  {tool.badge && (
                    <Chip label={tool.badge} size="small" color="primary" variant="outlined" />
                  )}
                </Box>

                <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                  {tool.label}
                </Typography>

                <Typography variant="body2" color="text.secondary">
                  {tool.description}
                </Typography>
              </CardContent>
            </CardActionArea>
          </Card>
        ))}
      </Box>
    </Box>
  )
}
