import { AlertTriangle, Info, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { humanizeAlert, inkColor, SENTIMENT_COLORS, SEVERITY_STYLES } from '../lib/format'
import { CARD_HELP, SENTIMENT_HELP, SEVERITY_HELP, STAT_HELP } from '../lib/help'
import { LogoMark } from './Brand'
import { useLive } from '../lib/live'

// ---- Hover pop-ups ------------------------------------------------------
// Rendered into <body> so cards with overflow-hidden never clip them, and kept
// inside the viewport: above the element when there is room, otherwise below.

const TIP_WIDTH = 280

function TipBubble({ rect, text }) {
  const left = Math.min(Math.max(8, rect.left + rect.width / 2 - TIP_WIDTH / 2), window.innerWidth - TIP_WIDTH - 8)
  const above = rect.top > 140
  const style = above
    ? { left, bottom: window.innerHeight - rect.top + 8, width: TIP_WIDTH }
    : { left, top: rect.bottom + 8, width: TIP_WIDTH }
  return createPortal(
    <div style={style}
      className="animate-tip pointer-events-none fixed z-[100] rounded-sm bg-stone-50 px-3 py-2 font-sans text-[12px] font-normal normal-case leading-relaxed tracking-normal text-ink-950 shadow-xl">
      {text}
    </div>,
    document.body,
  )
}

/** Attach a hover pop-up to any element: spread `handlers` on it and render `bubble`. */
export function useTip(text) {
  const [rect, setRect] = useState(null)
  useEffect(() => {
    if (!rect) return
    const hide = () => setRect(null)
    window.addEventListener('scroll', hide, true)
    return () => window.removeEventListener('scroll', hide, true)
  }, [rect])
  const show = (e) => text && setRect(e.currentTarget.getBoundingClientRect())
  const hide = () => setRect(null)
  return {
    handlers: { onMouseEnter: show, onMouseLeave: hide, onFocus: show, onBlur: hide },
    bubble: rect && text ? <TipBubble rect={rect} text={text} /> : null,
  }
}

/** Wrap children with a hover pop-up. */
export function Tip({ text, children, className = '', block = false }) {
  const { handlers, bubble } = useTip(text)
  if (!text) return children
  const Tag = block ? 'div' : 'span'
  return (
    <Tag {...handlers} className={`${block ? '' : 'inline-flex'} cursor-help ${className}`}>
      {children}
      {bubble}
    </Tag>
  )
}

/** Small "i" icon that explains something on hover. */
export function InfoDot({ text, size = 13 }) {
  if (!text) return null
  return (
    <Tip text={text} className="align-middle">
      <Info size={size} className="text-stone-600 transition hover:text-red-500" tabIndex={0} />
    </Tip>
  )
}

export function Card({ title, subtitle, action, children, className = '', bodyClass = 'p-5 pt-3', info }) {
  const help = info ?? (typeof title === 'string' ? CARD_HELP[title] : undefined)
  return (
    <section className={`card card-hover flex flex-col ${className}`}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 px-5 pt-4">
          <div>
            {title && (
              <h2 className="display flex items-center gap-1.5 text-[17px] font-semibold leading-tight text-stone-50">
                {title} <InfoDot text={help} />
              </h2>
            )}
            {subtitle && <p className="mt-1 text-[12px] leading-relaxed text-stone-500">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={`flex-1 ${bodyClass}`}>{children}</div>
    </section>
  )
}

/** Animated number that counts to its value. */
export function CountUp({ value, digits = 0, duration = 700 }) {
  // Only plain numbers are animated; anything else ("n/a", pre-formatted text) is shown as-is.
  // Animating a formatted string such as "56.6%" used to produce "NaN".
  const target = typeof value === 'number' ? value : NaN
  const animatable = Number.isFinite(target)
  const [shown, setShown] = useState(animatable ? target : 0)
  const from = useRef(animatable ? target : 0)
  useEffect(() => {
    if (!animatable) return
    const start = performance.now()
    const a = from.current
    const b = target
    if (a === b) return
    let raf
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration)
      setShown(a + (b - a) * (1 - (1 - t) ** 3))
      if (t < 1) raf = requestAnimationFrame(tick)
      else from.current = b
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, animatable, duration])
  if (value === null || value === undefined) return '–'
  if (!animatable) return String(value)
  return shown.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function Sparkline({ data = [], color = '#f97316', height = 34, fill = true, className = '' }) {
  const points = data.filter((n) => Number.isFinite(n))
  if (points.length < 2) return <div style={{ height }} />
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const step = 100 / (points.length - 1)
  const coords = points.map((v, i) => [i * step, 100 - ((v - min) / span) * 100])
  const d = coords.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ')
  const id = `sp${color.replace(/[^a-z0-9]/gi, '')}`
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" height={height} className={`w-full ${className}`}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity=".45" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={`${d} L100,100 L0,100 Z`} fill={`url(#${id})`} />}
      <path d={d} fill="none" stroke={color} strokeWidth="2.5" vectorEffect="non-scaling-stroke"
            strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={coords.at(-1)[0]} cy={coords.at(-1)[1]} r="2.5" fill={color} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

export function Stat({ icon: Icon, label, value, delta, deltaSuffix = '', invert = false, tone,
                       hint, series, suffix = '', digits = 0, numeric }) {
  const good = delta === null || delta === undefined ? null : invert ? delta <= 0 : delta >= 0
  const { handlers, bubble } = useTip(hint ?? STAT_HELP[label])
  const accent = tone === 'red' ? 'text-red-500' : 'text-stone-50'
  return (
    <div className="group relative cursor-help border-t-2 border-stone-50 pt-3" {...handlers}>
      {bubble}
      {/* fixed two-line header so every figure in a row sits on the same baseline */}
      <div className="flex min-h-[30px] items-start justify-between gap-2">
        <span className="flex items-start gap-1.5 font-mono text-[10.5px] font-medium uppercase leading-[1.35] tracking-[.14em] text-stone-500">
          {Icon && <Icon size={12} className="mt-px shrink-0 text-stone-600" />}
          {label}
        </span>
        {delta !== null && delta !== undefined && (
          <span className={`whitespace-nowrap font-mono text-[11px] font-semibold ${good ? 'text-emerald-400' : 'text-red-400'}`}>
            {delta > 0 ? '▲' : delta < 0 ? '▼' : '■'} {Math.abs(delta).toFixed(1)}{deltaSuffix}
          </span>
        )}
      </div>
      <div className={`num mt-2 text-[40px] font-medium leading-none ${accent}`}>
        {numeric === false ? value : <><CountUp value={numeric ?? value} digits={digits} />{(numeric ?? value) != null && <span className="text-[22px] text-stone-500">{suffix}</span>}</>}
      </div>
      {series?.length > 1 && (
        <div className="mt-2 opacity-90"><Sparkline data={series} color={inkColor()} height={26} fill={false} /></div>
      )}
    </div>
  )
}

// darker text shades of the sentiment colours, AA on paper at label size
const SENTIMENT_TEXT = {
  positive: 'var(--color-emerald-300)',
  neutral: 'var(--color-stone-500)',
  negative: 'var(--color-red-300)',
  spam: 'var(--color-amber-400)',
}

export function SentimentBadge({ value, spam }) {
  const kind = spam ? 'spam' : value
  const color = SENTIMENT_COLORS[kind] || SENTIMENT_COLORS.neutral
  return (
    <Tip text={SENTIMENT_HELP[kind]}>
      <span className="inline-flex items-center gap-1.5 font-mono text-[10.5px] font-semibold uppercase tracking-[.12em]"
            style={{ color: SENTIMENT_TEXT[kind] || SENTIMENT_TEXT.neutral }}>
        <span className="size-2" style={{ background: color }} />
        {kind}
      </span>
    </Tip>
  )
}

export function SeverityBadge({ severity }) {
  const s = SEVERITY_STYLES[severity] || SEVERITY_STYLES.low
  return (
    <Tip text={SEVERITY_HELP[severity]}>
      <span className={`inline-flex items-center gap-1.5 rounded-sm border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[.12em] ${s.bg} ${s.text} ${s.border}`}>
        <span className={`size-1.5 ${s.dot}`} />
        {severity}
      </span>
    </Tip>
  )
}

export function Spinner({ label = 'Loading…', className = '' }) {
  return (
    <div className={`flex items-center justify-center gap-2 py-10 text-sm text-stone-500 ${className}`}>
      <LogoMark size={18} pulse title="" /> {label}
    </div>
  )
}

export function Skeleton({ className = 'h-24' }) {
  return <div className={`skeleton ${className}`} />
}

export function Empty({ children }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center text-sm text-stone-500">
      <LogoMark size={28} tone="muted" title="" />
      <div>{children}</div>
    </div>
  )
}

export function ErrorBox({ message }) {
  if (!message) return null
  return (
    <div className="flex items-center gap-2 border-l-4 border-red-500 bg-red-500/[0.06] px-3 py-2 text-sm text-red-300">
      <AlertTriangle size={15} /> {message}
    </div>
  )
}

export function Segmented({ options, value, onChange, tip }) {
  const { handlers, bubble } = useTip(tip ?? (options === WINDOW_OPTIONS ? 'Time window used for every number and chart on this page.' : undefined))
  return (
    <div className="inline-flex border border-stone-50" {...handlers}>
      {bubble}
      {options.map((o) => (
        <button key={o.value} onClick={() => onChange(o.value)}
          className={`px-2.5 py-1 font-mono text-[11px] font-semibold uppercase transition ${
            value === o.value ? 'bg-stone-50 text-ink-950' : 'text-stone-400 hover:bg-ink-850 hover:text-stone-50'}`}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export const WINDOW_OPTIONS = [
  { value: 6, label: '6h' },
  { value: 24, label: '24h' },
  { value: 72, label: '3d' },
  { value: 168, label: '7d' },
  { value: 720, label: '30d' },
]

export function SentimentBar({ positive = 0, neutral = 0, negative = 0, height = 'h-1.5' }) {
  const total = positive + neutral + negative || 1
  const seg = (v, c) => <div className="transition-all duration-700" style={{ width: `${(100 * v) / total}%`, background: c }} />
  return (
    <div className={`flex ${height} w-full overflow-hidden bg-ink-800`}>
      {seg(positive, SENTIMENT_COLORS.positive)}
      {seg(neutral, SENTIMENT_COLORS.neutral)}
      {seg(negative, SENTIMENT_COLORS.negative)}
    </div>
  )
}

export function Toasts() {
  const { toasts, dismissToast } = useLive()
  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-2">
      {toasts.map(({ id, alert }) => {
        const s = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.low
        return (
          <div key={id} className="animate-slide-in pointer-events-auto card p-3 shadow-xl">
            <div className="flex items-start gap-3">
              <span className="mt-1 size-2 shrink-0 rounded-full bg-red-500 pulse-dot" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <SeverityBadge severity={alert.severity} />
                  <span className="text-[11px] text-stone-500">New alert</span>
                </div>
                <p className="display mt-1.5 text-[15px] font-semibold text-stone-50">{alert.title}</p>
                <p className="mt-0.5 line-clamp-2 text-xs text-stone-400">{humanizeAlert(alert.message)}</p>
              </div>
              <button onClick={() => dismissToast(id)} className="text-stone-500 transition hover:text-stone-200">
                <X size={14} />
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
