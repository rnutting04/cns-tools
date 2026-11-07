import { QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { queryClient } from './api/queryClient'
import { AuthProvider } from './context/AuthContext'
import { ColorModeProvider, useColorMode } from './context/ColorModeContext'
import AppRouter from './routes/AppRouter'

// Sonner renders outside the MUI tree, so it needs the mode handed to it
// directly or toasts stay light while the rest of the app goes dark.
function ThemedToaster() {
  const { mode } = useColorMode()
  return <Toaster position="bottom-right" richColors duration={8000} theme={mode} />
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* ColorModeProvider owns ThemeProvider + CssBaseline so the theme can
          be rebuilt when the mode changes. */}
      <ColorModeProvider>
        <ThemedToaster />
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </ColorModeProvider>
    </QueryClientProvider>
  )
}
