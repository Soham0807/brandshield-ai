import { Plus, Save, Send, ServerCog, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Accounts from '../components/Accounts'
import { Card, ErrorBox, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { aspectLabel } from '../lib/format'
import { useApi } from '../lib/hooks'
import { useTheme } from '../lib/theme'
import { Segmented } from '../components/ui'

const CHANNELS = { email: 'Email', slack: 'Slack', teams: 'Microsoft Teams', sms: 'SMS' }

export default function SettingsPage() {
  const { data, error, reload } = useApi('/settings')
  const presets = useApi('/settings/topic-presets')
  const theme = useTheme()
  const [cfg, setCfg] = useState(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [saveError, setSaveError] = useState(null)

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
      // only the fields owned by this page; sources and thresholds live in Server setup
      const r = await api.put('/settings', {
        brand_name: cfg.brand_name,
        keywords: cfg.keywords,
        notifications: cfg.notifications,
        aspects: cfg.aspects,
      })
      setCfg(r.config)
      setMessage('Settings saved')
      reload()
    } catch (e) {
      setSaveError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function sendTest() {
    setSaveError(null)
    setMessage(null)
    try {
      const r = await api.post('/alerts/test')
      const sent = Object.entries(r.delivery).filter(([, v]) => v === 'sent').map(([k]) => CHANNELS[k])
      setMessage(sent.length ? `Test alert sent to the dashboard and ${sent.join(', ')}` : 'Test alert sent to the dashboard')
    } catch (e) {
      setSaveError(e.message)
    }
  }

  return (
    <div className="space-y-5 pb-20">
      <div>
        <h1 className="display text-[30px] font-semibold leading-tight text-stone-50">Settings</h1>
        <p className="text-sm text-stone-500">Which brand to watch, the topics you care about, and where alerts go</p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Brand">
          <label className="label">Brand name</label>
          <input className="input" value={cfg.brand_name} onChange={(e) => set({ brand_name: e.target.value })} />
          <label className="label mt-4">Keywords / handles to track</label>
          <TagInput values={cfg.keywords} onChange={(keywords) => set({ keywords })} placeholder="Add keyword and press Enter" />
          <p className="mt-2 text-xs text-stone-500">Adding a YouTube channel or Instagram account updates these automatically.</p>
        </Card>

        <Card title="Alert notifications" subtitle="Alerts always appear on the dashboard; choose where else they go">
          <div className="space-y-2">
            {Object.entries(CHANNELS).map(([ch, label]) => {
              const available = data?.channels?.[ch]
              return (
                <div key={ch} className="flex items-center justify-between rounded-lg border border-ink-700 bg-ink-850 px-3 py-2.5">
                  <div>
                    <div className="text-sm text-stone-100">{label}</div>
                    <div className={`text-xs ${available ? 'text-emerald-400' : 'text-stone-500'}`}>
                      {available ? 'Available' : 'Not available on this installation'}
                    </div>
                  </div>
                  <Toggle checked={!!cfg.notifications[ch]} disabled={!available}
                          onChange={(v) => setNested('notifications', { [ch]: v })} />
                </div>
              )
            })}
            <div className="flex items-end gap-3 pt-2">
              <div className="flex-1">
                <label className="label">Only send alerts that are at least</label>
                <select className="input" value={cfg.notifications.min_severity}
                        onChange={(e) => setNested('notifications', { min_severity: e.target.value })}>
                  {['low', 'medium', 'high', 'critical'].map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
                </select>
              </div>
              <button className="btn-ghost" onClick={sendTest}><Send size={14} /> Send test alert</button>
            </div>
          </div>
        </Card>
      </div>

      <Accounts />

      <Card title="Appearance" subtitle="Paper for daylight, the night edition for dark rooms. Saved in this browser.">
        <Segmented
          options={[{ value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }, { value: 'system', label: 'Match system' }]}
          value={theme.choice} onChange={theme.setChoice} tip="Colour theme for this browser" />
      </Card>

      <Card title="Topics" subtitle="Words that link a comment to a topic, so you can see sentiment per topic (any language). Saving re-tags the last 30 days of comments."
            action={presets.data && (
              <select className="input w-auto py-1.5 text-xs" value=""
                      onChange={(e) => {
                        const preset = presets.data.presets.find((x) => x.id === e.target.value)
                        if (preset) set({ aspects: preset.aspects })
                      }}>
                <option value="">Load a preset…</option>
                {presets.data.presets.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
              </select>
            )}>
        <AspectEditor aspects={cfg.aspects} onChange={(aspects) => set({ aspects })} />
      </Card>

      <p className="flex items-center gap-1.5 text-xs text-stone-500">
        <ServerCog size={13} /> Running this BrandShield installation?
        <Link to="/setup" className="link">Open server setup</Link>
        for API keys, data sources, detection thresholds and demo tools.
      </p>

      <div className="fixed inset-x-0 bottom-0 z-20 border-t-2 border-stone-50 bg-ink-950/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] items-center gap-3 md:px-4">
          <button className="btn-primary" onClick={save} disabled={saving}><Save size={14} /> {saving ? 'Saving…' : 'Save settings'}</button>
          <button className="btn-ghost" onClick={() => setCfg(data.config)}>Discard changes</button>
          {message && <span className="text-sm text-emerald-400">{message}</span>}
          {saveError && <span className="text-sm text-red-400">{saveError}</span>}
        </div>
      </div>
    </div>
  )
}

export function Toggle({ checked, onChange, disabled = false }) {
  return (
    <button type="button" role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)}
            className={`relative h-5 w-9 rounded-full transition disabled:opacity-40 ${checked ? 'bg-stone-50' : 'bg-ink-600'}`}>
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
              <button className="text-stone-500 hover:text-red-300" title="Remove topic"
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
        <input className="input" placeholder="New topic (e.g. parking)" value={name} onChange={(e) => setName(e.target.value)} />
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
