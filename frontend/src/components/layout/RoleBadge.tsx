import Chip from '@mui/material/Chip'
import type { UserRole } from '../../types'

const config: Record<UserRole, { label: string; color: 'error' | 'warning' | 'info' | 'default' }> = {
  super_admin: { label: 'Super admin', color: 'error' },
  admin: { label: 'Admin', color: 'warning' },
  manager: { label: 'Manager', color: 'info' },
  employee: { label: 'Employee', color: 'default' },
}

interface Props {
  role: UserRole
  size?: 'small' | 'medium'
}

export default function RoleBadge({ role, size = 'small' }: Props) {
  const { label, color } = config[role]
  return <Chip label={label} color={color} size={size} />
}
