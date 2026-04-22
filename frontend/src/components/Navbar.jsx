import { useState, useRef, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'

function XcoutLogo() {
  return (
    <svg viewBox="0 0 40 40" className="w-9 h-9" fill="none" aria-hidden="true">
      <defs>
        {/* Gradient for \ diagonal — cyan ends, white center */}
        <linearGradient id="xg1" x1="11" y1="11" x2="29" y2="29" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#22d3ee" stopOpacity="0.55" />
          <stop offset="48%"  stopColor="#e0faff" stopOpacity="1" />
          <stop offset="52%"  stopColor="#ffffff"  stopOpacity="1" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.55" />
        </linearGradient>
        {/* Gradient for / diagonal */}
        <linearGradient id="xg2" x1="29" y1="11" x2="11" y2="29" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#22d3ee" stopOpacity="0.55" />
          <stop offset="48%"  stopColor="#e0faff" stopOpacity="1" />
          <stop offset="52%"  stopColor="#ffffff"  stopOpacity="1" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.55" />
        </linearGradient>
        {/* Radial glow at the crossing */}
        <radialGradient id="xglow" cx="50%" cy="50%" r="50%">
          <stop offset="0%"   stopColor="#ffffff"  stopOpacity="0.85" />
          <stop offset="45%"  stopColor="#67e8f9"  stopOpacity="0.25" />
          <stop offset="100%" stopColor="#22d3ee"  stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Outer dashed scope ring — suggests scouting/targeting */}
      <circle
        cx="20" cy="20" r="17.5"
        stroke="#22d3ee" strokeWidth="0.7" strokeOpacity="0.18"
        strokeDasharray="3.5 4.5" fill="none"
      />
      {/* Inner solid ring — very subtle */}
      <circle
        cx="20" cy="20" r="11.5"
        stroke="#22d3ee" strokeWidth="0.5" strokeOpacity="0.09"
        fill="none"
      />

      {/* X arm 1: top-left → bottom-right */}
      <line
        x1="11.5" y1="11.5" x2="28.5" y2="28.5"
        stroke="url(#xg1)" strokeWidth="1.9" strokeLinecap="round"
      />
      {/* X arm 2: top-right → bottom-left */}
      <line
        x1="28.5" y1="11.5" x2="11.5" y2="28.5"
        stroke="url(#xg2)" strokeWidth="1.9" strokeLinecap="round"
      />

      {/* Soft glow halo at intersection */}
      <circle cx="20" cy="20" r="5.5" fill="url(#xglow)" />
      {/* Hard bright center dot */}
      <circle cx="20" cy="20" r="1.3" fill="white" fillOpacity="0.92" />
    </svg>
  )
}

const CLUBES = [
  {
    categoria: 'España',
    ligas: ['LaLiga', 'LaLiga Hypermotion', 'Copa del Rey'],
  },
  {
    categoria: 'Europa',
    ligas: ['Champions League', 'Europa League', 'Conference League'],
  },
  {
    categoria: 'Inglaterra',
    ligas: ['Premier League', 'Championship', 'FA Cup', 'Carabao Cup'],
  },
  {
    categoria: 'Grandes Ligas',
    ligas: ['Bundesliga', 'Serie A', 'Ligue 1'],
  },
  {
    categoria: 'Latinoamérica',
    ligas: ['Liga MX', 'Liga Profesional', 'Brasileirão', 'Primera División', 'Liga BetPlay', 'Copa Libertadores', 'Copa Sudamericana'],
  },
  {
    categoria: 'Otros',
    ligas: ['MLS', 'Saudi Pro League'],
  },
]

const SELECCIONES = [
  {
    categoria: 'Europa',
    ligas: ['Eurocopa', 'UEFA Nations League', 'Clasificación Eurocopa'],
  },
  {
    categoria: 'Sudamérica',
    ligas: ['Copa América', 'Eliminatorias Sudamericanas'],
  },
  {
    categoria: 'Mundial',
    ligas: ['Mundial FIFA', 'Clasificación Mundial'],
  },
]

const LIGAS = [...CLUBES, ...SELECCIONES]

function LigaGrupo({ categoria, ligas, ligaSel, onSelect }) {
  return (
    <div>
      <p className="px-4 pt-2.5 pb-1 text-[10px] font-bold text-slate-600
                    uppercase tracking-widest select-none">
        {categoria}
      </p>
      {ligas.map(liga => (
        <button
          key={liga}
          onClick={() => onSelect(liga)}
          className={`w-full text-left px-4 py-2 text-sm font-medium
                      transition-colors duration-100 ${
            liga === ligaSel
              ? 'text-cyan-400 bg-cyan-400/5'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/70'
          }`}
        >
          {liga === ligaSel && (
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400 mr-2 mb-0.5" />
          )}
          {liga}
        </button>
      ))}
    </div>
  )
}

const links = [
  { to: '/', label: 'Jugadores' },
  { to: '/scouting', label: 'Scouting' },
  { to: '/equipos', label: 'Equipos' },
  { to: '/partidos', label: 'Partidos' },
  { to: '/insights', label: 'Insights' },
]

export default function Navbar() {
  const [open, setOpen] = useState(false)
  const [ligaOpen, setLigaOpen] = useState(false)
  const [ligaSel, setLigaSel] = useState('LaLiga')
  const [backendOk, setBackendOk] = useState(null)
  const dropRef = useRef(null)
  const { pathname } = useLocation()

  useEffect(() => {
    function ping() {
      fetch('http://localhost:8080/health')
        .then(r => setBackendOk(r.ok))
        .catch(() => setBackendOk(false))
    }
    ping()
    const id = setInterval(ping, 30000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    function handleClick(e) {
      if (dropRef.current && !dropRef.current.contains(e.target)) {
        setLigaOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <nav className="sticky top-0 z-50 bg-slate-950/90 backdrop-blur-md border-b border-slate-800/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 group">
            <XcoutLogo />
            <span
              className="text-[1.2rem] font-black tracking-tight select-none"
              style={{ letterSpacing: '-0.03em' }}
            >
              <span
                className="text-cyan-400"
                style={{ textShadow: '0 0 18px rgba(34,211,238,0.55), 0 0 6px rgba(34,211,238,0.3)' }}
              >
                X
              </span>
              <span
                className="text-white font-semibold"
                style={{ letterSpacing: '-0.01em' }}
              >
                cout
              </span>
            </span>
            {/* Backend status dot */}
            <div className="relative group/dot ml-0.5 flex items-center">
              <span
                className={`block w-1.5 h-1.5 rounded-full ${
                  backendOk === true
                    ? 'bg-green-400 animate-pulse'
                    : backendOk === false
                    ? 'bg-red-500'
                    : 'bg-slate-600'
                }`}
              />
              <div className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-4
                             opacity-0 group-hover/dot:opacity-100 transition-opacity duration-150
                             whitespace-nowrap bg-slate-800 border border-slate-700 text-slate-300
                             text-[11px] font-medium px-2 py-1 rounded-lg shadow-lg z-50">
                {backendOk === true ? 'Backend conectado' : backendOk === false ? 'Backend desconectado' : 'Comprobando...'}
              </div>
            </div>
          </Link>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-1">
            {links.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className={`relative px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                  pathname === to
                    ? 'text-cyan-400'
                    : 'text-slate-500 hover:text-slate-200'
                }`}
              >
                {label}
                {pathname === to && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-0.5 bg-cyan-400 rounded-full" />
                )}
              </Link>
            ))}
          </div>

          {/* Selector de liga */}
          <div className="hidden md:flex items-center gap-2 relative" ref={dropRef}>
            <button
              onClick={() => setLigaOpen(v => !v)}
              className="flex items-center gap-2 text-xs font-semibold text-slate-300
                         border border-slate-800 hover:border-cyan-400/40 hover:text-cyan-400
                         rounded-full px-3 py-1.5 transition-all duration-150 group"
            >
              <svg className="w-3 h-3 text-slate-500 group-hover:text-cyan-400 transition-colors"
                   fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" strokeWidth="2" />
                <path strokeWidth="2" strokeLinecap="round"
                      d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10
                         15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z" />
              </svg>
              {ligaSel}
              <svg className={`w-3 h-3 text-slate-600 transition-transform duration-150 ${ligaOpen ? 'rotate-180' : ''}`}
                   fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {ligaOpen && (
              <div className="absolute top-full right-0 mt-2 w-56
                             bg-slate-900 border border-slate-800 rounded-2xl
                             shadow-2xl shadow-black/40 overflow-hidden z-50
                             max-h-[70vh] overflow-y-auto scrollbar-hide">

                {/* Sección CLUBES */}
                <p className="px-4 pt-3 pb-1 text-[10px] font-black text-slate-500
                              uppercase tracking-widest select-none">
                  Clubes
                </p>
                {CLUBES.map(({ categoria, ligas }) => (
                  <LigaGrupo key={categoria} categoria={categoria} ligas={ligas}
                             ligaSel={ligaSel} onSelect={liga => { setLigaSel(liga); setLigaOpen(false) }} />
                ))}

                {/* Divisor SELECCIONES */}
                <div className="mx-3 my-2 flex items-center gap-2">
                  <div className="flex-1 h-px bg-slate-700/60" />
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest
                                   px-2 py-0.5 rounded-full border border-slate-700/60 select-none
                                   bg-slate-800/60 whitespace-nowrap">
                    Selecciones
                  </span>
                  <div className="flex-1 h-px bg-slate-700/60" />
                </div>

                {/* Sección SELECCIONES */}
                {SELECCIONES.map(({ categoria, ligas }) => (
                  <LigaGrupo key={categoria} categoria={categoria} ligas={ligas}
                             ligaSel={ligaSel} onSelect={liga => { setLigaSel(liga); setLigaOpen(false) }} />
                ))}
                <div className="h-2" />
              </div>
            )}
          </div>

          {/* Mobile burger */}
          <button
            onClick={() => setOpen(!open)}
            className="md:hidden p-2 rounded-lg text-slate-500 hover:text-white hover:bg-slate-800 transition-colors"
          >
            {open ? (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden border-t border-slate-800/60 bg-slate-950/95 backdrop-blur-md">
          {links.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              className={`flex items-center justify-between px-5 py-3.5 text-sm font-medium transition-colors ${
                pathname === to
                  ? 'text-cyan-400 bg-cyan-400/5'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              {label}
              {pathname === to && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />}
            </Link>
          ))}

          {/* Liga selector móvil */}
          <div className="border-t border-slate-800/60 px-4 py-3">
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1 px-1">
              Clubes
            </p>
            <div className="max-h-56 overflow-y-auto scrollbar-hide">
              {CLUBES.map(({ categoria, ligas }) => (
                <LigaGrupo key={categoria} categoria={categoria} ligas={ligas}
                           ligaSel={ligaSel} onSelect={liga => { setLigaSel(liga); setOpen(false) }} />
              ))}

              {/* Divisor móvil */}
              <div className="flex items-center gap-2 my-2 px-1">
                <div className="flex-1 h-px bg-slate-700/60" />
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest
                                 px-2 py-0.5 rounded-full border border-slate-700/60 bg-slate-800/60
                                 select-none whitespace-nowrap">
                  Selecciones
                </span>
                <div className="flex-1 h-px bg-slate-700/60" />
              </div>

              {SELECCIONES.map(({ categoria, ligas }) => (
                <LigaGrupo key={categoria} categoria={categoria} ligas={ligas}
                           ligaSel={ligaSel} onSelect={liga => { setLigaSel(liga); setOpen(false) }} />
              ))}
            </div>
          </div>
        </div>
      )}
    </nav>
  )
}
