import {
  AlertTriangle,
  BadgeCheck,
  CheckCircle2,
  ExternalLink,
  Heart,
  Image as ImageIcon,
  Loader2,
  LogIn,
  MessageCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  Unplug,
  Users,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import MentionRow from '../components/MentionRow'
import { Card, Empty, ErrorBox, SentimentBar, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { igImage, num, timeAgo } from '../lib/format'
import { useApi } from '../lib/hooks'
import { useLiveEvent } from '../lib/live'

export default function Instagram() {
  const [params, setParams] = useSearchParams()
  const status = useApi('/instagram/status', { interval: 30000 })
  const media = useApi('/instagram/media?limit=60', { interval: 60000 })
  const pages = useApi('/instagram/pages', { interval: 15000 })
  const pagePosts = useApi('/instagram/pages/posts?limit=60', { interval: 30000 })
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [openPost, setOpenPost] = useState(null)

  const connected = params.get('connected')
  const loginError = params.get('error')

  const reloadAll = () => {
    status.reload()
    media.reload()
    pages.reload()
    pagePosts.reload()
  }
  useLiveEvent('mentions', (items) => {
    if (items.some((m) => m.source === 'instagram' && m.parent_id)) reloadAll()
  })
  useLiveEvent('instagram_pages', reloadAll)
  useLiveEvent('refresh', reloadAll)

  async function run(key, fn, success) {
    setBusy(key)
    setError(null)
    setMessage(null)
    try {
      const r = await fn()
      if (success) setMessage(typeof success === 'function' ? success(r) : success)
      reloadAll()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  async function addPage() {
    await run('add', () => api.post('/instagram/pages', { query: query.trim(), set_brand: true }),
      (r) => `Now monitoring @${r.page.username}. Its latest posts and comments are being imported – this takes about a minute.`)
    setQuery('')
  }

  const s = status.data
  const accounts = s?.accounts || []
  const pg = pages.data
  const pageList = pg?.pages || []
  const showOwnAccount = s && (s.app_configured || accounts.length > 0)

  return (
    <div className="space-y-5">
      <div>
        <h1 className="display text-[30px] font-semibold leading-tight text-stone-50">Instagram</h1>
        <p className="text-sm text-stone-500">Monitor any public Instagram page – real posts, real comments, analysed by the same AI pipeline</p>
      </div>

      {connected && (
        <Banner tone="green" onClose={() => setParams({}, { replace: true })}>
          <CheckCircle2 size={16} /> Connected <b>@{connected}</b>. Comments are being imported and analysed – this can take a minute.
        </Banner>
      )}
      {loginError && (
        <Banner tone="red" onClose={() => setParams({}, { replace: true })}>
          <AlertTriangle size={16} /> {loginError}
        </Banner>
      )}
      <ErrorBox message={error || pages.error} />
      {message && <Banner tone="green" onClose={() => setMessage(null)}><CheckCircle2 size={16} /> {message}</Banner>}

      {!pg ? <Spinner /> : !pg.configured ? (
        <div className="card flex flex-col items-center justify-center p-10 text-center">
          <span className="grid size-16 place-items-center rounded-sm bg-stone-50 text-ink-950">
            <ImageIcon size={30} />
          </span>
          <h2 className="mt-5 text-lg font-semibold text-stone-50">Instagram page monitoring isn’t switched on yet</h2>
          <p className="mt-2 max-w-md text-sm text-stone-400">
            Once it is, you can type any public Instagram handle here and BrandShield reads its posts and comments for you.
            Ask whoever runs BrandShield to turn it on in <Link to="/setup" className="link">Server setup</Link>.
          </p>
        </div>
      ) : (
        <>
          <Card title="Monitor a page" subtitle="Type any public Instagram handle (@zomato) or paste a profile link – no Instagram login needed">
            <div className="flex flex-wrap gap-2">
              <div className="relative min-w-64 flex-1">
                <Search size={15} className="absolute left-3 top-2.5 text-stone-500" />
                <input className="input pl-9" placeholder="@zomato" value={query}
                       onKeyDown={(e) => e.key === 'Enter' && query.trim() && busy !== 'add' && addPage()}
                       onChange={(e) => setQuery(e.target.value)} />
              </div>
              <button className="btn-primary" disabled={busy === 'add' || !query.trim()} onClick={addPage}>
                {busy === 'add' ? <Loader2 size={14} className="animate-spin" /> : <ImageIcon size={14} />}
                {busy === 'add' ? 'Looking up the page…' : 'Monitor page'}
              </button>
            </div>
            <p className="mt-2 text-xs text-stone-500">
              BrandShield reads the page’s latest posts and their newest comments, then checks again every 15 minutes.
              Private accounts can’t be monitored.
            </p>
          </Card>

          {s?.simulated_mentions > 0 && pageList.length > 0 && (
            <div className="card flex flex-wrap items-center gap-3 p-4">
              <AlertTriangle size={18} className="text-red-400" />
              <div className="flex-1 text-sm text-stone-300">
                The dashboard still mixes in <b>{num(s.simulated_mentions)}</b> simulated demo mentions. Show only real data?
              </div>
              <button className="btn-primary" disabled={busy === 'live'} onClick={() => {
                if (confirm('Turn off the simulator and delete all simulated mentions and alerts?')) {
                  run('live', () => api.post('/data/use-live-only', { confirm: true, rename_brand: false }),
                    (r) => `Removed ${num(r.deleted_simulated)} simulated mentions. The dashboard now shows only real data.`)
                }
              }}>
                {busy === 'live' ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />} Use only real data
              </button>
            </div>
          )}

          {pageList.map((p) => (
            <PageCard key={p.username} page={p} busy={busy}
              onSync={() => run(`psync-${p.username}`, () => api.post(`/instagram/pages/${p.username}/sync`, { force: true }),
                (r) => `Fetched ${r.queued_comments} new comments from @${p.username}.`)}
              onRemove={() => {
                const del = confirm(`Stop monitoring @${p.username}?\n\nOK = also delete its imported comments\nCancel = keep the data`)
                run(`prm-${p.username}`, () => fetch(`/api/instagram/pages/${p.username}?delete_data=${del}`, { method: 'DELETE' })
                  .then(async (r) => { if (!r.ok) throw new Error((await r.json()).detail) }), `Stopped monitoring @${p.username}`)
              }} />
          ))}

          {pageList.length > 0 && (
            <Card title="Posts" subtitle="Sentiment of the comments on each post · click a post to read its comments">
              {!pagePosts.data ? <Spinner /> : !pagePosts.data.items.length ? (
                <Empty>Posts appear here as soon as the first import finishes.</Empty>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                  {pagePosts.data.items.map((m) => <PostCard key={m.id} post={m} onOpen={() => setOpenPost(m)} />)}
                </div>
              )}
            </Card>
          )}
        </>
      )}

      {showOwnAccount && (
        <div className="space-y-4 border-t border-ink-700 pt-6">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-stone-100">Your own Business account</h2>
              <p className="text-sm text-stone-500">Own a Business or Creator account? Log in to analyse comments on your posts directly from Instagram.</p>
            </div>
            {accounts.length > 0 && (
              <a href="/api/auth/instagram/login" className="btn-ghost"><LogIn size={14} /> Connect another account</a>
            )}
          </div>

          {accounts.length === 0 ? <ConnectHero setup={s} /> : (
            <>
              {accounts.map((a) => (
                <AccountCard
                  key={a.ig_user_id}
                  account={a}
                  busy={busy}
                  collector={s.collector}
                  onSync={() => run(`sync-${a.ig_user_id}`, () => api.post(`/instagram/accounts/${a.ig_user_id}/sync`, { force: true }),
                    (r) => `Fetched ${r.queued_comments} comments from @${a.username}. New ones are analysed in the background.`)}
                  onDisconnect={() => {
                    const deleteData = confirm(`Disconnect @${a.username}?\n\nOK = also delete its imported comments\nCancel = keep the data`)
                    run(`disc-${a.ig_user_id}`, () => fetch(`/api/instagram/accounts/${a.ig_user_id}?delete_data=${deleteData}`, { method: 'DELETE' })
                      .then(async (r) => { if (!r.ok) throw new Error((await r.json()).detail) }), `Disconnected @${a.username}`)
                  }}
                />
              ))}
              <Card title="Your posts" subtitle="Sentiment of the comments on each post · click a post to read its comments">
                {!media.data ? <Spinner /> : !media.data.items.length ? (
                  <Empty>No posts imported yet. Click “Sync now”.</Empty>
                ) : (
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                    {media.data.items.map((m) => <PostCard key={m.id} post={m} onOpen={() => setOpenPost(m)} />)}
                  </div>
                )}
              </Card>
            </>
          )}
        </div>
      )}

      {openPost && <PostComments post={openPost} onClose={() => setOpenPost(null)} />}
    </div>
  )
}

function PageCard({ page: p, busy, onSync, onRemove }) {
  const [broken, setBroken] = useState(false)
  const total = (p.positive || 0) + (p.neutral || 0) + (p.negative || 0)
  const importing = !p.last_sync_at && !p.last_error
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center gap-4">
        {p.profile_pic_url && !broken ? (
          <img src={igImage(p.profile_pic_url)} alt="" referrerPolicy="no-referrer" onError={() => setBroken(true)}
               className="size-16 rounded-full border border-ink-600 object-cover" />
        ) : (
          <div className="grid size-16 place-items-center rounded-full bg-stone-50 display text-2xl font-semibold text-ink-950">
            {p.username[0]?.toUpperCase()}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <a href={`https://www.instagram.com/${p.username}/`} target="_blank" rel="noreferrer"
               className="text-lg font-semibold text-stone-50 hover:underline">{p.full_name || `@${p.username}`}</a>
            {p.verified && <BadgeCheck size={16} className="text-sky-400" />}
          </div>
          <div className="text-sm text-stone-400">@{p.username}{p.category ? ` · ${p.category}` : ''}</div>
          <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-stone-500">
            {importing ? (
              <span className="flex items-center gap-1 text-amber-400"><Loader2 size={12} className="animate-spin" /> Importing posts and comments…</span>
            ) : <span>Last checked {p.last_sync_at ? timeAgo(p.last_sync_at) : '—'}</span>}
            <span>{num(p.posts_tracked)} posts tracked</span>
          </div>
          {p.last_error && <div className="mt-1 text-xs text-red-400">{p.last_error}</div>}
        </div>
        <div className="grid grid-cols-3 gap-6 text-center">
          <Metric label="Followers" value={num(p.followers_count)} />
          <Metric label="Posts" value={num(p.posts_count)} />
          <Metric label="Comments analysed" value={num(p.analysed_comments)} />
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={onSync} disabled={busy === `psync-${p.username}` || importing}>
            {busy === `psync-${p.username}` ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Check now
          </button>
          <button className="btn-danger" onClick={onRemove} disabled={busy === `prm-${p.username}`}><Trash2 size={14} /></button>
        </div>
      </div>
      {total > 0 && (
        <div className="mt-4 border-t border-ink-700 pt-4">
          <div className="mb-1.5 flex justify-between text-xs text-stone-400">
            <span className="flex items-center gap-1"><Users size={12} /> Audience sentiment</span>
            <span>
              <span className="text-emerald-400">{Math.round((100 * p.positive) / total)}% positive</span> ·{' '}
              <span className="text-slate-300">{Math.round((100 * p.neutral) / total)}% neutral</span> ·{' '}
              <span className="text-red-400">{Math.round((100 * p.negative) / total)}% negative</span>
              {p.spam > 0 && <> · <span className="text-amber-400">{p.spam} spam</span></>}
            </span>
          </div>
          <SentimentBar positive={p.positive} neutral={p.neutral} negative={p.negative} />
          <div className="mt-3 text-xs"><Link to="/" className="link">Open the dashboard</Link> for trends, topics, anomalies and alerts on these comments.</div>
        </div>
      )}
    </div>
  )
}

function Banner({ tone, children, onClose }) {
  const cls = tone === 'green' ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : 'border-red-500/30 bg-red-500/10 text-red-200'
  return (
    <div className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-sm ${cls}`}>
      <div className="flex flex-1 flex-wrap items-center gap-2">{children}</div>
      <button onClick={onClose} className="opacity-60 hover:opacity-100"><X size={14} /></button>
    </div>
  )
}

function ConnectHero({ setup }) {
  return (
    <div className="card flex flex-col items-center justify-center p-10 text-center">
      <span className="grid size-16 place-items-center rounded-sm bg-stone-50 text-ink-950">
        <ImageIcon size={30} />
      </span>
      <h2 className="mt-5 text-lg font-semibold text-stone-50">Connect your Instagram account</h2>
      {setup.app_configured ? (
        <>
          <p className="mt-2 max-w-md text-sm text-stone-400">
            You log in on Instagram’s own page and allow BrandShield to read your posts and comments.
            BrandShield never sees your password.
          </p>
          <a href="/api/auth/instagram/login"
             className="btn-primary mt-6 px-5 py-2.5">
            <LogIn size={16} /> Continue with Instagram
          </a>
          <p className="mt-4 text-xs text-stone-500">
            Works with Instagram <b>Business</b> or <b>Creator</b> accounts (free to switch: Instagram app →
            Settings → Account type).
          </p>
        </>
      ) : (
        <p className="mt-2 max-w-md text-sm text-stone-400">
          Instagram login isn’t switched on for this installation yet. Ask whoever runs BrandShield to turn it on in{' '}
          <Link to="/setup" className="link">Server setup</Link>.
        </p>
      )}
    </div>
  )
}

function AccountCard({ account: a, busy, collector, onSync, onDisconnect }) {
  const total = (a.positive || 0) + (a.neutral || 0) + (a.negative || 0)
  const expiresDays = a.token_expires_at ? Math.round((new Date(a.token_expires_at) - Date.now()) / 86400000) : null
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center gap-4">
        {a.profile_picture_url ? (
          <img src={igImage(a.profile_picture_url)} alt="" referrerPolicy="no-referrer" className="size-16 rounded-full border border-ink-600 object-cover" />
        ) : (
          <div className="grid size-16 place-items-center rounded-full bg-stone-50 display text-2xl font-semibold text-ink-950">
            {a.username[0]?.toUpperCase()}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <a href={`https://www.instagram.com/${a.username}/`} target="_blank" rel="noreferrer" className="text-lg font-semibold text-stone-50 hover:underline">@{a.username}</a>
            {a.account_type && <span className="rounded bg-ink-700 px-1.5 py-0.5 text-[10px] uppercase text-stone-400">{a.account_type.replace('_', ' ')}</span>}
          </div>
          {a.name && <div className="text-sm text-stone-400">{a.name}</div>}
          <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-stone-500">
            <span>Last sync {a.last_sync_at ? timeAgo(a.last_sync_at) : 'pending…'}</span>
            {expiresDays !== null && <span>Token valid {expiresDays} days (auto-renewed)</span>}
            {collector?.last_error && !a.last_error && <span className="text-red-400">{collector.last_error}</span>}
          </div>
          {a.last_error && <div className="mt-1 text-xs text-red-400">{a.last_error}</div>}
        </div>
        <div className="grid grid-cols-3 gap-6 text-center">
          <Metric label="Followers" value={num(a.followers_count)} />
          <Metric label="Posts" value={num(a.media_count)} />
          <Metric label="Comments analysed" value={num(a.analysed_comments)} />
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={onSync} disabled={busy === `sync-${a.ig_user_id}`}>
            {busy === `sync-${a.ig_user_id}` ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Sync now
          </button>
          <button className="btn-danger" onClick={onDisconnect} disabled={busy === `disc-${a.ig_user_id}`}><Unplug size={14} /> Disconnect</button>
        </div>
      </div>
      {total > 0 && (
        <div className="mt-4 border-t border-ink-700 pt-4">
          <div className="mb-1.5 flex justify-between text-xs text-stone-400">
            <span>Comment sentiment</span>
            <span>
              <span className="text-emerald-400">{Math.round((100 * a.positive) / total)}% positive</span> ·{' '}
              <span className="text-slate-300">{Math.round((100 * a.neutral) / total)}% neutral</span> ·{' '}
              <span className="text-red-400">{Math.round((100 * a.negative) / total)}% negative</span>
              {a.spam > 0 && <> · <span className="text-amber-400">{a.spam} spam</span></>}
            </span>
          </div>
          <SentimentBar positive={a.positive} neutral={a.neutral} negative={a.negative} />
          <div className="mt-3 text-xs"><Link to="/" className="link">Open the dashboard</Link> for trends, topics, anomalies and alerts on these comments.</div>
        </div>
      )}
    </div>
  )
}

function Metric({ label, value }) {
  return (
    <div>
      <div className="text-lg font-semibold text-stone-50">{value}</div>
      <div className="text-[11px] text-stone-500">{label}</div>
    </div>
  )
}

function PostCard({ post: m, onOpen }) {
  const [broken, setBroken] = useState(false)
  const image = m.media_type === 'VIDEO' ? m.thumbnail_url : m.media_url
  const score = m.avg_score
  return (
    <button onClick={onOpen} className="group overflow-hidden rounded-xl border border-ink-700 bg-ink-850 text-left transition hover:border-ink-600">
      <div className="relative aspect-square bg-ink-800">
        {image && !broken ? (
          <img src={igImage(image)} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(true)}
               className="size-full object-cover transition group-hover:scale-[1.02]" />
        ) : (
          <div className="grid size-full place-items-center text-stone-600"><ImageIcon size={32} /></div>
        )}
        {score !== null && score !== undefined && m.analysed > 0 && (
          <span className={`absolute right-2 top-2 rounded-full px-2 py-0.5 text-xs font-semibold backdrop-blur ${
            score >= 0.2 ? 'bg-emerald-500/80 text-white' : score <= -0.2 ? 'bg-red-500/85 text-white' : 'bg-stone-700/85 text-stone-100'}`}>
            {score > 0 ? '+' : ''}{score.toFixed(2)}
          </span>
        )}
      </div>
      <div className="p-3">
        <p className="line-clamp-2 min-h-10 text-sm text-stone-300">{m.caption || <span className="text-stone-600">No caption</span>}</p>
        <div className="mt-2 flex items-center gap-3 text-xs text-stone-500">
          <span className="flex items-center gap-1"><Heart size={12} /> {num(m.like_count)}</span>
          <span className="flex items-center gap-1"><MessageCircle size={12} /> {num(m.comments_count)}</span>
          <span className="ml-auto">{timeAgo(m.timestamp)}</span>
        </div>
        {m.analysed > 0 && (
          <div className="mt-2"><SentimentBar positive={m.positive} neutral={m.neutral} negative={m.negative} /></div>
        )}
      </div>
    </button>
  )
}

function PostComments({ post, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    api.get(`/mentions?parent_id=${encodeURIComponent(post.id)}&limit=200&sort=oldest`).then(setData).catch((e) => setError(e.message))
  }, [post.id])
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
            <div className="text-sm font-semibold text-stone-100">Post comments</div>
            <p className="mt-1 line-clamp-3 text-xs text-stone-400">{post.caption || 'No caption'}</p>
            {post.permalink && (
              <a href={post.permalink} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 link text-xs">
                Open on Instagram <ExternalLink size={11} />
              </a>
            )}
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-100"><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <ErrorBox message={error} />
          {!data ? <Spinner /> : data.items.length ? data.items.map((m) => <MentionRow key={m.id} mention={m} />)
            : <Empty>No analysed comments on this post yet.</Empty>}
        </div>
      </div>
    </div>
  )
}
