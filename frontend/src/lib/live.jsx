import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

const LiveContext = createContext(null)

/**
 * Keeps one WebSocket connection to the backend and fans events out to
 * subscribers. Reconnects automatically.
 */
export function LiveProvider({ children }) {
  const [connected, setConnected] = useState(false)
  const [status, setStatus] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [risk, setRisk] = useState(null)
  const [toasts, setToasts] = useState([])
  const listeners = useRef(new Map())

  const subscribe = useCallback((type, fn) => {
    if (!listeners.current.has(type)) listeners.current.set(type, new Set())
    listeners.current.get(type).add(fn)
    return () => listeners.current.get(type)?.delete(fn)
  }, [])

  const dismissToast = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), [])

  useEffect(() => {
    let ws
    let retry
    let pinger
    let closed = false

    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${window.location.host}/ws`)
      ws.onopen = () => {
        setConnected(true)
        pinger = setInterval(() => ws.readyState === 1 && ws.send('ping'), 25000)
      }
      ws.onclose = () => {
        setConnected(false)
        clearInterval(pinger)
        if (!closed) retry = setTimeout(connect, 2500)
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (event) => {
        let msg
        try {
          msg = JSON.parse(event.data)
        } catch {
          return
        }
        if (msg.type === 'status') setStatus(msg.data)
        if (msg.type === 'metrics') setMetrics(msg.data)
        if (msg.type === 'risk') setRisk(msg.data)
        if (msg.type === 'alert') {
          const alert = msg.data
          const id = `${alert.id}-${Date.now()}`
          setToasts((t) => [...t.slice(-3), { id, alert }])
          setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 9000)
          if ('Notification' in window && Notification.permission === 'granted' &&
              ['high', 'critical'].includes(alert.severity)) {
            new Notification(`BrandShield AI – ${alert.severity.toUpperCase()}`, { body: alert.title })
          }
        }
        listeners.current.get(msg.type)?.forEach((fn) => fn(msg.data))
      }
    }
    connect()
    return () => {
      closed = true
      clearTimeout(retry)
      clearInterval(pinger)
      ws?.close()
    }
  }, [])

  return (
    <LiveContext.Provider value={{ connected, status, setStatus, metrics, risk, subscribe, toasts, dismissToast }}>
      {children}
    </LiveContext.Provider>
  )
}

export function useLive() {
  return useContext(LiveContext)
}

/** Subscribe to a live event type for the lifetime of the component. */
export function useLiveEvent(type, handler) {
  const { subscribe } = useLive()
  const ref = useRef(handler)
  ref.current = handler
  useEffect(() => subscribe(type, (data) => ref.current(data)), [subscribe, type])
}
