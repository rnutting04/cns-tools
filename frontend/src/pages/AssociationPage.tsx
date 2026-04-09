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
import GroupAddIcon from '@mui/icons-material/GroupAdd'
import LocationOnIcon from '@mui/icons-material/LocationOn'
import PersonIcon from '@mui/icons-material/Person'
import PersonRemoveIcon from '@mui/icons-material/PersonRemove'
import SearchIcon from '@mui/icons-material/Search'
import { DataGrid } from '@mui/x-data-grid'
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import apiClient from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { hasRole } from '../utils/auth'
import type { Association, User } from '../types'
import ConfirmDialog from '../components/layout/ConfrimDialog'
import ErrorAlert from '../components/layout/ErrorAlert'

const emptyForm = { legal_name: '', filter_name: '', location_name: '' }

// ─── Skeleton list ────────────────────────────────────────────────────────────

function AssocListSkeleton() {
  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
      {[0, 1, 2, 3].map((i) => (
        <Box key={i}>
          {i > 0 && <Divider />}
          <Box sx={{ p: 2 }}>
            <Skeleton variant="text" width="55%" height={22} />
            <Skeleton variant="text" width="35%" height={18} sx={{ mt: 0.5 }} />
            <Skeleton variant="text" width="45%" height={18} sx={{ mt: 0.25 }} />
            <Box display="flex" gap={1} mt={1.25}>
              <Skeleton variant="rounded" width={56} height={22} />
              <Skeleton variant="rounded" width={96} height={22} />
            </Box>
          </Box>
        </Box>
      ))}
    </Paper>
  )
}

// ─── Mobile list item ─────────────────────────────────────────────────────────

interface AssocRowProps {
  assoc: Association
  isAdmin: boolean
  isSuperAdmin: boolean
  isLast: boolean
  onEdit: (a: Association) => void
  onManageManagers: (a: Association) => void
  onDeactivate: (a: Association) => void
}

function AssocRow({ assoc, isAdmin, isSuperAdmin, isLast, onEdit, onManageManagers, onDeactivate }: AssocRowProps) {
  return (
    <>
      <Box sx={{ p: 2 }}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={1}>
          {/* Left: info */}
          <Box minWidth={0} flex={1}>
            <Typography variant="subtitle1" fontWeight={500} lineHeight={1.3}>
              {assoc.legal_name}
            </Typography>
            <Typography variant="body2" color="text.secondary" mt={0.25}>
              {assoc.filter_name}
            </Typography>
            <Box display="flex" alignItems="center" gap={0.5} mt={0.25}>
              <LocationOnIcon sx={{ fontSize: 13, color: 'text.disabled', flexShrink: 0 }} />
              <Typography variant="body2" color="text.secondary">
                {assoc.location_name}
              </Typography>
            </Box>
            {/* Managers + status chips */}
            <Box display="flex" gap={1} flexWrap="wrap" mt={1.25} alignItems="center">
              <Chip
                label={assoc.is_active ? 'Active' : 'Inactive'}
                color={assoc.is_active ? 'success' : 'default'}
                size="small"
              />
              {assoc.managers.length === 0 ? (
                <Box display="flex" alignItems="center" gap={0.5}>
                  <PersonIcon sx={{ fontSize: 13, color: 'text.disabled' }} />
                  <Typography variant="body2" color="text.disabled">Unassigned</Typography>
                </Box>
              ) : (
                assoc.managers.map((m) => (
                  <Chip
                    key={m.id}
                    icon={<PersonIcon />}
                    label={`${m.fname} ${m.lname}`}
                    size="small"
                    variant="outlined"
                  />
                ))
              )}
            </Box>
          </Box>
          {/* Right: actions */}
          {isAdmin && (
            <Box display="flex" gap={0.25} flexShrink={0}>
              <Tooltip title="Edit">
                <IconButton size="small" onClick={() => onEdit(assoc)}>
                  <EditIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Manage managers">
                <IconButton size="small" onClick={() => onManageManagers(assoc)}>
                  <GroupAddIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              {isSuperAdmin && assoc.is_active && (
                <Tooltip title="Deactivate">
                  <IconButton size="small" color="error" onClick={() => onDeactivate(assoc)}>
                    <BlockIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}
            </Box>
          )}
        </Box>
      </Box>
      {!isLast && <Divider />}
    </>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AssociationPage() {
  const { user } = useAuth()
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))

  const isAdmin = user ? hasRole(user, ['admin', 'super_admin']) : false
  const isSuperAdmin = user?.role === 'super_admin'

  const [rows, setRows] = useState<Association[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const [formOpen, setFormOpen] = useState(false)
  const [formData, setFormData] = useState(emptyForm)
  const [editTarget, setEditTarget] = useState<Association | null>(null)
  const [formLoading, setFormLoading] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [deactivateTarget, setDeactivateTarget] = useState<Association | null>(null)
  const [deactivateLoading, setDeactivateLoading] = useState(false)

  const [managerDialogAssoc, setManagerDialogAssoc] = useState<Association | null>(null)
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [selectedUserId, setSelectedUserId] = useState('')
  const [managerLoading, setManagerLoading] = useState(false)
  const [managerError, setManagerError] = useState<string | null>(null)

  const fetchAssociations = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await apiClient.get<Association[]>('/api/associations')
      setRows(data)
    } catch {
      setError('Failed to load associations.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAssociations() }, [fetchAssociations])

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    if (!q) return rows
    return rows.filter((a) =>
      `${a.legal_name} ${a.filter_name} ${a.location_name}`.toLowerCase().includes(q),
    )
  }, [rows, search])

  function openCreate() {
    setEditTarget(null)
    setFormData(emptyForm)
    setFormError(null)
    setFormOpen(true)
  }

  function openEdit(assoc: Association) {
    setEditTarget(assoc)
    setFormData({ legal_name: assoc.legal_name, filter_name: assoc.filter_name, location_name: assoc.location_name })
    setFormError(null)
    setFormOpen(true)
  }

  async function handleFormSubmit() {
    setFormLoading(true)
    setFormError(null)
    try {
      if (editTarget) {
        await apiClient.patch(`/api/associations/${editTarget.id}`, formData)
      } else {
        await apiClient.post('/api/associations', formData)
      }
      setFormOpen(false)
      fetchAssociations()
    } catch (err: unknown) {
      setFormError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Save failed.',
      )
    } finally {
      setFormLoading(false)
    }
  }

  async function handleDeactivate() {
    if (!deactivateTarget) return
    setDeactivateLoading(true)
    try {
      await apiClient.delete(`/api/associations/${deactivateTarget.id}`)
      setDeactivateTarget(null)
      fetchAssociations()
    } catch {
      setError('Failed to deactivate association.')
    } finally {
      setDeactivateLoading(false)
    }
  }

  async function openManagerDialog(assoc: Association) {
    setManagerDialogAssoc(assoc)
    setSelectedUserId('')
    setManagerError(null)
    if (isAdmin) {
      const { data } = await apiClient.get<User[]>('/api/users')
      setAllUsers(data.filter((u) => u.is_active))
    }
  }

  async function handleAssignManager() {
    if (!managerDialogAssoc || !selectedUserId) return
    setManagerLoading(true)
    setManagerError(null)
    try {
      await apiClient.post(`/api/associations/${managerDialogAssoc.id}/managers`, { user_id: selectedUserId })
      const updated = await apiClient.get<Association[]>('/api/associations')
      setRows(updated.data)
      setManagerDialogAssoc(updated.data.find((a) => a.id === managerDialogAssoc.id) ?? null)
      setSelectedUserId('')
    } catch (err: unknown) {
      setManagerError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to assign manager.',
      )
    } finally {
      setManagerLoading(false)
    }
  }

  async function handleRemoveManager(assocId: string, userId: string) {
    setManagerLoading(true)
    setManagerError(null)
    try {
      await apiClient.delete(`/api/associations/${assocId}/managers/${userId}`)
      const updated = await apiClient.get<Association[]>('/api/associations')
      setRows(updated.data)
      setManagerDialogAssoc(updated.data.find((a) => a.id === assocId) ?? null)
    } catch {
      setManagerError('Failed to remove manager.')
    } finally {
      setManagerLoading(false)
    }
  }

  const columns: GridColDef<Association>[] = [
    { field: 'legal_name', headerName: 'Legal name', flex: 2, minWidth: 200 },
    { field: 'filter_name', headerName: 'Filter name', flex: 1, minWidth: 130 },
    { field: 'location_name', headerName: 'Location', flex: 1, minWidth: 130 },
    {
      field: 'managers', headerName: 'Managers', flex: 1.5, minWidth: 180, sortable: false,
      renderCell: (params: GridRenderCellParams<Association, User[]>) => (
        <Box display="flex" flexWrap="wrap" gap={0.5} alignItems="center" py={0.5}>
          {(params.value ?? []).map((m) => (
            <Chip key={m.id} label={`${m.fname} ${m.lname}`} size="small" />
          ))}
        </Box>
      ),
    },
    {
      field: 'is_active', headerName: 'Status', width: 100,
      renderCell: (params) => (
        <Chip label={params.value ? 'Active' : 'Inactive'} color={params.value ? 'success' : 'default'} size="small" />
      ),
    },
    ...(isAdmin ? ([{
      field: 'actions', headerName: 'Actions', width: 140, sortable: false,
      renderCell: (params: GridRenderCellParams<Association>) => (
        <Box display="flex" gap={0.5}>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEdit(params.row)}><EditIcon fontSize="small" /></IconButton>
          </Tooltip>
          <Tooltip title="Manage managers">
            <IconButton size="small" onClick={() => openManagerDialog(params.row)}><GroupAddIcon fontSize="small" /></IconButton>
          </Tooltip>
          {isSuperAdmin && params.row.is_active && (
            <Tooltip title="Deactivate">
              <IconButton size="small" color="error" onClick={() => setDeactivateTarget(params.row)}>
                <BlockIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      ),
    }] as GridColDef<Association>[]) : []),
  ]

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Associations</Typography>
        {isAdmin && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            New association
          </Button>
        )}
      </Box>

      {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

      {/* Search */}
      <TextField
        placeholder="Search by name or location…"
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
          <AssocListSkeleton />
        ) : filtered.length === 0 ? (
          <Typography color="text.secondary" textAlign="center" py={6}>
            No associations found.
          </Typography>
        ) : (
          <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
            {filtered.map((a, i) => (
              <AssocRow
                key={a.id}
                assoc={a}
                isAdmin={isAdmin}
                isSuperAdmin={isSuperAdmin}
                isLast={i === filtered.length - 1}
                onEdit={openEdit}
                onManageManagers={openManagerDialog}
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
          getRowHeight={() => 'auto'}
          autoHeight
          pageSizeOptions={[25, 50, 100]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          disableRowSelectionOnClick
          sx={{ bgcolor: 'background.paper', borderRadius: 2 }}
        />
      )}

      {/* Create / edit dialog */}
      <Dialog open={formOpen} onClose={() => setFormOpen(false)} fullScreen={fullScreen} maxWidth="sm" fullWidth>
        <DialogTitle>{editTarget ? 'Edit association' : 'New association'}</DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} pt={1}>
            {formError && <ErrorAlert message={formError} onClose={() => setFormError(null)} />}
            <TextField label="Legal name" value={formData.legal_name} fullWidth required
              onChange={(e) => setFormData((p) => ({ ...p, legal_name: e.target.value }))} />
            <TextField label="Filter name" value={formData.filter_name} fullWidth required
              onChange={(e) => setFormData((p) => ({ ...p, filter_name: e.target.value }))} />
            <TextField label="Location" value={formData.location_name} fullWidth required
              onChange={(e) => setFormData((p) => ({ ...p, location_name: e.target.value }))} />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setFormOpen(false)} disabled={formLoading}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleFormSubmit}
            disabled={formLoading}
            startIcon={formLoading ? <CircularProgress size={16} color="inherit" /> : undefined}
          >
            {formLoading ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Deactivate confirm */}
      <ConfirmDialog
        open={!!deactivateTarget}
        title="Deactivate association"
        description={`Deactivate "${deactivateTarget?.legal_name}"? This cannot be undone from the UI.`}
        confirmLabel="Deactivate"
        loading={deactivateLoading}
        onConfirm={handleDeactivate}
        onCancel={() => setDeactivateTarget(null)}
      />

      {/* Manager assignment dialog */}
      <Dialog
        open={!!managerDialogAssoc}
        onClose={() => setManagerDialogAssoc(null)}
        fullScreen={fullScreen}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          Manage managers
          <Typography variant="body2" color="text.secondary" mt={0.25}>
            {managerDialogAssoc?.filter_name}
          </Typography>
        </DialogTitle>
        <Divider />
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} pt={1}>
            {managerError && <ErrorAlert message={managerError} onClose={() => setManagerError(null)} />}

            <Typography variant="body2" color="text.secondary">Current managers</Typography>
            <Box display="flex" flexWrap="wrap" gap={1} minHeight={32}>
              {(managerDialogAssoc?.managers ?? []).length === 0 && (
                <Typography variant="body2" color="text.disabled">None assigned</Typography>
              )}
              {(managerDialogAssoc?.managers ?? []).map((m) => (
                <Chip
                  key={m.id}
                  label={`${m.fname} ${m.lname}`}
                  onDelete={() => handleRemoveManager(managerDialogAssoc!.id, m.id)}
                  deleteIcon={<PersonRemoveIcon />}
                  disabled={managerLoading}
                />
              ))}
            </Box>

            <Divider />
            <Typography variant="body2" color="text.secondary">Assign a manager</Typography>
            <FormControl fullWidth size="small">
              <InputLabel>Select user</InputLabel>
              <Select value={selectedUserId} label="Select user"
                onChange={(e) => setSelectedUserId(e.target.value)}>
                {allUsers
                  .filter((u) => !managerDialogAssoc?.managers.some((m) => m.id === u.id))
                  .map((u) => (
                    <MenuItem key={u.id} value={u.id}>
                      {u.fname} {u.lname} — {u.title}
                    </MenuItem>
                  ))}
              </Select>
            </FormControl>
            <Button
              variant="contained"
              onClick={handleAssignManager}
              disabled={!selectedUserId || managerLoading}
              fullWidth
              startIcon={managerLoading ? <CircularProgress size={16} color="inherit" /> : undefined}
            >
              {managerLoading ? 'Assigning…' : 'Assign'}
            </Button>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setManagerDialogAssoc(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
