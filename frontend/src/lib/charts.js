import {
  ArcElement,
  BarController,
  BarElement,
  LineController,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'
import { cssVar } from './cssvar'

ChartJS.register(ArcElement, BarController, BarElement, LineController, CategoryScale, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip)

ChartJS.defaults.font.family = '"IBM Plex Sans", ui-sans-serif, system-ui, Segoe UI, sans-serif'
ChartJS.defaults.font.size = 11
ChartJS.defaults.plugins.legend.labels.boxWidth = 9
ChartJS.defaults.plugins.legend.labels.boxHeight = 9
ChartJS.defaults.plugins.legend.labels.usePointStyle = true
ChartJS.defaults.plugins.legend.labels.pointStyle = 'rect'
ChartJS.defaults.plugins.tooltip.borderWidth = 0
ChartJS.defaults.plugins.tooltip.cornerRadius = 2
ChartJS.defaults.plugins.tooltip.padding = 10
ChartJS.defaults.plugins.tooltip.titleFont = { family: '"IBM Plex Mono", monospace', size: 11, weight: '600' }
ChartJS.defaults.maintainAspectRatio = false
ChartJS.defaults.animation.duration = 400
// smooth lines without overshooting the data (no fake peaks between points)
ChartJS.defaults.elements.line.cubicInterpolationMode = 'monotone'
ChartJS.defaults.elements.bar.borderRadius = 0

/** Gridline colour for the active theme (live binding: re-read after a theme switch). */
export let gridColor = 'rgba(18, 18, 18, 0.07)'

/** Point the chart defaults at the active theme's colours. Called by lib/theme.jsx. */
export function applyChartTheme() {
  const dark = document.documentElement.dataset.theme === 'dark'
  const ink = cssVar('--color-stone-50', '#121212')
  const paper = cssVar('--color-ink-950', '#f4f0e8')
  ChartJS.defaults.color = cssVar('--color-stone-500', '#6b655b')
  ChartJS.defaults.borderColor = cssVar('--color-ink-700', '#d8d1c3')
  // tooltips are an inverted slip: ink on paper in the light theme, paper on ink in the dark one
  ChartJS.defaults.plugins.tooltip.backgroundColor = ink
  ChartJS.defaults.plugins.tooltip.titleColor = paper
  ChartJS.defaults.plugins.tooltip.bodyColor = paper
  gridColor = dark ? 'rgba(242, 237, 227, 0.08)' : 'rgba(18, 18, 18, 0.07)'
}

applyChartTheme()

export function baseScales({ stacked = false, yMin, yMax, yTitle } = {}) {
  return {
    x: { stacked, grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
    y: {
      stacked,
      min: yMin,
      max: yMax,
      grid: { color: gridColor },
      border: { display: false },
      title: yTitle ? { display: true, text: yTitle } : undefined,
    },
  }
}

export function alpha(hex, a) {
  if (!hex.startsWith('#')) return hex
  const n = parseInt(hex.slice(1, 7), 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`
}
