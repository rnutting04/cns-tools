import Box from '@mui/material/Box'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import Typography from '@mui/material/Typography'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { ACCOUNTING_TOOLS } from './tools'

/** Accounting tools: a header and tabs over each tool's page. */
export default function AccountingLayout() {
  const { pathname } = useLocation()
  const segment = pathname.replace(/^\/accounting\/?/, '').split('/')[0]
  const current = ACCOUNTING_TOOLS.some((t) => t.path === segment) ? segment : ''

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={1}>
        Accounting tools
      </Typography>
      <Tabs
        value={current}
        variant="scrollable"
        allowScrollButtonsMobile
        sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab label="Overview" value="" component={Link} to="/accounting" />
        {ACCOUNTING_TOOLS.map((t) => (
          <Tab
            key={t.path}
            label={t.title}
            value={t.path}
            component={Link}
            to={`/accounting/${t.path}`}
          />
        ))}
      </Tabs>
      <Outlet />
    </Box>
  )
}
