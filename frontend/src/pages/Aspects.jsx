import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { useState } from 'react'
import { Bar } from 'react-chartjs-2'
import { Link } from 'react-router-dom'
import { Card, Empty, Segmented, SentimentBar, Spinner, WINDOW_OPTIONS } from '../components/ui'
import { aspectLabel, SENTIMENT_COLORS } from '../lib/format'
import { gridColor } from '../lib/charts'
import { useApi } from '../lib/hooks'

export default function Aspects() {
  const [hours, setHours] = useState(24)
  const { data } = useApi(`/aspects?hours=${hours}`, { interval: 30000 })

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="display text-[30px] font-semibold leading-tight text-stone-50">Topics</h1>
          <p className="text-sm text-stone-500">Which parts of the experience customers praise or complain about</p>
        </div>
        <Segmented options={WINDOW_OPTIONS} value={hours} onChange={setHours} />
      </div>

      {!data ? <Spinner /> : !data.aspects.length ? <Card><Empty>No topics detected in this window.</Empty></Card> : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {data.aspects.map((a) => {
              const change = a.previous_negative ? ((a.negative - a.previous_negative) / a.previous_negative) * 100 : null
              return (
                <Link key={a.aspect} to={`/mentions?aspect=${a.aspect}&hours=${hours}`} className="card p-4 hover:border-ink-600">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-stone-100">{aspectLabel(a.aspect)}</span>
                    <span className="text-xs text-stone-500">{a.total} mentions</span>
                  </div>
                  <div className="mt-3 flex items-baseline gap-2">
                    <span className={`num text-[30px] font-medium leading-none ${a.avg_score >= 0.2 ? 'text-emerald-400' : a.avg_score <= -0.2 ? 'text-red-400' : 'text-stone-300'}`}>
                      {a.avg_score > 0 ? '+' : ''}{a.avg_score.toFixed(2)}
                    </span>
                    <span className="text-xs text-stone-500">sentiment index</span>
                  </div>
                  <div className="mt-3"><SentimentBar positive={a.positive} neutral={a.neutral} negative={a.negative} /></div>
                  <div className="mt-2 flex items-center justify-between text-xs">
                    <span className="text-red-300">{a.negative} complaints ({a.negative_pct}%)</span>
                    {change !== null && (
                      <span className={`flex items-center ${change > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                        {change > 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
                        {Math.abs(change).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </Link>
              )
            })}
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card title="Sentiment by topic" subtitle="Share of positive / neutral / negative" className="xl:col-span-2">
              <div className="h-96">
                <Bar
                  data={{
                    labels: data.aspects.map((a) => aspectLabel(a.aspect)),
                    datasets: ['positive', 'neutral', 'negative'].map((k) => ({
                      label: k,
                      data: data.aspects.map((a) => +(100 * a[k] / a.total).toFixed(1)),
                      backgroundColor: SENTIMENT_COLORS[k],
                      borderRadius: 2,
                    })),
                  }}
                  options={{
                    scales: {
                      x: { stacked: true, grid: { display: false } },
                      y: { stacked: true, max: 100, grid: { color: gridColor }, ticks: { callback: (v) => `${v}%` } },
                    },
                    plugins: { legend: { position: 'top', align: 'end' }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw}%` } } },
                  }}
                />
              </div>
            </Card>
            <Card title="Top complaint terms" subtitle="Words that come up most in negative comments">
              <KeywordTable words={data.negative_keywords} color="bg-red-500" />
            </Card>
          </div>
          <Card title="Top praise terms" subtitle="Words that come up most in positive comments">
            <div className="grid gap-x-8 md:grid-cols-3"><KeywordTable words={data.positive_keywords} color="bg-emerald-500" /></div>
          </Card>
        </>
      )}
    </div>
  )
}

function KeywordTable({ words, color }) {
  if (!words?.length) return <Empty>Nothing yet.</Empty>
  const max = words[0].count
  return words.map((w) => (
    <div key={w.word} className="flex items-center gap-3 py-1.5 text-sm">
      <span className="w-28 truncate text-stone-300">{w.word}</span>
      <div className="h-1.5 flex-1 rounded-full bg-ink-700">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${(100 * w.count) / max}%` }} />
      </div>
      <span className="w-10 text-right text-xs text-stone-500">{w.count}</span>
    </div>
  ))
}
