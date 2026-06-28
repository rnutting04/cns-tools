import { useEffect, useRef, useState } from 'react'
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
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Select from '@mui/material/Select'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import AddIcon from '@mui/icons-material/Add'
import BlockIcon from '@mui/icons-material/Block'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import { DataGrid } from '@mui/x-data-grid'
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import apiClient from '../api/client'
import ErrorAlert from '../components/layout/ErrorAlert'
import type { FieldRow, FieldDefinition, Template, RendererType } from '../types'

const EMPTY_FIELD: Omit<FieldDefinition, 'options'> & { options: string; auto_populate: boolean } =
  {
    key: '',
    label: '',
    type: 'text',
    options: '',
    auto_populate: false,
  }

function FieldBuilder({
  fields,
  onChange,
}: {
  fields: FieldRow[]
  onChange: (fields: FieldRow[]) => void
}) {
  const addField = () => onChange([...fields, { ...EMPTY_FIELD }])
  const removeField = (i: number) => onChange(fields.filter((_, idx) => idx !== i))
  const update = (i: number, patch: Partial<FieldRow>) =>
    onChange(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f)))

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
        <Typography variant="subtitle2" color="text.secondary">
          Fields
        </Typography>
        <Button size="small" startIcon={<AddIcon />} onClick={addField}>
          Add field
        </Button>
      </Box>

      {fields.length === 0 && (
        <Typography variant="body2" color="text.secondary" mb={1}>
          No fields defined. Click &quot;Add field&quot; to add placeholders.
        </Typography>
      )}

      <Box display="flex" flexDirection="column" gap={2}>
        {fields.map((f, i) => (
          <Paper key={i} variant="outlined" sx={{ p: 1.5, borderRadius: 1 }}>
            <Box display="flex" gap={1} flexWrap="wrap" alignItems="flex-start">
              <TextField
                label="Key (placeholder)"
                size="small"
                value={f.key}
                onChange={(e) => update(i, { key: e.target.value })}
                sx={{ flex: '1 1 140px' }}
                helperText={`{{${f.key || 'key'}}}`}
              />

              <TextField
                label="Label"
                size="small"
                value={f.label}
                onChange={(e) => update(i, { label: e.target.value })}
                sx={{ flex: '1 1 140px' }}
              />

              <FormControl size="small" sx={{ flex: '0 0 110px' }}>
                <InputLabel>Type</InputLabel>
                <Select
                  value={f.type}
                  label="Type"
                  onChange={(e) => update(i, { type: e.target.value as FieldRow['type'] })}
                >
                  <MenuItem value="text">Text</MenuItem>
                  <MenuItem value="date">Date</MenuItem>
                  <MenuItem value="dropdown">Dropdown</MenuItem>
                  <MenuItem value="association">Association</MenuItem>
                  <MenuItem value="manager">Manager</MenuItem>
                  <MenuItem value="time">Time</MenuItem>
                </Select>
              </FormControl>

              {f.type === 'dropdown' && (
                <TextField
                  label="Options (comma-separated)"
                  size="small"
                  value={f.options}
                  onChange={(e) => update(i, { options: e.target.value })}
                  sx={{ flex: '1 1 200px' }}
                />
              )}

              <FormControl size="small" sx={{ flex: '0 0 140px' }}>
                <InputLabel>Auto-populate</InputLabel>
                <Select
                  value={f.auto_populate ? 'yes' : 'no'}
                  label="Auto-populate"
                  onChange={(e) => update(i, { auto_populate: e.target.value === 'yes' })}
                >
                  <MenuItem value="no">No</MenuItem>
                  <MenuItem value="yes">Yes</MenuItem>
                </Select>
              </FormControl>

              <IconButton size="small" onClick={() => removeField(i)} sx={{ mt: 0.5 }}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Box>
          </Paper>
        ))}
      </Box>
    </Box>
  )
}

type DialogMode = 'create' | 'edit' | 'duplicate'

function fieldDefToRow(f: FieldDefinition): FieldRow {
  return {
    key: f.key,
    label: f.label,
    type: f.type,
    options: (f.options ?? []).join(', '),
    auto_populate: f.auto_populate ?? false,
  }
}

function fileNameFromPath(path: string): string {
  return path.split('/').pop() ?? path
}

function TemplateDialog({
  open,
  mode,
  template,
  onClose,
  onSaved,
}: {
  open: boolean
  mode: DialogMode
  template?: Template
  onClose: () => void
  onSaved: (t: Template, mode: DialogMode) => void
}) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  const fileRef = useRef<HTMLInputElement>(null)

  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [rendererType, setRendererType] = useState<RendererType>('simple')
  const [file, setFile] = useState<File | null>(null)
  const [fields, setFields] = useState<FieldRow[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Prefill from the source template whenever the dialog is (re)opened for a
  // given template, so edit/duplicate show existing values and stale data from
  // a previously opened template never leaks in.
  useEffect(() => {
    if (!open) return
    if ((mode === 'edit' || mode === 'duplicate') && template) {
      setName(mode === 'duplicate' ? `${template.name} (Copy)` : template.name)
      setCategory(template.category)
      setRendererType(template.renderer_type ?? 'simple')
      setFields(template.fields.map(fieldDefToRow))
    } else {
      setName('')
      setCategory('')
      setRendererType('simple')
      setFields([])
    }
    setFile(null)
    setError(null)
    if (fileRef.current) {
      fileRef.current.value = ''
    }
  }, [open, mode, template])

  const handleClose = () => {
    onClose()
  }

  const handleSubmit = async () => {
    const fileRequired = mode === 'create'
    if (!name.trim() || !category.trim() || (fileRequired && !file)) {
      setError(
        fileRequired ? 'Name, category, and file are required.' : 'Name and category are required.',
      )
      return
    }

    const invalidField = fields.find((f) => !f.key.trim() || !f.label.trim())
    if (invalidField) {
      setError('Every field needs both a key and label.')
      return
    }

    setError(null)
    setSubmitting(true)

    const fieldsPayload: FieldDefinition[] = fields.map((f) => ({
      key: f.key.trim(),
      label: f.label.trim(),
      type: f.type,
      options:
        f.type === 'dropdown'
          ? f.options
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean)
          : [],
      auto_populate: f.auto_populate,
    }))

    const form = new FormData()
    form.append('name', name.trim())
    form.append('category', category.trim())
    form.append('renderer_type', rendererType)
    form.append('fields', JSON.stringify(fieldsPayload))
    if (file) {
      form.append('file', file)
    }

    const config = { headers: { 'Content-Type': 'multipart/form-data' } }

    try {
      let res
      if (mode === 'edit' && template) {
        res = await apiClient.patch<Template>(`/api/templates/${template.id}`, form, config)
      } else if (mode === 'duplicate' && template) {
        res = await apiClient.post<Template>(
          `/api/templates/${template.id}/duplicate`,
          form,
          config,
        )
      } else {
        res = await apiClient.post<Template>('/api/templates', form, config)
      }
      onSaved(res.data, mode)
      handleClose()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Save failed.'
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const titleText =
    mode === 'edit'
      ? 'Edit template'
      : mode === 'duplicate'
        ? 'Duplicate template'
        : 'Upload template'
  const submitText =
    mode === 'edit' ? 'Save changes' : mode === 'duplicate' ? 'Create duplicate' : 'Upload'
  const submittingText =
    mode === 'edit' ? 'Saving…' : mode === 'duplicate' ? 'Creating…' : 'Uploading…'
  const currentFileName = template ? fileNameFromPath(template.docx_path) : null

  const helperText =
    rendererType === 'proxy'
      ? 'Requires {{BLOCK:PROXY_VOTES}} anchor. Generates a vote-item table.'
      : rendererType === 'ballot'
        ? 'Requires {{BLOCK:BALLOT_CANDIDATES}} anchor. Accepts dynamic candidate list from user.'
        : rendererType === 'electronic_ballot'
          ? 'Requires {{BLOCK:ELECTRONIC_BALLOT_CANDIDATES}} anchor. Checkbox-style electronic ballot.'
          : rendererType === 'notice_candidacy'
            ? 'Standard placeholder replacement for notice/candidacy documents. Includes 60-day meeting-date warning.'
            : 'Standard placeholder-based template, e.g. {{association_name}}.'

  return (
    <Dialog open={open} onClose={handleClose} fullScreen={fullScreen} maxWidth="md" fullWidth>
      <DialogTitle>{titleText}</DialogTitle>

      <DialogContent>
        <Box display="flex" flexDirection="column" gap={2} pt={1}>
          {error && <ErrorAlert message={error} onClose={() => setError(null)} />}

          <TextField
            label="Template name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            size="small"
            fullWidth
          />

          <TextField
            label="Category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            size="small"
            fullWidth
          />

          <FormControl size="small" fullWidth>
            <InputLabel>Renderer type</InputLabel>
            <Select
              value={rendererType}
              label="Renderer type"
              onChange={(e) => setRendererType(e.target.value as RendererType)}
            >
              <MenuItem value="simple">simple</MenuItem>
              <MenuItem value="proxy">proxy</MenuItem>
              <MenuItem value="ballot">ballot</MenuItem>
              <MenuItem value="electronic_ballot">electronic_ballot</MenuItem>
              <MenuItem value="notice_candidacy">notice_candidacy</MenuItem>
            </Select>
          </FormControl>

          <Typography variant="body2" color="text.secondary">
            {helperText}
          </Typography>

          <Box>
            <Typography variant="subtitle2" color="text.secondary" mb={0.5}>
              {mode === 'create' ? '.docx file' : 'Replace .docx (optional)'}
            </Typography>
            <Button
              variant="outlined"
              startIcon={<UploadFileIcon />}
              component="label"
              size="small"
            >
              {file ? file.name : 'Choose file'}
              <input
                ref={fileRef}
                type="file"
                accept=".docx"
                hidden
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </Button>
            {!file && currentFileName && mode !== 'create' && (
              <Typography variant="caption" color="text.secondary" display="block" mt={0.5}>
                {mode === 'edit' ? 'Current file: ' : 'Will copy: '}
                {currentFileName}
              </Typography>
            )}
          </Box>

          <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Template note
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Keep placeholders in a single Word run when possible. If Word splits a placeholder
              across styled runs, backend replacement can fail.
            </Typography>
          </Paper>

          <Divider />

          <FieldBuilder fields={fields} onChange={setFields} />
        </Box>
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={submitting}
          startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          {submitting ? submittingText : submitText}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

function TemplateRow({
  template,
  isLast,
  onEdit,
  onDuplicate,
  onDeactivate,
}: {
  template: Template
  isLast: boolean
  onEdit: (t: Template) => void
  onDuplicate: (t: Template) => void
  onDeactivate: (id: string) => void
}) {
  return (
    <Box>
      <Box
        sx={{
          p: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 1,
        }}
      >
        <Box flex={1} minWidth={0}>
          <Typography variant="body1" fontWeight={600} noWrap>
            {template.name}
          </Typography>

          <Typography variant="caption" color="text.secondary">
            {template.category}
          </Typography>

          <Box display="flex" gap={0.5} mt={0.75} flexWrap="wrap">
            <Chip
              label={template.is_active ? 'Active' : 'Inactive'}
              size="small"
              color={template.is_active ? 'success' : 'default'}
            />
            <Chip label={template.renderer_type ?? 'simple'} size="small" variant="outlined" />
            <Chip
              label={`${template.fields.length} field${template.fields.length !== 1 ? 's' : ''}`}
              size="small"
              variant="outlined"
            />
          </Box>
        </Box>

        <Box display="flex" gap={0.5}>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => onEdit(template)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Duplicate">
            <IconButton size="small" onClick={() => onDuplicate(template)}>
              <ContentCopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          {template.is_active && (
            <Tooltip title="Deactivate">
              <IconButton size="small" onClick={() => onDeactivate(template.id)}>
                <BlockIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Box>

      {!isLast && <Divider />}
    </Box>
  )
}

let templateCache: Template[] | null = null

export default function TemplateManagerPage() {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))

  const [templates, setTemplates] = useState<Template[]>(templateCache ?? [])
  const [loading, setLoading] = useState(templateCache === null)
  const [error, setError] = useState<string | null>(null)
  const [dialog, setDialog] = useState<{ mode: DialogMode; template?: Template } | null>(null)

  const fetchTemplates = (silent = false) => {
    if (!silent) setLoading(true)
    setError(null)

    apiClient
      .get<Template[]>('/api/templates')
      .then((res) => {
        templateCache = res.data
        setTemplates(res.data)
      })
      .catch(() => setError('Failed to load templates.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchTemplates(templateCache !== null)
  }, [])

  const handleDeactivate = async (id: string) => {
    try {
      await apiClient.delete(`/api/templates/${id}`)
      // Backend list only returns active templates, so refetch to stay in sync.
      fetchTemplates(true)
    } catch {
      setError('Failed to deactivate template.')
    }
  }

  const handleSaved = (t: Template, mode: DialogMode) => {
    if (mode === 'edit') {
      setTemplates((prev) => prev.map((existing) => (existing.id === t.id ? t : existing)))
    } else {
      setTemplates((prev) => [t, ...prev])
    }
  }

  const columns: GridColDef<Template>[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1.2,
      minWidth: 180,
    },
    {
      field: 'category',
      headerName: 'Category',
      flex: 1,
      minWidth: 140,
    },
    {
      field: 'renderer_type',
      headerName: 'Renderer',
      minWidth: 120,
      valueGetter: (_, row) => row.renderer_type ?? 'simple',
      renderCell: (params: GridRenderCellParams<Template>) => (
        <Chip label={String(params.value ?? 'simple')} size="small" variant="outlined" />
      ),
    },
    {
      field: 'field_count',
      headerName: 'Fields',
      minWidth: 100,
      valueGetter: (_, row) => row.fields.length,
    },
    {
      field: 'is_active',
      headerName: 'Status',
      minWidth: 110,
      renderCell: (params: GridRenderCellParams<Template, boolean>) => (
        <Chip
          label={params.value ? 'Active' : 'Inactive'}
          size="small"
          color={params.value ? 'success' : 'default'}
        />
      ),
    },
    {
      field: 'actions',
      headerName: '',
      sortable: false,
      filterable: false,
      width: 150,
      renderCell: (params: GridRenderCellParams<Template>) => (
        <Box>
          <Tooltip title="Edit">
            <IconButton
              size="small"
              onClick={() => setDialog({ mode: 'edit', template: params.row })}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Duplicate">
            <IconButton
              size="small"
              onClick={() => setDialog({ mode: 'duplicate', template: params.row })}
            >
              <ContentCopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          {params.row.is_active && (
            <Tooltip title="Deactivate">
              <IconButton size="small" onClick={() => handleDeactivate(params.row.id)}>
                <BlockIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      ),
    },
  ]

  return (
    <Box>
      <Box
        mb={3}
        display="flex"
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        flexDirection={{ xs: 'column', sm: 'row' }}
        gap={2}
      >
        <Box>
          <Typography variant="h5" fontWeight={700}>
            Template Manager
          </Typography>
          <Typography color="text.secondary">
            Upload, review, and deactivate document templates.
          </Typography>
        </Box>

        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setDialog({ mode: 'create' })}
        >
          Upload template
        </Button>
      </Box>

      {error && (
        <Box mb={2}>
          <ErrorAlert message={error} onClose={() => setError(null)} />
        </Box>
      )}

      {loading ? (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress />
        </Box>
      ) : templates.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Typography color="text.secondary">No templates uploaded yet.</Typography>
        </Paper>
      ) : isMobile ? (
        <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
          {templates.map((template, index) => (
            <TemplateRow
              key={template.id}
              template={template}
              isLast={index === templates.length - 1}
              onEdit={(t) => setDialog({ mode: 'edit', template: t })}
              onDuplicate={(t) => setDialog({ mode: 'duplicate', template: t })}
              onDeactivate={handleDeactivate}
            />
          ))}
        </Paper>
      ) : (
        <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
          <DataGrid
            autoHeight
            rows={templates}
            columns={columns}
            getRowId={(row) => row.id}
            disableRowSelectionOnClick
            hideFooterSelectedRowCount
            pageSizeOptions={[10, 25, 50]}
            initialState={{
              pagination: {
                paginationModel: { pageSize: 10, page: 0 },
              },
            }}
          />
        </Paper>
      )}

      <TemplateDialog
        open={dialog !== null}
        mode={dialog?.mode ?? 'create'}
        template={dialog?.template}
        onClose={() => setDialog(null)}
        onSaved={handleSaved}
      />
    </Box>
  )
}
