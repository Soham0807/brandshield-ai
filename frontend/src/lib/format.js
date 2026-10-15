import { cssVar } from './cssvar'

// Read from the active theme on every access, so light and dark both get the right values.
export const SENTIMENT_COLORS = {
  get positive() { return cssVar('--color-positive', '#3e7c59') },
  get neutral() { return cssVar('--color-neutral', '#b3ac9f') },
  get negative() { return cssVar('--color-negative', '#d2381e') },
  get spam() { return cssVar('--color-spam', '#c98a1a') },
}

/** The ink colour of the active theme (near-black on paper, near-white at night). */
export const INK = { toString: () => cssVar('--color-stone-50', '#121212') }
export const inkColor = () => cssVar('--color-stone-50', '#121212')

export const SEVERITY_STYLES = {
  critical: { text: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/70', dot: 'bg-red-500' },
  high: { text: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/50', dot: 'bg-orange-500' },
  medium: { text: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/50', dot: 'bg-amber-500' },
  low: { text: 'text-sky-400', bg: 'bg-sky-500/10', border: 'border-sky-500/40', dot: 'bg-sky-500' },
}

export const RISK_COLORS = {
  get low() { return cssVar('--color-positive', '#3e7c59') },
  get medium() { return cssVar('--color-amber-500', '#c98a1a') },
  get high() { return cssVar('--color-orange-500', '#d9681e') },
  get critical() { return cssVar('--color-red-500', '#d2381e') },
}

/** "apple" -> "Apple"; names that already have capitals are left alone. */
export function brandTitle(name) {
  if (!name) return ''
  return name === name.toLowerCase() ? name.replace(/(^|\s)\S/g, (c) => c.toUpperCase()) : name
}

/** YouTube display names already start with "@". */
export function authorLabel(author) {
  return `@${String(author || 'unknown').replace(/^@+/, '')}`
}

const ISO_RE = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z/g

/** Make alert text readable: local times instead of ISO stamps, no doubled "@", no model jargon. */
export function humanizeAlert(text) {
  if (!text) return ''
  return text
    .replace(/@@/g, '@')
    .replace(ISO_RE, (iso) => new Date(iso).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' }))
    .replace(/Prophet forecasts the sentiment index to fall to/g, 'The forecast expects sentiment to dip to')
    .replace(/\(floor ([-\d.]+)\)/g, '(alert level $1)')
}

export function aspectLabel(name) {
  if (!name) return ''
  return name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function timeAgo(iso) {
  if (!iso) return ''
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 45) return 'just now'
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`
  return `${Math.round(seconds / 86400)}d ago`
}

export function formatTime(iso, withDate = false) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString(undefined, withDate
    ? { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }
    : { hour: '2-digit', minute: '2-digit' })
}

export function chartLabel(iso, hours) {
  const d = new Date(iso)
  if (hours > 24) return d.toLocaleString(undefined, { day: '2-digit', month: 'short', hour: '2-digit' })
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

// "Last hour" / "Last 6 h" for the risk score's recent window
export function windowLabel(hours) {
  if (!hours || hours <= 1) return 'Last hour'
  return `Last ${Math.round(hours)} h`
}

export function num(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return '–'
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })
}

export const SOURCE_LABELS = {
  instagram: 'Instagram',
  twitter: 'Twitter / X',
  reddit: 'Reddit',
  news: 'News / RSS',
  youtube: 'YouTube',
  appstore: 'App Store',
  google_reviews: 'Google Reviews',
  manual: 'Manual',
  api: 'API',
  csv: 'CSV upload',
}

/** Instagram's CDN blocks embedding on other sites, so its images go through the backend relay. */
export function igImage(url) {
  if (!url) return url
  try {
    const host = new URL(url).hostname
    if (host.endsWith('.cdninstagram.com') || host.endsWith('.fbcdn.net')) {
      return `/api/instagram/image?url=${encodeURIComponent(url)}`
    }
  } catch {
    // not a valid URL – use as is
  }
  return url
}
