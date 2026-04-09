import { useCallback, useEffect, useMemo, useState } from 'react'
import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardActionArea from '@mui/material/CardActionArea'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import FormControl from '@mui/material/FormControl'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Select from '@mui/material/Select'
import Step from '@mui/material/Step'
import StepLabel from '@mui/material/StepLabel'
import Stepper from '@mui/material/Stepper'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import DownloadIcon from '@mui/icons-material/Download'
import RestartAltIcon from '@mui/icons-material/RestartAlt'
import apiClient from '../api/client'
import { useAuth } from '../hooks/useAuth'
import ErrorAlert from '../components/layout/ErrorAlert'
import BallotCandidateEditor from '../components/letters/BallotCandidateEditor'
import NoticeCandidacyWarningDialog from '../components/letters/NoticeCandidacyWarningDialog'
import type { Association, Template, ProxyVote } from '../types'
import ProxyVoteEditor from '../components/letters/ProxyVoteEditor'
const STEPS = ['Select template', 'Fill in fields', 'Generate']

const AUTO_POPULATE_KEYS = new Set([
  's0ke'
])

type RendererType = 'simple' | 'proxy' | 'ballot' | 'electronic_ballot' | 'notice_candidacy'
type FieldValueMap = Record<string, unknown>

type ManagerOption = {
  id: string
  fname: string
  lname: string
  email?: string
  title?: string
  is_active?: boolean
}

function getRendererType(template: Template | null): RendererType {
  return (template?.renderer_type ?? 'simple') as RendererType
}

function getAssociationFieldKey(template: Template | null): string {
  return template?.fields.find((f) => f.type === 'association')?.key ?? 'association_id'
}

function getManagerFieldKey(template: Template | null): string {
  return template?.fields.find((f) => f.type === 'manager')?.key ?? 'manager_id'
}

function getAssociationIdFromValues(values: FieldValueMap, template: Template | null): string {
  const key = getAssociationFieldKey(template)
  return typeof values[key] === 'string' ? (values[key] as string) : ''
}

function getManagerIdFromValues(values: FieldValueMap, template: Template | null): string {
  const key = getManagerFieldKey(template)
  return typeof values[key] === 'string' ? (values[key] as string) : ''
}

function getSelectedAssociation(
  values: FieldValueMap,
  associations: Association[],
  template: Template | null,
): Association | null {
  const associationId = getAssociationIdFromValues(values, template)
  return associations.find((a) => a.id === associationId) ?? null
}

function getSelectedManager(
  values: FieldValueMap,
  managers: ManagerOption[],
  template: Template | null,
): ManagerOption | null {
  const managerId = getManagerIdFromValues(values, template)
  return managers.find((m) => m.id === managerId) ?? null
}

function TemplateStep({
  templates,
  selected,
  onSelect,
}: {
  templates: Template[]
  selected: Template | null
  onSelect: (t: Template) => void
}) {
  const byCategory = useMemo(() => {
    const map: Record<string, Template[]> = {}
    for (const t of templates) {
      ;(map[t.category] ??= []).push(t)
    }
    return map
  }, [templates])

  return (
    <Box>
      {templates.length === 0 && (
        <Typography color="text.secondary">No templates available.</Typography>
      )}

      {Object.entries(byCategory).map(([cat, items]) => (
        <Box key={cat} mb={3}>
          <Typography variant="subtitle2" color="text.secondary" mb={1}>
            {cat}
          </Typography>

          <Box display="flex" flexWrap="wrap" gap={2}>
            {items.map((t) => (
              <Card
                key={t.id}
                variant="outlined"
                sx={{
                  width: { xs: '100%', sm: 250 },
                  borderColor: selected?.id === t.id ? 'primary.main' : undefined,
                  borderWidth: selected?.id === t.id ? 2 : 1,
                }}
              >
                <CardActionArea onClick={() => onSelect(t)} sx={{ p: 0.5 }}>
                  <CardContent>
                    <Typography variant="body1" fontWeight={600}>
                      {t.name}
                    </Typography>

                    <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                      {t.fields.filter((f) => !AUTO_POPULATE_KEYS.has(f.key)).length} field(s)
                    </Typography>

                    <Box display="flex" gap={0.75} flexWrap="wrap">
                      <Chip label={t.category} size="small" variant="outlined" />
                      <Chip label={t.renderer_type ?? 'simple'} size="small" variant="outlined" />
                      {selected?.id === t.id && (
                        <Chip
                          label="Selected"
                          color="primary"
                          size="small"
                          icon={<CheckCircleIcon />}
                        />
                      )}
                    </Box>
                  </CardContent>
                </CardActionArea>
              </Card>
            ))}
          </Box>
        </Box>
      ))}
    </Box>
  )
}

function AutoFieldsPreview({
  template,
  selectedAssociation,
  selectedManager,
  userName,
}: {
  template: Template
  selectedAssociation: Association | null
  selectedManager: ManagerOption | null
  userName: string
}) {
  const autoFields = template.fields.filter((f) => AUTO_POPULATE_KEYS.has(f.key))

  const autoValues: Record<string, string> = {
    legal_association_name: selectedAssociation?.legal_name ?? '',
    filtered_association_name: selectedAssociation?.filter_name ?? '',
    assn_city: selectedAssociation?.location_name ?? '',
    association_location_name: selectedAssociation?.location_name ?? '',
    manager_full_name: selectedManager
      ? `${selectedManager.fname} ${selectedManager.lname}`
      : userName,
    manager_titles: selectedManager?.title ?? '',
    manager_email: selectedManager?.email ?? '',
    today_date: '(generated automatically)',
    office_street: '(from office location)',
    office_city_state_zip: '(from office location)',
    office_phone: '(from office location)',
  }

  if (autoFields.length === 0) return null

  return (
    <Box>
      <Typography variant="subtitle2" color="text.secondary" mb={1}>
        Auto-populated fields
      </Typography>

      <Box display="flex" flexDirection="column" gap={1.5}>
        {autoFields.map((f) => (
          <TextField
            key={f.key}
            label={f.label}
            value={autoValues[f.key] ?? ''}
            disabled
            size="small"
            fullWidth
            helperText="Filled automatically"
          />
        ))}
      </Box>
    </Box>
  )
}

function FieldsStep({
  template,
  values,
  onChange,
  associations,
  managers,
  userName,
}: {
  template: Template
  values: FieldValueMap
  onChange: (key: string, val: unknown) => void
  associations: Association[]
  managers: ManagerOption[]
  userName: string
}) {
  const rendererType = getRendererType(template)
  const selectedAssociation = getSelectedAssociation(values, associations, template)
  const selectedManager = getSelectedManager(values, managers, template)

  const manualFields = template.fields.filter((f) => !AUTO_POPULATE_KEYS.has(f.key))

  return (
    <Box display="flex" flexDirection="column" gap={3} maxWidth={640}>
      <AutoFieldsPreview
        template={template}
        selectedAssociation={selectedAssociation}
        selectedManager={selectedManager}
        userName={userName}
      />

      {manualFields.length > 0 && (
        <Box>
          <Typography variant="subtitle2" color="text.secondary" mb={1}>
            Required fields
          </Typography>

          <Box display="flex" flexDirection="column" gap={2}>
            {manualFields.map((f) => {
              if (f.type === 'association') {
                return (
                  <Autocomplete
                    key={f.key}
                    options={associations}
                    value={selectedAssociation}
                    onChange={(_, value) => onChange(f.key, value?.id ?? '')}
                    getOptionLabel={(option) =>
                      `${option.legal_name} (${option.filter_name} · ${option.location_name})`
                    }
                    isOptionEqualToValue={(option, value) => option.id === value.id}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label={f.label}
                        size="small"
                        fullWidth
                        helperText="Search and select an association"
                      />
                    )}
                  />
                )
              }

              if (f.type === 'manager') {
                return (
                  <Autocomplete
                    key={f.key}
                    options={managers}
                    value={selectedManager}
                    onChange={(_, value) => onChange(f.key, value?.id ?? '')}
                    getOptionLabel={(option) =>
                      `${option.fname} ${option.lname}${option.title ? ` (${option.title})` : ''}`
                    }
                    isOptionEqualToValue={(option, value) => option.id === value.id}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label={f.label}
                        size="small"
                        fullWidth
                        helperText="Search and select a manager"
                      />
                    )}
                  />
                )
              }

              if (f.type === 'dropdown') {
                return (
                  <FormControl key={f.key} size="small" fullWidth>
                    <InputLabel>{f.label}</InputLabel>
                    <Select
                      value={String(values[f.key] ?? '')}
                      label={f.label}
                      onChange={(e) => onChange(f.key, e.target.value)}
                    >
                      {f.options.map((opt) => (
                        <MenuItem key={opt} value={opt}>
                          {opt}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                )
              }

              if (f.type === 'date') {
                return (
                  <TextField
                    key={f.key}
                    label={f.label}
                    type="date"
                    size="small"
                    fullWidth
                    value={String(values[f.key] ?? '')}
                    onChange={(e) => onChange(f.key, e.target.value)}
                    slotProps={{ inputLabel: { shrink: true } }}
                  />
                )
              }

              if (f.type === 'time') {
                return (
                  <TextField
                    key={f.key}
                    label={f.label}
                    type="time"
                    size="small"
                    fullWidth
                    value={String(values[f.key] ?? '')}
                    onChange={(e) => onChange(f.key, e.target.value)}
                    slotProps={{ inputLabel: { shrink: true } }}
                  />
                )
              }

              return (
                <TextField
                  key={f.key}
                  label={f.label}
                  size="small"
                  fullWidth
                  value={String(values[f.key] ?? '')}
                  onChange={(e) => onChange(f.key, e.target.value)}
                />
              )
            })}
          </Box>
        </Box>
      )}

      {rendererType === 'proxy' && (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <ProxyVoteEditor
            votes={Array.isArray(values.votes) ? (values.votes as ProxyVote[]) : []}
            onChange={(votes) => onChange('votes', votes)}
          />
        </Paper>
      )}
      {(rendererType === 'ballot' || rendererType === 'electronic_ballot') && (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          {(() => {
            const thisYear = new Date().getFullYear()
            const candidates = Array.isArray(values.candidates)
              ? (values.candidates as string[])
              : []

            return (
              <Box display="flex" flexDirection="column" gap={2}>
                {rendererType === 'ballot' && (
                  <FormControl size="small" fullWidth>
                    <InputLabel>Ballot year</InputLabel>
                    <Select
                      value={String(values.ballot_year ?? '')}
                      label="Ballot year"
                      onChange={(e) => onChange('ballot_year', e.target.value)}
                    >
                      <MenuItem value={String(thisYear)}>{thisYear}</MenuItem>
                      <MenuItem value={String(thisYear + 1)}>{thisYear + 1}</MenuItem>
                    </Select>
                  </FormControl>
                )}

                <BallotCandidateEditor
                  candidates={candidates}
                  onChange={(c) => onChange('candidates', c)}
                />
              </Box>
            )
          })()}
        </Paper>
      )}
    </Box>
  )
}

function GenerateStep({
  template,
  values,
  associations,
  managers,
  onGenerate,
  onDownload,
  generating,
  downloading,
  downloadUrl,
  error,
  onReset,
}: {
  template: Template
  values: FieldValueMap
  associations: Association[]
  managers: ManagerOption[]
  onGenerate: () => void
  onDownload: () => void
  generating: boolean
  downloading: boolean
  downloadUrl: string | null
  error: string | null
  onReset: () => void
}) {
  const rendererType = getRendererType(template)
  const selectedAssociation = getSelectedAssociation(values, associations, template)
  const selectedManager = getSelectedManager(values, managers, template)
  const votes = Array.isArray(values.votes) ? (values.votes as string[]) : []

  return (
    <Box maxWidth={560}>
      <Typography variant="subtitle2" color="text.secondary" gutterBottom>
        Review
      </Typography>

      <Paper variant="outlined" sx={{ p: 2, mb: 3, borderRadius: 2 }}>
        <Box display="flex" justifyContent="space-between" mb={1}>
          <Typography variant="body2" color="text.secondary">
            Template
          </Typography>
          <Typography variant="body2" fontWeight={600}>
            {template.name}
          </Typography>
        </Box>

        <Divider />

        <Box display="flex" justifyContent="space-between" mt={1} mb={1}>
          <Typography variant="body2" color="text.secondary">
            Association
          </Typography>
          <Typography variant="body2" fontWeight={600}>
            {selectedAssociation?.legal_name ?? '—'}
          </Typography>
        </Box>

        <Divider />

        <Box display="flex" justifyContent="space-between" mt={1} mb={1}>
          <Typography variant="body2" color="text.secondary">
            Manager
          </Typography>
          <Typography variant="body2" fontWeight={600}>
            {selectedManager ? `${selectedManager.fname} ${selectedManager.lname}` : '—'}
          </Typography>
        </Box>

        <Divider />

        <Box display="flex" justifyContent="space-between" mt={1}>
          <Typography variant="body2" color="text.secondary">
            Renderer
          </Typography>
          <Typography variant="body2" fontWeight={600}>
            {rendererType}
          </Typography>
        </Box>

        {rendererType === 'proxy' && (
          <>
            <Divider />
            <Box display="flex" justifyContent="space-between" mt={1}>
              <Typography variant="body2" color="text.secondary">
                Vote items
              </Typography>
              <Typography variant="body2" fontWeight={600}>
                {votes.length}
              </Typography>
            </Box>
          </>
        )}

        {(rendererType === 'ballot' || rendererType === 'electronic_ballot') && (
          <>
            <Divider />
            <Box display="flex" justifyContent="space-between" mt={1}>
              <Typography variant="body2" color="text.secondary">
                Candidates
              </Typography>
              <Typography variant="body2" fontWeight={600}>
                {(Array.isArray(values.candidates) ? (values.candidates as string[]) : []).length}
              </Typography>
            </Box>
          </>
        )}
      </Paper>

      {downloadUrl ? (
        <Box>
          <Box display="flex" alignItems="center" gap={1} mb={2}>
            <CheckCircleIcon color="success" />
            <Typography color="success.main" fontWeight={600}>
              Letter generated successfully
            </Typography>
          </Box>

          <Box display="flex" gap={2} flexWrap="wrap">
          <Button
            variant="contained"
            startIcon={downloading ? <CircularProgress size={16} color="inherit" /> : <DownloadIcon />}
            onClick={onDownload}
            disabled={downloading}
          >
            {downloading ? 'Downloading…' : 'Download letter'}
          </Button>

            <Button variant="outlined" startIcon={<RestartAltIcon />} onClick={onReset}>
              Generate another
            </Button>
          </Box>
        </Box>
      ) : (
        <Box>
          {error && (
            <Typography color="error" variant="body2" mb={2}>
              {error}
            </Typography>
          )}

        <Button
          variant="contained"
          onClick={onGenerate}
          disabled={generating}
          startIcon={generating ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          {generating ? 'Generating…' : 'Generate letter'}
        </Button>
        </Box>
      )}
    </Box>
  )
}

function isProxyVoteComplete(vote: ProxyVote): boolean {
  const has = (value?: string) => !!value?.trim()

  switch (vote.type) {
    case 'waive_financial_one_year':
      return has(vote.fiscal_year)

    case 'lower_financial_level':
      return ( has(vote.from_level) &&
        has(vote.to_level) &&
        has(vote.fiscal_year) &&
        vote.from_level !== vote.to_level
      )

    case 'cross_utilization_reserves':
      return has(vote.fiscal_year)

    case 'straight_line_to_pooled':
      return true

    case 'partial_reserve_funding':
      return has(vote.percentage) && has(vote.fiscal_year)

    case 'waive_reserves':
      return has(vote.fiscal_year)

    case 'use_reserves_other_purpose':
      return has(vote.amount) && has(vote.reserve_from) && has(vote.purpose)

    case 'move_reserve_line_items':
      return has(vote.amount) && has(vote.reserve_from) && has(vote.reserve_to)

    case 'irs_rollover':
      return has(vote.tax_year)

    default:
      return false
  }
}

export default function LetterGeneratorPage() {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'))
  const { user } = useAuth()
  const [activeStep, setActiveStep] = useState(0)
  const [templates, setTemplates] = useState<Template[]>([])
  const [associations, setAssociations] = useState<Association[]>([])
  const [managers, setManagers] = useState<ManagerOption[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null)
  const [fieldValues, setFieldValues] = useState<FieldValueMap>({})

  const [generating, setGenerating] = useState(false)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [genError, setGenError] = useState<string | null>(null)
  const [noticeWarningOpen, setNoticeWarningOpen] = useState(false)

  useEffect(() => {
    Promise.all([
      apiClient.get<Template[]>('/api/templates'),
      apiClient.get<Association[]>('/api/associations'),
      apiClient.get<ManagerOption[]>('/api/managers'),
    ])
      .then(([tmplRes, assocRes, managerRes]) => {
        setTemplates(tmplRes.data)
        setAssociations(assocRes.data.filter((a) => a.is_active))
        setManagers(managerRes.data.filter((m) => m.is_active !== false))
      })
      .catch(() => setLoadError('Failed to load data. Please refresh.'))
  }, [])

  const handleTemplateSelect = useCallback((template: Template) => {
    setSelectedTemplate(template)
    setFieldValues({})
    setDownloadUrl(null)
    setGenError(null)
  }, [])

  const handleFieldChange = useCallback((key: string, val: unknown) => {
    setFieldValues((prev) => ({
      ...prev,
      [key]: val,
    }))
  }, [])

  const canAdvance = useMemo(() => {
    if (activeStep === 0) return selectedTemplate !== null

    if (activeStep === 1) {
      if (!selectedTemplate) return false

      const rendererType = getRendererType(selectedTemplate)

      // Ballot renderers require a year selection and at least one non-empty candidate
      if (rendererType === 'ballot' || rendererType === 'electronic_ballot') {
        if (rendererType === 'ballot' && !fieldValues.ballot_year) return false
      
        const candidates = Array.isArray(fieldValues.candidates)
          ? (fieldValues.candidates as string[])
          : []
      
        if (candidates.length === 0 || candidates.some((c) => !c.trim())) return false
      }

      if (rendererType === 'proxy') {
        const votes = Array.isArray(fieldValues.votes) ? (fieldValues.votes as ProxyVote[]) : []
      
        if (votes.length === 0) return false
        if (votes.some((vote) => !isProxyVoteComplete(vote))) return false
      }

      const manualFields = selectedTemplate.fields.filter((f) => !AUTO_POPULATE_KEYS.has(f.key))

      return manualFields.every((f) => {
        const value = fieldValues[f.key]

        if (typeof value === 'string') {
          return value.trim() !== ''
        }

        return value !== null && value !== undefined
      })
    }

    return true
  }, [activeStep, selectedTemplate, fieldValues])

  const handleNext = () => {
    if (!canAdvance) return
    setActiveStep((s) => Math.min(s + 1, STEPS.length - 1))
  }

  const handleBack = () => {
    setActiveStep((s) => Math.max(s - 1, 0))
  }

  const handleDownload = async () => {
    if (!downloadUrl) return
  
    try {
      setDownloading(true)
  
      const response = await fetch(downloadUrl)
      if (!response.ok) {
        throw new Error('Failed to download file.')
      }
  
      const blob = await response.blob()
      const blobUrl = window.URL.createObjectURL(blob)
  
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = `${selectedTemplate?.name ?? 'letter'}.docx`
      document.body.appendChild(a)
      a.click()
      a.remove()
  
      window.URL.revokeObjectURL(blobUrl)
    } catch {
      setGenError('Failed to download file.')
    } finally {
      setDownloading(false)
    }
  }

  const handleGenerate = async () => {
    if (!selectedTemplate) return

    const associationId = getAssociationIdFromValues(fieldValues, selectedTemplate)
    if (!associationId) {
      setGenError('Please select an association.')
      return
    }

    setGenerating(true)
    setGenError(null)

    try {
      const res = await apiClient.post<{ job_id: string; download_url: string; status: string }>(
        '/api/letters/generate',
        {
          template_id: selectedTemplate.id,
          association_id: associationId,
          field_values: fieldValues,
        },
      )

      setDownloadUrl(res.data.download_url)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Generation failed.'
      setGenError(msg)
    } finally {
      setGenerating(false)
    }
  }

  // 60-day notice check for notice_candidacy renderer.
  // Finds the first date-type field value and checks if it's < 60 days from today.
  const isMeetingDateInNoticePeriod = useCallback((): boolean => {
    if (!selectedTemplate) return false
    const dateField = selectedTemplate.fields.find((f) => f.type === 'date')
    if (!dateField) return false
    const raw = fieldValues[dateField.key]
    if (typeof raw !== 'string' || !raw) return false
    const meetingDate = new Date(raw)
    const diffDays = (meetingDate.getTime() - Date.now()) / 86_400_000
    return diffDays < 60
  }, [selectedTemplate, fieldValues])

  // Intercept generate for notice_candidacy — show warning if inside 60-day window
  const handleGenerateClick = useCallback(() => {
    if (
      selectedTemplate &&
      getRendererType(selectedTemplate) === 'notice_candidacy' &&
      isMeetingDateInNoticePeriod()
    ) {
      setNoticeWarningOpen(true)
      return
    }
    handleGenerate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTemplate, isMeetingDateInNoticePeriod])

  const handleReset = () => {
    setActiveStep(0)
    setSelectedTemplate(null)
    setFieldValues({})
    setDownloadUrl(null)
    setGenError(null)
  }

  const userName = user ? `${user.fname} ${user.lname}` : ''

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={3}>
        Letter generator
      </Typography>

      {loadError && (
        <Box mb={2}>
          <ErrorAlert message={loadError} onClose={() => setLoadError(null)} />
        </Box>
      )}

      <Stepper
        activeStep={activeStep}
        orientation={isMobile ? 'vertical' : 'horizontal'}
        sx={{ mb: 4 }}
      >
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <Box mb={4}>
        {activeStep === 0 && (
          <TemplateStep
            templates={templates}
            selected={selectedTemplate}
            onSelect={handleTemplateSelect}
          />
        )}

        {activeStep === 1 && selectedTemplate && (
          <FieldsStep
            template={selectedTemplate}
            values={fieldValues}
            onChange={handleFieldChange}
            associations={associations}
            managers={managers}
            userName={userName}
          />
        )}

        {activeStep === 2 && selectedTemplate && (
          <GenerateStep
            template={selectedTemplate}
            values={fieldValues}
            associations={associations}
            managers={managers}
            onGenerate={handleGenerateClick}
            onDownload={handleDownload}
            generating={generating}
            downloading={downloading}
            downloadUrl={downloadUrl}
            error={genError}
            onReset={handleReset}
          />
        )}
      </Box>

      <NoticeCandidacyWarningDialog
        open={noticeWarningOpen}
        onConfirm={() => {
          setNoticeWarningOpen(false)
          handleGenerate()
        }}
        onCancel={() => setNoticeWarningOpen(false)}
      />

      <Box display="flex" gap={2} flexWrap="wrap">
        <Button variant="outlined" onClick={handleBack} disabled={activeStep === 0 || generating}>
          Back
        </Button>

        {activeStep < STEPS.length - 1 && (
          <Button variant="contained" onClick={handleNext} disabled={!canAdvance}>
            Next
          </Button>
        )}
      </Box>
    </Box>
  )
}