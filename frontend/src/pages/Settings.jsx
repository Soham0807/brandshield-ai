import { Flame, KeyRound, Plus, RefreshCw, Save, Send, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Card, ErrorBox, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { aspectLabel, timeAgo } from '../lib/format'
import { useApi } from '../lib/hooks'
import { useLive } from '../lib/live'

const SOURCE_INFO = {
  simulator: ['Live simulator', 'Realistic synthetic stream (Instagram, Twitter, Reddit, Google reviews) with crisis injection'],
  reddit: ['Reddit', 'Search API – needs free REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET (public access is blocked by Reddit)'],
  rss: ['News / RSS', 'Google News search for your brand + custom RSS_FEEDS'],
  twitter: ['Twitter / X', 'API v2 recent search – needs a paid TWITTER_BEARER_TOKEN'],
  youtube: ['YouTube', 'Comments on videos about ANY brand – needs a free YouTube API key'],
  appstore: ['App Store reviews', 'iOS reviews of ANY brand’s app – no key needed, star ratings included'],
  instagram: ['Instagram', 'Comments on posts of accounts connected with Instagram login (Instagram page)'],
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

export default function SettingsPage() {
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
      const r = await api.put('/settings', cfg)
      setCfg(r.config)
      setMessage('Settings saved')
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
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-stone-50">Settings</h1>
          <p className="text-sm text-stone-500">Brand, data sources, aspects, thresholds and notifications</p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Brand">
          <label className="label">Brand name</label>
          <input className="input" value={cfg.brand_name} onChange={(e) => set({ brand_name: e.target.value })} />
          <label className="label mt-4">Keywords / handles to track</label>
          <TagInput values={cfg.keywords} onChange={(keywords) => set({ keywords })} placeholder="Add keyword and press Enter" />
        </Card>

        <Card title="Crisis simulation" subtitle="Inject a burst of complaints to demo anomaly detection and alerts">
          {!cfg.sources.simulator && <p className="mb-3 text-xs text-amber-300">Enable the live simulator source to use this.</p>}
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="label">Aspect</label>
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
      </div>

      <Card title="Data sources" subtitle="API credentials are read from backend/.env">
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

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Alert thresholds">
          <div className="grid gap-3 sm:grid-cols-2">
            {THRESHOLDS.map(([key, label, step]) => (
              <div key={key}>
                <label className="label normal-case">{label}</label>
                <input type="number" step={step} className="input" value={cfg.thresholds[key]}
                       onChange={(e) => setNested('thresholds', { [key]: Number(e.target.value) })} />
              </div>
            ))}
          </div>
        </Card>

        <Card title="Notifications" subtitle="Dashboard + browser alerts are always on">
          <div className="space-y-2">
            {['email', 'slack', 'teams', 'sms'].map((ch) => (
              <div key={ch} className="flex items-center justify-between rounded-lg border border-ink-700 bg-ink-850 px-3 py-2.5">
                <div>
                  <div className="text-sm capitalize text-stone-100">{ch === 'sms' ? 'SMS (Twilio)' : ch}</div>
                  <div className={`text-xs ${data?.channels?.[ch] ? 'text-emerald-400' : 'text-stone-500'}`}>
                    {data?.channels?.[ch] ? 'Configured' : 'Not configured in .env'}
                  </div>
                </div>
                <Toggle checked={!!cfg.notifications[ch]} onChange={(v) => setNested('notifications', { [ch]: v })} />
              </div>
            ))}
            <div className="flex items-end gap-3 pt-2">
              <div className="flex-1">
                <label className="label">Minimum severity to send</label>
                <select className="input" value={cfg.notifications.min_severity}
                        onChange={(e) => setNested('notifications', { min_severity: e.target.value })}>
                  {['low', 'medium', 'high', 'critical'].map((s) => <option key={s}>{s}</option>)}
                </select>
              </div>
              <button className="btn-ghost" onClick={() => action(() => api.post('/alerts/test'),
                (r) => `Test alert sent${Object.keys(r.delivery).length ? `: ${JSON.stringify(r.delivery)}` : ' to the dashboard (no external channel configured)'}`)}>
                <Send size={14} /> Send test
              </button>
            </div>
          </div>
        </Card>
      </div>

      <Card title="Aspects" subtitle="Keywords used for aspect-based sentiment analysis (whole-word match, any language)">
        <AspectEditor aspects={cfg.aspects} onChange={(aspects) => set({ aspects })} />
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

      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-ink-700 bg-ink-950/90 px-4 py-3 backdrop-blur md:left-60">
        <div className="mx-auto flex max-w-[1500px] items-center gap-3 md:px-4">
          <button className="btn-primary" onClick={save} disabled={saving}><Save size={14} /> {saving ? 'Saving…' : 'Save settings'}</button>
          <button className="btn-ghost" onClick={() => setCfg(data.config)}>Discard changes</button>
          {message && <span className="text-sm text-emerald-400">{message}</span>}
          {saveError && <span className="text-sm text-red-400">{saveError}</span>}
        </div>
      </div>
    </div>
  )
}

function Toggle({ checked, onChange }) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
            className={`relative h-5 w-9 rounded-full transition ${checked ? 'bg-amber-500' : 'bg-ink-600'}`}>
      <span className={`absolute top-0.5 size-4 rounded-full bg-white transition-all ${checked ? 'left-[18px]' : 'left-0.5'}`} />
    </button>
  )
}

function TagInput({ values, onChange, placeholder }) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const v = draft.trim()
    if (v && !values.includes(v)) onChange([...values, v])
    setDraft('')
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 p-2">
      {values.map((v) => (
        <span key={v} className="flex items-center gap-1 rounded-md bg-ink-700 px-2 py-0.5 text-xs text-stone-200">
          {v}
          <button onClick={() => onChange(values.filter((x) => x !== v))} className="text-stone-400 hover:text-red-300"><X size={11} /></button>
        </span>
      ))}
      <input
        className="min-w-32 flex-1 bg-transparent px-1 text-sm outline-none placeholder:text-stone-600"
        value={draft}
        placeholder={placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault()
            add()
          }
        }}
        onBlur={add}
      />
    </div>
  )
}

function AspectEditor({ aspects, onChange }) {
  const [name, setName] = useState('')
  return (
    <div>
      <div className="grid gap-3 md:grid-cols-2">
        {Object.entries(aspects).map(([aspect, words]) => (
          <div key={aspect} className="rounded-xl border border-ink-700 bg-ink-850 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-stone-100">{aspectLabel(aspect)}</span>
              <button className="text-stone-500 hover:text-red-300" title="Remove aspect"
                      onClick={() => {
                        const next = { ...aspects }
                        delete next[aspect]
                        onChange(next)
                      }}>
                <Trash2 size={13} />
              </button>
            </div>
            <TagInput values={words} onChange={(w) => onChange({ ...aspects, [aspect]: w })} placeholder="keyword…" />
          </div>
        ))}
      </div>
      <div className="mt-3 flex max-w-sm gap-2">
        <input className="input" placeholder="New aspect name (e.g. parking)" value={name} onChange={(e) => setName(e.target.value)} />
        <button className="btn-ghost" onClick={() => {
          const key = name.trim().toLowerCase().replace(/\s+/g, '_')
          if (key && !aspects[key]) onChange({ ...aspects, [key]: [name.trim().toLowerCase()] })
          setName('')
        }}>
          <Plus size={14} /> Add
        </button>
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
