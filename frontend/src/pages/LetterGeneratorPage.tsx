import { useCallback, useMemo, useState } from 'react'
import Autocomplete from '@mui/material/Autocomplete'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardActionArea from '@mui/material/CardActionArea'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import FormControl from '@mui/material/FormControl'
import InputAdornment from '@mui/material/InputAdornment'
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
import { alpha, useTheme } from '@mui/material/styles'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import SendIcon from '@mui/icons-material/Send'
import SearchIcon from '@mui/icons-material/Search'
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined'
import HowToVoteOutlinedIcon from '@mui/icons-material/HowToVoteOutlined'
import BallotOutlinedIcon from '@mui/icons-material/BallotOutlined'
import CampaignOutlinedIcon from '@mui/icons-material/CampaignOutlined'
import type { SvgIconComponent } from '@mui/icons-material'
import Skeleton from '@mui/material/Skeleton'
import { useQuery } from '@tanstack/react-query'
import SessionJobsPanel from '../components/common/SessionJobsPanel'
import apiClient from '../api/client'
import {
  fetchAssociations,
  fetchManagers,
  fetchTemplates,
  queryKeys,
  type ManagerOption,
} from '../api/queries'
import { useAuth } from '../context/AuthContext'
import ErrorAlert from '../components/layout/ErrorAlert'
import BallotCandidateEditor from '../components/letters/BallotCandidateEditor'
import NoticeCandidacyWarningDialog from '../components/letters/NoticeCandidacyWarningDialog'
import type { Association, Template, ProxyVote, GenerateAccepted } from '../types'
import ProxyVoteEditor from '../components/letters/ProxyVoteEditor'
import { useJobs } from '../context/JobsContext'
const STEPS = ['Select template', 'Fill in fields', 'Generate']

const AUTO_POPULATE_KEYS = new Set(['s0ke'])

type RendererType = 'simple' | 'proxy' | 'ballot' | 'electronic_ballot' | 'notice_candidacy'
type FieldValueMap = Record<string, unknown>

function getRendererType(template: Template | null): RendererType {
  return (template?.renderer_type ?? 'simple') as RendererType
}

function getAssociationFieldKey(template: Template | null): string {
  return template?.fields.find((f) => f.type === 'association')?.key ?? 'association_id'
}

function getManagerFieldKey(template: Template | null): string {
  return template?.fields.find((f) => f.type === 'manager')?.key ?? 'manager_id'
}

type BrandColor = 'primary' | 'secondary' | 'warning'

const RENDERER_META: Record<RendererType, { color: BrandColor; Icon: SvgIconComponent }> = {
  simple: { color: 'primary', Icon: DescriptionOutlinedIcon },
  proxy: { color: 'primary', Icon: HowToVoteOutlinedIcon },
  ballot: { color: 'secondary', Icon: BallotOutlinedIcon },
  electronic_ballot: { color: 'secondary', Icon: BallotOutlinedIcon },
  notice_candidacy: { color: 'warning', Icon: CampaignOutlinedIcon },
}

function getRendererMeta(type?: string) {
  return RENDERER_META[(type ?? 'simple') as RendererType] ?? RENDERER_META.simple
}

function formatRendererType(type?: string): string {
  const value = type ?? 'simple'
  return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
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
  loading,
  selected,
  onSelect,
}: {
  templates: Template[]
  loading: boolean
  selected: Template | null
  onSelect: (t: Template) => void
}) {
  const [search, setSearch] = useState('')

  const byCategory = useMemo(() => {
    const q = search.trim().toLowerCase()
    const filtered = q ? templates.filter((t) => t.name.toLowerCase().includes(q)) : templates

    const map: Record<string, Template[]> = {}
    for (const t of filtered) {
      ;(map[t.category] ??= []).push(t)
    }
    for (const items of Object.values(map)) {
      items.sort((a, b) => a.name.localeCompare(b.name))
    }
    return map
  }, [templates, search])

  const sortedCategories = useMemo(
    () => Object.keys(byCategory).sort((a, b) => a.localeCompare(b)),
    [byCategory],
  )

  if (loading) {
    return (
      <Box display="flex" flexWrap="wrap" gap={2}>
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} variant="rounded" width={256} height={132} sx={{ borderRadius: 2.5 }} />
        ))}
      </Box>
    )
  }

  return (
    <Box>
      {templates.length === 0 && (
        <Typography color="text.secondary">No templates available.</Typography>
      )}

      {templates.length > 0 && (
        <TextField
          placeholder="Search templates…"
          size="small"
          fullWidth
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ mb: 3, maxWidth: 360 }}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            },
          }}
        />
      )}

      {templates.length > 0 && sortedCategories.length === 0 && (
        <Typography color="text.secondary">No templates match your search.</Typography>
      )}

      {sortedCategories.map((cat) => (
        <Box key={cat} mb={3.5}>
          <Typography
            variant="overline"
            color="text.secondary"
            sx={{ fontWeight: 700, letterSpacing: '0.08em', display: 'block', mb: 1.25 }}
          >
            {cat}
          </Typography>

          <Box display="flex" flexWrap="wrap" gap={2}>
            {byCategory[cat].map((t) => {
              const isSelected = selected?.id === t.id
              const meta = getRendererMeta(t.renderer_type)
              const fieldCount = t.fields.filter((f) => !AUTO_POPULATE_KEYS.has(f.key)).length

              return (
                <Card
                  key={t.id}
                  variant="outlined"
                  sx={(theme) => ({
                    position: 'relative',
                    width: { xs: '100%', sm: 256 },
                    height: 132,
                    borderRadius: 2.5,
                    borderColor: isSelected ? `${meta.color}.main` : 'divider',
                    borderWidth: isSelected ? 2 : 1,
                    bgcolor: isSelected
                      ? alpha(theme.palette[meta.color].main, 0.04)
                      : 'background.paper',
                    boxShadow: 'none',
                    transition: theme.transitions.create(
                      ['box-shadow', 'border-color', 'transform'],
                      { duration: theme.transitions.duration.shorter },
                    ),
                    '&:hover': {
                      borderColor: `${meta.color}.main`,
                      boxShadow: `0 6px 16px ${alpha(theme.palette[meta.color].main, 0.16)}`,
                      transform: 'translateY(-2px)',
                    },
                  })}
                >
                  {isSelected && (
                    <CheckCircleIcon
                      sx={{
                        position: 'absolute',
                        top: 10,
                        right: 10,
                        fontSize: 20,
                        color: `${meta.color}.main`,
                        bgcolor: 'background.paper',
                        borderRadius: '50%',
                        pointerEvents: 'none',
                        zIndex: 1,
                      }}
                    />
                  )}
                  <CardActionArea
                    onClick={() => onSelect(t)}
                    sx={{
                      height: '100%',
                      p: 2,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'stretch',
                      justifyContent: 'space-between',
                    }}
                  >
                    <Box display="flex" alignItems="flex-start" gap={1.5}>
                      <Box
                        sx={(theme) => ({
                          width: 40,
                          height: 40,
                          flexShrink: 0,
                          borderRadius: 2,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          bgcolor: alpha(theme.palette[meta.color].main, 0.12),
                          color: `${meta.color}.main`,
                        })}
                      >
                        <meta.Icon fontSize="small" />
                      </Box>

                      <Box minWidth={0} flex={1} pr={isSelected ? 2.5 : 0}>
                        <Typography
                          variant="body2"
                          fontWeight={600}
                          lineHeight={1.3}
                          sx={{
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                          }}
                        >
                          {t.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {fieldCount} field{fieldCount === 1 ? '' : 's'}
                        </Typography>
                      </Box>
                    </Box>

                    <Chip
                      label={formatRendererType(t.renderer_type)}
                      size="small"
                      sx={(theme) => ({
                        alignSelf: 'flex-start',
                        height: 22,
                        fontWeight: 600,
                        fontSize: '0.7rem',
                        border: 'none',
                        color: theme.palette[meta.color].main,
                        bgcolor: alpha(theme.palette[meta.color].main, 0.12),
                      })}
                    />
                  </CardActionArea>
                </Card>
              )
            })}
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
                    renderOption={(props, option) => {
                      const { key, ...optionProps } = props
                      return (
                        <Box
                          component="li"
                          key={key}
                          {...optionProps}
                          sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'flex-start',
                            gap: 0.25,
                          }}
                        >
                          <Typography variant="body2" fontWeight={600}>
                            {option.fname} {option.lname}
                          </Typography>
                          {(option.title || option.email) && (
                            <Typography variant="caption" color="text.secondary">
                              {[option.title, option.email].filter(Boolean).join(' · ')}
                            </Typography>
                          )}
                        </Box>
                      )
                    }}
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
  submitting,
  error,
}: {
  template: Template
  values: FieldValueMap
  associations: Association[]
  managers: ManagerOption[]
  onGenerate: () => void
  submitting: boolean
  error: string | null
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

      {error && (
        <Box mb={2}>
          <ErrorAlert message={error} onClose={() => {}} />
        </Box>
      )}

      <Button
        variant="contained"
        onClick={onGenerate}
        disabled={submitting}
        startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : <SendIcon />}
      >
        {submitting ? 'Submitting…' : 'Generate letter'}
      </Button>
    </Box>
  )
}

function isProxyVoteComplete(vote: ProxyVote): boolean {
  const has = (value?: string) => !!value?.trim()

  switch (vote.type) {
    case 'waive_financial_one_year':
      return has(vote.fiscal_year)

    case 'lower_financial_level':
      return (
        has(vote.from_level) &&
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
  const { trackJob } = useJobs()
  const [activeStep, setActiveStep] = useState(0)
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null)
  const [fieldValues, setFieldValues] = useState<FieldValueMap>({})
  const [submitting, setSubmitting] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)
  const [noticeWarningOpen, setNoticeWarningOpen] = useState(false)

  const templatesQuery = useQuery({ queryKey: queryKeys.templates, queryFn: fetchTemplates })
  const associationsQuery = useQuery({
    queryKey: queryKeys.associations,
    queryFn: fetchAssociations,
    // Only active associations, alphabetized by legal name.
    select: (data) =>
      data.filter((a) => a.is_active).sort((a, b) => a.legal_name.localeCompare(b.legal_name)),
  })
  const managersQuery = useQuery({
    queryKey: queryKeys.managers,
    queryFn: fetchManagers,
    // Only active managers, alphabetized by name.
    select: (data) =>
      data
        .filter((m) => m.is_active !== false)
        .sort((a, b) => `${a.lname} ${a.fname}`.localeCompare(`${b.lname} ${b.fname}`)),
  })

  const templates = templatesQuery.data ?? []
  const associations = associationsQuery.data ?? []
  const managers = managersQuery.data ?? []
  const loadingData =
    templatesQuery.isLoading || associationsQuery.isLoading || managersQuery.isLoading
  const loadError =
    templatesQuery.isError || associationsQuery.isError || managersQuery.isError
      ? 'Failed to load data. Please refresh.'
      : null

  const retryLoad = () => {
    void templatesQuery.refetch()
    void associationsQuery.refetch()
    void managersQuery.refetch()
  }

  const handleTemplateSelect = useCallback((template: Template) => {
    setSelectedTemplate(template)
    setFieldValues({})
    setGenError(null)
    setSubmitting(false)
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

  const handleGenerate = async () => {
    if (!selectedTemplate) return

    const associationId = getAssociationIdFromValues(fieldValues, selectedTemplate)
    if (!associationId) {
      setGenError('Please select an association.')
      return
    }

    setSubmitting(true)
    setGenError(null)

    try {
      const res = await apiClient.post<GenerateAccepted>('/api/letters/generate', {
        template_id: selectedTemplate.id,
        association_id: associationId,
        field_values: fieldValues,
      })
      trackJob(res.data.job_id, 'letter')
      handleReset()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Generation failed.'
      setGenError(msg)
    } finally {
      setSubmitting(false)
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
    setGenError(null)
    setSubmitting(false)
  }

  const userName = user ? `${user.fname} ${user.lname}` : ''

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={3}>
        Letter generator
      </Typography>

      {loadError && (
        <Box mb={2}>
          <ErrorAlert message={loadError} onClose={retryLoad} />
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
            loading={loadingData}
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
            submitting={submitting}
            error={genError}
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
        <Button variant="outlined" onClick={handleBack} disabled={activeStep === 0 || submitting}>
          Back
        </Button>

        {activeStep < STEPS.length - 1 && (
          <Button variant="contained" onClick={handleNext} disabled={!canAdvance}>
            Next
          </Button>
        )}
      </Box>

      <SessionJobsPanel jobType="letter" />
    </Box>
  )
}
