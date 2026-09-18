import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  ExternalLink,
  Globe,
  Heart,
  Image as ImageIcon,
  Loader2,
  KeyRound,
  LogIn,
  MessageCircle,
  Power,
  RefreshCw,
  ShieldCheck,
  Unplug,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import MentionRow from '../components/MentionRow'
import { Card, Empty, ErrorBox, SentimentBar, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { num, timeAgo } from '../lib/format'
import { useApi } from '../lib/hooks'
import { useLiveEvent } from '../lib/live'

export default function Instagram() {
  const [params, setParams] = useSearchParams()
  const status = useApi('/instagram/status', { interval: 30000 })
  const media = useApi('/instagram/media?limit=60', { interval: 60000 })
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [openPost, setOpenPost] = useState(null)

  const connected = params.get('connected')
  const loginError = params.get('error')

  useLiveEvent('mentions', (items) => {
    if (items.some((m) => m.source === 'instagram' && m.parent_id)) {
      media.reload()
      status.reload()
    }
  })
  useLiveEvent('refresh', () => {
    status.reload()
    media.reload()
  })

  async function run(key, fn, success) {
    setBusy(key)
    setError(null)
    setMessage(null)
    try {
      const r = await fn()
      if (success) setMessage(typeof success === 'function' ? success(r) : success)
      status.reload()
      media.reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  const s = status.data
  const accounts = s?.accounts || []

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-stone-50">Instagram</h1>
          <p className="text-sm text-stone-500">Connect a Business or Creator account to analyse real comments on your posts</p>
        </div>
        {accounts.length > 0 && (
          <a href="/api/auth/instagram/login" className="btn-ghost"><LogIn size={14} /> Connect another account</a>
        )}
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
      <ErrorBox message={error || status.error} />
      {message && <Banner tone="green" onClose={() => setMessage(null)}><CheckCircle2 size={16} /> {message}</Banner>}

      {!s ? <Spinner /> : (
        <>
          {accounts.length === 0 ? (
            <ConnectHero setup={s} reload={status.reload} />
          ) : (
            <>
              {s.simulated_mentions > 0 && (
                <div className="card flex flex-wrap items-center gap-3 border-amber-500/30 bg-amber-500/[0.06] p-4">
                  <AlertTriangle size={18} className="text-amber-400" />
                  <div className="flex-1 text-sm text-stone-300">
                    The dashboard still contains <b>{num(s.simulated_mentions)}</b> simulated demo mentions
                    {s.simulator_enabled ? ' and the simulator is running' : ''}. Switch to real data only?
                  </div>
                  <button
                    className="btn-primary"
                    disabled={busy === 'live'}
                    onClick={() => {
                      if (confirm('Turn off the simulator, delete all simulated mentions and alerts, and use the Instagram account name as the brand?')) {
                        run('live', () => api.post('/data/use-live-only', { confirm: true, rename_brand: true }),
                          (r) => `Removed ${num(r.deleted_simulated)} simulated mentions. The dashboard now shows only real Instagram data.`)
                      }
                    }}
                  >
                    {busy === 'live' ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />} Use only real data
                  </button>
                </div>
              )}

              {s.tunnel?.state === "running" && (
                <div className="card flex flex-wrap items-center gap-3 border-sky-500/30 bg-sky-500/[0.06] p-4">
                  <Globe size={18} className="text-sky-400" />
                  <div className="flex-1 text-sm text-stone-300">
                    Public address <span className="font-mono text-xs text-sky-300">{s.tunnel.url}</span> is live – your dashboard is
                    reachable from the internet. It is only needed while connecting an account.
                  </div>
                  <button className="btn-ghost" disabled={busy === "tunnel"}
                          onClick={() => run("tunnel", () => api.post("/instagram/tunnel/stop"), "Public address stopped")}>
                    {busy === "tunnel" ? <Loader2 size={14} className="animate-spin" /> : <Power size={14} />} Stop public address
                  </button>
                </div>
              )}

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

              <Card title="Posts" subtitle="Sentiment of the comments on each post · click a post to read its comments">
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
        </>
      )}

      {openPost && <PostComments post={openPost} onClose={() => setOpenPost(null)} />}
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

function ConnectHero({ setup, reload }) {
  const [appId, setAppId] = useState('')
  const [appSecret, setAppSecret] = useState('')
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const tunnel = setup.tunnel || {}
  const redirectUri = tunnel.redirect_uri || setup.redirect_uri
  const isHttps = redirectUri.startsWith('https://')

  async function call(key, fn) {
    setBusy(key)
    setError(null)
    try {
      await fn()
      await reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  const copy = () => {
    navigator.clipboard?.writeText(redirectUri)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="grid gap-4 xl:grid-cols-5">
      <div className="card flex flex-col items-center justify-center p-8 text-center xl:col-span-2">
        <span className="grid size-16 place-items-center rounded-2xl bg-gradient-to-br from-fuchsia-500 via-pink-500 to-amber-400 text-white shadow-lg shadow-pink-900/30">
          <ImageIcon size={30} />
        </span>
        <h2 className="mt-5 text-lg font-semibold text-stone-50">Connect your Instagram account</h2>
        <p className="mt-2 max-w-sm text-sm text-stone-400">
          You enter your Instagram username and password on Instagram’s own login page and approve read
          access to your posts and comments. BrandShield AI never sees your password.
        </p>
        {setup.app_configured ? (
          <>
            <a href="/api/auth/instagram/login"
               className="mt-6 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-fuchsia-600 via-pink-600 to-orange-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg hover:brightness-110">
              <LogIn size={16} /> Continue with Instagram
            </a>
            {!isHttps && (
              <p className="mt-3 max-w-xs text-xs text-amber-300">
                Meta usually rejects http redirect URIs. If login fails, start the secure address in step 3.
              </p>
            )}
          </>
        ) : (
          <div className="mt-6 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            Finish the 3 setup steps once, then this button works for every account.
          </div>
        )}
        <p className="mt-4 text-xs text-stone-500">
          Requires an Instagram <b>Business</b> or <b>Creator</b> account (free to switch: Instagram app →
          Settings → Account type).
        </p>
      </div>

      <Card title="One-time setup" subtitle="About 10 minutes, only needed once for this installation" className="xl:col-span-3">
        <ErrorBox message={error} />
        <ol className="mt-1 space-y-4 text-sm text-stone-300">
          <Step n={1}>
            <div className="font-medium text-stone-100">Create a Meta app</div>
            <p className="mt-1 text-stone-400">
              Open <a className="text-amber-400 hover:underline" href="https://developers.facebook.com/apps" target="_blank" rel="noreferrer">developers.facebook.com/apps</a> →
              <b> Create app</b> → use case <b>“Manage messaging and content on Instagram”</b> (type Business).
              Then open <b>Instagram → API setup with Instagram login</b> and copy the app ID and secret.
            </p>
          </Step>

          <Step n={2}>
            <div className="font-medium text-stone-100">Paste the keys here</div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <input className="input" placeholder="Instagram app ID" value={appId} onChange={(e) => setAppId(e.target.value)} />
              <input className="input" type="password" placeholder="Instagram app secret" value={appSecret} onChange={(e) => setAppSecret(e.target.value)} />
            </div>
            <div className="mt-2 flex items-center gap-3">
              <button className="btn-primary" disabled={busy === 'creds' || !appId.trim() || !appSecret.trim()}
                      onClick={() => call('creds', () => api.post('/instagram/credentials', { app_id: appId.trim(), app_secret: appSecret.trim() }))}>
                {busy === 'creds' ? <Loader2 size={14} className="animate-spin" /> : <KeyRound size={14} />} Save keys
              </button>
              {setup.app_configured && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 size={13} /> Saved to backend/.env</span>}
            </div>
          </Step>

          <Step n={3}>
            <div className="font-medium text-stone-100">Give Instagram an address it can reach</div>
            <p className="mt-1 text-stone-400">
              Meta only accepts <b>https</b> redirect URIs, which a laptop on 127.0.0.1 cannot provide.
              This starts a free Cloudflare tunnel for you (downloads a small helper the first time).
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {tunnel.state === 'running' ? (
                <button className="btn-ghost" disabled={busy === 'tunnel'} onClick={() => call('tunnel', () => api.post('/instagram/tunnel/stop'))}>
                  {busy === 'tunnel' ? <Loader2 size={14} className="animate-spin" /> : <Power size={14} />} Stop secure address
                </button>
              ) : (
                <button className="btn-ghost" disabled={busy === 'tunnel'} onClick={() => call('tunnel', () => api.post('/instagram/tunnel/start'))}>
                  {busy === 'tunnel' ? <Loader2 size={14} className="animate-spin" /> : <Globe size={14} />}
                  {tunnel.binary_present ? 'Start secure address' : 'Download helper & start'}
                </button>
              )}
              {tunnel.state === 'running' && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 size={13} /> {tunnel.url}</span>}
              {tunnel.state === 'downloading' && <span className="text-xs text-stone-400">Downloading cloudflared…</span>}
              {tunnel.error && <span className="text-xs text-red-400">{tunnel.error}</span>}
            </div>
            <p className="mt-3 text-stone-400">Copy this <b>OAuth redirect URI</b> into the Meta app (Instagram → Business login settings):</p>
            <div className="mt-1.5 flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-3 py-2 font-mono text-xs text-stone-200">
              <span className="flex-1 break-all">{redirectUri}</span>
              <button className="text-stone-400 hover:text-amber-300" onClick={copy}>{copied ? <CheckCircle2 size={14} /> : <Copy size={14} />}</button>
            </div>
            {tunnel.state === 'running' && (
              <p className="mt-2 text-xs text-amber-300">
                While this address is live your dashboard is reachable from the internet by anyone who knows the
                link. Stop it once the account is connected – the connection keeps working without it.
              </p>
            )}
          </Step>

          <Step n={4}>
            <div className="font-medium text-stone-100">Allow your account to log in</div>
            <p className="mt-1 text-stone-400">
              A Meta app in <b>development mode</b> only accepts accounts listed as testers – any other account gets
              <b> “Insufficient developer role”</b>. Two steps, both required:
            </p>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-stone-400">
              <li>
                In the Meta app: <b>App roles → Roles → Add people → Instagram tester</b>, search the Instagram
                username and send the invite.
              </li>
              <li>
                Accept it as that account at{" "}
                <a className="text-amber-400 hover:underline" href="https://www.instagram.com/accounts/manage_access/" target="_blank" rel="noreferrer">
                  instagram.com/accounts/manage_access
                </a>{" "}
                → <b>Tester invites</b> → <b>Accept</b>. (App → Settings → Apps and websites on mobile.)
              </li>
            </ol>
            <p className="mt-2 text-stone-400">
              The account must also be <b>Business</b> or <b>Creator</b>. For anyone outside the tester list, submit the app
              for <b>App Review</b> with <code className="mx-1 text-stone-200">instagram_business_basic</code> and
              <code className="mx-1 text-stone-200">instagram_business_manage_comments</code>.
            </p>
          </Step>
        </ol>
      </Card>
    </div>
  )
}

function Step({ n, children }) {
  return (
    <li className="flex gap-3">
      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-amber-500/15 text-xs font-semibold text-amber-300">{n}</span>
      <div className="min-w-0 flex-1 pt-0.5">{children}</div>
    </li>
  )
}

function AccountCard({ account: a, busy, collector, onSync, onDisconnect }) {
  const total = (a.positive || 0) + (a.neutral || 0) + (a.negative || 0)
  const expiresDays = a.token_expires_at ? Math.round((new Date(a.token_expires_at) - Date.now()) / 86400000) : null
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center gap-4">
        {a.profile_picture_url ? (
          <img src={a.profile_picture_url} alt="" referrerPolicy="no-referrer" className="size-16 rounded-full border-2 border-pink-500/60 object-cover" />
        ) : (
          <div className="grid size-16 place-items-center rounded-full bg-gradient-to-br from-fuchsia-500 to-amber-400 text-xl font-semibold text-white">
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
              {a.spam > 0 && <> · <span className="text-orange-300">{a.spam} spam</span></>}
            </span>
          </div>
          <SentimentBar positive={a.positive} neutral={a.neutral} negative={a.negative} />
          <div className="mt-3 text-xs"><Link to="/" className="text-amber-400 hover:underline">Open the dashboard</Link> for trends, aspects, anomalies and alerts on these comments.</div>
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
          <img src={image} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(true)}
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
    <div className="fixed inset-0 z-40 flex justify-end bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="flex h-full w-full max-w-xl flex-col border-l border-ink-700 bg-ink-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-3 border-b border-ink-700 p-4">
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-stone-100">Post comments</div>
            <p className="mt-1 line-clamp-3 text-xs text-stone-400">{post.caption || 'No caption'}</p>
            {post.permalink && (
              <a href={post.permalink} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs text-amber-400 hover:underline">
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
