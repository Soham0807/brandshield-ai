import { AlertTriangle, Loader2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { SENTIMENT_COLORS, SEVERITY_STYLES } from '../lib/format'
import { useLive } from '../lib/live'

export function Card({ title, subtitle, action, children, className = '', bodyClass = 'p-5 pt-3' }) {
  return (
    <section className={`card card-hover flex flex-col ${className}`}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 px-5 pt-4">
          <div>
            {title && <h2 className="display text-[13px] font-semibold tracking-wide text-stone-100">{title}</h2>}
            {subtitle && <p className="mt-1 text-[11px] leading-relaxed text-stone-500">{subtitle}</p>}
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
  const [shown, setShown] = useState(value ?? 0)
  const from = useRef(value ?? 0)
  useEffect(() => {
    const start = performance.now()
    const a = from.current
    const b = Number(value ?? 0)
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
  }, [value, duration])
  if (value === null || value === undefined) return '–'
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

const TONES = {
  amber: ['#fbbf24', 'from-amber-400/20 to-amber-500/5', 'text-amber-300'],
  green: ['#22d3a5', 'from-emerald-400/20 to-emerald-500/5', 'text-emerald-300'],
  red: ['#ff4d6d', 'from-rose-400/20 to-rose-500/5', 'text-rose-300'],
  sky: ['#38bdf8', 'from-sky-400/20 to-sky-500/5', 'text-sky-300'],
  violet: ['#a78bfa', 'from-violet-400/20 to-violet-500/5', 'text-violet-300'],
  orange: ['#fb923c', 'from-orange-400/20 to-orange-500/5', 'text-orange-300'],
}

export function Stat({ icon: Icon, label, value, delta, deltaSuffix = '', invert = false, tone = 'amber',
                       hint, series, suffix = '', digits = 0, numeric }) {
  const [color, bg, text] = TONES[tone] || TONES.amber
  const good = delta === null || delta === undefined ? null : invert ? delta <= 0 : delta >= 0
  return (
    <div className="card card-hover group relative overflow-hidden p-4" title={hint}>
      <span className={`pointer-events-none absolute inset-x-0 -top-16 h-24 bg-gradient-to-b ${bg} opacity-0 blur-2xl transition duration-500 group-hover:opacity-100`} />
      <div className="relative flex items-start justify-between">
        <span className={`grid size-9 place-items-center rounded-xl bg-gradient-to-br ${bg} ${text} ring-1 ring-white/10`}>
          <Icon size={16} />
        </span>
        {delta !== null && delta !== undefined && (
          <span className={`rounded-full px-1.5 py-0.5 text-[11px] font-semibold ${good ? 'bg-emerald-500/12 text-emerald-300' : 'bg-rose-500/12 text-rose-300'}`}>
            {delta > 0 ? '▲' : delta < 0 ? '▼' : '■'} {Math.abs(delta).toFixed(1)}{deltaSuffix}
          </span>
        )}
      </div>
      <div className="num relative mt-3 text-[26px] font-semibold leading-none text-stone-50">
        {numeric === false ? value : <><CountUp value={numeric ?? value} digits={digits} />{suffix}</>}
      </div>
      <div className="relative mt-1.5 text-[11px] font-medium uppercase tracking-wider text-stone-500">{label}</div>
      {series?.length > 1 && (
        <div className="relative -mx-1 mt-2 opacity-80"><Sparkline data={series} color={color} height={28} /></div>
      )}
    </div>
  )
}

export function SentimentBadge({ value, spam }) {
  if (spam) {
    return <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-300 ring-1 ring-amber-500/20">spam</span>
  }
  const styles = {
    positive: 'bg-emerald-500/12 text-emerald-300 ring-emerald-500/20',
    neutral: 'bg-slate-500/15 text-slate-300 ring-slate-400/20',
    negative: 'bg-rose-500/12 text-rose-300 ring-rose-500/20',
  }
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${styles[value]}`}>{value}</span>
}

export function SeverityBadge({ severity }) {
  const s = SEVERITY_STYLES[severity] || SEVERITY_STYLES.low
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${s.bg} ${s.text} ${s.border}`}>
      <span className={`size-1.5 rounded-full ${s.dot}`} />
      {severity}
    </span>
  )
}

export function Spinner({ label = 'Loading…', className = '' }) {
  return (
    <div className={`flex items-center justify-center gap-2 py-10 text-sm text-stone-500 ${className}`}>
      <Loader2 size={16} className="animate-spin text-brand-400" /> {label}
    </div>
  )
}

export function Skeleton({ className = 'h-24' }) {
  return <div className={`skeleton ${className}`} />
}

export function Empty({ children }) {
  return <div className="py-10 text-center text-sm text-stone-500">{children}</div>
}

export function ErrorBox({ message }) {
  if (!message) return null
  return (
    <div className="flex items-center gap-2 rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
      <AlertTriangle size={15} /> {message}
    </div>
  )
}

export function Segmented({ options, value, onChange }) {
  return (
    <div className="inline-flex rounded-xl border border-white/10 bg-black/30 p-0.5">
      {options.map((o) => (
        <button key={o.value} onClick={() => onChange(o.value)}
          className={`relative rounded-lg px-2.5 py-1 text-[11px] font-semibold transition ${
            value === o.value ? 'text-ink-950' : 'text-stone-400 hover:text-stone-100'}`}>
          {value === o.value && <span className="absolute inset-0 rounded-lg bg-gradient-to-br from-amber-300 to-orange-500" />}
          <span className="relative">{o.label}</span>
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
    <div className={`flex ${height} w-full overflow-hidden rounded-full bg-white/[0.06]`}>
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
          <div key={id} className={`animate-slide-in pointer-events-auto card border ${s.border} p-3 shadow-2xl`}>
            <div className="flex items-start gap-3">
              <span className={`mt-1 size-2 shrink-0 rounded-full ${s.dot} pulse-dot`} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <SeverityBadge severity={alert.severity} />
                  <span className="text-[11px] text-stone-500">New alert</span>
                </div>
                <p className="mt-1.5 text-sm font-medium text-stone-100">{alert.title}</p>
                <p className="mt-0.5 line-clamp-2 text-xs text-stone-400">{alert.message}</p>
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
