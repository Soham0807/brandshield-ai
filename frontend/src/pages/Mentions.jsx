import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import MentionRow from '../components/MentionRow'
import { Card, Empty, ErrorBox, Spinner } from '../components/ui'
import { qs } from '../lib/api'
import { aspectLabel, SOURCE_LABELS } from '../lib/format'
import { useApi } from '../lib/hooks'
import { useLiveEvent } from '../lib/live'

const PAGE = 30

export default function Mentions() {
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') || '')
  const [page, setPage] = useState(0)
  const [live, setLive] = useState(true)
  const facets = useApi('/mentions/facets')

  const filters = {
    sentiment: params.get('sentiment') || '',
    source: params.get('source') || '',
    aspect: params.get('aspect') || '',
    language: params.get('language') || '',
    spam: params.get('spam') || '',
    origin: params.get('origin') || '',
    hours: params.get('hours') || '',
    sort: params.get('sort') || 'newest',
    q: params.get('q') || '',
  }
  const path = `/mentions${qs({ ...filters, limit: PAGE, offset: page * PAGE })}`
  const mentions = useApi(path)

  useEffect(() => setPage(0), [params])
  useEffect(() => {
    const t = setTimeout(() => update('q', query), 350)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query])

  useLiveEvent('mentions', () => {
    if (live && page === 0 && filters.sort === 'newest') mentions.reload()
  })

  function update(key, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (next.toString() !== params.toString()) setParams(next, { replace: true })
  }

  const total = mentions.data?.total || 0

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-stone-50">Mentions</h1>
        <p className="text-sm text-stone-500">Every collected post and comment with its sentiment, aspects and spam verdict</p>
      </div>

      <Card bodyClass="p-4">
        <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-9">
          <div className="relative md:col-span-2">
            <Search size={15} className="absolute left-3 top-2.5 text-stone-500" />
            <input className="input pl-9" placeholder="Search text or author…" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <Select value={filters.sentiment} onChange={(v) => update('sentiment', v)} placeholder="All sentiment"
                  options={['positive', 'neutral', 'negative'].map((s) => [s, s])} />
          <Select value={filters.source} onChange={(v) => update('source', v)} placeholder="All sources"
                  options={(facets.data?.sources || []).map((s) => [s, SOURCE_LABELS[s] || s])} />
          <Select value={filters.aspect} onChange={(v) => update('aspect', v)} placeholder="All aspects"
                  options={(facets.data?.aspects || []).map((a) => [a, aspectLabel(a)])} />
          <Select value={filters.language} onChange={(v) => update('language', v)} placeholder="All languages"
                  options={(facets.data?.languages || []).map((l) => [l, l])} />
          <Select value={filters.spam} onChange={(v) => update('spam', v)} placeholder="Spam: any"
                  options={[['false', 'Genuine only'], ['true', 'Spam only']]} />
          <Select value={filters.origin} onChange={(v) => update('origin', v)} placeholder="Real + demo data"
                  options={[['live', 'Real data only'], ['simulated', 'Simulated only']]} />
          <Select value={filters.sort} onChange={(v) => update('sort', v)}
                  options={[['newest', 'Newest'], ['oldest', 'Oldest'], ['engagement', 'Most engagement'], ['most_negative', 'Most negative']]} />
        </div>
      </Card>

      <ErrorBox message={mentions.error} />

      <Card
        title={`${total.toLocaleString()} mentions`}
        bodyClass="pt-2"
        action={
          <label className="flex items-center gap-2 text-xs text-stone-400">
            <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} className="accent-amber-500" />
            Live updates
          </label>
        }
      >
        {mentions.loading && !mentions.data ? (
          <Spinner />
        ) : mentions.data?.items?.length ? (
          mentions.data.items.map((m) => <MentionRow key={m.id} mention={m} />)
        ) : (
          <Empty>No mentions match these filters.</Empty>
        )}
        <div className="flex items-center justify-between border-t border-ink-700 px-5 pt-3 text-xs text-stone-500">
          <span>
            {total ? `${page * PAGE + 1}–${Math.min(total, (page + 1) * PAGE)} of ${total.toLocaleString()}` : ''}
          </span>
          <div className="flex gap-2">
            <button className="btn-ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <button className="btn-ghost" disabled={(page + 1) * PAGE >= total} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        </div>
      </Card>
    </div>
  )
}

function Select({ value, onChange, options, placeholder }) {
  return (
    <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
      {placeholder && <option value="">{placeholder}</option>}
      {options.map(([v, l]) => (
        <option key={v} value={v}>{l}</option>
      ))}
    </select>
  )
}
