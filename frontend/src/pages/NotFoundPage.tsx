import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Typography from '@mui/material/Typography'
import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <Box
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      minHeight="100vh"
      gap={2}
    >
      <Typography variant="h4">Page not found</Typography>
      <Typography color="text.secondary">
        The page you're looking for doesn't exist.
      </Typography>
      <Button variant="contained" component={Link} to="/">
        Go to dashboard
      </Button>
    </Box>
  )
}
