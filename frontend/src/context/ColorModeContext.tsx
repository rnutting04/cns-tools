import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { createAppTheme, type ColorMode } from '../theme'

const STORAGE_KEY = 'cns.colorMode'

interface ColorModeValue {
  mode: ColorMode
  toggle: () => void
  /** True when the mode is following the OS rather than an explicit choice. */
  isSystem: boolean
  /** Drop the saved preference and follow the OS again. */
  useSystem: () => void
}

const ColorModeContext = createContext<ColorModeValue | null>(null)

function systemMode(): ColorMode {
  return typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

function storedMode(): ColorMode | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw === 'light' || raw === 'dark' ? raw : null
  } catch {
    // Private windows and blocked site data make localStorage throw rather
    // than return null, so a failed read must not take the app down with it.
    return null
  }
}

export function ColorModeProvider({ children }: { children: React.ReactNode }) {
  const [explicit, setExplicit] = useState<ColorMode | null>(storedMode)
  const [system, setSystem] = useState<ColorMode>(systemMode)

  // Keep following the OS while no explicit choice has been made, so a user
  // who flips their system theme at dusk sees the app follow along.
  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!mq) return
    const onChange = (e: MediaQueryListEvent) => setSystem(e.matches ? 'dark' : 'light')
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const mode = explicit ?? system

  const toggle = useCallback(() => {
    setExplicit((current) => {
      const next: ColorMode = (current ?? systemMode()) === 'dark' ? 'light' : 'dark'
      try {
        localStorage.setItem(STORAGE_KEY, next)
      } catch {
        // Preference just won't survive a reload; the toggle still works.
      }
      return next
    })
  }, [])

  const useSystemMode = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Nothing to clean up if storage is unavailable.
    }
    setExplicit(null)
  }, [])

  const theme = useMemo(() => createAppTheme(mode), [mode])

  const value = useMemo<ColorModeValue>(
    () => ({ mode, toggle, isSystem: explicit === null, useSystem: useSystemMode }),
    [mode, toggle, explicit, useSystemMode],
  )

  // Tell the browser which scheme is active so form controls, scrollbars and
  // the page behind the app render in the matching theme.
  useEffect(() => {
    document.documentElement.style.colorScheme = mode
  }, [mode])

  return (
    <ColorModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useColorMode(): ColorModeValue {
  const ctx = useContext(ColorModeContext)
  if (!ctx) throw new Error('useColorMode must be used within a ColorModeProvider')
  return ctx
}
