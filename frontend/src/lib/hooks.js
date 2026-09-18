import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'

/**
 * Fetch JSON from the API, re-fetching when `path` changes and optionally on
 * an interval. `reload()` forces a refresh (used by live events).
 */
export function useApi(path, { interval = 0, enabled = true } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const current = useRef(path)
  current.current = path

  const reload = useCallback(async () => {
    if (!path || !enabled) return
    try {
      const result = await api.get(path)
      if (current.current === path) {
        setData(result)
        setError(null)
      }
    } catch (err) {
      if (current.current === path) setError(err.message)
    } finally {
      if (current.current === path) setLoading(false)
    }
  }, [path, enabled])

  useEffect(() => {
    setLoading(true)
    reload()
    if (!interval) return
    const id = setInterval(reload, interval)
    return () => clearInterval(id)
  }, [reload, interval])

  return { data, error, loading, reload, setData }
}

/** Run `fn` at most once every `wait` ms (trailing call guaranteed). */
export function useThrottle(fn, wait) {
  const last = useRef(0)
  const timer = useRef(null)
  const fnRef = useRef(fn)
  fnRef.current = fn
  useEffect(() => () => clearTimeout(timer.current), [])
  return useCallback(() => {
    const now = Date.now()
    const remaining = wait - (now - last.current)
    if (remaining <= 0) {
      last.current = now
      fnRef.current()
    } else if (!timer.current) {
      timer.current = setTimeout(() => {
        timer.current = null
        last.current = Date.now()
        fnRef.current()
      }, remaining)
    }
  }, [wait])
}
