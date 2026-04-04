import Drawer from '@mui/material/Drawer'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import Toolbar from '@mui/material/Toolbar'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import DashboardIcon from '@mui/icons-material/Dashboard'
import ApartmentIcon from '@mui/icons-material/Apartment'
import PeopleIcon from '@mui/icons-material/People'
import DescriptionIcon from '@mui/icons-material/Description'
import TableChartIcon from '@mui/icons-material/TableChart'
import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { hasRole } from '../../utils/auth'

const DRAWER_WIDTH = 220

interface NavItem {
  label: string
  to: string
  icon: React.ReactNode
  roles?: Array<'super_admin' | 'admin' | 'manager' | 'employee'>
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', to: '/', icon: <DashboardIcon fontSize="small" /> },
  {
    label: 'Associations',
    to: '/associations',
    icon: <ApartmentIcon fontSize="small" />,
    roles: ['manager', 'admin', 'super_admin'],
  },
  {
    label: 'Users',
    to: '/users',
    icon: <PeopleIcon fontSize="small" />,
    roles: ['admin', 'super_admin'],
  },
  { label: 'Letter generator', to: '/letters', icon: <DescriptionIcon fontSize="small" /> },
  { label: 'Excel tools', to: '/excel', icon: <TableChartIcon fontSize="small" /> },
]

interface Props {
  mobileOpen: boolean
  onClose: () => void
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth()
  const location = useLocation()

  const visible = NAV_ITEMS.filter(
    (item) => !item.roles || (user && hasRole(user, item.roles)),
  )

  return (
    <List dense sx={{ pt: 1 }}>
      {visible.map((item) => {
        const active =
          item.to === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(item.to)
        return (
          <ListItemButton
            key={item.to}
            component={NavLink}
            to={item.to}
            selected={active}
            onClick={onNavigate}
            sx={{
              mx: 1,
              mb: 0.5,
              borderRadius: 1,
              '&.Mui-selected': {
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                '& .MuiListItemIcon-root': { color: 'primary.contrastText' },
                '&:hover': { bgcolor: 'primary.dark' },
              },
            }}
          >
            <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} slotProps={{ primary: { variant: 'body2' } }} />
          </ListItemButton>
        )
      })}
    </List>
  )
}

export default function Sidebar({ mobileOpen, onClose }: Props) {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))

  if (isMobile) {
    return (
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onClose}
        ModalProps={{ keepMounted: true }}
        sx={{
          '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' },
        }}
      >
        <Toolbar />
        <NavList onNavigate={onClose} />
      </Drawer>
    )
  }

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' },
      }}
    >
      <Toolbar />
      <NavList />
    </Drawer>
  )
}
