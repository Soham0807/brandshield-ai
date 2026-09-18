import { RISK_COLORS } from '../lib/format'

export default function RiskGauge({ score = 0, level = 'low', size = 180 }) {
  const radius = 70
  const circumference = Math.PI * radius
  const progress = Math.max(0, Math.min(100, score)) / 100
  const color = RISK_COLORS[level] || RISK_COLORS.low
  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.6} viewBox="0 0 180 105" role="img" aria-label={`Risk ${score} of 100`}>
        <path d="M 20 95 A 70 70 0 0 1 160 95" fill="none" stroke="#2c2521" strokeWidth="14" strokeLinecap="round" />
        <path
          d="M 20 95 A 70 70 0 0 1 160 95"
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={`${circumference * progress} ${circumference}`}
          style={{ transition: 'stroke-dasharray .6s ease, stroke .6s ease' }}
        />
        <text x="90" y="80" textAnchor="middle" fill="#fafaf9" fontSize="30" fontWeight="600">{score}</text>
        <text x="90" y="98" textAnchor="middle" fill="#78716c" fontSize="10">out of 100</text>
      </svg>
      <span className="mt-1 rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide"
            style={{ color, background: `${color}22` }}>
        {level} risk
      </span>
    </div>
  )
}
