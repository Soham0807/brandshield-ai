import { Download, Printer } from 'lucide-react'
import { useState } from 'react'
import { ErrorBox, Segmented, Spinner, WINDOW_OPTIONS } from '../components/ui'
import { qs } from '../lib/api'
import { aspectLabel, brandTitle, humanizeAlert, num, SENTIMENT_COLORS, SOURCE_LABELS } from '../lib/format'
import { useApi } from '../lib/hooks'

/** One-page printable brand report built from the live analytics. */
export default function Report() {
  const [hours, setHours] = useState(24)
  const overview = useApi(`/overview?hours=${hours}`)
  const alerts = useApi('/alerts?limit=8')
  const complaints = useApi(`/mentions${qs({ sort: 'most_negative', spam: 'false', sentiment: 'negative', hours, limit: 5 })}`)
  const praise = useApi(`/mentions${qs({ sort: 'engagement', spam: 'false', sentiment: 'positive', hours, limit: 3 })}`)

  const o = overview.data
  const cur = o?.current
  const risk = o?.risk
  const generated = new Date().toLocaleString(undefined, { dateStyle: 'long', timeStyle: 'short' })

  function print() {
    // print on the light theme whatever the screen theme is
    const root = document.documentElement
    const previous = root.dataset.theme
    root.dataset.theme = 'light'
    const restore = () => {
      if (previous) root.dataset.theme = previous
      window.removeEventListener('afterprint', restore)
    }
    window.addEventListener('afterprint', restore)
    setTimeout(() => window.print(), 50)
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3 print:hidden">
        <div>
          <h1 className="display text-[30px] font-semibold leading-tight text-stone-50">Brand Report</h1>
          <p className="text-sm text-stone-500">A one-page summary to print, save as PDF or send to management</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented options={WINDOW_OPTIONS} value={hours} onChange={setHours} />
          <a className="btn-ghost" href={`/api/mentions/export.csv${qs({ hours, spam: 'false' })}`}>
            <Download size={14} /> Mentions CSV
          </a>
          <button className="btn-primary" onClick={print} disabled={!o}><Printer size={14} /> Print / PDF</button>
        </div>
      </div>

      <ErrorBox message={overview.error} />
      {!o ? <Spinner /> : (
        <article className="report mx-auto max-w-4xl border border-ink-700 bg-ink-900 p-6 md:p-10 print:max-w-none print:border-0 print:p-0">
          <header className="border-b-[3px] border-double border-stone-50 pb-4">
            <div className="font-mono text-[10.5px] uppercase tracking-[.14em] text-stone-500">
              BrandShield AI · Brand report · {windowName(hours)}
            </div>
            <h2 className="display mt-1 text-[32px] font-semibold leading-tight text-stone-50">
              {brandTitle(o.brand_name) || 'Brand'}
            </h2>
            <p className="mt-1 text-xs text-stone-500">Generated {generated}</p>
          </header>

          <section className="mt-5">
            <h3 className="label">Summary</h3>
            <p className="text-[15px] leading-relaxed text-stone-300">{o.summary}</p>
          </section>

          <section className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-5">
            <Figure label="Risk score" value={`${risk?.score ?? 0}/100`} note={risk?.level} strong={risk?.level && risk.level !== 'low'} />
            <Figure label="Brand health" value={cur.health} note="0–100" />
            <Figure label="Mentions" value={num(cur.total)} note="genuine" />
            <Figure label="Positive" value={`${cur.positive_pct}%`} />
            <Figure label="Negative" value={`${cur.negative_pct}%`} strong={cur.negative_pct >= 35} />
          </section>

          <section className="mt-5">
            <h3 className="label">Sentiment split</h3>
            <SplitBar cur={cur} />
          </section>

          <div className="mt-6 grid gap-6 md:grid-cols-2">
            <section>
              <h3 className="label">Topics</h3>
              {o.aspects?.length ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wide text-stone-500">
                      <th className="pb-1 font-medium">Topic</th>
                      <th className="pb-1 text-right font-medium">Pos</th>
                      <th className="pb-1 text-right font-medium">Neg</th>
                      <th className="pb-1 text-right font-medium">Neg %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {o.aspects.slice(0, 8).map((a) => {
                      const total = (a.positive || 0) + (a.neutral || 0) + (a.negative || 0)
                      const negPct = total ? Math.round((100 * a.negative) / total) : 0
                      return (
                        <tr key={a.aspect} className="border-t border-ink-700">
                          <td className="py-1 text-stone-200">{aspectLabel(a.aspect)}</td>
                          <td className="py-1 text-right text-stone-400">{num(a.positive)}</td>
                          <td className="py-1 text-right text-stone-400">{num(a.negative)}</td>
                          <td className={`py-1 text-right font-medium ${negPct >= 40 ? 'text-red-400' : 'text-stone-300'}`}>{negPct}%</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              ) : <p className="text-sm text-stone-500">No topics detected in this window.</p>}
            </section>

            <section>
              <h3 className="label">What is driving the risk</h3>
              {risk?.drivers?.length ? (
                <ul className="space-y-1 text-sm text-stone-300">
                  {risk.drivers.map((d) => <li key={d}>• {d}</li>)}
                </ul>
              ) : <p className="text-sm text-stone-500">No risk drivers: conversation looks normal.</p>}
              <Words title="Words in complaints" words={o.negative_keywords} />
              <Words title="Words in praise" words={o.positive_keywords} />
              {Object.keys(o.sources || {}).length > 0 && (
                <p className="mt-3 text-xs text-stone-500">
                  Sources: {Object.entries(o.sources).sort((x, y) => y[1] - x[1])
                    .map(([k, n]) => `${SOURCE_LABELS[k] || k} ${num(n)}`).join(' · ')}
                </p>
              )}
            </section>
          </div>

          <section className="mt-6 break-inside-avoid">
            <h3 className="label">Most negative comments</h3>
            <Quotes items={complaints.data?.items} empty="No negative comments in this window." />
          </section>

          <section className="mt-5 break-inside-avoid">
            <h3 className="label">Most engaged praise</h3>
            <Quotes items={praise.data?.items} empty="No positive comments in this window." />
          </section>

          <section className="mt-5 break-inside-avoid">
            <h3 className="label">Recent alerts</h3>
            {alerts.data?.items?.length ? (
              <ul className="space-y-2 text-sm">
                {alerts.data.items.map((a) => (
                  <li key={a.id} className="border-l-2 border-red-500 pl-2">
                    <span className="font-mono text-[10.5px] uppercase tracking-wide text-stone-500">
                      {a.severity} · {a.status} · {new Date(a.created_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
                    </span>
                    <div className="font-semibold text-stone-100">{a.title}</div>
                    <div className="text-xs text-stone-400">{humanizeAlert(a.message)}</div>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-stone-500">No alerts.</p>}
          </section>

          <footer className="mt-8 border-t border-ink-700 pt-3 font-mono text-[10px] uppercase tracking-[.12em] text-stone-500">
            Sentiment: XLM-RoBERTa + RoBERTa ensemble with Hinglish lexicon · anomalies: Isolation Forest · forecast: Prophet
          </footer>
        </article>
      )}
    </div>
  )
}

function windowName(hours) {
  return { 6: 'last 6 hours', 24: 'last 24 hours', 72: 'last 3 days', 168: 'last 7 days', 720: 'last 30 days' }[hours] || `last ${hours} hours`
}

function Figure({ label, value, note, strong }) {
  return (
    <div className="border border-ink-700 p-3">
      <div className="text-[11px] uppercase tracking-wide text-stone-500">{label}</div>
      <div className={`num mt-1 text-2xl font-medium ${strong ? 'text-red-400' : 'text-stone-50'}`}>{value}</div>
      {note && <div className="text-[11px] capitalize text-stone-500">{note}</div>}
    </div>
  )
}

function SplitBar({ cur }) {
  const parts = [
    ['positive', cur.positive], ['neutral', cur.neutral], ['negative', cur.negative],
  ]
  const total = parts.reduce((a, [, v]) => a + v, 0) || 1
  return (
    <div>
      <div className="flex h-4 w-full overflow-hidden" style={{ printColorAdjust: 'exact', WebkitPrintColorAdjust: 'exact' }}>
        {parts.map(([k, v]) => (
          <div key={k} style={{ width: `${(100 * v) / total}%`, background: SENTIMENT_COLORS[k] }} />
        ))}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-4 text-xs text-stone-400">
        {parts.map(([k, v]) => (
          <span key={k} className="capitalize">
            <span className="mr-1 inline-block size-2" style={{ background: SENTIMENT_COLORS[k], printColorAdjust: 'exact', WebkitPrintColorAdjust: 'exact' }} />
            {k} {num(v)} ({Math.round((100 * v) / total)}%)
          </span>
        ))}
        <span>spam filtered {num(cur.spam)}</span>
      </div>
    </div>
  )
}

function Words({ title, words }) {
  if (!words?.length) return null
  return (
    <p className="mt-3 text-sm text-stone-300">
      <span className="text-[11px] uppercase tracking-wide text-stone-500">{title}: </span>
      {words.slice(0, 10).map((w) => w.word).join(', ')}
    </p>
  )
}

function Quotes({ items, empty }) {
  if (!items) return <Spinner />
  if (!items.length) return <p className="text-sm text-stone-500">{empty}</p>
  return (
    <ul className="space-y-2">
      {items.map((m) => (
        <li key={m.id} className="text-sm">
          <span className="text-stone-200">“{m.text.length > 220 ? `${m.text.slice(0, 220)}…` : m.text}”</span>
          <span className="ml-1 text-xs text-stone-500">
            · {SOURCE_LABELS[m.source] || m.source}{m.author ? ` · ${m.author}` : ''}
          </span>
        </li>
      ))}
    </ul>
  )
}
