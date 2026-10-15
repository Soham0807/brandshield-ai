// BrandShield identity elements. The mark is a shield holding two lines of text;
// the short line ends in a vermilion dot - a mention, flagged.
// Source files: frontend/public/brand/ (and docs/brand/ for the brand kit).

const INK = '#121212'
const PAPER = '#f4f0e8'
const VERMILION = '#d2381e'
const SHIELD = 'M32 3 L57 11.5 V30.5 C57 46 46.5 56.5 32 61 C17.5 56.5 7 46 7 30.5 V11.5 Z'

const TONES = {
  // follows the theme: ink shield on paper, paper shield in the night edition
  auto: { shield: 'var(--color-stone-50)', lines: 'var(--color-ink-950)', dot: 'var(--color-red-500)' },
  ink: { shield: INK, lines: PAPER, dot: VERMILION },      // fixed: on paper
  paper: { shield: PAPER, lines: INK, dot: VERMILION },    // fixed: on ink
  muted: { shield: 'var(--color-ink-700)', lines: 'var(--color-ink-950)', dot: 'var(--color-ink-500)' },
}

/** The shield mark. `pulse` animates the dot (live / loading states). */
export function LogoMark({ size = 32, tone = 'auto', pulse = false, title = 'BrandShield', className = '' }) {
  const t = TONES[tone] || TONES.auto
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} role="img" aria-label={title} className={className}>
      <path d={SHIELD} style={{ fill: t.shield }} />
      <rect x="17" y="21" width="30" height="6" style={{ fill: t.lines }} />
      <rect x="17" y="33" width="17" height="6" style={{ fill: t.lines }} />
      <circle cx="42.5" cy="36" r="5" style={{ fill: t.dot }} className={pulse ? 'brand-dot-pulse' : undefined} />
    </svg>
  )
}

/** Wordmark set live in Fraunces (the outlined SVG lives in public/brand/). */
export function Wordmark({ className = '' }) {
  return (
    <span className={`display font-semibold leading-none tracking-tight text-stone-50 ${className}`}>
      BrandShield<span className="text-red-500">.</span>
    </span>
  )
}

/** Thin three-part bar in the sentiment colours: the brand's signature rule. */
export function SentimentRule({ className = '' }) {
  return (
    <div aria-hidden className={`flex h-[3px] ${className}`}>
      <span className="flex-[31] bg-positive" />
      <span className="flex-[46] bg-neutral" />
      <span className="flex-[23] bg-red-500" />
    </div>
  )
}
