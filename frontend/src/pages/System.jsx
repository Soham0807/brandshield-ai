import { Clock, Cpu, Layers, Loader2, Play, Radio, Timer, Zap } from 'lucide-react'
import { useState } from 'react'
import { Card, Empty, ErrorBox, Spinner, Stat, Tip } from '../components/ui'
import { METRIC_HELP } from '../lib/help'
import { api } from '../lib/api'
import { num } from '../lib/format'
import { useApi } from '../lib/hooks'
import { useLive, useLiveEvent } from '../lib/live'

const DATASET_TITLES = {
  real: 'Real comments (200 from YouTube, Instagram and news, hand-labelled)',
  domain: 'Team test set (83 brand comments incl. Hinglish, Hindi, Marathi)',
  appstore: "App Store reviews (labelled by the reviewer's own star rating)",
  tweet_eval: 'TweetEval benchmark',
}
const DATASET_ORDER = ['real', 'domain', 'appstore', 'tweet_eval']

export default function System() {
  const { metrics: liveMetrics } = useLive()
  const polled = useApi('/system/metrics', { interval: liveMetrics ? 0 : 5000 })
  const evaluation = useApi('/system/evaluation')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const m = liveMetrics || polled.data

  useLiveEvent('evaluation', (d) => {
    setRunning(false)
    if (d.error) setError(d.error)
    evaluation.reload()
  })

  async function runEvaluation() {
    setError(null)
    try {
      await api.post('/system/evaluation/run')
      setRunning(true)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="display text-[30px] font-semibold leading-tight text-stone-50">Performance</h1>
        <p className="text-sm text-stone-500">Live pipeline metrics and model evaluation (accuracy, precision, recall, F1)</p>
      </div>

      {!m ? <Spinner /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Stat icon={Zap} tone="amber" label="Throughput (msg/s, 1 min)" value={m.throughput_per_sec} digits={2} />
            <Stat icon={Timer} tone="sky" label="Latency p50 (ingest → stored)" value={m.latency_ms.p50} suffix=" ms" />
            <Stat icon={Clock} tone="violet" label="Latency p95" value={m.latency_ms.p95} suffix=" ms" />
            <Stat icon={Cpu} tone="green" label="Model inference / text" value={m.model.avg_inference_ms_per_text} digits={1} suffix=" ms" />
            <Stat icon={Layers} tone="orange" label="Queue depth" value={m.queue_depth ?? 'n/a'} />
            <Stat icon={Radio} tone="red" label="Errors" value={m.errors_total} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Streaming pipeline">
              <table className="w-full text-sm">
                <tbody>
                  {[
                    ['Message bus', m.bus === 'kafka' ? 'Apache Kafka' : 'In-memory queue (Kafka fallback)'],
                    ['Uptime', `${Math.floor(m.uptime_seconds / 3600)}h ${Math.floor((m.uptime_seconds % 3600) / 60)}m`],
                    ['Messages ingested', num(m.ingested_total)],
                    ['Messages processed', num(m.processed_total)],
                    ['Stored (new)', num(m.stored_total)],
                    ['Duplicates skipped', num(m.duplicates_total)],
                    ['Processed last minute', num(m.processed_last_minute)],
                    ['Batches', num(m.batches_total)],
                    ['Processing time per item', m.processing_ms_per_item ? `${m.processing_ms_per_item} ms` : '–'],
                    ['Max latency', m.latency_ms.max ? `${num(m.latency_ms.max)} ms` : '–'],
                    ['Last error', m.last_error || 'none'],
                  ].map(([k, v]) => (
                    <tr key={k} className="border-t border-ink-700 first:border-0">
                      <td className="py-2 text-stone-400">{k}</td>
                      <td className="py-2 text-right text-stone-100">{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
            <Card title="Sentiment model">
              <table className="w-full text-sm">
                <tbody>
                  {[
                    ['Model', m.model.name || 'loading…'],
                    ['Status', m.model.ready ? 'ready' : 'loading'],
                    ['Texts inferred', num(m.model.texts_inferred)],
                    ['Avg inference per text', `${num(m.model.avg_inference_ms_per_text, 2)} ms`],
                    ['Live agreement with simulator labels',
                      m.live_agreement ? `${(m.live_agreement.accuracy * 100).toFixed(1)}% (${num(m.live_agreement.samples)} samples)` : '–'],
                  ].map(([k, v]) => (
                    <tr key={k} className="border-t border-ink-700 first:border-0">
                      <td className="py-2 text-stone-400">{k}</td>
                      <td className="max-w-64 truncate py-2 text-right text-stone-100" title={String(v)}>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-xs text-stone-500">
                Cached predictions are not counted as inferences, so repeated texts are served instantly.
              </p>
            </Card>
          </div>
        </>
      )}

      <Card
        title="Model evaluation"
        subtitle="Labelled test sets · hybrid = XLM-RoBERTa + RoBERTa ensemble + regional lexicon + neutral margin"
        action={
          <button className="btn-primary" onClick={runEvaluation} disabled={running}>
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run evaluation
          </button>
        }
      >
        <ErrorBox message={error} />
        {!evaluation.data ? <Spinner /> : !evaluation.data.available ? (
          <Empty>No evaluation yet. Click “Run evaluation” or run <code>python -m scripts.evaluate_model</code>.</Empty>
        ) : (
          <div className="space-y-6">
            {Object.entries(evaluation.data.datasets).sort(([a], [b]) => DATASET_ORDER.indexOf(a) - DATASET_ORDER.indexOf(b)).map(([name, d]) => <EvalBlock key={name} name={name} d={d} />)}
          </div>
        )}
      </Card>
    </div>
  )
}

function EvalBlock({ name, d }) {
  const rows = [['Models only', d.model_only ?? d.distilbert_only], ['Hybrid (deployed)', d.hybrid]].filter(([, v]) => v)
  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="font-semibold text-stone-100">{DATASET_TITLES[name] || name}</h3>
        <span className="text-xs text-stone-500">{d.samples} samples · {d.inference_ms_per_text} ms/text · {d.evaluated_at}</span>
      </div>
      {d.polarity?.accuracy != null && (
        <p className="mt-2 text-sm text-stone-400">
          <Tip text="Of the comments that are really positive or negative and that the model labels positive or negative, how many it gets right. It shows how rarely the model mistakes praise for a complaint, or the reverse. Coverage is the share of those comments it labels positive or negative rather than neutral.">
            Polarity accuracy
          </Tip>{' '}
          <b className="text-emerald-400">{(d.polarity.accuracy * 100).toFixed(1)}%</b>
          {' '}({d.polarity.correct} of {d.polarity.decisive} positive-vs-negative calls correct, coverage {(d.polarity.coverage * 100).toFixed(0)}%)
          {' '}· 3-class accuracy <b className="text-stone-100">{(d.hybrid.accuracy * 100).toFixed(1)}%</b>
        </p>
      )}
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-stone-500">
              <th className="py-2"><Tip text="Hybrid = AI model plus our Hinglish/Hindi/Marathi word list. Model only = the AI model alone. Comparing them shows what the word list adds.">Variant</Tip></th><th><Tip text={METRIC_HELP.accuracy}>Accuracy</Tip></th><th><Tip text={METRIC_HELP.precision}>Precision</Tip></th><th><Tip text={METRIC_HELP.recall}>Recall</Tip></th><th><Tip text={METRIC_HELP.f1}>F1 (macro)</Tip></th><th><Tip text={METRIC_HELP.f1_weighted}>F1 (weighted)</Tip></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, r]) => (
              <tr key={label} className="border-t border-ink-700">
                <td className="py-2 text-stone-300">{label}</td>
                <td className="text-stone-100">{(r.accuracy * 100).toFixed(1)}%</td>
                <td className="text-stone-100">{(r.precision_macro * 100).toFixed(1)}%</td>
                <td className="text-stone-100">{(r.recall_macro * 100).toFixed(1)}%</td>
                <td className="font-semibold text-stone-50 underline decoration-red-500 decoration-2 underline-offset-4">{(r.f1_macro * 100).toFixed(1)}%</td>
                <td className="text-stone-100">{(r.f1_weighted * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <div className="label">Per class (hybrid)</div>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-stone-500"><th className="py-1">Class</th><th><Tip text={METRIC_HELP.precision}>P</Tip></th><th><Tip text={METRIC_HELP.recall}>R</Tip></th><th><Tip text={METRIC_HELP.f1}>F1</Tip></th><th><Tip text={METRIC_HELP.support}>n</Tip></th></tr></thead>
            <tbody>
              {Object.entries(d.hybrid.per_class).map(([k, v]) => (
                <tr key={k} className="border-t border-ink-700">
                  <td className="py-1.5 capitalize text-stone-300">{k}</td>
                  <td>{v.precision.toFixed(2)}</td><td>{v.recall.toFixed(2)}</td><td>{v.f1.toFixed(2)}</td><td className="text-stone-500">{v.support}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {d.aspect_detection && (
            <p className="mt-3 text-sm text-stone-400">
              Aspect detection: precision <b className="text-stone-100">{d.aspect_detection.precision.toFixed(2)}</b>,
              recall <b className="text-stone-100">{d.aspect_detection.recall.toFixed(2)}</b>,
              F1 <b className="text-stone-100">{d.aspect_detection.f1.toFixed(2)}</b>
            </p>
          )}
        </div>
        <div>
          <div className="label"><Tip text="Each row is the true label given by a person, each column is what the model predicted. Numbers on the diagonal are correct. The key cell: negative comments predicted as positive, which would hide an unhappy customer.">Confusion matrix (rows = true, columns = predicted)</Tip></div>
          <Confusion cm={d.hybrid.confusion_matrix} />
        </div>
      </div>
    </div>
  )
}

function Confusion({ cm }) {
  const max = Math.max(1, ...cm.matrix.flat())
  return (
    <table className="text-sm">
      <thead>
        <tr><th />{cm.labels.map((l) => <th key={l} className="px-2 pb-1 text-xs font-normal capitalize text-stone-500">{l}</th>)}</tr>
      </thead>
      <tbody>
        {cm.matrix.map((row, i) => (
          <tr key={cm.labels[i]}>
            <td className="pr-2 text-xs capitalize text-stone-500">{cm.labels[i]}</td>
            {row.map((v, j) => (
              <td key={j} className="size-14 rounded text-center font-medium"
                  style={{ background: i === j ? `rgba(62,124,89,${0.1 + (0.6 * v) / max})` : `rgba(210,56,30,${(0.5 * v) / max})` }}>
                {v}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
