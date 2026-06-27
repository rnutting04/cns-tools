import { useState } from 'react'
import Box from '@mui/material/Box'
import Toolbar from '@mui/material/Toolbar'
import { Outlet } from 'react-router-dom'
import TopBar from './Topbar'
import Sidebar from './Sidebar'
import { JobsProvider } from '../../context/JobsContext'

export default function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <JobsProvider>
      <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
        <TopBar onMenuClick={() => setMobileOpen((o) => !o)} />
        <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: { xs: 2, sm: 3 },
            minWidth: 0,
          }}
        >
          <Toolbar />
          <Outlet />
        </Box>
      </Box>
    </JobsProvider>
  )
}
