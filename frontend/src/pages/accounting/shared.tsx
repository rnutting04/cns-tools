/** Building blocks shared by the Accounting tools. */
import { useRef, useState } from 'react'
import type { DragEvent, ReactNode } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import CloseIcon from '@mui/icons-material/Close'
import ReplayIcon from '@mui/icons-material/Replay'
import RestartAltIcon from '@mui/icons-material/RestartAlt'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import type { UploadItem, UploadStore } from '../../hooks/createUploadStore'

/** A tool's title and one-line description. */
export function ToolHeader({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box mb={2.5}>
      <Typography variant="h6" fontWeight={700}>
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {children}
      </Typography>
    </Box>
  )
}

/** Choose-or-drop area accepting several files. */
export function DropZone({
  accept,
  hint,
  buttonLabel,
  onFiles,
  onClear,
}: {
  accept: string
  hint: string
  buttonLabel: string
  onFiles: (files: File[]) => void
  onClear?: () => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    onFiles(Array.from(e.dataTransfer.files ?? []))
  }
  return (
    <Paper
      variant="outlined"
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      sx={{
        p: { xs: 2, md: 3 },
        mb: 3,
        borderRadius: 2,
        borderStyle: 'dashed',
        borderColor: dragging ? 'primary.main' : 'divider',
        bgcolor: dragging ? 'action.hover' : 'background.paper',
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        flexWrap: 'wrap',
      }}
    >
      <Button
        variant="contained"
        startIcon={<UploadFileIcon />}
        onClick={() => inputRef.current?.click()}
      >
        {buttonLabel}
      </Button>
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 0 }}>
        {hint}
      </Typography>
      {onClear && (
        <Button
          color="inherit"
          startIcon={<RestartAltIcon />}
          onClick={onClear}
          sx={{ ml: 'auto' }}
        >
          Clear
        </Button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple
        hidden
        onChange={(e) => {
          onFiles(Array.from(e.target.files ?? []))
          e.target.value = ''
        }}
      />
    </Paper>
  )
}

/** Status / retry / remove controls for one uploaded file. */
export function ItemStatus<T>({ item, store }: { item: UploadItem<T>; store: UploadStore<T> }) {
  return (
    <Box display="flex" alignItems="center" gap={1} flexShrink={0}>
      {item.status === 'queued' && (
        <Typography variant="caption" color="text.secondary">
          Waiting…
        </Typography>
      )}
      {item.status === 'running' && (
        <>
          <CircularProgress size={14} />
          <Typography variant="caption" color="text.secondary">
            Reading…
          </Typography>
        </>
      )}
      {item.status === 'error' && (
        <Button
          size="small"
          startIcon={<ReplayIcon fontSize="small" />}
          onClick={() => store.retry(item.id)}
        >
          Retry
        </Button>
      )}
      {item.status !== 'running' && (
        <Tooltip title="Remove">
          <IconButton
            size="small"
            aria-label={`Remove ${item.name}`}
            onClick={() => store.remove(item.id)}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
    </Box>
  )
}
