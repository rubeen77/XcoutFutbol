import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { getEquipoDetallePagina } from '../services/api'

/* ── helpers ──────────────────────────────────────────────────────────────── */

const POS_MAP = {
  'FW': 'Delantero', 'FW,MF': 'Extremo', 'MF,FW': 'Mediapunta',
  'MF': 'Centrocampista', 'MF,DF': 'Centrocampista',
  'DF,MF': 'Defensa Central', 'DF': 'Defensa Central', 'GK': 'Portero',
}

const TEAM_COLORS = [
  '#22d3ee', '#818cf8', '#4ade80', '#fb923c', '#f472b6',
  '#a78bfa', '#34d399', '#fbbf24', '#60a5fa', '#f87171',
  '#38bdf8', '#c084fc', '#86efac', '#fcd34d', '#f9a8d4',
  '#67e8f9', '#a5b4fc', '#6ee7b7', '#fde68a', '#fca5a5',
]

function teamColor(nombre) {
  let h = 0
  for (const c of (nombre || '')) h = (h * 31 + c.charCodeAt(0)) & 0xffffff
  return TEAM_COLORS[Math.abs(h) % TEAM_COLORS.length]
}

function teamAbrev(nombre) {
  const words = (nombre || '').split(' ').filter(w => w.length > 2)
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase()
  return (nombre || '???').slice(0, 3).toUpperCase()
}

const ZONA_MAP = {
  champions:  { border: 'rgba(0,82,204,0.7)',   dot: '#3b82f6', bg: 'rgba(0,82,204,0.08)'   },
  europa:     { border: 'rgba(255,140,0,0.7)',  dot: '#f97316', bg: 'rgba(255,140,0,0.08)'  },
  conference: { border: 'rgba(0,168,107,0.7)', dot: '#10b981', bg: 'rgba(0,168,107,0.08)' },
  playoff:    { border: 'rgba(128,0,128,0.7)', dot: '#a855f7', bg: 'rgba(128,0,128,0.08)' },
  descenso:   { border: 'rgba(212,63,63,0.7)', dot: '#ef4444', bg: 'rgba(212,63,63,0.08)' },
}

function getZona(pos, ligaId = 1) {
  if (pos == null) return null
  if (ligaId === 25) {
    if (pos <= 4)   return ZONA_MAP.champions
    if (pos === 5)  return ZONA_MAP.europa
    if (pos === 6)  return ZONA_MAP.conference
    if (pos === 16) return ZONA_MAP.playoff
    if (pos >= 17)  return ZONA_MAP.descenso
    return null
  }
  if (ligaId === 24) {
    if (pos <= 5)  return ZONA_MAP.champions
    if (pos === 6) return ZONA_MAP.europa
    if (pos === 7) return ZONA_MAP.conference
    if (pos >= 18) return ZONA_MAP.descenso
    return null
  }
  if (ligaId === 27) {
    // Ligue 1: 18 equipos — 4 CL, 1 EL, 1 Conference, 16 playoff, 17-18 descenso
    if (pos <= 4)  return ZONA_MAP.champions
    if (pos === 5) return ZONA_MAP.europa
    if (pos === 6) return ZONA_MAP.conference
    if (pos === 16) return ZONA_MAP.playoff
    if (pos >= 17) return ZONA_MAP.descenso
    return null
  }
  if (ligaId === 26) {
    // Serie A: 20 equipos — 4 CL, 1 EL, 1 Conference, 18-20 descenso
    if (pos <= 4)  return ZONA_MAP.champions
    if (pos === 5) return ZONA_MAP.europa
    if (pos === 6) return ZONA_MAP.conference
    if (pos >= 18) return ZONA_MAP.descenso
    return null
  }
  // LaLiga default: 20 equipos — 4 CL, 1 EL, 1 Conference, 18-20 descenso
  if (pos <= 4)  return ZONA_MAP.champions
  if (pos === 5) return ZONA_MAP.europa
  if (pos === 6) return ZONA_MAP.conference
  if (pos >= 18) return ZONA_MAP.descenso
  return null
}

/* ── TeamShield ───────────────────────────────────────────────────────────── */
function TeamShield({ nombre, escudo_url, size = 'md' }) {
  const [errored, setErrored] = useState(false)
  const color   = teamColor(nombre)
  const abrev   = teamAbrev(nombre)
  const showImg = escudo_url && !errored
  const dim     = size === 'xs' ? 26 : size === 'sm' ? 40 : size === 'lg' ? 72 : 48
  const fs      = size === 'xs' ? '9px' : size === 'sm' ? '11px' : size === 'lg' ? '18px' : '13px'
  return (
    <div style={{
      position: 'relative', width: `${dim}px`, height: `${dim}px`, minWidth: `${dim}px`,
      flexShrink: 0, borderRadius: size === 'lg' ? '14px' : '8px', overflow: 'hidden',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 900, fontSize: fs,
      background: showImg ? 'rgba(15,23,42,0.85)' : `${color}18`,
      color, border: `1.5px solid ${color}40`,
    }}>
      {!showImg && abrev}
      {showImg && (
        <img
          src={escudo_url} alt={nombre} referrerPolicy="no-referrer"
          style={{ position: 'absolute', inset: '4px', width: 'calc(100% - 8px)', height: 'calc(100% - 8px)', objectFit: 'contain' }}
          onError={() => setErrored(true)}
        />
      )}
    </div>
  )
}

/* ── ClasificacionRow ─────────────────────────────────────────────────────── */
function ClasificacionRow({ equipo, ligaId, isCurrent, pos }) {
  const zona = getZona(pos, ligaId)

  return (
    <Link
      to={`/equipos/${equipo.id}`}
      className={`flex items-center gap-3 px-4 py-2.5 transition-colors
        hover:bg-slate-800/50 border-b border-slate-800/40 last:border-0
        ${isCurrent ? 'bg-cyan-400/5' : ''}`}
    >
      {/* Zone dot */}
      <div
        className="w-1 h-7 rounded-full shrink-0"
        style={{ background: zona ? zona.dot : 'transparent', opacity: zona ? 1 : 0 }}
      />

      {/* Position */}
      <span className="text-xs font-bold text-slate-500 w-5 text-right shrink-0 tabular-nums">
        {pos ?? '—'}
      </span>

      {/* Shield */}
      <TeamShield nombre={equipo.nombre} escudo_url={equipo.escudo_url} size="xs" />

      {/* Name */}
      <span className={`flex-1 text-sm truncate font-medium ${isCurrent ? 'text-cyan-400 font-bold' : 'text-white'}`}>
        {equipo.nombre}
      </span>

      {/* Points */}
      <span className="text-sm font-black tabular-nums shrink-0" style={{ color: isCurrent ? '#00E5FF' : '#f1f5f9' }}>
        {equipo.puntos ?? '—'}
      </span>
      <span className="text-xs text-slate-600 shrink-0 w-5">pts</span>
    </Link>
  )
}

/* ── PlantillaRow ─────────────────────────────────────────────────────────── */
function PlantillaRow({ jugador, index }) {
  const [imgErr, setImgErr] = useState(false)
  const stats    = jugador.stats || {}
  const pos      = POS_MAP[jugador.posicion] || jugador.posicion || '—'
  const initials = (jugador.nombre || '').split(' ').filter(Boolean).map(w => w[0]).join('').slice(0, 2).toUpperCase()
  const showImg  = jugador.foto_url && !imgErr

  return (
    <div
      className="flex items-center gap-3 rounded-xl p-3 border border-slate-800/60
        hover:bg-slate-800/50 hover:border-slate-700/60 transition-colors cursor-pointer animate-fade-up"
      style={{ animationDelay: `${Math.min(index * 25, 500)}ms`, background: '#0D1117' }}
    >
      {/* Avatar */}
      <div className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 overflow-hidden">
        {showImg ? (
          <img src={jugador.foto_url} alt="" className="w-full h-full object-cover" referrerPolicy="no-referrer"
               onError={() => setImgErr(true)} />
        ) : (
          <span className="text-xs font-black text-slate-400">{initials}</span>
        )}
      </div>

      {/* Name + pos */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-white truncate">{jugador.nombre}</p>
        <p className="text-xs text-slate-500">{pos}</p>
      </div>

      {/* Stats */}
      <div className="flex gap-4 text-right shrink-0">
        <div>
          <p className="text-xs font-bold text-slate-300 tabular-nums">{stats.minutos ?? 0}'</p>
          <p className="text-[10px] text-slate-600">Min</p>
        </div>
        <div>
          <p className="text-xs font-bold text-white tabular-nums">{stats.goles ?? 0}</p>
          <p className="text-[10px] text-slate-600">Goles</p>
        </div>
        <div>
          <p className="text-xs font-bold text-white tabular-nums">{stats.asistencias ?? 0}</p>
          <p className="text-[10px] text-slate-600">Asis.</p>
        </div>
        <div>
          <p className="text-xs font-bold tabular-nums" style={{ color: '#00E5FF' }}>
            {stats.xg != null ? Number(stats.xg).toFixed(1) : '—'}
          </p>
          <p className="text-[10px] text-slate-600">xG</p>
        </div>
      </div>

      <svg className="w-3.5 h-3.5 text-slate-700 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </div>
  )
}

/* ── Loading skeleton ─────────────────────────────────────────────────────── */
function Skeleton() {
  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="skeleton h-5 w-28 rounded mb-8" />
      <div className="flex items-center gap-5 mb-10">
        <div className="skeleton w-16 h-16 rounded-2xl shrink-0" />
        <div className="flex flex-col gap-2.5">
          <div className="skeleton h-7 w-48 rounded" />
          <div className="skeleton h-4 w-36 rounded" />
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-8">
        <div className="skeleton h-80 rounded-2xl" />
        <div className="flex flex-col gap-2">
          {[...Array(10)].map((_, i) => <div key={i} className="skeleton h-14 rounded-xl" />)}
        </div>
      </div>
    </main>
  )
}

/* ── Page ─────────────────────────────────────────────────────────────────── */
export default function EquipoDetalle() {
  const { id }         = useParams()
  const navigate       = useNavigate()
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(false)
    getEquipoDetallePagina(parseInt(id))
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <Skeleton />

  if (error || !data) return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <button
        onClick={() => navigate('/equipos')}
        className="flex items-center gap-1.5 text-slate-400 hover:text-cyan-400 text-sm transition-colors mb-8"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Equipos
      </button>
      <p className="text-red-400 text-sm">No se pudo cargar el equipo.</p>
    </main>
  )

  const { equipo, clasificacion, plantilla } = data
  const ligaId = equipo.liga_id

  const plantillaSorted = plantilla
    .map(j => ({ ...j, stats: (j.estadisticas_jugador || [])[0] || {} }))
    .sort((a, b) => (b.stats.goles || 0) - (a.stats.goles || 0))

  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      {/* Back */}
      <button
        onClick={() => navigate('/equipos')}
        className="flex items-center gap-1.5 text-slate-400 hover:text-cyan-400 text-sm transition-colors mb-8"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Equipos
      </button>

      {/* Header */}
      <div className="flex items-center gap-5 mb-10">
        <TeamShield nombre={equipo.nombre} escudo_url={equipo.escudo_url} size="lg" />
        <div>
          <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">{equipo.nombre}</h1>
          <p className="text-sm text-slate-400 mt-1">
            {equipo.ligas?.nombre} · 2025/26
            {equipo.posicion_clasificacion != null && (
              <span className="text-slate-300"> · {equipo.posicion_clasificacion}º clasificado</span>
            )}
            {equipo.puntos != null && (
              <span style={{ color: '#00E5FF' }}> · {equipo.puntos} pts</span>
            )}
          </p>
        </div>
      </div>

      {/* Main layout */}
      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-8 items-start">

        {/* LEFT — Clasificación */}
        <section>
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Clasificación · {equipo.ligas?.nombre}
          </h2>
          <div
            className="rounded-2xl border border-slate-800 overflow-hidden"
            style={{ background: '#0D1117' }}
          >
            {clasificacion.length > 0 ? (
              clasificacion.map((eq, i) => (
                <ClasificacionRow
                  key={eq.id}
                  equipo={eq}
                  ligaId={ligaId}
                  isCurrent={eq.id === equipo.id}
                  pos={i + 1}
                />
              ))
            ) : (
              <p className="text-slate-500 text-sm text-center py-8">Sin datos de clasificación.</p>
            )}
          </div>
        </section>

        {/* RIGHT — Plantilla */}
        <section>
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Plantilla — {plantillaSorted.length} jugadores
          </h2>
          <div className="flex flex-col gap-2">
            {plantillaSorted.length > 0 ? (
              plantillaSorted.map((j, i) => (
                <Link key={j.id} to={`/jugador/${j.id}`} className="block">
                  <PlantillaRow jugador={j} index={i} />
                </Link>
              ))
            ) : (
              <p className="text-slate-500 text-sm text-center py-8">Sin jugadores registrados.</p>
            )}
          </div>
        </section>
      </div>
    </main>
  )
}
