import { ThemeProvider, CssBaseline } from '@mui/material'
import { Toaster } from 'sonner'
import theme from './theme'
import { AuthProvider } from './context/AuthContext'
import AppRouter from './routes/AppRouter'

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Toaster position="bottom-right" richColors duration={8000} />
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </ThemeProvider>
  )
}
