/**
 * A little life while a job runs: a pulsing sparkle and a shimmering,
 * rotating status word ("Finagling…", "Footing columns…"). The real progress
 * is shown beside it; this is just to show something is happening.
 */
import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import { keyframes } from '@mui/system'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'

const WORDS = [
  'Thinking',
  'Finagling',
  'Shimmying',
  'Tallying',
  'Footing columns',
  'Cross-footing',
  'Reconciling',
  'Squinting at decimals',
  'Counting pennies',
  'Crunching numbers',
  'Wrangling PDFs',
  'Deciphering scans',
  'Double-checking',
  'Balancing the books',
  'Sleuthing',
  'Noodling',
  'Ledgering',
  'Untangling',
  'Pondering',
  'Accruing',
  'Amortizing',
  'Bean-counting',
  'Puzzling',
  'Calculating',
]

/** How long each word stays, in ms. */
const WORD_MS = 2600

const shimmer = keyframes`
  from { background-position: 150% 0; }
  to { background-position: -50% 0; }
`

const pulse = keyframes`
  0%, 100% { transform: scale(0.85) rotate(0deg); opacity: 0.7; }
  50% { transform: scale(1.1) rotate(20deg); opacity: 1; }
`

const enter = keyframes`
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: none; }
`

function nextWord(current: string): string {
  let w = current
  while (w === current) w = WORDS[Math.floor(Math.random() * WORDS.length)]
  return w
}

export default function WorkingText() {
  const [word, setWord] = useState(() => nextWord(''))

  useEffect(() => {
    const id = window.setInterval(() => setWord(nextWord), WORD_MS)
    return () => window.clearInterval(id)
  }, [])

  return (
    <Box
      component="span"
      role="status"
      aria-live="polite"
      sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75, verticalAlign: 'middle' }}
    >
      <AutoAwesomeIcon
        aria-hidden
        sx={{
          fontSize: 16,
          color: 'secondary.main',
          animation: `${pulse} 1.6s ease-in-out infinite`,
          '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
        }}
      />
      <Box
        key={word}
        component="span"
        sx={(t) => ({
          fontWeight: 600,
          backgroundImage: `linear-gradient(90deg, ${t.palette.text.secondary} 35%, ${t.palette.primary.main} 50%, ${t.palette.text.secondary} 65%)`,
          backgroundSize: '200% 100%',
          backgroundClip: 'text',
          WebkitBackgroundClip: 'text',
          color: 'transparent',
          animation: `${shimmer} 1.8s linear infinite, ${enter} .3s ease-out`,
          '@media (prefers-reduced-motion: reduce)': {
            animation: 'none',
            color: t.palette.text.secondary,
          },
        })}
      >
        {word}…
      </Box>
    </Box>
  )
}
