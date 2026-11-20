import { Lock, LogIn, UserPlus } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { LogoMark, Wordmark } from './Brand'

const AuthContext = createContext({ authEnabled: false, username: null, role: 'admin', isAdmin: true, logout: () => {}, refresh: () => {} })
export const useAuth = () => useContext(AuthContext)

/** Shows the sign-in / sign-up screen until the backend confirms a session (or login is disabled). */
export default function AuthGate({ children }) {
  const [session, setSession] = useState(null) // null = still checking
  const [checkError, setCheckError] = useState('')

  const check = useCallback(() => {
    api.get('/auth/session')
      .then((s) => { setSession(s); setCheckError('') })
      .catch((e) => setCheckError(e.message || 'Cannot reach the BrandShield server.'))
  }, [])

  useEffect(() => { check() }, [check])

  // Any API call answering 401 (e.g. the session expired) sends the user back to the sign-in screen
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
      <div className="flex min-h-screen items-center justify-center bg-ink-950 px-4 text-center">
        {checkError
          ? <div><p className="text-sm text-red-400">{checkError}</p><button className="btn-ghost mt-4" onClick={check}>Retry</button></div>
          : <p className="font-mono text-xs uppercase tracking-[.14em] text-stone-500">Connecting…</p>}
      </div>
    )
  }
  if (session.auth_enabled && !session.authenticated) {
    return <AuthForm signupAllowed={session.signup_allowed}
                     onSuccess={(s) => setSession({ ...session, authenticated: true, username: s.username, role: s.role })} />
  }
  const value = {
    authEnabled: session.auth_enabled,
    username: session.username,
    role: session.role,
    isAdmin: session.role === 'admin',
    logout,
    refresh: check,
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

function AuthForm({ signupAllowed, onSuccess }) {
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const registering = mode === 'register'

  const switchMode = () => {
    setMode(registering ? 'login' : 'register')
    setError('')
    setPassword('')
    setConfirm('')
  }

  const submit = async (e) => {
    e.preventDefault()
    if (registering && password !== confirm) {
      setError('The two passwords do not match.')
      return
    }
    setBusy(true)
    setError('')
    try {
      onSuccess(await api.post(registering ? '/auth/register' : '/auth/login', { username, password }))
    } catch (err) {
      setError(err.message)
      setPassword('')
      setConfirm('')
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
          <Lock size={11} /> {registering ? 'Create a viewer account' : 'Sign in to the brand risk desk'}
        </p>

        <label className="label" htmlFor="bs-user">Username</label>
        <input id="bs-user" className="input" autoComplete="username" autoFocus value={username}
               onChange={(e) => setUsername(e.target.value)} required />

        <label className="label mt-4" htmlFor="bs-pass">Password</label>
        <input id="bs-pass" type="password" className="input" autoComplete={registering ? 'new-password' : 'current-password'}
               value={password} onChange={(e) => setPassword(e.target.value)} required />

        {registering && (
          <>
            <label className="label mt-4" htmlFor="bs-confirm">Confirm password</label>
            <input id="bs-confirm" type="password" className="input" autoComplete="new-password"
                   value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
            <p className="mt-2 text-xs text-stone-500">
              At least 8 characters, mixing letters with digits or symbols. New accounts are read-only viewers until an admin grants edit access.
            </p>
          </>
        )}

        {error && <p role="alert" className="mt-3 text-sm text-red-400">{error}</p>}

        <button type="submit" className="btn-primary mt-6 w-full justify-center" disabled={busy}>
          {registering ? <UserPlus size={14} /> : <LogIn size={14} />}
          {busy ? (registering ? 'Creating account…' : 'Signing in…') : (registering ? 'Create account' : 'Sign in')}
        </button>

        {signupAllowed && (
          <p className="mt-4 text-center text-sm text-stone-500">
            {registering ? 'Already have an account? ' : 'New here? '}
            <button type="button" onClick={switchMode} className="font-semibold text-stone-50 underline-offset-2 hover:underline">
              {registering ? 'Sign in' : 'Create an account'}
            </button>
          </p>
        )}
      </form>
    </div>
  )
}
