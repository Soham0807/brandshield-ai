import { AlertOctagon, HeartPulse, MessageCircle, ShieldAlert, Smile, ThumbsDown } from 'lucide-react'
import { useState } from 'react'
import { Bar, Doughnut, Line } from 'react-chartjs-2'
import { Link } from 'react-router-dom'
import MentionRow from '../components/MentionRow'
import RiskGauge from '../components/RiskGauge'
import { Card, Empty, ErrorBox, Segmented, SeverityBadge, Spinner, Stat, Tip, WINDOW_OPTIONS } from '../components/ui'
import { RISK_HELP } from '../lib/help'
import { alpha, baseScales, gridColor } from '../lib/charts'
import { cssVar } from '../lib/cssvar'
import { aspectLabel, brandTitle, chartLabel, humanizeAlert, num, SENTIMENT_COLORS, SOURCE_LABELS, timeAgo, windowLabel } from '../lib/format'
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
      <ErrorBox message={overview.error} />

      {!o ? (
        <Spinner />
      ) : (
        <>
          <section className="grid gap-6 border-b border-ink-700 pb-6 lg:grid-cols-[1fr_auto]">
            <div className="max-w-4xl">
              <div className="kicker">Brand briefing · {windowName(hours)}</div>
              <h1 className="display mt-2 text-[34px] font-semibold leading-[1.08] text-stone-50 md:text-[46px]">
                {headline(o, cur)}
              </h1>
              <p className="mt-3 max-w-3xl text-[16px] leading-relaxed text-stone-400">{o.summary}</p>
              <p className="mt-3 font-mono text-[10.5px] uppercase tracking-[.12em] text-stone-500">
                Updated {timeAgo(o.generated_at)} · {num(cur.total)} genuine mentions
                {Object.keys(o.sources).length > 0 && ' · ' + Object.entries(o.sources)
                  .sort((x, y) => y[1] - x[1]).map(([k, n]) => `${SOURCE_LABELS[k] || k} ${num(n)}`).join(' · ')}
              </p>
            </div>
            <div className="lg:pt-1"><Segmented options={WINDOW_OPTIONS} value={hours} onChange={setHours} /></div>
          </section>

          <div className="grid grid-cols-2 gap-x-6 gap-y-5 md:grid-cols-3 xl:grid-cols-6">
            <Stat icon={HeartPulse} label="Brand health" value={cur.health} delta={o.deltas.health}
                  hint="0-100, derived from the average sentiment score" />
            <Stat icon={MessageCircle} label="Mentions" value={cur.total} delta={o.deltas.total_pct} deltaSuffix="%" />
            <Stat icon={Smile} label="Positive sentiment" value={cur.positive_pct} digits={1} suffix="%"
                  delta={o.deltas.positive_pct} deltaSuffix=" pts" />
            <Stat icon={ThumbsDown} tone="red" label="Negative sentiment" value={cur.negative_pct} digits={1} suffix="%"
                  delta={o.deltas.negative_pct} deltaSuffix=" pts" invert />
            <Stat icon={AlertOctagon} label="Spam filtered" value={cur.spam} delta={o.deltas.spam_pct} deltaSuffix="%" invert />
            <Stat icon={ShieldAlert} tone={risk?.level === 'low' ? undefined : 'red'} label="Risk score"
                  value={risk?.score ?? 0} suffix="/100" />
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
              action={<Link to="/analytics" className="link text-xs">Details</Link>}>
          {risk ? (
            <div>
              <Tip block text="Overall risk from 0 to 100. Green (below 30) is normal, amber is worth watching, red (55+) means a likely PR problem. Hover over each signal below to see what it measures.">
                <RiskGauge score={risk.score} level={risk.level} />
              </Tip>
              <div className="mt-4 space-y-2">
                {Object.entries(risk.components || {}).map(([k, v]) => (
                  <Tip key={k} block text={RISK_HELP[k]} className="flex items-center gap-2 text-xs hover:bg-ink-850">
                    <span className="w-24 capitalize text-stone-400">{k}</span>
                    <div className="h-1.5 flex-1 bg-ink-800">
                      <div className="h-full bg-stone-50" style={{ width: `${Math.min(100, (v / MAX_COMPONENT[k]) * 100)}%` }} />
                    </div>
                    <span className="w-12 text-right text-stone-300">{v}<span className="text-stone-600">/{MAX_COMPONENT[k]}</span></span>
                  </Tip>
                ))}
              </div>
              {risk.drivers?.length > 0 && (
                <ul className="mt-3 space-y-1 text-xs text-stone-400">
                  {risk.drivers.map((d) => <li key={d}>• {d}</li>)}
                </ul>
              )}
              {risk.recent_mentions != null && (
                <p className="mt-3 text-[11px] text-stone-500">
                  Based on {risk.recent_mentions} mentions in {windowLabel(risk.recent_window_hours).toLowerCase()}
                </p>
              )}
            </div>
          ) : <Spinner />}
        </Card>
        <Card title="Topic insights" subtitle="What people talk about, and how they feel about it"
              action={<Link to="/aspects" className="link text-xs">All topics</Link>}>
          <div className="h-72">{o ? <AspectBars aspects={o.aspects} /> : <Spinner />}</div>
        </Card>
        <Card title="Active alerts" subtitle="AI-detected issues requiring attention"
              action={<Link to="/alerts" className="link text-xs">View all</Link>}>
          {alerts.data?.items?.length ? (
            <div>
              {alerts.data.items.map((a) => (
                <Link to="/alerts" key={a.id} className="block border-b border-ink-700 py-3 first:pt-0 last:border-0 hover:bg-ink-850">
                  <div className="flex items-center justify-between">
                    <SeverityBadge severity={a.severity} />
                    <span className="text-[11px] text-stone-500">{timeAgo(a.created_at)}</span>
                  </div>
                  <p className="display mt-1.5 text-[15px] font-semibold text-stone-50">{a.title}</p>
                  <p className="mt-0.5 line-clamp-2 text-xs text-stone-400">{humanizeAlert(a.message)}</p>
                </Link>
              ))}
            </div>
          ) : alerts.data ? <Empty>No open alerts. All quiet.</Empty> : <Spinner />}
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Live mention feed" subtitle="Streaming in real time" className="xl:col-span-2" bodyClass="pt-2"
              action={<Link to="/mentions" className="link text-xs">Explore</Link>}>
          {feed.data ? (
            feed.data.items.length ? (
              <div className="max-h-[520px] overflow-y-auto">
                {feed.data.items.map((m) => <MentionRow key={m.id} mention={m} fresh={fresh.has(m.id)} />)}
              </div>
            ) : <Empty>No mentions yet.</Empty>
          ) : <Spinner />}
        </Card>
        <Card title="Trending words" subtitle="Words that come up most in praise and complaints">
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
                        <span className="text-stone-400">{SOURCE_LABELS[s] || s}</span>
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

function windowName(hours) {
  return { 6: 'last 6 hours', 24: 'last 24 hours', 72: 'last 3 days', 168: 'last 7 days', 720: 'last 30 days' }[hours] || `last ${hours} hours`
}

/** One-line front-page headline written from the numbers. */
function headline(o, cur) {
  const brand = brandTitle(o.brand_name) || 'The brand'
  if (!cur?.total) return `No conversation about ${brand} yet`
  const worst = [...(o.aspects || [])].filter((a) => a.negative >= 3).sort((a, b) => b.negative - a.negative)[0]
  const topic = worst ? aspectLabel(worst.aspect).toLowerCase() : null
  if (cur.negative_pct >= 45) return topic ? `${brand} under fire over ${topic}` : `${brand} faces a wave of criticism`
  if (cur.positive_pct >= 55) return topic ? `Fans warm to ${brand}, but ${topic} draws complaints` : `${brand} is winning over its audience`
  return topic ? `Mixed reactions to ${brand}; ${topic} draws the most complaints` : `Mixed reactions to ${brand}`
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
    backgroundColor: alpha(SENTIMENT_COLORS[key], key === 'neutral' ? 0.35 : 0.22),
    fill: true,
    pointRadius: 0,
    borderWidth: 1.5,
  }))
  datasets.push({
    type: 'bar',
    label: 'Anomaly',
    data: data.points.map((p) => (p.anomaly ? anomalyMax : null)),
    backgroundColor: 'rgba(210, 56, 30, 0.10)',
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
          data={{ labels: items.map((i) => i.label), datasets: [{ data: items.map((i) => i.value), backgroundColor: items.map((i) => i.color), borderWidth: 2, borderColor: cssVar('--color-ink-900', '#fbf9f4') }] }}
          options={{ cutout: '74%', plugins: { legend: { display: false } } }}
        />
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="num text-4xl font-medium text-stone-50">{cur.positive_pct}%</span>
          <span className="font-mono text-[10px] uppercase tracking-[.14em] text-stone-500">Positive</span>
        </div>
      </div>
      <div className="mt-4 space-y-2">
        {items.map((i) => (
          <div key={i.label} className="flex items-center gap-2 text-sm">
            <span className="size-2.5" style={{ background: i.color }} />
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
  if (!aspects?.length) return <Empty>No topics detected yet.</Empty>
  const top = aspects.slice(0, 8)
  return (
    <Bar
      data={{
        labels: top.map((a) => aspectLabel(a.aspect)),
        datasets: ['positive', 'neutral', 'negative'].map((key) => ({
          label: key[0].toUpperCase() + key.slice(1),
          data: top.map((a) => a[key]),
          backgroundColor: SENTIMENT_COLORS[key],
          barThickness: 12,
        })),
      }}
      options={{
        indexAxis: 'y',
        scales: {
          x: { stacked: true, grid: { color: gridColor }, border: { display: false } },
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
  const cls = color === 'red' ? 'border-red-500/30 bg-red-500/[0.05] text-red-400' : 'border-emerald-500/30 bg-emerald-500/[0.05] text-emerald-400'
  return (
    <div>
      <div className="label">{title}</div>
      <div className="flex flex-wrap gap-1.5">
        {words.map((w) => (
          <span key={w.word} className={`border px-2 py-0.5 ${cls}`}
                style={{ fontSize: `${11 + (4 * w.count) / max}px`, opacity: 0.55 + (0.45 * w.count) / max }}>
            {w.word} <span className="text-[10px] opacity-60">{w.count}</span>
          </span>
        ))}
      </div>
    </div>
  )
}
