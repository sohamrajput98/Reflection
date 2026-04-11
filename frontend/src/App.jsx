import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { Cpu, History, Activity } from 'lucide-react'
import { getHealth } from './api/api' 
import AnalyzePage from './pages/AnalyzePage'
import HistoryPage from './pages/HistoryPage'

function StatusDot() {
  const [status, setStatus] = useState('checking')

  useEffect(() => {
    getHealth()
      .then(() => setStatus('online'))
      .catch(() => setStatus('offline'))
  }, [])

  const color = status === 'online' ? 'bg-emerald-400' : status === 'offline' ? 'bg-red-400' : 'bg-yellow-400'
  const label = status === 'online' ? 'Connected' : status === 'offline' ? 'Offline' : 'Connecting...'

  return (
    <div className="flex items-center gap-2 text-xs font-display text-subtle">
      <span className={`w-1.5 h-1.5 rounded-full ${color} ${status === 'online' ? 'animate-pulse-slow' : ''}`} />
      {label}
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-bg flex flex-col">
        {/* Top nav */}
        <header className="border-b border-border px-6 py-3 flex items-center justify-between sticky top-0 z-50 bg-bg/95 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-accent/20 border border-accent/30 flex items-center justify-center">
              <Cpu size={14} className="text-accent" />
            </div>
            <span className="font-body font-700 text-sm tracking-wide text-text">Campaign Intelligence</span>
          </div>

          <nav className="flex items-center gap-1">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-body font-500 transition-all ${
                  isActive ? 'bg-accent/15 text-accent' : 'text-subtle hover:text-text hover:bg-card'
                }`
              }
            >
              <Activity size={12} />
              Analyze
            </NavLink>
            <NavLink
              to="/history"
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-body font-500 transition-all ${
                  isActive ? 'bg-accent/15 text-accent' : 'text-subtle hover:text-text hover:bg-card'
                }`
              }
            >
              <History size={12} />
              History
            </NavLink>
          </nav>

          <StatusDot />
        </header>

        <main className="flex-1">
          <Routes>
            <Route path="/" element={<AnalyzePage />} />
            <Route path="/history" element={<HistoryPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}