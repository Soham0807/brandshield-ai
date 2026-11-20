import { Activity, LogOut, Moon, Sun, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { brandTitle } from '../lib/format'
import { NAV_HELP, PAGE_HELP } from '../lib/help'
import { useApi } from '../lib/hooks'
import { useLive, useLiveEvent } from '../lib/live'
import { useTheme } from '../lib/theme'
import { useAuth } from './AuthGate'
import Backdrop from './Backdrop'
import { LogoMark, SentimentRule, Wordmark } from './Brand'
import { Tip, Toasts } from './ui'

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/instagram', label: 'Instagram' },
  { to: '/youtube', label: 'YouTube' },
  { to: '/mentions', label: 'Mentions' },
  { to: '/analytics', label: 'Trends & Forecast' },
  { to: '/aspects', label: 'Topics' },
  { to: '/alerts', label: 'Alerts', badge: true },
  { to: '/analyze', label: 'Analyze Text' },
  { to: '/system', label: 'Performance' },
  { to: '/settings', label: 'Settings' },
]

export default function Layout() {
  const { connected, status } = useLive()
  const { resolved, toggle } = useTheme()
  const { authEnabled, username, logout } = useAuth()
  const location = useLocation()
  const alerts = useApi('/alerts?status=open&limit=1', { interval: 60000 })
  useLiveEvent('alert', () => alerts.reload())
  useLiveEvent('alert_updated', () => alerts.reload())
  const openCount = Object.values(alerts.data?.open_counts || {}).reduce((a, b) => a + b, 0)
  const crisis = status?.simulator?.crisis
  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

  return (
    <div className="flex min-h-full flex-col">
      <Backdrop />

      <header className="sticky top-0 z-30 border-b-[3px] border-double border-stone-50 bg-ink-950/95 backdrop-blur">
        <div className="mx-auto w-full max-w-[1400px] px-4 md:px-8">
          {/* dateline */}
          <div className="flex items-center gap-3 border-b border-ink-700 py-1.5 font-mono text-[10.5px] uppercase tracking-[.14em] text-stone-500">
            <span className="hidden sm:inline">{today}</span>
            <span className="min-w-0 truncate">
              <span className="sm:before:mr-3 sm:before:content-['·']">Monitoring </span>
              <span className="font-semibold text-stone-50">{brandTitle(status?.brand_name) || '…'}</span>
            </span>
            <span className="ml-auto flex shrink-0 items-center gap-3">
              {crisis?.active && (
                <span className="flex items-center gap-1 text-red-400"><Activity size={11} className="animate-pulse" /> Demo crisis: {crisis.aspect}</span>
              )}
              {status?.seeding && (
                <span className="text-amber-400">Generating history {Math.round((100 * status.seeding.done) / Math.max(status.seeding.total, 1))}%</span>
              )}
              {status && status.model !== 'ready' && <span className="text-sky-400">Loading AI model…</span>}
              <button type="button" onClick={toggle}
                      className="flex items-center gap-1 uppercase tracking-[.14em] text-stone-500 transition hover:text-stone-50"
                      aria-label={resolved === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
                      title={resolved === 'dark' ? 'Light theme' : 'Dark theme'}>
                {resolved === 'dark' ? <Sun size={12} /> : <Moon size={12} />}
                <span className="hidden sm:inline">{resolved === 'dark' ? 'Day' : 'Night'}</span>
              </button>
              {authEnabled && (
                <button type="button" onClick={logout} title={username ? `Signed in as ${username}` : 'Sign out'}
                        className="flex items-center gap-1 uppercase tracking-[.14em] text-stone-500 transition hover:text-stone-50">
                  <LogOut size={12} /> <span className="hidden sm:inline">Sign out</span>
                </button>
              )}
              <Tip text="Data updates on its own: new comments, risk score and alerts appear without refreshing the page.">
                <span className={`flex items-center gap-1.5 font-semibold ${connected ? 'text-red-400' : 'text-stone-500'}`}>
                  <span className={`size-1.5 rounded-full ${connected ? 'bg-red-500 pulse-dot' : 'bg-stone-500'}`} />
                  {connected ? 'Live' : 'Reconnecting'}
                </span>
              </Tip>
            </span>
          </div>

          {/* nameplate */}
          <div className="flex items-end justify-between gap-4 pb-2 pt-3">
            <NavLink to="/" className="flex items-center gap-2.5">
              <LogoMark size={38} />
              <Wordmark className="text-[30px]" />
            </NavLink>
            <span className="hidden pb-0.5 font-mono text-[10.5px] uppercase tracking-[.16em] text-stone-500 md:block">
              Brand risk &amp; sentiment desk
            </span>
          </div>

          {/* section nav: scrolls sideways on small screens instead of widening the page */}
          <nav className="no-scrollbar -mx-4 flex gap-0.5 overflow-x-auto px-4 md:-mx-0 md:px-0">
            {NAV.map(({ to, label, short, end, badge }) => {
              const active = end ? location.pathname === to : location.pathname.startsWith(to)
              return (
                <Tip key={to} text={NAV_HELP[label]}>
                  <NavLink to={to} end={end}
                    className={`relative flex shrink-0 items-center gap-1.5 whitespace-nowrap px-2.5 py-2 text-[13px] font-medium transition ${
                      active ? 'text-stone-50' : 'text-stone-400 hover:text-stone-50'}`}>
                    {short ? <><span className="hidden lg:inline">{label}</span><span className="lg:hidden">{short}</span></> : label}
                    {badge && openCount > 0 && (
                      <span className="bg-red-500 px-1 font-mono text-[10px] font-semibold leading-4 text-on-signal">{openCount}</span>
                    )}
                    {active && <span className="absolute inset-x-2.5 -bottom-[3px] h-[3px] bg-red-500" />}
                  </NavLink>
                </Tip>
              )
            })}
          </nav>
        </div>
      </header>

      <main key={resolved} className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 md:px-8">
        <PageIntro path={location.pathname} />
        <Outlet />
      </main>

      <footer>
        <SentimentRule />
        <div className="mx-auto flex w-full max-w-[1400px] flex-wrap gap-x-5 gap-y-1 px-4 py-3 font-mono text-[10.5px] uppercase tracking-[.12em] text-stone-500 md:px-8">
          <span className="flex items-center gap-1.5 text-stone-50"><LogoMark size={14} /> BrandShield AI</span>
          {status && (
            <>
              <span>{status.mentions_stored?.toLocaleString()} mentions analysed</span>
              <span>Model {status.model === 'ready' ? 'ready' : status.model}</span>
              <span>Stream {status.bus === 'kafka' ? 'Apache Kafka' : 'in-memory'}</span>
            </>
          )}
        </div>
      </footer>
      <Toasts />
    </div>
  )
}

/** Slim "what am I looking at" line at the top of each page. */
function PageIntro({ path }) {
  const [hidden, setHidden] = useState({})
  const help = PAGE_HELP[path]
  if (!help || hidden[path]) return null
  return (
    <div className="animate-rise mb-6 flex items-start gap-3 border-l-2 border-red-500 pl-3">
      <p className="flex-1 text-[13px] leading-relaxed text-stone-400">
        <span className="font-semibold text-stone-50">{help.title}. </span>
        {help.text}
      </p>
      <button onClick={() => setHidden({ ...hidden, [path]: true })} className="shrink-0 text-stone-500 hover:text-stone-50" aria-label="Hide">
        <X size={14} />
      </button>
    </div>
  )
}
