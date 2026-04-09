interface CnsLogoProps {
  height?: number
  showText?: boolean
}

// Fixed viewBox — SVG scales automatically
const VW = 224
const VH = 130
const BW = 58    // block width
const BH = 96    // block height (tall portrait, like the real logo)
const GAP = 4    // gap between blocks
const RX = 3     // corner radius
const B1X = 20
const B2X = B1X + BW + GAP   // 82
const B3X = B2X + BW + GAP   // 144
const TEXT_Y = 73
const AMP_Y = 71

export default function CnsLogo({ height = 48, showText = false }: CnsLogoProps) {
  const aspect = VW / VH
  const w = height * aspect
  const totalH = showText ? height + 30 : height
  const totalVH = showText ? VH + 30 : VH

  return (
    <svg
      width={w}
      height={totalH}
      viewBox={`0 0 ${VW} ${totalVH}`}
      xmlns="http://www.w3.org/2000/svg"
      aria-label="C&S Community Management Services"
    >
      {/* Blue block C */}
      <rect x={B1X} y={0} width={BW} height={BH} rx={RX} fill="#1E3D8F" />
      <text x={B1X + BW / 2} y={TEXT_Y} textAnchor="middle" fontSize={78} fontWeight="900" fill="white" fontFamily="Arial Black, Arial, sans-serif">C</text>

      {/* Green block & */}
      <rect x={B2X} y={0} width={BW} height={BH} rx={RX} fill="#2E9B4E" />
      <text x={B2X + BW / 2} y={AMP_Y} textAnchor="middle" fontSize={50} fontWeight="900" fill="white" fontFamily="Arial Black, Arial, sans-serif">&amp;</text>

      {/* Blue block S */}
      <rect x={B3X} y={0} width={BW} height={BH} rx={RX} fill="#1E3D8F" />
      <text x={B3X + BW / 2} y={TEXT_Y} textAnchor="middle" fontSize={78} fontWeight="900" fill="white" fontFamily="Arial Black, Arial, sans-serif">S</text>

      {/* Green arch arc — endpoints low, peak high (hill shape) */}
      <path
        d={`M 2 ${VH - 3} Q ${VW / 2} ${BH + 8} ${VW - 2} ${VH - 3}`}
        stroke="#2E9B4E"
        strokeWidth={5}
        fill="none"
        strokeLinecap="round"
      />

      {showText && (
        <>
          <text x={VW / 2} y={VH + 16} textAnchor="middle" fontSize={13} fontWeight="700" fill="#1E3D8F" fontFamily="Arial, sans-serif" letterSpacing="2">COMMUNITY</text>
          <text x={VW / 2} y={VH + 30} textAnchor="middle" fontSize={13} fontWeight="700" fill="#1E3D8F" fontFamily="Arial, sans-serif" letterSpacing="2">MANAGEMENT SERVICES, INC.</text>
        </>
      )}
    </svg>
  )
}
