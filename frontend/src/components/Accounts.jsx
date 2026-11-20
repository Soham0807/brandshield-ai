import { KeyRound, Shield, Trash2, User } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { useAuth } from './AuthGate'
import { Card } from './ui'

const fmt = (ts) => (ts ? new Date(ts * 1000).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : 'never')

/** "Your account" (everyone) + "Users" (admins only). Renders nothing when login is disabled. */
export default function Accounts() {
  const { authEnabled, isAdmin } = useAuth()
  if (!authEnabled) return null
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <ChangePassword />
      {isAdmin && <UserList />}
    </div>
  )
}

function ChangePassword() {
  const { username, role } = useAuth()
  const [form, setForm] = useState({ current: '', next: '', confirm: '' })
  const [status, setStatus] = useState(null) // { ok, text }
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    if (form.next !== form.confirm) return setStatus({ ok: false, text: 'The new passwords do not match.' })
    setBusy(true)
    setStatus(null)
    try {
      await api.post('/auth/password', { current_password: form.current, new_password: form.next })
      setForm({ current: '', next: '', confirm: '' })
      setStatus({ ok: true, text: 'Password changed. Other devices have been signed out.' })
    } catch (err) {
      setStatus({ ok: false, text: err.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Your account" subtitle={`Signed in as ${username} · ${role}`}>
      <form onSubmit={submit}>
        <label className="label" htmlFor="pw-cur">Current password</label>
        <input id="pw-cur" type="password" className="input" autoComplete="current-password" value={form.current} onChange={set('current')} required />
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="pw-new">New password</label>
            <input id="pw-new" type="password" className="input" autoComplete="new-password" value={form.next} onChange={set('next')} required />
          </div>
          <div>
            <label className="label" htmlFor="pw-conf">Confirm new password</label>
            <input id="pw-conf" type="password" className="input" autoComplete="new-password" value={form.confirm} onChange={set('confirm')} required />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button type="submit" className="btn-ghost" disabled={busy}><KeyRound size={14} /> {busy ? 'Changing…' : 'Change password'}</button>
          {status && <span className={`text-sm ${status.ok ? 'text-emerald-400' : 'text-red-400'}`}>{status.text}</span>}
        </div>
      </form>
    </Card>
  )
}

function UserList() {
  const { username: me } = useAuth()
  const { data, error, reload } = useApi('/auth/users')
  const [actionError, setActionError] = useState(null)

  async function run(fn) {
    setActionError(null)
    try {
      await fn()
      reload()
    } catch (err) {
      setActionError(err.message)
    }
  }

  const users = data?.users || []
  return (
    <Card title="Users" subtitle="Admins can change settings and data. Viewers can only look and analyse text. People who sign up start as viewers.">
      {error && <p className="text-sm text-red-400">{error}</p>}
      <ul className="divide-y divide-ink-700">
        {users.map((u) => {
          const self = u.username.toLowerCase() === me?.toLowerCase()
          return (
            <li key={u.username} className="flex flex-wrap items-center gap-3 py-2.5">
              {u.role === 'admin' ? <Shield size={15} className="text-stone-50" /> : <User size={15} className="text-stone-500" />}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-stone-50">{u.username}{self && <span className="ml-1.5 font-normal text-stone-500">(you)</span>}</p>
                <p className="text-xs text-stone-500">Joined {fmt(u.created_at)} · last sign-in {fmt(u.last_login)}</p>
              </div>
              <select className="input w-auto py-1 text-xs" value={u.role} disabled={self}
                      aria-label={`Role of ${u.username}`}
                      onChange={(e) => run(() => api.put(`/auth/users/${encodeURIComponent(u.username)}`, { role: e.target.value }))}>
                <option value="admin">Admin</option>
                <option value="viewer">Viewer</option>
              </select>
              <button type="button" className="btn-ghost px-2 py-1" disabled={self} title={self ? 'You cannot delete yourself' : `Delete ${u.username}`}
                      onClick={() => window.confirm(`Delete the account "${u.username}"?`) &&
                        run(() => api.del(`/auth/users/${encodeURIComponent(u.username)}`))}>
                <Trash2 size={13} />
              </button>
            </li>
          )
        })}
      </ul>
      {actionError && <p className="mt-2 text-sm text-red-400">{actionError}</p>}
    </Card>
  )
}
