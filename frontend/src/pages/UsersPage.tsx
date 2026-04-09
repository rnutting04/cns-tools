import { useCallback, useEffect, useMemo, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Divider from '@mui/material/Divider'
import FormControl from '@mui/material/FormControl'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Select from '@mui/material/Select'
import Skeleton from '@mui/material/Skeleton'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import AddIcon from '@mui/icons-material/Add'
import BlockIcon from '@mui/icons-material/Block'
import EditIcon from '@mui/icons-material/Edit'
import EmailIcon from '@mui/icons-material/Email'
import ManageAccountsIcon from '@mui/icons-material/ManageAccounts'
import SearchIcon from '@mui/icons-material/Search'
import WorkIcon from '@mui/icons-material/Work'
import { DataGrid } from '@mui/x-data-grid'
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import apiClient from '../api/client'
import { useAuth } from '../hooks/useAuth'
import type { User, UserRole } from '../types'
import RoleBadge from '../components/layout/RoleBadge'
import ConfirmDialog from '../components/layout/ConfrimDialog'
import ErrorAlert from '../components/layout/ErrorAlert'

const ROLES: UserRole[] = ['super_admin', 'admin', 'manager', 'employee']

const emptyCreateForm = {
  fname: '', lname: '', email: '', title: '',
  role: 'manager' as UserRole, password: '',
}
const emptyEditForm = { fname: '', lname: '', email: '', title: '', is_active: true }

// ─── Skeleton list ────────────────────────────────────────────────────────────

function UserListSkeleton() {
  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
      {[0, 1, 2, 3].map((i) => (
        <Box key={i}>
          {i > 0 && <Divider />}
          <Box sx={{ p: 2 }}>
            <Skeleton variant="text" width="45%" height={22} />
            <Skeleton variant="text" width="65%" height={18} sx={{ mt: 0.5 }} />
            <Skeleton variant="text" width="40%" height={18} sx={{ mt: 0.25 }} />
            <Box display="flex" gap={1} mt={1.5}>
              <Skeleton variant="rounded" width={72} height={22} />
              <Skeleton variant="rounded" width={56} height={22} />
            </Box>
          </Box>
        </Box>
      ))}
    </Paper>
  )
}

// ─── Mobile list item ─────────────────────────────────────────────────────────

interface UserRowProps {
  user: User
  isSuperAdmin: boolean
  isLast: boolean
  onEdit: (u: User) => void
  onRoleChange: (u: User) => void
  onDeactivate: (u: User) => void
}

function UserRow({ user, isSuperAdmin, isLast, onEdit, onRoleChange, onDeactivate }: UserRowProps) {
  return (
    <>
      <Box sx={{ p: 2 }}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={1}>
          {/* Left: info */}
          <Box minWidth={0} flex={1}>
            <Typography variant="subtitle1" fontWeight={500} lineHeight={1.3}>
              {user.fname} {user.lname}
            </Typography>
            <Box display="flex" alignItems="center" gap={0.5} mt={0.5}>
              <EmailIcon sx={{ fontSize: 13, color: 'text.disabled', flexShrink: 0 }} />
              <Typography variant="body2" color="text.secondary" noWrap>
                {user.email}
              </Typography>
            </Box>
            <Box display="flex" alignItems="center" gap={0.5} mt={0.25}>
              <WorkIcon sx={{ fontSize: 13, color: 'text.disabled', flexShrink: 0 }} />
              <Typography variant="body2" color="text.secondary" noWrap>
                {user.title}
              </Typography>
            </Box>
            <Box display="flex" gap={1} flexWrap="wrap" mt={1.25}>
              <RoleBadge role={user.role} />
              <Chip
                label={user.is_active ? 'Active' : 'Inactive'}
                color={user.is_active ? 'success' : 'default'}
                size="small"
              />
            </Box>
          </Box>
          {/* Right: actions */}
          <Box display="flex" gap={0.25} flexShrink={0}>
            <Tooltip title="Edit">
              <IconButton size="small" onClick={() => onEdit(user)}>
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {isSuperAdmin && (
              <>
                <Tooltip title="Change role">
                  <IconButton size="small" onClick={() => onRoleChange(user)}>
                    <ManageAccountsIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                {user.is_active && (
                  <Tooltip title="Deactivate">
                    <IconButton size="small" color="error" onClick={() => onDeactivate(user)}>
                      <BlockIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </>
            )}
          </Box>
        </Box>
      </Box>
      {!isLast && <Divider />}
    </>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  const isSuperAdmin = currentUser?.role === 'super_admin'

  const [rows, setRows] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState(emptyCreateForm)
  const [createLoading, setCreateLoading] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const [editTarget, setEditTarget] = useState<User | null>(null)
  const [editForm, setEditForm] = useState(emptyEditForm)
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  const [roleTarget, setRoleTarget] = useState<User | null>(null)
  const [selectedRole, setSelectedRole] = useState<UserRole>('manager')
  const [roleLoading, setRoleLoading] = useState(false)
  const [roleError, setRoleError] = useState<string | null>(null)

  const [deactivateTarget, setDeactivateTarget] = useState<User | null>(null)
  const [deactivateLoading, setDeactivateLoading] = useState(false)

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await apiClient.get<User[]>('/api/users')
      setRows(data)
    } catch {
      setError('Failed to load users.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchUsers() }, [fetchUsers])

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    if (!q) return rows
    return rows.filter((u) =>
      `${u.fname} ${u.lname} ${u.email} ${u.title}`.toLowerCase().includes(q),
    )
  }, [rows, search])

  function openCreate() {
    setCreateForm(emptyCreateForm)
    setCreateError(null)
    setCreateOpen(true)
  }

  async function handleCreate() {
    setCreateLoading(true)
    setCreateError(null)
    try {
      await apiClient.post('/api/users', createForm)
      setCreateOpen(false)
      fetchUsers()
    } catch (err: unknown) {
      setCreateError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create user.',
      )
    } finally {
      setCreateLoading(false)
    }
  }

  function openEdit(u: User) {
    setEditTarget(u)
    setEditForm({ fname: u.fname, lname: u.lname, email: u.email, title: u.title, is_active: u.is_active })
    setEditError(null)
  }

  async function handleEdit() {
    if (!editTarget) return
    setEditLoading(true)
    setEditError(null)
    try {
      await apiClient.patch(`/api/users/${editTarget.id}`, editForm)
      setEditTarget(null)
      fetchUsers()
    } catch (err: unknown) {
      setEditError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to update user.',
      )
    } finally {
      setEditLoading(false)
    }
  }

  function openRoleChange(u: User) {
    setRoleTarget(u)
    setSelectedRole(u.role)
    setRoleError(null)
  }

  async function handleRoleChange() {
    if (!roleTarget) return
    setRoleLoading(true)
    setRoleError(null)
    try {
      await apiClient.patch(`/api/users/${roleTarget.id}/role`, { role: selectedRole })
      setRoleTarget(null)
      fetchUsers()
    } catch (err: unknown) {
      setRoleError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to change role.',
      )
    } finally {
      setRoleLoading(false)
    }
  }

  async function handleDeactivate() {
    if (!deactivateTarget) return
    setDeactivateLoading(true)
    try {
      await apiClient.delete(`/api/users/${deactivateTarget.id}`)
      setDeactivateTarget(null)
      fetchUsers()
    } catch {
      setError('Failed to deactivate user.')
    } finally {
      setDeactivateLoading(false)
    }
  }

  const columns: GridColDef<User>[] = [
    {
      field: 'name', headerName: 'Name', flex: 1, minWidth: 160,
      valueGetter: (_v, row) => `${row.fname} ${row.lname}`,
    },
    { field: 'email', headerName: 'Email', flex: 1.5, minWidth: 200 },
    { field: 'title', headerName: 'Title', flex: 1, minWidth: 160 },
    {
      field: 'role', headerName: 'Role', width: 130,
      renderCell: (params: GridRenderCellParams<User, UserRole>) => <RoleBadge role={params.value!} />,
    },
    {
      field: 'is_active', headerName: 'Status', width: 100,
      renderCell: (params) => (
        <Chip label={params.value ? 'Active' : 'Inactive'} color={params.value ? 'success' : 'default'} size="small" />
      ),
    },
    {
      field: 'actions', headerName: 'Actions', width: 140, sortable: false,
      renderCell: (params: GridRenderCellParams<User>) => (
        <Box display="flex" gap={0.5}>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEdit(params.row)}><EditIcon fontSize="small" /></IconButton>
          </Tooltip>
          {isSuperAdmin && (
            <>
              <Tooltip title="Change role">
                <IconButton size="small" onClick={() => openRoleChange(params.row)}><ManageAccountsIcon fontSize="small" /></IconButton>
              </Tooltip>
              {params.row.is_active && (
                <Tooltip title="Deactivate">
                  <IconButton size="small" color="error" onClick={() => setDeactivateTarget(params.row)}><BlockIcon fontSize="small" /></IconButton>
                </Tooltip>
              )}
            </>
          )}
        </Box>
      ),
    },
  ]

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Users</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          New user
        </Button>
      </Box>

      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

      {/* Search */}
      <TextField
        placeholder="Search by name, email or title…"
        size="small"
        fullWidth
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 2 }}
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          },
        }}
      />

      {/* Desktop: DataGrid — Mobile: list */}
      {isMobile ? (
        loading ? (
          <UserListSkeleton />
        ) : filtered.length === 0 ? (
          <Typography color="text.secondary" textAlign="center" py={6}>
            No users found.
          </Typography>
        ) : (
          <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
            {filtered.map((u, i) => (
              <UserRow
                key={u.id}
                user={u}
                isSuperAdmin={isSuperAdmin}
                isLast={i === filtered.length - 1}
                onEdit={openEdit}
                onRoleChange={openRoleChange}
                onDeactivate={setDeactivateTarget}
              />
            ))}
          </Paper>
        )
      ) : (
        <DataGrid
          rows={filtered}
          columns={columns}
          loading={loading}
          autoHeight
          pageSizeOptions={[25, 50, 100]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          disableRowSelectionOnClick
          sx={{ bgcolor: 'background.paper', borderRadius: 2 }}
        />
      )}

      {/* Create user dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullScreen={fullScreen} maxWidth="sm" fullWidth>
        <DialogTitle>New user</DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} pt={1}>
            {createError && <ErrorAlert message={createError} onClose={() => setCreateError(null)} />}
            <Box display="flex" flexDirection={{ xs: 'column', sm: 'row' }} gap={2}>
              <TextField label="First name" value={createForm.fname} fullWidth required
                onChange={(e) => setCreateForm((p) => ({ ...p, fname: e.target.value }))} />
              <TextField label="Last name" value={createForm.lname} fullWidth required
                onChange={(e) => setCreateForm((p) => ({ ...p, lname: e.target.value }))} />
            </Box>
            <TextField label="Email" type="email" value={createForm.email} fullWidth required
              onChange={(e) => setCreateForm((p) => ({ ...p, email: e.target.value }))} />
            <TextField label="Title" value={createForm.title} fullWidth required
              onChange={(e) => setCreateForm((p) => ({ ...p, title: e.target.value }))} />
            <FormControl fullWidth required>
              <InputLabel>Role</InputLabel>
              <Select value={createForm.role} label="Role"
                onChange={(e) => setCreateForm((p) => ({ ...p, role: e.target.value as UserRole }))}>
                {ROLES.map((r) => <MenuItem key={r} value={r}>{r.replace('_', ' ')}</MenuItem>)}
              </Select>
            </FormControl>
            <TextField label="Password" type="password" value={createForm.password} fullWidth required
              autoComplete="new-password"
              onChange={(e) => setCreateForm((p) => ({ ...p, password: e.target.value }))} />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setCreateOpen(false)} disabled={createLoading}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={createLoading}
            startIcon={createLoading ? <CircularProgress size={16} color="inherit" /> : undefined}
          >
            {createLoading ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit user dialog */}
      <Dialog open={!!editTarget} onClose={() => setEditTarget(null)} fullScreen={fullScreen} maxWidth="sm" fullWidth>
        <DialogTitle>Edit user</DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} pt={1}>
            {editError && <ErrorAlert message={editError} onClose={() => setEditError(null)} />}
            <Box display="flex" flexDirection={{ xs: 'column', sm: 'row' }} gap={2}>
              <TextField label="First name" value={editForm.fname} fullWidth
                onChange={(e) => setEditForm((p) => ({ ...p, fname: e.target.value }))} />
              <TextField label="Last name" value={editForm.lname} fullWidth
                onChange={(e) => setEditForm((p) => ({ ...p, lname: e.target.value }))} />
            </Box>
            <TextField label="Email" type="email" value={editForm.email} fullWidth
              onChange={(e) => setEditForm((p) => ({ ...p, email: e.target.value }))} />
            <TextField label="Title" value={editForm.title} fullWidth
              onChange={(e) => setEditForm((p) => ({ ...p, title: e.target.value }))} />
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select value={editForm.is_active ? 'active' : 'inactive'} label="Status"
                onChange={(e) => setEditForm((p) => ({ ...p, is_active: e.target.value === 'active' }))}>
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="inactive">Inactive</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEditTarget(null)} disabled={editLoading}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleEdit}
            disabled={editLoading}
            startIcon={editLoading ? <CircularProgress size={16} color="inherit" /> : undefined}
          >
            {editLoading ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Change role dialog */}
      <Dialog open={!!roleTarget} onClose={() => setRoleTarget(null)} fullScreen={fullScreen} maxWidth="xs" fullWidth>
        <DialogTitle>Change role</DialogTitle>
        <DialogContent>
          <Box pt={0.5} pb={1}>
            <Typography variant="body2" color="text.secondary" mb={2}>
              {roleTarget?.fname} {roleTarget?.lname}
            </Typography>
            <Divider sx={{ mb: 2 }} />
            {roleError && <ErrorAlert message={roleError} onClose={() => setRoleError(null)} />}
            <FormControl fullWidth>
              <InputLabel>Role</InputLabel>
              <Select value={selectedRole} label="Role"
                onChange={(e) => setSelectedRole(e.target.value as UserRole)}>
                {ROLES.map((r) => <MenuItem key={r} value={r}>{r.replace('_', ' ')}</MenuItem>)}
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setRoleTarget(null)} disabled={roleLoading}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleRoleChange}
            disabled={roleLoading}
            startIcon={roleLoading ? <CircularProgress size={16} color="inherit" /> : undefined}
          >
            {roleLoading ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Deactivate confirm */}
      <ConfirmDialog
        open={!!deactivateTarget}
        title="Deactivate user"
        description={`Deactivate ${deactivateTarget?.fname} ${deactivateTarget?.lname}? They will no longer be able to log in.`}
        confirmLabel="Deactivate"
        loading={deactivateLoading}
        onConfirm={handleDeactivate}
        onCancel={() => setDeactivateTarget(null)}
      />
    </Box>
  )
}
