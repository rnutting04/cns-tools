import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Paper from '@mui/material/Paper'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Typography from '@mui/material/Typography'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import type { UploadItem } from '../../hooks/createUploadStore'
import type { FdicReport } from '../../types'
import { money, useStoreUpload } from './helpers'
import { DropZone, ItemStatus, ToolHeader } from './shared'
import { fdicStore } from './stores'

function ResultCard({ item }: { item: UploadItem<FdicReport> }) {
  const r = item.result
  const over = r?.institutions.filter((i) => i.over_limit) ?? []
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
        {r?.balance_sheet_found &&
          (over.length ? (
            <Chip
              size="small"
              color="warning"
              icon={<WarningAmberIcon />}
              label={`${over.length} bank${over.length === 1 ? '' : 's'} at or over ${money(r.limit).replace('.00', '')}`}
            />
          ) : (
            <Chip
              size="small"
              color="success"
              variant="outlined"
              icon={<CheckCircleIcon />}
              label="All banks under the limit"
            />
          ))}
        <ItemStatus item={item} store={fdicStore} />
      </Box>

      {item.status === 'error' && (
        <Typography variant="body2" color="error.main" px={2} py={1.5}>
          {item.error}
        </Typography>
      )}
      {r && !r.balance_sheet_found && (
        <Alert severity="warning" sx={{ m: 2 }}>
          No balance sheet found in this PDF.
        </Alert>
      )}

      {r?.balance_sheet_found && (
        <Box sx={{ overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Bank</TableCell>
                <TableCell>Accounts</TableCell>
                <TableCell align="right">Total</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {r.institutions.map((inst) => (
                <TableRow
                  key={inst.name}
                  sx={{ bgcolor: inst.over_limit ? 'rgba(237, 108, 2, 0.08)' : undefined }}
                >
                  <TableCell sx={{ verticalAlign: 'top', whiteSpace: 'nowrap' }}>
                    <Typography variant="body2" fontWeight={700}>
                      {inst.name}
                    </Typography>
                    {inst.over_limit && (
                      <Chip size="small" color="warning" label="Over FDIC limit" sx={{ mt: 0.5 }} />
                    )}
                  </TableCell>
                  <TableCell sx={{ verticalAlign: 'top' }}>
                    {inst.accounts.map((a) => (
                      <Box key={a.label} display="flex" justifyContent="space-between" gap={2}>
                        <Typography variant="body2" color="text.secondary">
                          {a.label}
                          {a.network && (
                            <Chip
                              size="small"
                              variant="outlined"
                              label="ICS/CDARS"
                              sx={{ ml: 1, height: 18, fontSize: 11 }}
                            />
                          )}
                        </Typography>
                        <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                          {money(a.amount)}
                        </Typography>
                      </Box>
                    ))}
                    {inst.notes.map((n) => (
                      <Typography
                        key={n}
                        variant="caption"
                        color="text.secondary"
                        display="block"
                        mt={0.5}
                      >
                        {n}
                      </Typography>
                    ))}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      verticalAlign: 'top',
                      fontWeight: 700,
                      fontVariantNumeric: 'tabular-nums',
                      color: inst.over_limit ? 'warning.main' : undefined,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {money(inst.total)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}

      {r && r.unrecognized.length > 0 && (
        <Alert severity="warning" sx={{ m: 2 }}>
          Couldn&apos;t tell which bank these deposit accounts are at, so they aren&apos;t in the
          totals above:
          {r.unrecognized.map((a) => (
            <Box key={a.label} display="flex" justifyContent="space-between" gap={2} mt={0.5}>
              <span>{a.label}</span>
              <span>{money(a.amount)}</span>
            </Box>
          ))}
        </Alert>
      )}
    </Paper>
  )
}

export default function FdicTool() {
  const { items, add, errorBanner } = useStoreUpload(fdicStore, 'a PDF')
  return (
    <Box>
      <ToolHeader title="FDIC exposure">
        Adds up the association&apos;s bank and CD balances at each bank from the balance sheet and
        flags any bank holding $250,000 or more.
      </ToolHeader>
      <DropZone
        accept=".pdf,application/pdf"
        buttonLabel="Choose PDFs"
        hint="Balance sheets or full financial packets — drop several at once"
        onFiles={add}
        onClear={items.length ? () => fdicStore.clear() : undefined}
      />
      {errorBanner}
      {items.map((item) => (
        <ResultCard key={item.id} item={item} />
      ))}
    </Box>
  )
}
