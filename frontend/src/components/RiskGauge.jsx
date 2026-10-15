import { RISK_COLORS } from '../lib/format'

export default function RiskGauge({ score = 0, level = 'low', size = 180 }) {
  const radius = 70
  const circumference = Math.PI * radius
  const progress = Math.max(0, Math.min(100, score)) / 100
  const color = RISK_COLORS[level] || RISK_COLORS.low
  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.6} viewBox="0 0 180 105" role="img" aria-label={`Risk ${score} of 100`}>
        <path d="M 20 95 A 70 70 0 0 1 160 95" fill="none" style={{ stroke: 'var(--color-ink-800)' }} strokeWidth="12" strokeLinecap="butt" />
        <path
          d="M 20 95 A 70 70 0 0 1 160 95"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="butt"
          strokeDasharray={`${circumference * progress} ${circumference}`}
          style={{ transition: 'stroke-dasharray .6s ease, stroke .6s ease' }}
        />
        <text x="90" y="80" textAnchor="middle" style={{ fill: 'var(--color-stone-50)' }} fontSize="34" fontWeight="600" fontFamily="Fraunces, Georgia, serif">{score}</text>
        <text x="90" y="98" textAnchor="middle" style={{ fill: 'var(--color-stone-500)' }} fontSize="9" fontFamily="IBM Plex Mono, monospace" letterSpacing="1">OUT OF 100</text>
      </svg>
      <span className="mt-1 px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-[.14em]"
            style={{ color, borderTop: `2px solid ${color}` }}>
        {level} risk
      </span>
    </div>
  )
}
