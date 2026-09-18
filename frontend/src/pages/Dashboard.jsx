import { AlertOctagon, HeartPulse, MessageCircle, ShieldAlert, Smile, Sparkles, ThumbsDown } from 'lucide-react'
import { useState } from 'react'
import { Bar, Doughnut, Line } from 'react-chartjs-2'
import { Link } from 'react-router-dom'
import MentionRow from '../components/MentionRow'
import RiskGauge from '../components/RiskGauge'
import { Card, Empty, ErrorBox, Segmented, SeverityBadge, Spinner, Stat, WINDOW_OPTIONS } from '../components/ui'
import { alpha, baseScales } from '../lib/charts'
import { aspectLabel, chartLabel, num, SENTIMENT_COLORS, timeAgo } from '../lib/format'
import { useApi, useThrottle } from '../lib/hooks'
import { useLive, useLiveEvent } from '../lib/live'

export default function Dashboard() {
  const [hours, setHours] = useState(24)
  const { risk: liveRisk } = useLive()
  const overview = useApi(`/overview?hours=${hours}`, { interval: 30000 })
  const trends = useApi(`/trends?hours=${hours}`, { interval: 60000 })
  const alerts = useApi('/alerts?status=open&limit=4')
  const feed = useApi('/mentions?limit=12')
  const [fresh, setFresh] = useState(new Set())

  const refreshAggregates = useThrottle(() => {
    overview.reload()
    trends.reload()
  }, 10000)

  useLiveEvent('mentions', (items) => {
    feed.setData((prev) => {
      const existing = prev?.items || []
      const ids = new Set(existing.map((m) => m.id))
      const incoming = items.filter((m) => !ids.has(m.id))
      if (!incoming.length) return prev
      setFresh(new Set(incoming.map((m) => m.id)))
      const merged = [...incoming, ...existing]
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .slice(0, 12)
      return { total: (prev?.total || 0) + incoming.length, items: merged }
    })
    refreshAggregates()
  })
  useLiveEvent('alert', () => alerts.reload())
  useLiveEvent('alert_updated', () => alerts.reload())
  useLiveEvent('refresh', () => {
    overview.reload()
    trends.reload()
    feed.reload()
    alerts.reload()
  })

  const o = overview.data
  const cur = o?.current
  const risk = liveRisk || o?.risk

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-stone-50">{o?.brand_name || 'Brand'} — Brand Overview</h1>
          <p className="text-sm text-stone-500">AI-powered real-time social media monitoring and sentiment analysis</p>
        </div>
        <Segmented options={WINDOW_OPTIONS} value={hours} onChange={setHours} />
      </div>

      <ErrorBox message={overview.error} />

      {!o ? (
        <Spinner />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Stat icon={HeartPulse} tone="green" label="Brand health" value={cur.health ?? '–'} delta={o.deltas.health}
                  hint="0-100, derived from the average sentiment score" />
            <Stat icon={MessageCircle} tone="violet" label="Mentions" value={num(cur.total)} delta={o.deltas.total_pct} deltaSuffix="%" />
            <Stat icon={Smile} tone="green" label="Positive sentiment" value={`${cur.positive_pct}%`} delta={o.deltas.positive_pct} deltaSuffix=" pts" />
            <Stat icon={ThumbsDown} tone="red" label="Negative sentiment" value={`${cur.negative_pct}%`} delta={o.deltas.negative_pct} deltaSuffix=" pts" invert />
            <Stat icon={AlertOctagon} tone="orange" label="Spam filtered" value={num(cur.spam)} delta={o.deltas.spam_pct} deltaSuffix="%" invert />
            <Stat icon={ShieldAlert} tone={risk?.level === 'low' ? 'sky' : 'red'} label="Risk score"
                  value={`${risk?.score ?? 0}/100`} />
          </div>

          <div className="card flex gap-3 border-amber-500/20 bg-gradient-to-r from-amber-500/[0.07] to-transparent p-4">
            <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-amber-500/15 text-amber-400">
              <Sparkles size={16} />
            </span>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-amber-400">AI Summary</div>
              <p className="mt-1 text-sm leading-relaxed text-stone-300">{o.summary}</p>
            </div>
          </div>
        </>
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Sentiment over time" subtitle="Mentions per interval, anomalies highlighted" className="xl:col-span-2">
          <div className="h-72">
            {trends.data ? <SentimentTrend data={trends.data} hours={hours} /> : <Spinner />}
          </div>
        </Card>
        <Card title="Sentiment distribution" subtitle="Across genuine mentions (spam excluded)">
          {cur ? <Distribution cur={cur} /> : <Spinner />}
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Brand risk" subtitle="Sentiment + anomaly + forecast signals"
              action={<Link to="/analytics" className="text-xs text-amber-400 hover:underline">Details</Link>}>
          {risk ? (
            <div>
              <RiskGauge score={risk.score} level={risk.level} />
              <div className="mt-4 space-y-2">
                {Object.entries(risk.components || {}).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2 text-xs">
                    <span className="w-24 capitalize text-stone-400">{k}</span>
                    <div className="h-1.5 flex-1 rounded-full bg-ink-700">
                      <div className="h-full rounded-full bg-amber-500" style={{ width: `${Math.min(100, (v / MAX_COMPONENT[k]) * 100)}%` }} />
                    </div>
                    <span className="w-8 text-right text-stone-300">{v}</span>
                  </div>
                ))}
              </div>
              {risk.drivers?.length > 0 && (
                <ul className="mt-3 space-y-1 text-xs text-stone-400">
                  {risk.drivers.map((d) => <li key={d}>• {d}</li>)}
                </ul>
              )}
            </div>
          ) : <Spinner />}
        </Card>
        <Card title="Aspect insights" subtitle="What people talk about"
              action={<Link to="/aspects" className="text-xs text-amber-400 hover:underline">All aspects</Link>}>
          <div className="h-72">{o ? <AspectBars aspects={o.aspects} /> : <Spinner />}</div>
        </Card>
        <Card title="Active alerts" subtitle="AI-detected issues requiring attention"
              action={<Link to="/alerts" className="text-xs text-amber-400 hover:underline">View all</Link>}>
          {alerts.data?.items?.length ? (
            <div className="space-y-2.5">
              {alerts.data.items.map((a) => (
                <Link to="/alerts" key={a.id} className="block rounded-xl border border-ink-700 bg-ink-850 p-3 hover:border-ink-600">
                  <div className="flex items-center justify-between">
                    <SeverityBadge severity={a.severity} />
                    <span className="text-[11px] text-stone-500">{timeAgo(a.created_at)}</span>
                  </div>
                  <p className="mt-1.5 text-sm font-medium text-stone-100">{a.title}</p>
                  <p className="mt-0.5 line-clamp-2 text-xs text-stone-400">{a.message}</p>
                </Link>
              ))}
            </div>
          ) : alerts.data ? <Empty>No open alerts. All quiet 🎉</Empty> : <Spinner />}
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Live mention feed" subtitle="Streaming in real time" className="xl:col-span-2" bodyClass="pt-2"
              action={<Link to="/mentions" className="text-xs text-amber-400 hover:underline">Explore</Link>}>
          {feed.data ? (
            feed.data.items.length ? (
              <div className="max-h-[520px] overflow-y-auto">
                {feed.data.items.map((m) => <MentionRow key={m.id} mention={m} fresh={fresh.has(m.id)} />)}
              </div>
            ) : <Empty>No mentions yet.</Empty>
          ) : <Spinner />}
        </Card>
        <Card title="Trending words" subtitle="Most frequent terms (after lemmatization)">
          {o ? (
            <div className="space-y-4">
              <KeywordCloud title="In complaints" words={o.negative_keywords} color="red" />
              <KeywordCloud title="In praise" words={o.positive_keywords} color="green" />
              {Object.keys(o.sources).length > 0 && (
                <div>
                  <div className="label">Sources</div>
                  <div className="space-y-1.5">
                    {Object.entries(o.sources).map(([s, n]) => (
                      <div key={s} className="flex justify-between text-xs">
                        <span className="text-stone-400">{s}</span>
                        <span className="text-stone-200">{num(n)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : <Spinner />}
        </Card>
      </div>
    </div>
  )
}

const MAX_COMPONENT = { negativity: 35, velocity: 20, anomaly: 25, forecast: 10, concentration: 10 }

function SentimentTrend({ data, hours }) {
  const labels = data.points.map((p) => chartLabel(p.t, hours))
  const anomalyMax = Math.max(1, ...data.points.map((p) => p.total))
  const datasets = [
    { key: 'positive', label: 'Positive' },
    { key: 'neutral', label: 'Neutral' },
    { key: 'negative', label: 'Negative' },
  ].map(({ key, label }) => ({
    label,
    data: data.points.map((p) => p[key]),
    borderColor: SENTIMENT_COLORS[key],
    backgroundColor: alpha(SENTIMENT_COLORS[key], 0.25),
    fill: true,
    tension: 0.35,
    pointRadius: 0,
    borderWidth: 1.5,
  }))
  datasets.push({
    type: 'bar',
    label: 'Anomaly',
    data: data.points.map((p) => (p.anomaly ? anomalyMax : null)),
    backgroundColor: 'rgba(239, 68, 68, 0.12)',
    borderWidth: 0,
    barPercentage: 1,
    categoryPercentage: 1,
    stack: 'anomaly',
  })
  return (
    <Line
      data={{ labels, datasets }}
      options={{
        interaction: { mode: 'index', intersect: false },
        scales: { ...baseScales(), y: { ...baseScales().y, stacked: true, beginAtZero: true } },
        plugins: { legend: { position: 'top', align: 'end' } },
      }}
    />
  )
}

function Distribution({ cur }) {
  const items = [
    { label: 'Positive', value: cur.positive, color: SENTIMENT_COLORS.positive },
    { label: 'Neutral', value: cur.neutral, color: SENTIMENT_COLORS.neutral },
    { label: 'Negative', value: cur.negative, color: SENTIMENT_COLORS.negative },
    { label: 'Spam', value: cur.spam, color: SENTIMENT_COLORS.spam },
  ]
  const total = items.reduce((a, b) => a + b.value, 0) || 1
  return (
    <div>
      <div className="relative mx-auto h-52 w-52">
        <Doughnut
          data={{ labels: items.map((i) => i.label), datasets: [{ data: items.map((i) => i.value), backgroundColor: items.map((i) => i.color), borderWidth: 0, spacing: 2 }] }}
          options={{ cutout: '72%', plugins: { legend: { display: false } } }}
        />
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-semibold text-stone-50">{cur.positive_pct}%</span>
          <span className="text-xs text-stone-500">Positive</span>
        </div>
      </div>
      <div className="mt-4 space-y-2">
        {items.map((i) => (
          <div key={i.label} className="flex items-center gap-2 text-sm">
            <span className="size-2.5 rounded-sm" style={{ background: i.color }} />
            <span className="flex-1 text-stone-300">{i.label}</span>
            <span className="text-stone-500">{num(i.value)}</span>
            <span className="w-12 text-right font-medium text-stone-200">{((100 * i.value) / total).toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function AspectBars({ aspects }) {
  if (!aspects?.length) return <Empty>No aspects detected yet.</Empty>
  const top = aspects.slice(0, 8)
  return (
    <Bar
      data={{
        labels: top.map((a) => aspectLabel(a.aspect)),
        datasets: ['positive', 'neutral', 'negative'].map((key) => ({
          label: key[0].toUpperCase() + key.slice(1),
          data: top.map((a) => a[key]),
          backgroundColor: SENTIMENT_COLORS[key],
          borderRadius: 3,
          barThickness: 14,
        })),
      }}
      options={{
        indexAxis: 'y',
        scales: {
          x: { stacked: true, grid: { color: 'rgba(120,104,94,.14)' }, border: { display: false } },
          y: { stacked: true, grid: { display: false } },
        },
        plugins: { legend: { display: false } },
      }}
    />
  )
}

function KeywordCloud({ title, words, color }) {
  if (!words?.length) return null
  const max = Math.max(...words.map((w) => w.count))
  const cls = color === 'red' ? 'border-red-500/25 bg-red-500/[0.07] text-red-300' : 'border-emerald-500/25 bg-emerald-500/[0.07] text-emerald-300'
  return (
    <div>
      <div className="label">{title}</div>
      <div className="flex flex-wrap gap-1.5">
        {words.map((w) => (
          <span key={w.word} className={`rounded-md border px-2 py-0.5 ${cls}`}
                style={{ fontSize: `${11 + (4 * w.count) / max}px`, opacity: 0.55 + (0.45 * w.count) / max }}>
            {w.word} <span className="text-[10px] opacity-60">{w.count}</span>
          </span>
        ))}
      </div>
    </div>
  )
}
