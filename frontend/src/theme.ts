import { createTheme, type Theme } from '@mui/material/styles'

/**
 * C&S Community Management Services, Inc. — brand theme.
 *
 * Taken from the logo: deep navy serif letterforms with a gold calligraphic
 * ampersand. The previous green is gone entirely.
 *
 * A note on the gold, because it constrains how it can be used: #C9A227 on
 * white is about 2.4:1, nowhere near the 4.5:1 needed for text. Navy on gold
 * is ~5.7:1 and passes. So gold is an accent — rules, highlights, selected
 * states, the login flourish — and wherever it becomes a surface, the text on
 * it is navy, never white. That is why `secondary.contrastText` is navy.
 */

export const brand = {
  navy: '#13294B',
  navyLight: '#24416E',
  navyDark: '#0B1A33',
  gold: '#C9A227',
  goldLight: '#E0BE5E',
  goldDark: '#9A7B16',
} as const

// Dark mode cannot reuse the brand navy as the primary — #13294B on a dark
// ground is nearly invisible. It becomes the *surface* instead, and a lifted
// tint of it carries the interactive role.
const darkPrimary = '#7FA3D9'

const sans = '"Inter", "Roboto", "Helvetica Neue", "Arial", sans-serif'
// System serif, deliberately not a webfont — it echoes the logo's classical
// letterforms on page titles without a network round-trip or layout shift.
const serif = 'Georgia, "Iowan Old Style", "Times New Roman", serif'

export type ColorMode = 'light' | 'dark'

export function createAppTheme(mode: ColorMode): Theme {
  const isLight = mode === 'light'

  const divider = isLight ? '#E3E7EE' : '#25334A'
  const paper = isLight ? '#FFFFFF' : '#141F33'
  const defaultBg = isLight ? '#F5F7FA' : '#0C1524'
  const subtleFill = isLight ? '#F5F7FA' : '#1B2840'

  return createTheme({
    palette: {
      mode,
      primary: {
        main: isLight ? brand.navy : darkPrimary,
        light: isLight ? brand.navyLight : '#A3BEE8',
        dark: isLight ? brand.navyDark : '#5B82BC',
        contrastText: isLight ? '#FFFFFF' : '#0B1A33',
      },
      secondary: {
        main: isLight ? brand.gold : '#D9B64A',
        light: isLight ? brand.goldLight : '#E8CD7B',
        dark: isLight ? brand.goldDark : '#B8942F',
        // Navy on gold, never white — see the contrast note above.
        contrastText: brand.navyDark,
      },
      background: { default: defaultBg, paper },
      text: {
        primary: isLight ? '#16202E' : '#E6EAF2',
        secondary: isLight ? '#5A6A7E' : '#9BA8BC',
      },
      divider,
      success: { main: isLight ? '#1F7A4C' : '#4FBF86' },
      warning: { main: isLight ? '#B57A0B' : '#E0A93B' },
      error: { main: isLight ? '#B3261E' : '#F0756C' },
      info: { main: isLight ? brand.navyLight : darkPrimary },
    },

    typography: {
      fontFamily: sans,
      // Page titles pick up the logo's serif; everything below stays sans so
      // dense tables and forms keep their legibility.
      h4: { fontFamily: serif, fontWeight: 700, letterSpacing: '-0.3px' },
      h5: { fontFamily: serif, fontWeight: 700, letterSpacing: '-0.2px' },
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
          // Gold outline buttons need the darker gold for a readable label.
          outlinedSecondary: { color: isLight ? brand.goldDark : '#E8CD7B' },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            // Pinned to the brand navy rather than palette.primary, which
            // inverts to a pale blue in dark mode and would wash out the
            // white logo sitting on it.
            backgroundColor: isLight ? brand.navy : '#101A2B',
            color: '#FFFFFF',
            boxShadow: 'none',
            // The gold hairline under the app bar is the logo's AAMC rule.
            borderBottom: `2px solid ${isLight ? brand.gold : '#B8942F'}`,
            backgroundImage: 'none',
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            boxShadow: isLight
              ? '0 1px 3px rgba(19,41,75,0.08), 0 1px 2px rgba(19,41,75,0.04)'
              : '0 1px 3px rgba(0,0,0,0.4)',
            border: `1px solid ${divider}`,
          },
        },
      },
      MuiPaper: {
        styleOverrides: { root: { backgroundImage: 'none' } },
      },
      MuiDrawer: {
        styleOverrides: { paper: { borderRight: `1px solid ${divider}`, backgroundImage: 'none' } },
      },
      MuiTableCell: {
        styleOverrides: {
          head: { fontWeight: 600, backgroundColor: subtleFill },
          root: { borderColor: divider },
        },
      },
      MuiStepIcon: {
        styleOverrides: {
          root: {
            '&.Mui-active': { color: isLight ? brand.navy : darkPrimary },
            // Gold marks completion, taking over the role the green had.
            '&.Mui-completed': { color: isLight ? brand.gold : '#D9B64A' },
          },
        },
      },
      MuiChip: {
        styleOverrides: { root: { fontWeight: 500 } },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: { backgroundColor: isLight ? brand.navy : '#25334A', fontSize: '0.75rem' },
          arrow: { color: isLight ? brand.navy : '#25334A' },
        },
      },
    },
  })
}

export default createAppTheme('light')
