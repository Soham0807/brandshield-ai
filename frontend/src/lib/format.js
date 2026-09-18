export const SENTIMENT_COLORS = {
  positive: '#10b981',
  neutral: '#94a3b8',
  negative: '#ef4444',
  spam: '#f97316',
}

export const SEVERITY_STYLES = {
  critical: { text: 'text-red-300', bg: 'bg-red-500/15', border: 'border-red-500/30', dot: 'bg-red-500' },
  high: { text: 'text-orange-300', bg: 'bg-orange-500/15', border: 'border-orange-500/30', dot: 'bg-orange-500' },
  medium: { text: 'text-amber-300', bg: 'bg-amber-500/15', border: 'border-amber-500/30', dot: 'bg-amber-400' },
  low: { text: 'text-sky-300', bg: 'bg-sky-500/15', border: 'border-sky-500/30', dot: 'bg-sky-400' },
}

export const RISK_COLORS = { low: '#10b981', medium: '#f59e0b', high: '#f97316', critical: '#ef4444' }

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
