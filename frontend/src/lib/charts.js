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

ChartJS.register(ArcElement, BarController, BarElement, LineController, CategoryScale, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip)

ChartJS.defaults.color = '#a8a29e'
ChartJS.defaults.font.family = 'Inter, ui-sans-serif, system-ui, Segoe UI, sans-serif'
ChartJS.defaults.font.size = 11
ChartJS.defaults.borderColor = '#2c2521'
ChartJS.defaults.plugins.legend.labels.boxWidth = 10
ChartJS.defaults.plugins.legend.labels.boxHeight = 10
ChartJS.defaults.plugins.legend.labels.usePointStyle = true
ChartJS.defaults.plugins.tooltip.backgroundColor = '#1f1a17'
ChartJS.defaults.plugins.tooltip.borderColor = '#3d3430'
ChartJS.defaults.plugins.tooltip.borderWidth = 1
ChartJS.defaults.plugins.tooltip.padding = 10
ChartJS.defaults.plugins.tooltip.titleColor = '#fafaf9'
ChartJS.defaults.plugins.tooltip.bodyColor = '#d6d3d1'
ChartJS.defaults.maintainAspectRatio = false
ChartJS.defaults.animation.duration = 400

export const gridColor = 'rgba(120, 104, 94, 0.14)'

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
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`
}
