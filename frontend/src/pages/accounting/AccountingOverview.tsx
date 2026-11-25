import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardActionArea from '@mui/material/CardActionArea'
import Chip from '@mui/material/Chip'
import Typography from '@mui/material/Typography'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import { Link } from 'react-router-dom'
import { ACCOUNTING_TOOLS } from './tools'

export default function AccountingOverview() {
  return (
    <Box>
      <Typography color="text.secondary" mb={3} maxWidth={720}>
        Month-end and year-end checks on association financials. Every tool reads the files in
        memory — nothing you upload is stored.
      </Typography>
      <Box
        display="grid"
        gridTemplateColumns={{ xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))' }}
        gap={2}
      >
        {ACCOUNTING_TOOLS.map((t) => (
          <Card key={t.path} variant="outlined" sx={{ borderRadius: 2 }}>
            <CardActionArea
              component={Link}
              to={`/accounting/${t.path}`}
              sx={{ p: 2.5, height: '100%', display: 'flex', alignItems: 'flex-start' }}
            >
              <Box width="100%">
                <Box display="flex" alignItems="center" gap={1.5} mb={1}>
                  <Box
                    sx={{
                      width: 40,
                      height: 40,
                      borderRadius: 1.5,
                      display: 'grid',
                      placeItems: 'center',
                      bgcolor: 'primary.main',
                      color: 'primary.contrastText',
                      flexShrink: 0,
                    }}
                  >
                    {t.icon}
                  </Box>
                  <Typography variant="subtitle1" fontWeight={700} flex={1}>
                    {t.title}
                  </Typography>
                  <ArrowForwardIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                </Box>
                <Typography variant="body2" color="text.secondary" mb={1.5}>
                  {t.description}
                </Typography>
                <Chip size="small" variant="outlined" label={t.input} />
              </Box>
            </CardActionArea>
          </Card>
        ))}
      </Box>
    </Box>
  )
}
