interface Props {
  confidence: number  // 0.0 – 1.0
}

export function ConfidenceGauge({ confidence }: Props) {
  if (!confidence || confidence <= 0) return null

  const pct = Math.round(confidence * 100)

  // SVG arc parameters
  const size = 80
  const cx = size / 2
  const cy = size / 2
  const r = 30
  const strokeWidth = 7
  const circumference = Math.PI * r  // half-circle arc length

  // Fill based on pct (clockwise from left to right along top half)
  const filled = (pct / 100) * circumference

  // Arc color
  const arcColor =
    pct >= 75 ? '#15803d' : pct >= 50 ? '#d97706' : '#b91c1c'

  return (
    <div
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '2px',
      }}
    >
      <svg
        width={size}
        height={size / 2 + strokeWidth}
        viewBox={`0 0 ${size} ${size / 2 + strokeWidth}`}
        aria-label={`Confidence ${pct}%`}
      >
        {/* background arc */}
        <path
          d={`M ${strokeWidth / 2} ${cy} A ${r} ${r} 0 0 1 ${size - strokeWidth / 2} ${cy}`}
          fill="none"
          stroke="#334155"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* filled arc */}
        <path
          d={`M ${strokeWidth / 2} ${cy} A ${r} ${r} 0 0 1 ${size - strokeWidth / 2} ${cy}`}
          fill="none"
          stroke={arcColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
        />
        <text
          x={cx}
          y={cy - 2}
          textAnchor="middle"
          fill="#e2e8f0"
          fontSize="14"
          fontWeight="700"
        >
          {pct}%
        </text>
      </svg>
      <span style={{ fontSize: '10px', color: '#94a3b8' }}>Confidence</span>
    </div>
  )
}
