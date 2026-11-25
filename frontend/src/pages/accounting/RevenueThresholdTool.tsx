import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Paper from '@mui/material/Paper'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import VerifiedIcon from '@mui/icons-material/Verified'
import type { UploadItem } from '../../hooks/createUploadStore'
import type { ReportTier, RevenueBasis, RevenueThresholdReport, SourceFigure } from '../../types'
import { money, useStoreUpload } from './helpers'
import { DropZone, ItemStatus, ToolHeader } from './shared'
import { revenueStore } from './stores'

const TIER: Record<
  ReportTier,
  { label: string; color: 'default' | 'info' | 'warning' | 'primary'; range: string }
> = {
  none: { label: 'No report needed', color: 'default', range: 'Under $150,000' },
  compilation: { label: 'Compilation', color: 'info', range: '$150,000 – $299,999' },
  review: { label: 'Review', color: 'warning', range: '$300,000 – $499,999' },
  audit: { label: 'Audit', color: 'primary', range: '$500,000 and over' },
}

function TierChip({ tier }: { tier: ReportTier | null }) {
  if (!tier) return <Chip size="small" variant="outlined" label="Couldn't read" />
  const t = TIER[tier]
  return <Chip size="small" color={t.color} label={t.label} sx={{ fontWeight: 600 }} />
}

function Figure({ name, fig }: { name: string; fig: SourceFigure | null }) {
  return (
    <Box display="flex" justifyContent="space-between" gap={2}>
      <Typography variant="body2" color="text.secondary">
        {name}
        {fig && ` · page ${fig.page}`}
      </Typography>
      <Box display="flex" alignItems="center" gap={0.5}>
        <Typography
          variant="body2"
          sx={{ fontVariantNumeric: 'tabular-nums', fontStyle: fig?.guessed ? 'italic' : 'normal' }}
        >
          {money(fig?.amount)}
        </Typography>
        {fig?.verified === true && (
          <Tooltip title="Confirmed by the report's actual − budget = variance">
            <VerifiedIcon sx={{ fontSize: 15, color: 'success.main' }} />
          </Tooltip>
        )}
        {fig?.guessed && fig.verified !== true && (
          <Tooltip title="Line didn't read cleanly; picked by column position — confirm it">
            <ErrorOutlineIcon sx={{ fontSize: 15, color: 'warning.main' }} />
          </Tooltip>
        )}
      </Box>
    </Box>
  )
}

function Basis({ title, basis }: { title: string; basis: RevenueBasis }) {
  return (
    <Box flex={1} minWidth={{ xs: '100%', sm: 240 }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={1} gap={1}>
        <Typography variant="overline" color="text.secondary" lineHeight={1.5}>
          {title}
        </Typography>
        <TierChip tier={basis.tier} />
      </Box>
      <Figure name="Operating revenues" fig={basis.operating} />
      <Figure name="Reserve revenues" fig={basis.reserve} />
      <Box
        display="flex"
        justifyContent="space-between"
        mt={0.5}
        pt={0.5}
        sx={{ borderTop: 1, borderColor: 'divider' }}
      >
        <Typography variant="body2" fontWeight={700}>
          Total revenues
        </Typography>
        <Typography variant="body2" fontWeight={700} sx={{ fontVariantNumeric: 'tabular-nums' }}>
          {money(basis.total)}
        </Typography>
      </Box>
      {basis.notes.map((n) => (
        <Typography key={n} variant="caption" color="warning.main" display="block" mt={0.5}>
          {n}
        </Typography>
      ))}
    </Box>
  )
}

function ResultCard({ item }: { item: UploadItem<RevenueThresholdReport> }) {
  const r = item.result
  const differ = r && r.ytd_actual.tier && r.annual.tier && r.ytd_actual.tier !== r.annual.tier
  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, mb: 2, overflow: 'hidden' }}>
      <Box
        display="flex"
        alignItems="center"
        gap={1.5}
        px={2}
        py={1.25}
        bgcolor="action.hover"
        flexWrap="wrap"
      >
        <Typography variant="subtitle2" fontWeight={700} noWrap sx={{ minWidth: 0, flex: 1 }}>
          {item.name}
        </Typography>
        {r && (
          <Box display="flex" alignItems="center" gap={1}>
            <Typography variant="caption" color="text.secondary">
              YTD Actual
            </Typography>
            <TierChip tier={r.ytd_actual.tier} />
          </Box>
        )}
        <ItemStatus item={item} store={revenueStore} />
      </Box>
      {item.status === 'error' && (
        <Typography variant="body2" color="error.main" px={2} py={1.5}>
          {item.error}
        </Typography>
      )}
      {r && (
        <Box px={2} py={1.5}>
          <Box display="flex" gap={4} flexWrap="wrap">
            <Basis title="Year-to-date actual" basis={r.ytd_actual} />
            <Basis title="Annual (budget)" basis={r.annual} />
          </Box>
          {differ && (
            <Alert severity="info" sx={{ mt: 1.5 }}>
              Year-to-date actual and the annual budget point to different reports.
            </Alert>
          )}
          {r.ocr_pages > 0 && (
            <Typography variant="caption" color="text.secondary" display="block" mt={1}>
              {r.ocr_pages} page{r.ocr_pages === 1 ? '' : 's'} had no text layer and were read with
              OCR.
            </Typography>
          )}
        </Box>
      )}
    </Paper>
  )
}

export default function RevenueThresholdTool() {
  const { items, add, errorBanner } = useStoreUpload(revenueStore, 'a PDF')
  return (
    <Box>
      <ToolHeader title="Audit threshold">
        Adds operating and reserve TOTAL REVENUES from the income &amp; expense report and shows
        which year-end report the association needs — by year-to-date actual and by the annual
        budget.
      </ToolHeader>

      <Box display="flex" gap={1} flexWrap="wrap" mb={2}>
        {(Object.keys(TIER) as ReportTier[]).map((t) => (
          <Chip
            key={t}
            size="small"
            variant="outlined"
            color={TIER[t].color}
            label={`${TIER[t].range}: ${TIER[t].label}`}
          />
        ))}
      </Box>

      <DropZone
        accept=".pdf,application/pdf"
        buttonLabel="Choose PDFs"
        hint="Income & expense reports or full financial packets — drop several at once"
        onFiles={add}
        onClear={items.length ? () => revenueStore.clear() : undefined}
      />
      {errorBanner}
      {items.map((item) => (
        <ResultCard key={item.id} item={item} />
      ))}
    </Box>
  )
}
