import { useCallback, useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import FormControl from '@mui/material/FormControl'
import IconButton from '@mui/material/IconButton'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import AddIcon from '@mui/icons-material/Add'
import BlockIcon from '@mui/icons-material/Block'
import EditIcon from '@mui/icons-material/Edit'
import ManageAccountsIcon from '@mui/icons-material/ManageAccounts'
import { DataGrid } from '@mui/x-data-grid'
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import apiClient from '../api/client'
import { useAuth } from '../hooks/useAuth'
import type { User, UserRole } from '../types'
import RoleBadge from '../components/layout/RoleBadge'
import ConfirmDialog from '../components/layout/ConfrimDialog'
import ErrorAlert from '../components/layout/ErrorAlert'
import LoadingSpinner from '../components/layout/LoadingSpinner'

const ROLES: UserRole[] = ['super_admin', 'admin', 'manager', 'employee']

const emptyCreateForm = {
  fname: '',
  lname: '',
  email: '',
  title: '',
  role: 'manager' as UserRole,
  password: '',
}

const emptyEditForm = {
  fname: '',
  lname: '',
  email: '',
  title: '',
  is_active: true,
}

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))

  const isSuperAdmin = currentUser?.role === 'super_admin'

  const [rows, setRows] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Failed to create user.',
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
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Failed to update user.',
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
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Failed to change role.',
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

  // On mobile, drop email + title columns to keep the grid readable
  const columns: GridColDef<User>[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 140,
      valueGetter: (_value, row) => `${row.fname} ${row.lname}`,
    },
    ...(!isMobile
      ? [
          { field: 'email', headerName: 'Email', flex: 1.5, minWidth: 200 } as GridColDef<User>,
          { field: 'title', headerName: 'Title', flex: 1, minWidth: 160 } as GridColDef<User>,
        ]
      : []),
    {
      field: 'role',
      headerName: 'Role',
      width: isMobile ? 110 : 130,
      renderCell: (params: GridRenderCellParams<User, UserRole>) => (
        <RoleBadge role={params.value!} />
      ),
    },
    {
      field: 'is_active',
      headerName: 'Status',
      width: 90,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'Active' : 'Inactive'}
          color={params.value ? 'success' : 'default'}
          size="small"
        />
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: isMobile ? 80 : 140,
      sortable: false,
      renderCell: (params: GridRenderCellParams<User>) => (
        <Box display="flex" gap={0.5}>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEdit(params.row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          {isSuperAdmin && !isMobile && (
            <>
              <Tooltip title="Change role">
                <IconButton size="small" onClick={() => openRoleChange(params.row)}>
                  <ManageAccountsIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              {params.row.is_active && (
                <Tooltip title="Deactivate">
                  <IconButton size="small" color="error" onClick={() => setDeactivateTarget(params.row)}>
                    <BlockIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}
            </>
          )}
          {/* On mobile show role + deactivate inside edit dialog — just show edit icon here */}
        </Box>
      ),
    },
  ]

  if (loading) return <LoadingSpinner />

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Users</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          New user
        </Button>
      </Box>

      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

      <Box sx={{ width: '100%', overflowX: 'auto' }}>
        <DataGrid
          rows={rows}
          columns={columns}
          autoHeight
          pageSizeOptions={[25, 50, 100]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          disableRowSelectionOnClick
          sx={{ bgcolor: 'background.paper', borderRadius: 2, minWidth: isMobile ? 360 : 640 }}
        />
      </Box>

      {/* Create user dialog */}
      <Dialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        fullScreen={fullScreen}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>New user</DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} pt={1}>
            {createError && <ErrorAlert message={createError} onClose={() => setCreateError(null)} />}
            <Box display="flex" flexDirection={{ xs: 'column', sm: 'row' }} gap={2}>
              <TextField
                label="First name"
                value={createForm.fname}
                onChange={(e) => setCreateForm((p) => ({ ...p, fname: e.target.value }))}
                fullWidth required
              />
              <TextField
                label="Last name"
                value={createForm.lname}
                onChange={(e) => setCreateForm((p) => ({ ...p, lname: e.target.value }))}
                fullWidth required
              />
            </Box>
            <TextField
              label="Email"
              type="email"
              value={createForm.email}
              onChange={(e) => setCreateForm((p) => ({ ...p, email: e.target.value }))}
              fullWidth required
            />
            <TextField
              label="Title"
              value={createForm.title}
              onChange={(e) => setCreateForm((p) => ({ ...p, title: e.target.value }))}
              fullWidth required
            />
            <FormControl fullWidth required>
              <InputLabel>Role</InputLabel>
              <Select
                value={createForm.role}
                label="Role"
                onChange={(e) => setCreateForm((p) => ({ ...p, role: e.target.value as UserRole }))}
              >
                {ROLES.map((r) => (
                  <MenuItem key={r} value={r}>{r.replace('_', ' ')}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Password"
              type="password"
              value={createForm.password}
              onChange={(e) => setCreateForm((p) => ({ ...p, password: e.target.value }))}
              fullWidth required
              autoComplete="new-password"
            />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setCreateOpen(false)} disabled={createLoading}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate} disabled={createLoading}>
            {createLoading ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit user dialog */}
      <Dialog
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        fullScreen={fullScreen}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Edit user</DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} pt={1}>
            {editError && <ErrorAlert message={editError} onClose={() => setEditError(null)} />}
            <Box display="flex" flexDirection={{ xs: 'column', sm: 'row' }} gap={2}>
              <TextField
                label="First name"
                value={editForm.fname}
                onChange={(e) => setEditForm((p) => ({ ...p, fname: e.target.value }))}
                fullWidth
              />
              <TextField
                label="Last name"
                value={editForm.lname}
                onChange={(e) => setEditForm((p) => ({ ...p, lname: e.target.value }))}
                fullWidth
              />
            </Box>
            <TextField
              label="Email"
              type="email"
              value={editForm.email}
              onChange={(e) => setEditForm((p) => ({ ...p, email: e.target.value }))}
              fullWidth
            />
            <TextField
              label="Title"
              value={editForm.title}
              onChange={(e) => setEditForm((p) => ({ ...p, title: e.target.value }))}
              fullWidth
            />
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={editForm.is_active ? 'active' : 'inactive'}
                label="Status"
                onChange={(e) => setEditForm((p) => ({ ...p, is_active: e.target.value === 'active' }))}
              >
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="inactive">Inactive</MenuItem>
              </Select>
            </FormControl>
            {/* Surface role + deactivate inside edit dialog on mobile */}
            {isMobile && isSuperAdmin && editTarget && (
              <>
                <FormControl fullWidth>
                  <InputLabel>Role</InputLabel>
                  <Select
                    value={editForm.is_active ? editTarget.role : editTarget.role}
                    label="Role"
                    onChange={(e) => {
                      setRoleTarget(editTarget)
                      setSelectedRole(e.target.value as UserRole)
                    }}
                  >
                    {ROLES.map((r) => (
                      <MenuItem key={r} value={r}>{r.replace('_', ' ')}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                {editTarget.is_active && (
                  <Button
                    color="error"
                    variant="outlined"
                    startIcon={<BlockIcon />}
                    onClick={() => {
                      setEditTarget(null)
                      setDeactivateTarget(editTarget)
                    }}
                  >
                    Deactivate user
                  </Button>
                )}
              </>
            )}
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEditTarget(null)} disabled={editLoading}>Cancel</Button>
          <Button variant="contained" onClick={handleEdit} disabled={editLoading}>
            {editLoading ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Change role dialog (desktop only — mobile uses edit dialog) */}
      <Dialog open={!!roleTarget} onClose={() => setRoleTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Change role — {roleTarget?.fname} {roleTarget?.lname}</DialogTitle>
        <DialogContent>
          <Box pt={1} display="flex" flexDirection="column" gap={2}>
            {roleError && <ErrorAlert message={roleError} onClose={() => setRoleError(null)} />}
            <FormControl fullWidth>
              <InputLabel>Role</InputLabel>
              <Select
                value={selectedRole}
                label="Role"
                onChange={(e) => setSelectedRole(e.target.value as UserRole)}
              >
                {ROLES.map((r) => (
                  <MenuItem key={r} value={r}>{r.replace('_', ' ')}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setRoleTarget(null)} disabled={roleLoading}>Cancel</Button>
          <Button variant="contained" onClick={handleRoleChange} disabled={roleLoading}>
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
