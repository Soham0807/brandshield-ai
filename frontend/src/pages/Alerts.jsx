import { BellRing, Check, RotateCcw, Search, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, Empty, ErrorBox, Segmented, SeverityBadge, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { formatTime, SEVERITY_STYLES, timeAgo } from '../lib/format'
import { useApi } from '../lib/hooks'
import { useLiveEvent } from '../lib/live'

const INVESTIGATE = {
  aspect_surge: (a) => `/mentions?aspect=${a.meta?.aspect}&sentiment=negative&hours=2`,
  negative_spike: () => '/mentions?sentiment=negative&hours=2',
  negative_ratio: () => '/mentions?sentiment=negative&hours=1',
  risk_threshold: () => '/analytics',
  forecast_decline: () => '/analytics',
  spam_wave: () => '/mentions?spam=true&hours=1',
  viral_negative: () => '/mentions?sentiment=negative&sort=engagement&hours=6',
}

export default function Alerts() {
  const [status, setStatus] = useState('open')
  const { data, error, reload } = useApi(`/alerts?limit=200${status ? `&status=${status}` : ''}`)
  const [actionError, setActionError] = useState(null)
  const [permission, setPermission] = useState(typeof Notification !== 'undefined' ? Notification.permission : 'unsupported')
  useLiveEvent('alert', reload)
  useLiveEvent('alert_updated', reload)

  async function act(id, action) {
    try {
      setActionError(null)
      await api.post(`/alerts/${id}/${action}`)
      reload()
    } catch (e) {
      setActionError(e.message)
    }
  }

  const counts = data?.open_counts || {}

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-stone-50">Alerts</h1>
          <p className="text-sm text-stone-500">AI-detected issues requiring your attention</p>
        </div>
        <div className="flex gap-2">
          {permission === 'default' && (
            <button className="btn-ghost" onClick={async () => setPermission(await Notification.requestPermission())}>
              <BellRing size={14} /> Enable browser notifications
            </button>
          )}
          <Segmented value={status} onChange={setStatus}
                     options={[{ value: 'open', label: 'Open' }, { value: 'acknowledged', label: 'Acknowledged' }, { value: 'dismissed', label: 'Dismissed' }, { value: '', label: 'All' }]} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {['critical', 'high', 'medium', 'low'].map((s) => (
          <div key={s} className={`card flex items-center gap-3 p-4 ${counts[s] ? SEVERITY_STYLES[s].border : ''}`}>
            <span className={`size-2.5 rounded-full ${SEVERITY_STYLES[s].dot}`} />
            <div>
              <div className="text-2xl font-semibold text-stone-50">{counts[s] || 0}</div>
              <div className={`text-xs font-semibold uppercase ${SEVERITY_STYLES[s].text}`}>{s}</div>
            </div>
          </div>
        ))}
      </div>

      <ErrorBox message={error || actionError} />

      <Card bodyClass="p-3">
        {!data ? <Spinner /> : !data.items.length ? <Empty>No alerts here.</Empty> : (
          <div className="space-y-2">
            {data.items.map((a) => (
              <div key={a.id} className="rounded-xl border border-ink-700 bg-ink-850 p-4">
                <div className="flex flex-wrap items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={a.severity} />
                      <span className="rounded bg-ink-700 px-1.5 py-0.5 text-[10px] uppercase text-stone-400">{a.type.replace(/_/g, ' ')}</span>
                      <span className="text-xs text-stone-500" title={formatTime(a.created_at, true)}>{timeAgo(a.created_at)}</span>
                      {a.status !== 'open' && <span className="text-xs capitalize text-stone-500">· {a.status}</span>}
                    </div>
                    <h3 className="mt-2 font-medium text-stone-100">{a.title}</h3>
                    <p className="mt-1 text-sm text-stone-400">{a.message}</p>
                    {a.meta?.delivery && (
                      <p className="mt-1 text-xs text-stone-500">
                        Delivered: {Object.entries(a.meta.delivery).map(([k, v]) => `${k} (${v})`).join(', ')}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {INVESTIGATE[a.type] && (
                      <Link to={INVESTIGATE[a.type](a)} className="btn-ghost"><Search size={13} /> Investigate</Link>
                    )}
                    {a.status === 'open' ? (
                      <>
                        <button className="btn-ghost" onClick={() => act(a.id, 'acknowledge')} title="Acknowledge"><Check size={14} /></button>
                        <button className="btn-ghost" onClick={() => act(a.id, 'dismiss')} title="Dismiss"><X size={14} /></button>
                      </>
                    ) : (
                      <button className="btn-ghost" onClick={() => act(a.id, 'reopen')} title="Reopen"><RotateCcw size={14} /></button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
