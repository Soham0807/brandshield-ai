import { useState } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import { Card, Empty, Segmented, Spinner } from '../components/ui'
import { alpha, baseScales } from '../lib/charts'
import { chartLabel, formatTime, num, RISK_COLORS, SENTIMENT_COLORS } from '../lib/format'
import { useApi } from '../lib/hooks'
import { useLiveEvent } from '../lib/live'

export default function Analytics() {
  const [hours, setHours] = useState(24)
  const [target, setTarget] = useState('sentiment')
  const anomalies = useApi(`/anomalies?hours=${hours}`, { interval: 30000 })
  const forecast = useApi('/forecast', { interval: 120000 })
  const risk = useApi('/risk', { interval: 30000 })
  const overview = useApi(`/overview?hours=${hours}`, { interval: 60000 })
  useLiveEvent('refresh', () => {
    anomalies.reload()
    forecast.reload()
    risk.reload()
  })

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-stone-50">Trends, Anomalies & Forecast</h1>
          <p className="text-sm text-stone-500">Isolation Forest crisis detection and Prophet time-series forecasting</p>
        </div>
        <Segmented options={[{ value: 6, label: '6h' }, { value: 24, label: '24h' }, { value: 48, label: '48h' }, { value: 72, label: '3d' }]}
                   value={hours} onChange={setHours} />
      </div>

      <Card title="Anomaly detection"
            subtitle={`Negative mentions per ${anomalies.data?.bucket_minutes || 15} min · red points = anomalies flagged by Isolation Forest + adaptive z-score threshold`}>
        <div className="h-80">{anomalies.data ? <AnomalyChart data={anomalies.data} hours={hours} /> : <Spinner />}</div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Detected incidents" subtitle="Consecutive anomalous intervals merged">
          {anomalies.data?.incidents?.length ? (
            <div className="space-y-2">
              {[...anomalies.data.incidents].reverse().map((i) => (
                <div key={i.start} className="rounded-xl border border-red-500/25 bg-red-500/[0.06] p-3 text-sm">
                  <div className="font-medium text-red-200">{formatTime(i.start, true)} → {formatTime(i.end)}</div>
                  <div className="mt-1 grid grid-cols-3 gap-2 text-xs text-stone-400">
                    <span><b className="text-stone-200">{i.negative}</b> negatives</span>
                    <span>peak <b className="text-stone-200">{(i.peak_neg_ratio * 100).toFixed(0)}%</b> neg</span>
                    <span>score <b className="text-stone-200">{i.peak_score.toFixed(2)}</b></span>
                  </div>
                </div>
              ))}
            </div>
          ) : anomalies.data ? <Empty>No incidents in this window.</Empty> : <Spinner />}
        </Card>

        <Card title="Risk breakdown" subtitle={risk.data?.computed_at ? `Updated ${formatTime(risk.data.computed_at)}` : ''}>
          {risk.data ? (
            <div>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-semibold" style={{ color: RISK_COLORS[risk.data.level] }}>{risk.data.score}</span>
                <span className="text-sm uppercase text-stone-400">{risk.data.level} risk</span>
              </div>
              <div className="mt-2 text-xs text-stone-500">
                Last hour negative share {((risk.data.recent_negative_ratio || 0) * 100).toFixed(0)}% vs baseline {((risk.data.baseline_negative_ratio || 0) * 100).toFixed(0)}%
              </div>
              <table className="mt-4 w-full text-sm">
                <tbody>
                  {Object.entries(risk.data.components || {}).map(([k, v]) => (
                    <tr key={k} className="border-t border-ink-700">
                      <td className="py-2 capitalize text-stone-400">{k}</td>
                      <td className="py-2 text-right text-stone-100">{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {risk.data.drivers?.length > 0 && (
                <ul className="mt-3 space-y-1 text-xs text-amber-200/80">{risk.data.drivers.map((d) => <li key={d}>• {d}</li>)}</ul>
              )}
            </div>
          ) : <Spinner />}
        </Card>

        <Card title="Languages" subtitle="Detected language of genuine mentions">
          {overview.data ? (
            Object.keys(overview.data.languages).length ? (
              <div className="h-64">
                <Bar
                  data={{
                    labels: Object.keys(overview.data.languages),
                    datasets: [{ data: Object.values(overview.data.languages), backgroundColor: '#f59e0b', borderRadius: 4, barThickness: 18 }],
                  }}
                  options={{ plugins: { legend: { display: false } }, scales: baseScales() }}
                />
              </div>
            ) : <Empty>No data.</Empty>
          ) : <Spinner />}
        </Card>
      </div>

      <Card
        title="Sentiment forecast"
        subtitle={forecast.data?.computed_at
          ? `Next ${forecast.data.horizon_hours} hours · method: ${forecast.data[target]?.method || '–'} · refreshed ${formatTime(forecast.data.computed_at)}`
          : 'Hourly history and forecast with 80% confidence interval'}
        action={
          <Segmented
            value={target}
            onChange={setTarget}
            options={[{ value: 'sentiment', label: 'Sentiment index' }, { value: 'negative_ratio', label: 'Negative share' }, { value: 'volume', label: 'Volume' }]}
          />
        }
      >
        <div className="h-80">{forecast.data ? <ForecastChart data={forecast.data} target={target} /> : <Spinner />}</div>
      </Card>
    </div>
  )
}

function AnomalyChart({ data, hours }) {
  if (!data.points.length) return <Empty>Not enough data yet.</Empty>
  const labels = data.points.map((p) => chartLabel(p.t, hours))
  return (
    <Line
      data={{
        labels,
        datasets: [
          {
            label: 'Negative mentions',
            data: data.points.map((p) => p.negative),
            borderColor: SENTIMENT_COLORS.negative,
            backgroundColor: alpha(SENTIMENT_COLORS.negative, 0.12),
            fill: true,
            tension: 0.3,
            borderWidth: 1.5,
            pointRadius: data.points.map((p) => (p.is_anomaly ? 5 : 0)),
            pointBackgroundColor: '#fca5a5',
            pointBorderColor: '#ef4444',
            yAxisID: 'y',
          },
          {
            label: 'Total mentions',
            data: data.points.map((p) => p.total),
            borderColor: '#78716c',
            borderDash: [4, 4],
            borderWidth: 1,
            pointRadius: 0,
            tension: 0.3,
            yAxisID: 'y',
          },
          {
            label: 'Anomaly score',
            data: data.points.map((p) => p.anomaly_score),
            borderColor: '#f59e0b',
            borderWidth: 1,
            pointRadius: 0,
            tension: 0.3,
            yAxisID: 'y1',
          },
        ],
      }}
      options={{
        interaction: { mode: 'index', intersect: false },
        scales: {
          ...baseScales(),
          y: { ...baseScales().y, beginAtZero: true, title: { display: true, text: 'mentions' } },
          y1: { position: 'right', min: 0, max: 1, grid: { display: false }, title: { display: true, text: 'anomaly score' } },
        },
        plugins: {
          legend: { position: 'top', align: 'end' },
          tooltip: {
            callbacks: {
              afterBody: (items) => {
                const p = data.points[items[0].dataIndex]
                return [`negative z-score: ${p.neg_z}`, `ratio z-score: ${p.ratio_z}`, p.is_anomaly ? '⚠ anomaly' : '']
              },
            },
          },
        },
      }}
    />
  )
}

const TARGETS = {
  sentiment: { key: 'avg_score', label: 'Sentiment index (-1 to 1)', color: '#10b981' },
  negative_ratio: { key: 'neg_ratio', label: 'Negative share', color: '#ef4444' },
  volume: { key: 'volume', label: 'Mentions per hour', color: '#a78bfa' },
}

function ForecastChart({ data, target }) {
  const cfg = TARGETS[target]
  const fc = data[target]
  if (!data.history?.length || !fc?.points?.length) {
    return <Empty>Forecast needs at least a few hours of data.</Empty>
  }
  const history = data.history
  const labels = [...history.map((h) => h.t), ...fc.points.map((p) => p.t)].map((t) => chartLabel(t, 48))
  const pad = (arr, before) => [...Array(before).fill(null), ...arr]
  const lastValue = history[history.length - 1][cfg.key]
  const forecastLine = pad([lastValue, ...fc.points.map((p) => p.yhat)], history.length - 1)
  return (
    <Line
      data={{
        labels,
        datasets: [
          { label: 'Observed', data: history.map((h) => h[cfg.key]), borderColor: cfg.color, borderWidth: 1.8, pointRadius: 0, tension: 0.3 },
          { label: 'Forecast', data: forecastLine, borderColor: '#f59e0b', borderDash: [6, 4], borderWidth: 2, pointRadius: 0, tension: 0.3 },
          { label: 'Upper bound', data: pad(fc.points.map((p) => p.upper), history.length), borderWidth: 0, pointRadius: 0, fill: '+1', backgroundColor: 'rgba(245,158,11,.14)' },
          { label: 'Lower bound', data: pad(fc.points.map((p) => p.lower), history.length), borderWidth: 0, pointRadius: 0, fill: false },
        ],
      }}
      options={{
        interaction: { mode: 'index', intersect: false },
        scales: { ...baseScales(), y: { ...baseScales().y, title: { display: true, text: cfg.label } } },
        plugins: {
          legend: { position: 'top', align: 'end', labels: { filter: (i) => !i.text.includes('bound') } },
          tooltip: { callbacks: { label: (c) => (c.raw === null ? null : `${c.dataset.label}: ${num(c.raw, target === 'volume' ? 0 : 3)}`) } },
        },
      }}
    />
  )
}
