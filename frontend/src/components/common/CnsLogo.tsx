import fullLight from '../../assets/main_logo.png'
import fullBrand from '../../assets/main_logo_dark.png'
import markLight from '../../assets/main_logo_mark.png'
import markBrand from '../../assets/main_logo_mark_dark.png'

interface CnsLogoProps {
  /** Rendered height in px; width follows the artwork's aspect ratio. */
  height?: number
  /**
   * Include the "Community Management Services, Inc. / AAMC" wordmark.
   * Leave it off below ~80px — the wordmark is set small in the lockup and
   * turns to mush at app-bar sizes.
   */
  showText?: boolean
  /**
   * Which colourway. 'brand' is the navy lockup for light surfaces; 'light'
   * is the white lockup for the navy app bar and login header. The gold
   * ampersand is identical in both.
   */
  tone?: 'brand' | 'light'
}

// Intrinsic sizes of the source artwork, used to reserve the right width so
// the layout doesn't shift as the image decodes.
const RATIO = { full: 191 / 125, mark: 143 / 67 }

export default function CnsLogo({ height = 48, showText = false, tone = 'brand' }: CnsLogoProps) {
  const isLight = tone === 'light'
  const src = showText ? (isLight ? fullLight : fullBrand) : isLight ? markLight : markBrand
  const ratio = showText ? RATIO.full : RATIO.mark

  return (
    <img
      src={src}
      alt="C&S Community Management Services, Inc."
      height={height}
      width={Math.round(height * ratio)}
      style={{ height, width: 'auto', display: 'block' }}
    />
  )
}
