/** Read a colour token from the active theme (charts and SVG need real colour values, not var()). */
export function cssVar(name, fallback = '') {
  if (typeof document === 'undefined') return fallback
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}
