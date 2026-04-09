import { createTheme } from '@mui/material/styles'

// C&S Community Management Services brand colors
// Primary: navy/royal blue from the C and S logo blocks
// Secondary: medium green from the & logo block and arc

const theme = createTheme({
  palette: {
    primary: {
      main: '#1E3D8F',
      light: '#3358C4',
      dark: '#132770',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#2E9B4E',
      light: '#4CB86A',
      dark: '#1D7834',
      contrastText: '#ffffff',
    },
    background: {
      default: '#F4F6F9',
      paper: '#ffffff',
    },
    text: {
      primary: '#1A2332',
      secondary: '#5A6A7E',
    },
    success: { main: '#2E9B4E' },
    warning: { main: '#E8920A' },
    error: { main: '#C62828' },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica Neue", "Arial", sans-serif',
    h4: { fontWeight: 700, letterSpacing: '-0.5px' },
    h5: { fontWeight: 700, letterSpacing: '-0.5px' },
    h6: { fontWeight: 600 },
    subtitle1: { fontWeight: 500 },
    button: { textTransform: 'none', fontWeight: 500 },
  },
  shape: { borderRadius: 8 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 500 },
        contained: { boxShadow: 'none', '&:hover': { boxShadow: 'none' } },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: { boxShadow: '0 1px 4px rgba(0,0,0,0.18)' },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: { boxShadow: '0 1px 4px rgba(0,0,0,0.08)', border: '1px solid #E8ECF0' },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: { borderRight: '1px solid #E8ECF0' },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: { fontWeight: 600, backgroundColor: '#F4F6F9' },
      },
    },
    MuiStepIcon: {
      styleOverrides: {
        root: {
          '&.Mui-active': { color: '#1E3D8F' },
          '&.Mui-completed': { color: '#2E9B4E' },
        },
      },
    },
  },
})

export default theme
