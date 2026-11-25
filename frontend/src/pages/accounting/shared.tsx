/** Building blocks shared by the Accounting tools. */
import { useRef, useState } from 'react'
import type { DragEvent, ReactNode } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import RestartAltIcon from '@mui/icons-material/RestartAlt'
import UploadFileIcon from '@mui/icons-material/UploadFile'

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
