import {
  CheckCircle2, Copy, Flame, Globe, KeyRound, Loader2, Power, RefreshCw, Save, ServerCog, Trash2,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, ErrorBox, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { aspectLabel, timeAgo } from '../lib/format'
import { useApi } from '../lib/hooks'
import { useLive } from '../lib/live'
import { Toggle } from './Settings'

// Operator-only page: credentials, data sources, detection tuning and demo tools.
// Not linked from the main navigation - dashboard users never need it.

const SOURCE_INFO = {
  simulator: ['Live simulator', 'Realistic synthetic stream (Instagram, Twitter, Reddit, Google reviews) with crisis injection'],
  reddit: ['Reddit', 'Search API – needs free REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET (public access is blocked by Reddit)'],
  rss: ['News / RSS', 'Google News search for your brand + custom RSS_FEEDS'],
  twitter: ['Twitter / X', 'API v2 recent search – needs a paid TWITTER_BEARER_TOKEN'],
  youtube: ['YouTube', 'Comments on videos of monitored channels – needs a free YouTube API key'],
  appstore: ['App Store reviews', 'iOS reviews of ANY brand’s app – no key needed, star ratings included'],
  instagram_pages: ['Instagram pages', 'Public posts and comments of ANY Instagram page, read through Apify – needs an APIFY_TOKEN'],
  instagram: ['Instagram', 'Comments on posts of accounts connected with Instagram login'],
}

const THRESHOLDS = [
  ['risk_alert', 'Risk score alert (0–100)', 1],
  ['negative_ratio_alert', 'Negative share alert (0–1)', 0.01],
  ['min_negative_mentions', 'Min. negatives before alerting', 1],
  ['anomaly_contamination', 'Isolation Forest contamination', 0.01],
  ['z_threshold', 'Adaptive z-score threshold', 0.1],
  ['viral_engagement', 'Viral post engagement', 10],
  ['spam_wave', 'Spam wave (per hour)', 1],
  ['alert_cooldown_minutes', 'Alert cool-down (minutes)', 1],
  ['forecast_score_floor', 'Forecast sentiment floor (-1–1)', 0.05],
]

export default function Setup() {
  const { data, error, reload } = useApi('/settings')
  const { status } = useLive()
  const [cfg, setCfg] = useState(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [saveError, setSaveError] = useState(null)
  const [crisis, setCrisis] = useState({ aspect: 'delivery', minutes: 15, intensity: 0.8 })

  useEffect(() => {
    if (data && !cfg) setCfg(data.config)
  }, [data, cfg])

  if (!cfg) return error ? <ErrorBox message={error} /> : <Spinner />

  const set = (patch) => setCfg((c) => ({ ...c, ...patch }))
  const setNested = (key, patch) => setCfg((c) => ({ ...c, [key]: { ...c[key], ...patch } }))

  async function save() {
    setSaving(true)
    setSaveError(null)
    setMessage(null)
    try {
      // only the fields owned by this page; brand, topics and notifications live in Settings
      const r = await api.put('/settings', {
        sources: cfg.sources,
        simulator_rate_per_min: cfg.simulator_rate_per_min,
        thresholds: cfg.thresholds,
      })
      setCfg(r.config)
      setMessage('Setup saved')
      reload()
    } catch (e) {
      setSaveError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function action(fn, success) {
    setSaveError(null)
    setMessage(null)
    try {
      const r = await fn()
      setMessage(typeof success === 'function' ? success(r) : success)
    } catch (e) {
      setSaveError(e.message)
    }
  }

  const crisisState = status?.simulator?.crisis

  return (
    <div className="space-y-5 pb-20">
      <div>
        <h1 className="display flex items-center gap-2 text-[30px] font-semibold leading-tight text-stone-50"><ServerCog size={20} /> Server setup</h1>
        <p className="text-sm text-stone-500">
          For whoever runs this BrandShield installation – API keys, data sources, detection tuning and demo tools.
          Dashboard users never need this page. <Link to="/settings" className="link">Back to Settings</Link>
        </p>
      </div>

      <div className="rounded-xl border border-sky-500/30 bg-sky-500/[0.06] px-4 py-3 text-sm text-stone-300">
        Saving keys and starting the secure address only work on the computer running BrandShield (not through a
        public link). On a server, put the keys in <code className="text-stone-200">backend/.env</code> instead.
      </div>

      <Card title="Demo tools" subtitle="Inject a burst of complaints to demonstrate anomaly detection and alerts">
        {!cfg.sources.simulator && <p className="mb-3 text-xs text-amber-400">Turn on the live simulator source below (and save) to use this.</p>}
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label className="label">Topic</label>
            <select className="input" value={crisis.aspect} onChange={(e) => setCrisis({ ...crisis, aspect: e.target.value })}>
              {['delivery', 'food_quality', 'service', 'hygiene', 'price', 'app_experience', 'packaging', 'ambience'].map((a) => (
                <option key={a} value={a}>{aspectLabel(a)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Minutes</label>
            <input type="number" min={1} max={240} className="input" value={crisis.minutes}
                   onChange={(e) => setCrisis({ ...crisis, minutes: Number(e.target.value) })} />
          </div>
          <div>
            <label className="label">Intensity</label>
            <input type="range" min={0.1} max={1} step={0.1} className="mt-2 w-full accent-red-500" value={crisis.intensity}
                   onChange={(e) => setCrisis({ ...crisis, intensity: Number(e.target.value) })} />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button className="btn-danger" disabled={!cfg.sources.simulator}
                  onClick={() => action(() => api.post('/simulator/crisis', crisis), 'Crisis started – watch the dashboard and alerts')}>
            <Flame size={14} /> Start crisis
          </button>
          {crisisState?.active && (
            <button className="btn-ghost" onClick={() => action(() => api.post('/simulator/crisis/stop'), 'Crisis stopped')}>
              Stop
            </button>
          )}
          {crisisState?.active && (
            <span className="text-xs text-red-300">Running: {aspectLabel(crisisState.aspect)} until {new Date(crisisState.ends_at).toLocaleTimeString()}</span>
          )}
        </div>
        <p className="mt-3 text-xs text-stone-500">Anomaly checks run every 30 seconds; alerts usually appear within 1–3 minutes.</p>
      </Card>

      <Card title="Data sources" subtitle="Which collectors run. Credentials come from backend/.env or the API keys card below">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Object.entries(SOURCE_INFO).map(([key, [label, help]]) => {
            const collector = data?.collectors?.[key]
            return (
              <div key={key} className="rounded-xl border border-ink-700 bg-ink-850 p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-stone-100">{label}</span>
                  <Toggle checked={!!cfg.sources[key]} onChange={(v) => setNested('sources', { [key]: v })} />
                </div>
                <p className="mt-1 text-xs text-stone-500">{help}</p>
                {key === 'simulator' ? (
                  <div className="mt-3">
                    <label className="label">Mentions per minute (average)</label>
                    <input type="number" min={0.5} max={600} step={0.5} className="input" value={cfg.simulator_rate_per_min}
                           onChange={(e) => set({ simulator_rate_per_min: Number(e.target.value) })} />
                  </div>
                ) : collector && (
                  <div className="mt-3 space-y-0.5 text-xs">
                    <div className={collector.configured ? 'text-emerald-400' : 'text-stone-500'}>
                      {key === 'rss' ? 'No API key required'
                        : collector.configured ? 'Credentials found'
                        : collector.requires_credentials ? 'Credentials missing in backend/.env'
                        : 'No credentials – using public access'}
                    </div>
                    {collector.last_poll && <div className="text-stone-500">Last poll {timeAgo(new Date(collector.last_poll * 1000).toISOString())} · {collector.last_count} new · {collector.total_collected} total</div>}
                    {collector.last_error && <div className="text-red-400">{collector.last_error}</div>}
                  </div>
                )}
              </div>
            )
          })}
        </div>
        <button className="btn-ghost mt-4" onClick={() => action(() => api.post('/collectors/poll'), 'Polling enabled sources now')}>
          <RefreshCw size={14} /> Poll sources now
        </button>
      </Card>

      <ApiKeysCard />

      <InstagramAppCard />

      <Card title="Detection thresholds" subtitle="When the alert engine raises an alert">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {THRESHOLDS.map(([key, label, step]) => (
            <div key={key}>
              <label className="label normal-case">{label}</label>
              <input type="number" step={step} className="input" value={cfg.thresholds[key]}
                     onChange={(e) => setNested('thresholds', { [key]: Number(e.target.value) })} />
            </div>
          ))}
        </div>
      </Card>

      <Card title="Danger zone">
        <div className="flex flex-wrap gap-2">
          <button className="btn-danger" onClick={() => {
            if (confirm('Delete ALL mentions and alerts and regenerate simulated history?')) {
              action(() => api.post('/data/reset', { confirm: true, reseed: true }), (r) => `Data reset, ${r.seeded} historical mentions generated`)
            }
          }}>
            <Trash2 size={14} /> Reset data & regenerate demo history
          </button>
          <button className="btn-danger" onClick={() => {
            if (confirm('Delete ALL mentions and alerts (no demo history)?')) {
              action(() => api.post('/data/reset', { confirm: true, reseed: false }), 'All data deleted')
            }
          }}>
            <Trash2 size={14} /> Delete all data
          </button>
        </div>
      </Card>

      <div className="fixed inset-x-0 bottom-0 z-20 border-t-2 border-stone-50 bg-ink-950/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] items-center gap-3 md:px-4">
          <button className="btn-primary" onClick={save} disabled={saving}><Save size={14} /> {saving ? 'Saving…' : 'Save setup'}</button>
          <button className="btn-ghost" onClick={() => setCfg(data.config)}>Discard changes</button>
          {message && <span className="text-sm text-emerald-400">{message}</span>}
          {saveError && <span className="text-sm text-red-400">{saveError}</span>}
        </div>
      </div>
    </div>
  )
}

function ApiKeysCard() {
  const { data, reload } = useApi('/keys')
  const [values, setValues] = useState({})
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)
  if (!data) return null

  const FIELDS = [
    ['apify_token', 'Apify token (public Instagram pages)', 'password',
     'Free from console.apify.com → Settings → API & Integrations → Personal API tokens'],
    ['youtube_api_key', 'YouTube API key', 'password',
     'Free from console.cloud.google.com → APIs & Services → Library → "YouTube Data API v3" → Enable → Create credentials → API key'],
    ['reddit_client_id', 'Reddit client ID', 'password',
     'Free from reddit.com/prefs/apps → Create app → type "script"'],
    ['reddit_client_secret', 'Reddit client secret', 'password', ''],
    ['twitter_bearer_token', 'Twitter / X bearer token', 'password', 'Requires a paid X API plan'],
    ['appstore_country', 'App Store country code', 'text', 'e.g. in, us, gb'],
    ['appstore_app_id', 'App Store app ID (optional)', 'text', 'Leave empty to find the app by brand name'],
  ]

  async function save() {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      const payload = Object.fromEntries(Object.entries(values).filter(([, v]) => v !== undefined && v !== ''))
      const r = await api.put('/keys', payload)
      setMessage(`Saved: ${r.saved.join(', ')}`)
      setValues({})
      reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="API keys" subtitle="Stored in backend/.env and applied immediately – no restart needed">
      <div className="grid gap-3 md:grid-cols-2">
        {FIELDS.map(([key, label, type, help]) => (
          <div key={key}>
            <label className="label normal-case">
              {label}
              {data.configured?.[key] && <span className="ml-2 text-emerald-400">✓ saved</span>}
            </label>
            <input
              className="input"
              type={type}
              placeholder={data.configured?.[key] ? '•••••••• (replace to change)' : (key === 'appstore_country' ? data.appstore_country : '')}
              value={values[key] ?? (key === 'appstore_app_id' ? data.appstore_app_id ?? '' : '')}
              onChange={(e) => setValues({ ...values, [key]: e.target.value })}
            />
            {help && <p className="mt-1 text-[11px] text-stone-500">{help}</p>}
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button className="btn-primary" onClick={save} disabled={busy || !Object.keys(values).length}>
          <KeyRound size={14} /> {busy ? 'Saving…' : 'Save keys'}
        </button>
        {message && <span className="text-sm text-emerald-400">{message}</span>}
        {error && <span className="text-sm text-red-400">{error}</span>}
      </div>
    </Card>
  )
}

function InstagramAppCard() {
  const { data: setup, reload } = useApi('/instagram/status', { interval: 30000 })
  const [appId, setAppId] = useState('')
  const [appSecret, setAppSecret] = useState('')
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  if (!setup) return null

  const tunnel = setup.tunnel || {}
  const redirectUri = tunnel.redirect_uri || setup.redirect_uri

  async function call(key, fn) {
    setBusy(key)
    setError(null)
    try {
      await fn()
      await reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  const copy = () => {
    navigator.clipboard?.writeText(redirectUri)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <Card title="Instagram login (one-time)" subtitle="Lets dashboard users press “Continue with Instagram” on the Instagram page">
      <ErrorBox message={error} />
      <ol className="mt-1 space-y-4 text-sm text-stone-300">
        <Step n={1}>
          <div className="font-medium text-stone-100">Create a Meta app</div>
          <p className="mt-1 text-stone-400">
            Open <a className="link" href="https://developers.facebook.com/apps" target="_blank" rel="noreferrer">developers.facebook.com/apps</a> →
            <b> Create app</b> → use case <b>“Manage messaging and content on Instagram”</b> (type Business).
            Then open <b>Instagram → API setup with Instagram login</b> and copy the app ID and secret.
          </p>
        </Step>

        <Step n={2}>
          <div className="font-medium text-stone-100">Paste the keys here</div>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            <input className="input" placeholder="Instagram app ID" value={appId} onChange={(e) => setAppId(e.target.value)} />
            <input className="input" type="password" placeholder="Instagram app secret" value={appSecret} onChange={(e) => setAppSecret(e.target.value)} />
          </div>
          <div className="mt-2 flex items-center gap-3">
            <button className="btn-primary" disabled={busy === 'creds' || !appId.trim() || !appSecret.trim()}
                    onClick={() => call('creds', () => api.post('/instagram/credentials', { app_id: appId.trim(), app_secret: appSecret.trim() }))}>
              {busy === 'creds' ? <Loader2 size={14} className="animate-spin" /> : <KeyRound size={14} />} Save keys
            </button>
            {setup.app_configured && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 size={13} /> Saved to backend/.env</span>}
          </div>
        </Step>

        <Step n={3}>
          <div className="font-medium text-stone-100">Give Instagram an address it can reach</div>
          <p className="mt-1 text-stone-400">
            Meta only accepts <b>https</b> redirect URIs, which a laptop on 127.0.0.1 cannot provide.
            This starts a free Cloudflare tunnel (downloads a small helper the first time). Not needed on a server with a domain.
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {tunnel.state === 'running' ? (
              <button className="btn-ghost" disabled={busy === 'tunnel'} onClick={() => call('tunnel', () => api.post('/instagram/tunnel/stop'))}>
                {busy === 'tunnel' ? <Loader2 size={14} className="animate-spin" /> : <Power size={14} />} Stop secure address
              </button>
            ) : (
              <button className="btn-ghost" disabled={busy === 'tunnel'} onClick={() => call('tunnel', () => api.post('/instagram/tunnel/start'))}>
                {busy === 'tunnel' ? <Loader2 size={14} className="animate-spin" /> : <Globe size={14} />}
                {tunnel.binary_present ? 'Start secure address' : 'Download helper & start'}
              </button>
            )}
            {tunnel.state === 'running' && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 size={13} /> {tunnel.url}</span>}
            {tunnel.state === 'downloading' && <span className="text-xs text-stone-400">Downloading cloudflared…</span>}
            {tunnel.error && <span className="text-xs text-red-400">{tunnel.error}</span>}
          </div>
          <p className="mt-3 text-stone-400">Copy this <b>OAuth redirect URI</b> into the Meta app (Instagram → Business login settings):</p>
          <div className="mt-1.5 flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-3 py-2 font-mono text-xs text-stone-200">
            <span className="flex-1 break-all">{redirectUri}</span>
            <button className="text-stone-400 hover:text-red-400" onClick={copy}>{copied ? <CheckCircle2 size={14} /> : <Copy size={14} />}</button>
          </div>
          {tunnel.state === 'running' && (
            <p className="mt-2 text-xs text-amber-400">
              While this address is live the dashboard is reachable from the internet by anyone who knows the link.
              Stop it once accounts are connected – connected accounts keep working without it.
            </p>
          )}
        </Step>

        <Step n={4}>
          <div className="font-medium text-stone-100">Allow accounts to log in</div>
          <p className="mt-1 text-stone-400">
            A Meta app in <b>development mode</b> only accepts accounts listed as testers – any other account gets
            <b> “Insufficient developer role”</b>. Add each account under <b>App roles → Roles → Instagram tester</b>, then
            accept the invite at{' '}
            <a className="link" href="https://www.instagram.com/accounts/manage_access/" target="_blank" rel="noreferrer">
              instagram.com/accounts/manage_access
            </a>{' '}→ <b>Tester invites</b>. For everyone else, submit the app for <b>App Review</b> with
            <code className="mx-1 text-stone-200">instagram_business_basic</code> and
            <code className="mx-1 text-stone-200">instagram_business_manage_comments</code>.
          </p>
        </Step>
      </ol>
    </Card>
  )
}

function Step({ n, children }) {
  return (
    <li className="flex gap-3">
      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-stone-50 text-xs font-semibold text-ink-950">{n}</span>
      <div className="min-w-0 flex-1 pt-0.5">{children}</div>
    </li>
  )
}
