import {
  CheckCircle2, Eye, Loader2, MessageCircle, PlaySquare,
  RefreshCw, Search, ThumbsUp, Trash2, Users, X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import MentionRow from '../components/MentionRow'
import { Card, Empty, ErrorBox, SentimentBar, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { num, timeAgo } from '../lib/format'
import { useApi } from '../lib/hooks'
import { useLiveEvent } from '../lib/live'

export default function YouTube() {
  const status = useApi('/youtube/status', { interval: 30000 })
  const videos = useApi('/youtube/videos?limit=60', { interval: 60000 })
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [openVideo, setOpenVideo] = useState(null)

  useLiveEvent('mentions', (items) => {
    if (items.some((m) => m.source === 'youtube')) {
      videos.reload()
      status.reload()
    }
  })
  useLiveEvent('refresh', () => { status.reload(); videos.reload() })

  async function run(key, fn, success) {
    setBusy(key); setError(null); setMessage(null)
    try {
      const r = await fn()
      if (success) setMessage(typeof success === 'function' ? success(r) : success)
      status.reload(); videos.reload()
    } catch (e) { setError(e.message) } finally { setBusy(null) }
  }

  const s = status.data
  const channels = s?.channels || []

  return (
    <div className="space-y-5">
      <div>
        <h1 className="display text-[30px] font-semibold leading-tight text-stone-50">YouTube</h1>
        <p className="text-sm text-stone-500">
          Monitor any public channel — real videos, real comments, analysed by the same AI pipeline
        </p>
      </div>

      <ErrorBox message={error || status.error} />
      {message && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          <CheckCircle2 size={16} /> {message}
          <button className="ml-auto opacity-60 hover:opacity-100" onClick={() => setMessage(null)}><X size={14} /></button>
        </div>
      )}

      {!s ? <Spinner /> : !s.configured ? <NotEnabled /> : (
        <>
          <Card title="Add a channel" subtitle="Type a handle (@mkbhd), a channel URL, a channel ID or a channel name">
            <div className="flex flex-wrap gap-2">
              <div className="relative min-w-64 flex-1">
                <Search size={15} className="absolute left-3 top-2.5 text-stone-500" />
                <input className="input pl-9" placeholder="@zomato" value={query}
                       onKeyDown={(e) => e.key === 'Enter' && query.trim() && addChannel()}
                       onChange={(e) => setQuery(e.target.value)} />
              </div>
              <button className="btn-primary" disabled={busy === 'add' || !query.trim()} onClick={addChannel}>
                {busy === 'add' ? <Loader2 size={14} className="animate-spin" /> : <PlaySquare size={14} />}
                Monitor channel
              </button>
            </div>
            <p className="mt-2 text-xs text-stone-500">
              The channel's recent uploads and every comment on them are imported and analysed. This can take a minute
              for a busy channel.
            </p>
          </Card>

          {channels.map((c) => (
            <ChannelCard key={c.channel_id} channel={c} busy={busy}
              onSync={() => run(`sync-${c.channel_id}`,
                () => api.post(`/youtube/channels/${c.channel_id}/sync`, { force: true }),
                (r) => `Fetched ${r.queued_comments} comments from ${c.title}.`)}
              onRemove={() => {
                const del = confirm(`Stop monitoring ${c.title}?\n\nOK = also delete its imported comments\nCancel = keep the data`)
                run(`rm-${c.channel_id}`, () => fetch(`/api/youtube/channels/${c.channel_id}?delete_data=${del}`, { method: 'DELETE' })
                  .then(async (r) => { if (!r.ok) throw new Error((await r.json()).detail) }), `Removed ${c.title}`)
              }} />
          ))}

          {channels.length > 0 && (
            <Card title="Videos" subtitle="Comment sentiment per video · click one to read its comments">
              {!videos.data ? <Spinner /> : !videos.data.items.length ? (
                <Empty>No videos imported yet — click “Sync now”.</Empty>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                  {videos.data.items.map((v) => <VideoCard key={v.id} video={v} onOpen={() => setOpenVideo(v)} />)}
                </div>
              )}
            </Card>
          )}
        </>
      )}

      {openVideo && <VideoComments video={openVideo} onClose={() => setOpenVideo(null)} />}
    </div>
  )

  async function addChannel() {
    await run('add', () => api.post('/youtube/channels', { query: query.trim(), set_brand: true }),
      (r) => `Now monitoring ${r.channel.title} — ${r.queued_comments} comments imported and being analysed.`)
    setQuery('')
  }
}

function NotEnabled() {
  return (
    <div className="card flex flex-col items-center justify-center p-10 text-center">
      <span className="grid size-16 place-items-center rounded-sm bg-stone-50 text-ink-950">
        <PlaySquare size={30} />
      </span>
      <h2 className="display mt-5 text-lg font-semibold text-stone-50">YouTube monitoring isn’t switched on yet</h2>
      <p className="mt-2 max-w-md text-sm text-stone-400">
        Once it is, you can type any channel name here and BrandShield reads its videos and comments for you.
        Ask whoever runs BrandShield to turn it on in <Link to="/setup" className="link">Server setup</Link>.
      </p>
    </div>
  )
}

function ChannelCard({ channel: c, busy, onSync, onRemove }) {
  const total = (c.positive || 0) + (c.neutral || 0) + (c.negative || 0)
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center gap-4">
        {c.thumbnail_url ? (
          <img src={c.thumbnail_url} alt="" referrerPolicy="no-referrer"
               className="size-16 rounded-full border border-ink-600 object-cover" />
        ) : (
          <div className="grid size-16 place-items-center rounded-full bg-stone-50 display text-2xl font-semibold text-ink-950">
            {c.title?.[0] || '?'}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <a href={`https://www.youtube.com/channel/${c.channel_id}`} target="_blank" rel="noreferrer"
             className="display text-lg font-semibold text-stone-50 hover:underline">{c.title}</a>
          {c.handle && <div className="text-sm text-stone-400">@{c.handle}</div>}
          <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-stone-500">
            <span>Last sync {c.last_sync_at ? timeAgo(c.last_sync_at) : 'pending…'}</span>
            <span>{num(c.videos_tracked)} videos tracked</span>
          </div>
          {c.last_error && <div className="mt-1 text-xs text-red-400">{c.last_error}</div>}
        </div>
        <div className="grid grid-cols-4 gap-5 text-center">
          <Metric icon={Users} label="Subscribers" value={num(c.subscriber_count)} />
          <Metric icon={Eye} label="Total views" value={num(c.view_count)} />
          <Metric icon={PlaySquare} label="Videos" value={num(c.video_count)} />
          <Metric icon={MessageCircle} label="Comments analysed" value={num(c.analysed_comments)} />
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={onSync} disabled={busy === `sync-${c.channel_id}`}>
            {busy === `sync-${c.channel_id}` ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Sync now
          </button>
          <button className="btn-danger" onClick={onRemove} disabled={busy === `rm-${c.channel_id}`}><Trash2 size={14} /></button>
        </div>
      </div>
      {total > 0 && (
        <div className="mt-4 border-t border-ink-700 pt-4">
          <div className="mb-1.5 flex justify-between text-xs text-stone-400">
            <span>Audience sentiment</span>
            <span>
              <span className="text-emerald-400">{Math.round((100 * c.positive) / total)}% positive</span> ·{' '}
              <span className="text-slate-300">{Math.round((100 * c.neutral) / total)}% neutral</span> ·{' '}
              <span className="text-rose-400">{Math.round((100 * c.negative) / total)}% negative</span>
              {c.spam > 0 && <> · <span className="text-amber-400">{c.spam} spam</span></>}
            </span>
          </div>
          <SentimentBar positive={c.positive} neutral={c.neutral} negative={c.negative} />
          <div className="mt-3 text-xs">
            <Link to="/" className="link">Open the dashboard</Link> for trends, aspects,
            anomalies and alerts computed from these comments.
          </div>
        </div>
      )}
    </div>
  )
}

function Metric({ icon: Icon, label, value }) {
  return (
    <div>
      <div className="num flex items-center justify-center gap-1 text-lg font-semibold text-stone-50">
        <Icon size={13} className="text-stone-500" />{value}
      </div>
      <div className="text-[11px] text-stone-500">{label}</div>
    </div>
  )
}

function VideoCard({ video: v, onOpen }) {
  const score = v.avg_score
  return (
    <button onClick={onOpen} className="group overflow-hidden rounded-xl border border-ink-700 bg-ink-900 text-left transition hover:border-ink-600">
      <div className="relative aspect-video bg-ink-800">
        {v.thumbnail_url ? (
          <img src={v.thumbnail_url} alt="" loading="lazy" referrerPolicy="no-referrer"
               className="size-full object-cover transition group-hover:scale-[1.03]" />
        ) : <div className="grid size-full place-items-center text-stone-600"><PlaySquare size={30} /></div>}
        {v.analysed > 0 && score !== null && score !== undefined && (
          <span className={`absolute right-2 top-2 rounded-full px-2 py-0.5 text-xs font-semibold backdrop-blur ${
            score >= 0.2 ? 'bg-emerald-500/85 text-white' : score <= -0.2 ? 'bg-rose-500/85 text-white' : 'bg-stone-700/85 text-stone-100'}`}>
            {score > 0 ? '+' : ''}{score.toFixed(2)}
          </span>
        )}
      </div>
      <div className="p-3">
        <p className="line-clamp-2 min-h-10 text-sm text-stone-200">{v.title}</p>
        <div className="mt-2 flex items-center gap-3 text-xs text-stone-500">
          <span className="flex items-center gap-1"><Eye size={12} /> {num(v.view_count)}</span>
          <span className="flex items-center gap-1"><ThumbsUp size={12} /> {num(v.like_count)}</span>
          <span className="flex items-center gap-1"><MessageCircle size={12} /> {num(v.comment_count)}</span>
          <span className="ml-auto">{timeAgo(v.published_at)}</span>
        </div>
        {v.analysed > 0 && <div className="mt-2"><SentimentBar positive={v.positive} neutral={v.neutral} negative={v.negative} /></div>}
      </div>
    </button>
  )
}

function VideoComments({ video, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    api.get(`/mentions?parent_id=${encodeURIComponent(video.id)}&limit=200&sort=newest`).then(setData).catch((e) => setError(e.message))
  }, [video.id])
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/50" onClick={onClose}>
      <div className="flex h-full w-full max-w-xl flex-col border-l border-ink-700 bg-ink-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-3 border-b border-ink-700 p-4">
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-stone-100">{video.title}</div>
            <a href={`https://www.youtube.com/watch?v=${video.id}`} target="_blank" rel="noreferrer"
               className="mt-1 inline-block link text-xs">Watch on YouTube ↗</a>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-100"><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <ErrorBox message={error} />
          {!data ? <Spinner /> : data.items.length
            ? data.items.map((m) => <MentionRow key={m.id} mention={m} />)
            : <Empty>No analysed comments for this video yet.</Empty>}
        </div>
      </div>
    </div>
  )
}
