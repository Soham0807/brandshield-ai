import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import AuthGate from './components/AuthGate'
import Layout from './components/Layout'
import './index.css'
import './lib/charts'
import { LiveProvider } from './lib/live'
import { ThemeProvider } from './lib/theme'
import Alerts from './pages/Alerts'
import Analytics from './pages/Analytics'
import Analyze from './pages/Analyze'
import Aspects from './pages/Aspects'
import Dashboard from './pages/Dashboard'
import Instagram from './pages/Instagram'
import Mentions from './pages/Mentions'
import Report from './pages/Report'
import SettingsPage from './pages/Settings'
import Setup from './pages/Setup'
import YouTube from './pages/YouTube'
import System from './pages/System'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
    <AuthGate>
    <LiveProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="mentions" element={<Mentions />} />
            <Route path="instagram" element={<Instagram />} />
            <Route path="youtube" element={<YouTube />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="aspects" element={<Aspects />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="analyze" element={<Analyze />} />
            <Route path="report" element={<Report />} />
            <Route path="system" element={<System />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="setup" element={<Setup />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </LiveProvider>
    </AuthGate>
    </ThemeProvider>
  </StrictMode>,
)
