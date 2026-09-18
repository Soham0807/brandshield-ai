import { FileUp, Loader2, Wand2 } from 'lucide-react'
import { useState } from 'react'
import { Card, ErrorBox, SentimentBadge } from '../components/ui'
import { api } from '../lib/api'
import { aspectLabel, SENTIMENT_COLORS } from '../lib/format'

const EXAMPLES = [
  'The cappuccino was amazing but the delivery was 45 minutes late 😡',
  'Staff was super friendly, loved the cozy ambience ✨',
  'Khana bahut badhiya tha lekin bahut mehenga hai',
  'Found a hair in my food, absolutely disgusting. Never coming back!',
  'Get 10k free followers now!!! check my profile https://bit.ly/x1',
  'सर्विस बहुत खराब है',
  'Is the cafe open on Sunday?',
]

export default function Analyze() {
  const [text, setText] = useState(EXAMPLES[0])
  const [store, setStore] = useState(false)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [upload, setUpload] = useState(null)

  async function run() {
    if (!text.trim()) return
    setBusy(true)
    setError(null)
    try {
      setResult(await api.post('/analyze', { text, store }))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function uploadCsv(file) {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    setUpload({ busy: true })
    try {
      const r = await api.upload('/ingest/csv', form)
      setUpload({ message: `Queued ${r.queued} rows from ${r.filename} into the streaming pipeline.` })
    } catch (e) {
      setUpload({ error: e.message })
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-stone-50">Analyze Text</h1>
        <p className="text-sm text-stone-500">Run any comment through the full NLP pipeline and inspect every step</p>
      </div>

      <div className="grid gap-4 xl:grid-cols-5">
        <Card title="Input" className="xl:col-span-2">
          <textarea className="input min-h-36 resize-y" value={text} onChange={(e) => setText(e.target.value)}
                    maxLength={5000} placeholder="Paste a tweet, review or comment…" />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {EXAMPLES.map((ex) => (
              <button key={ex} onClick={() => setText(ex)}
                      className="max-w-full truncate rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-left text-[11px] text-stone-400 hover:text-stone-200">
                {ex.length > 42 ? `${ex.slice(0, 42)}…` : ex}
              </button>
            ))}
          </div>
          <div className="mt-4 flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm text-stone-400">
              <input type="checkbox" checked={store} onChange={(e) => setStore(e.target.checked)} className="accent-amber-500" />
              Save to dashboard
            </label>
            <button className="btn-primary" onClick={run} disabled={busy || !text.trim()}>
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />} Analyze
            </button>
          </div>
          <div className="mt-3"><ErrorBox message={error} /></div>

          <div className="mt-6 border-t border-ink-700 pt-4">
            <div className="label">Bulk import</div>
            <p className="text-xs text-stone-500">
              Upload a CSV with a <code className="text-stone-300">text</code> or <code className="text-stone-300">comment</code> column
              (optional: <code className="text-stone-300">timestamp</code>, <code className="text-stone-300">author</code>, <code className="text-stone-300">source</code>, <code className="text-stone-300">engagement</code>).
            </p>
            <label className="btn-ghost mt-3 cursor-pointer">
              <FileUp size={14} /> Choose CSV
              <input type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => uploadCsv(e.target.files?.[0])} />
            </label>
            {upload?.busy && <p className="mt-2 text-xs text-stone-400">Uploading…</p>}
            {upload?.message && <p className="mt-2 text-xs text-emerald-400">{upload.message}</p>}
            {upload?.error && <p className="mt-2 text-xs text-red-400">{upload.error}</p>}
          </div>
        </Card>

        <div className="space-y-4 xl:col-span-3">
          {!result ? (
            <Card><p className="py-16 text-center text-sm text-stone-500">Results will appear here.</p></Card>
          ) : (
            <>
              <Card title="Sentiment" subtitle={`${result.model} · ${result.processing_ms} ms`}>
                <div className="flex flex-wrap items-center gap-4">
                  <div className="text-3xl font-semibold capitalize" style={{ color: SENTIMENT_COLORS[result.sentiment.label] }}>
                    {result.preprocessing.is_spam ? 'Spam' : result.sentiment.label}
                  </div>
                  <div className="text-sm text-stone-400">
                    confidence <b className="text-stone-100">{(result.sentiment.confidence * 100).toFixed(1)}%</b> ·
                    score <b className="text-stone-100">{result.sentiment.score.toFixed(3)}</b>
                    {result.sentiment.lexicon_polarity !== null && (
                      <> · regional lexicon <b className="text-amber-300">{result.sentiment.lexicon_polarity.toFixed(2)}</b></>
                    )}
                  </div>
                </div>
                <div className="mt-4 space-y-2">
                  {['positive', 'neutral', 'negative'].map((k) => (
                    <div key={k} className="flex items-center gap-3 text-sm">
                      <span className="w-16 capitalize text-stone-400">{k}</span>
                      <div className="h-2 flex-1 rounded-full bg-ink-700">
                        <div className="h-full rounded-full transition-all" style={{ width: `${result.sentiment.probs[k] * 100}%`, background: SENTIMENT_COLORS[k] }} />
                      </div>
                      <span className="w-14 text-right text-stone-300">{(result.sentiment.probs[k] * 100).toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
                {result.stored_id && <p className="mt-3 text-xs text-emerald-400">Saved to the dashboard ({result.stored_id}).</p>}
              </Card>

              <Card title="Aspect-based sentiment" subtitle="Each clause is classified separately">
                {result.aspects.length ? (
                  <div className="grid gap-2 md:grid-cols-2">
                    {result.aspects.map((a) => (
                      <div key={a.aspect} className="rounded-xl border border-ink-700 bg-ink-850 p-3">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-stone-100">{aspectLabel(a.aspect)}</span>
                          <SentimentBadge value={a.sentiment} />
                        </div>
                        <p className="mt-1.5 text-xs text-stone-400">“{a.evidence}”</p>
                        <p className="mt-1 text-[11px] text-stone-500">score {a.score.toFixed(3)}</p>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-sm text-stone-500">No known aspect mentioned (general comment).</p>}
              </Card>

              <Card title="Preprocessing pipeline">
                <dl className="grid gap-3 text-sm md:grid-cols-2">
                  <Step label="1. Noise removal (URLs, mentions, #)" value={result.preprocessing.clean} />
                  <Step label="2. Normalised model input (emoji → words)" value={result.preprocessing.model_text} />
                  <Step label="3. Tokens" value={<Chips items={result.preprocessing.tokens} />} />
                  <Step label="4. Stop-words removed + lemmatized" value={<Chips items={result.preprocessing.lemmas} highlight />} />
                  <Step label="5. Language detection" value={result.preprocessing.language} />
                  <Step label="6. Spam filter"
                        value={result.preprocessing.is_spam ? <span className="text-orange-300">Spam – {result.preprocessing.spam_reason}</span> : <span className="text-emerald-400">Genuine</span>} />
                </dl>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function Step({ label, value }) {
  return (
    <div className="rounded-lg border border-ink-700 bg-ink-850 p-3">
      <dt className="text-[11px] uppercase tracking-wide text-stone-500">{label}</dt>
      <dd className="mt-1 break-words text-stone-200">{value || <span className="text-stone-600">(empty)</span>}</dd>
    </div>
  )
}

function Chips({ items, highlight }) {
  if (!items?.length) return <span className="text-stone-600">(none)</span>
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((t, i) => (
        <span key={`${t}-${i}`} className={`rounded px-1.5 py-0.5 text-xs ${highlight ? 'bg-amber-500/15 text-amber-200' : 'bg-ink-700 text-stone-300'}`}>{t}</span>
      ))}
    </div>
  )
}
