import { Lock, LogIn } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { LogoMark, Wordmark } from './Brand'

const AuthContext = createContext({ authEnabled: false, username: null, logout: () => {} })
export const useAuth = () => useContext(AuthContext)

/** Shows the login screen until the backend confirms a session (or login is disabled). */
export default function AuthGate({ children }) {
  const [session, setSession] = useState(null) // null = still checking
  const [checkError, setCheckError] = useState('')

  const check = useCallback(() => {
    api.get('/auth/session')
      .then((s) => { setSession(s); setCheckError('') })
      .catch((e) => setCheckError(e.message || 'Cannot reach the BrandShield server.'))
  }, [])

  useEffect(() => { check() }, [check])

  // Any API call answering 401 (e.g. the session expired) sends the user back to the login screen
  useEffect(() => {
    const onUnauthorized = () => setSession((s) => (s?.auth_enabled ? { ...s, authenticated: false } : s))
    window.addEventListener('brandshield:unauthorized', onUnauthorized)
    return () => window.removeEventListener('brandshield:unauthorized', onUnauthorized)
  }, [])

  const logout = useCallback(async () => {
    try { await api.post('/auth/logout') } finally { window.location.assign('/') }
  }, [])

  if (!session) {
    return (
      <Centered>
        {checkError
          ? <><p className="text-sm text-red-400">{checkError}</p><button className="btn-ghost mt-4" onClick={check}>Retry</button></>
          : <p className="font-mono text-xs uppercase tracking-[.14em] text-stone-500">Connecting…</p>}
      </Centered>
    )
  }
  if (session.auth_enabled && !session.authenticated) {
    return <LoginForm onSuccess={(s) => setSession({ auth_enabled: true, authenticated: true, username: s.username })} />
  }
  return (
    <AuthContext.Provider value={{ authEnabled: session.auth_enabled, username: session.username, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

function Centered({ children }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-950 px-4">
      <div className="w-full max-w-sm text-center">{children}</div>
    </div>
  )
}

function LoginForm({ onSuccess }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      onSuccess(await api.post('/auth/login', { username, password }))
    } catch (err) {
      setError(err.message)
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-950 px-4">
      <form onSubmit={submit} className="w-full max-w-sm border border-ink-700 bg-ink-900 p-7">
        <div className="mb-6 flex items-center gap-2.5">
          <LogoMark size={36} />
          <Wordmark className="text-[26px]" />
        </div>
        <p className="mb-5 flex items-center gap-1.5 font-mono text-[10.5px] uppercase tracking-[.14em] text-stone-500">
          <Lock size={11} /> Sign in to the brand risk desk
        </p>
        <label className="label" htmlFor="bs-user">Username</label>
        <input id="bs-user" className="input" autoComplete="username" value={username}
               onChange={(e) => setUsername(e.target.value)} required />
        <label className="label mt-4" htmlFor="bs-pass">Password</label>
        <input id="bs-pass" type="password" className="input" autoComplete="current-password" autoFocus
               value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <p role="alert" className="mt-3 text-sm text-red-400">{error}</p>}
        <button type="submit" className="btn-primary mt-6 w-full justify-center" disabled={busy}>
          <LogIn size={14} /> {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
