import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { applyChartTheme } from './charts'

// Light ("paper") or dark ("night edition"). The choice is remembered per browser;
// "system" follows the operating system setting.
const STORAGE_KEY = 'brandshield-theme'
const ThemeContext = createContext(null)

function readStored() {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

function systemPrefersDark() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches
}

export { cssVar } from './cssvar'

function apply(resolved) {
  const root = document.documentElement
  root.dataset.theme = resolved
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', resolved === 'dark' ? '#141311' : '#F4F0E8')
  applyChartTheme()
}

export function ThemeProvider({ children }) {
  const [choice, setChoiceState] = useState(readStored)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)
  const resolved = choice === 'system' ? (systemDark ? 'dark' : 'light') : choice

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!mq) return undefined
    const onChange = (e) => setSystemDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  // applied during render as well, so charts drawn in this render already see the new colours
  if (typeof document !== 'undefined' && document.documentElement.dataset.theme !== resolved) apply(resolved)

  const setChoice = useCallback((value) => {
    setChoiceState(value)
    try {
      if (value === 'system') localStorage.removeItem(STORAGE_KEY)
      else localStorage.setItem(STORAGE_KEY, value)
    } catch {
      // storage blocked: the choice still applies for this visit
    }
  }, [])

  const toggle = useCallback(() => setChoice(resolved === 'dark' ? 'light' : 'dark'), [resolved, setChoice])

  return (
    <ThemeContext.Provider value={{ choice, resolved, setChoice, toggle }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
