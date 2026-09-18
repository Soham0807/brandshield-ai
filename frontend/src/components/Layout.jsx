import {
  Activity,
  Bell,
  BrainCircuit,
  Gauge,
  Image,
  PlaySquare,
  LayoutDashboard,
  LineChart,
  MessageSquareText,
  Settings,
  ShieldCheck,
  Tags,
} from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useApi } from '../lib/hooks'
import { useLive, useLiveEvent } from '../lib/live'
import Backdrop from './Backdrop'
import { Toasts } from './ui'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/youtube', label: 'YouTube', icon: PlaySquare },
  { to: '/instagram', label: 'Instagram', icon: Image },
  { to: '/mentions', label: 'Mentions', icon: MessageSquareText },
  { to: '/analytics', label: 'Trends & Forecast', icon: LineChart },
  { to: '/aspects', label: 'Aspect Insights', icon: Tags },
  { to: '/alerts', label: 'Alerts', icon: Bell, badge: true },
  { to: '/analyze', label: 'Analyze Text', icon: BrainCircuit },
  { to: '/system', label: 'Performance', icon: Gauge },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Layout() {
  const { connected, status } = useLive()
  const location = useLocation()
  const alerts = useApi('/alerts?status=open&limit=1', { interval: 60000 })
  useLiveEvent('alert', () => alerts.reload())
  useLiveEvent('alert_updated', () => alerts.reload())
  const openCount = Object.values(alerts.data?.open_counts || {}).reduce((a, b) => a + b, 0)
  const crisis = status?.simulator?.crisis

  return (
    <div className="flex min-h-full">
      <Backdrop />

      <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col border-r border-white/[0.06] bg-black/30 backdrop-blur-xl md:flex">
        <div className="flex items-center gap-3 px-5 py-5">
          <span className="relative grid size-10 place-items-center rounded-2xl bg-gradient-to-br from-amber-300 via-orange-500 to-rose-500 text-ink-950 glow-brand">
            <ShieldCheck size={20} strokeWidth={2.5} />
            <span className="absolute inset-0 rounded-2xl ring-1 ring-white/25" />
          </span>
          <div>
            <div className="display text-[15px] font-bold leading-none text-stone-50">
              Brand<span className="gradient-text">Shield</span>
            </div>
            <div className="mt-1 text-[10px] font-medium uppercase tracking-[.18em] text-stone-500">AI Intelligence</div>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1 px-3">
          {NAV.map(({ to, label, icon: Icon, end, badge }) => {
            const active = end ? location.pathname === to : location.pathname.startsWith(to)
            return (
              <NavLink key={to} to={to} end={end}
                className="group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] transition">
                {active && (
                  <>
                    <span className="absolute inset-0 rounded-xl bg-gradient-to-r from-orange-500/20 to-transparent ring-1 ring-orange-400/25" />
                    <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-gradient-to-b from-amber-300 to-orange-500" />
                  </>
                )}
                <Icon size={16} className={`relative transition ${active ? 'text-orange-300' : 'text-stone-500 group-hover:text-stone-300'}`} />
                <span className={`relative flex-1 font-medium transition ${active ? 'text-stone-50' : 'text-stone-400 group-hover:text-stone-200'}`}>{label}</span>
                {badge && openCount > 0 && (
                  <span className="relative rounded-full bg-gradient-to-br from-rose-500 to-red-600 px-1.5 text-[10px] font-bold text-white shadow-lg shadow-rose-950/50">
                    {openCount}
                  </span>
                )}
              </NavLink>
            )
          })}
        </nav>


        <div className="m-3 rounded-2xl border border-white/[0.07] bg-black/30 p-3 text-[11px]">
          <div className="flex items-center gap-2">
            <span className={`size-2 rounded-full ${connected ? 'bg-emerald-400 pulse-dot' : 'bg-rose-500'}`} />
            <span className="font-medium text-stone-300">{connected ? 'Live stream connected' : 'Reconnecting…'}</span>
          </div>
          {status && (
            <div className="mt-2.5 space-y-1.5 text-stone-500">
              <Row label="Bus" value={status.bus === 'kafka' ? 'Apache Kafka' : 'In-memory'} />
              <Row label="Model" value={status.model === 'ready' ? 'DistilBERT ready' : status.model} />
              <Row label="Mentions" value={status.mentions_stored?.toLocaleString()} />
            </div>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-white/[0.06] bg-ink-950/70 px-4 py-3 backdrop-blur-xl md:px-8">
          <div className="flex items-center gap-2 md:hidden">
            <ShieldCheck size={18} className="text-orange-400" />
            <span className="display text-sm font-bold">BrandShield</span>
          </div>
          <div className="hidden items-center gap-2 text-sm md:flex">
            <span className="text-stone-500">Monitoring</span>
            <span className="display font-semibold text-stone-50">{status?.brand_name || '…'}</span>
            <span className="flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-300">
              <span className="size-1.5 rounded-full bg-emerald-400 pulse-dot" /> Live
            </span>
          </div>
          {crisis?.active && (
            <span className="flex items-center gap-1.5 rounded-full border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-[11px] font-medium text-rose-300">
              <Activity size={12} className="animate-pulse" /> Simulated {crisis.aspect} crisis
            </span>
          )}
          {status?.seeding && (
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] text-amber-300">
              Generating history {Math.round((100 * status.seeding.done) / Math.max(status.seeding.total, 1))}%
            </span>
          )}
          {status && status.model !== 'ready' && (
            <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-1 text-[11px] text-sky-300">
              Loading DistilBERT…
            </span>
          )}
          <nav className="ml-auto flex gap-1 overflow-x-auto md:hidden">
            {NAV.map(({ to, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end}
                className={({ isActive }) => `rounded-lg p-2 ${isActive ? 'bg-orange-500/15 text-orange-300' : 'text-stone-500'}`}>
                <Icon size={16} />
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="mx-auto w-full max-w-[1560px] flex-1 px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
      <Toasts />
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-2">
      <span>{label}</span>
      <span className="truncate font-medium text-stone-300">{value}</span>
    </div>
  )
}
