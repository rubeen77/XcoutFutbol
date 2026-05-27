import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getEquipos } from '../services/api'
import { useLiga } from '../contexts/LigaContext'
import UCLEliminatorias from '../components/UCLEliminatorias'

/* ── helpers ──────────────────────────────────────────────────────────────── */

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

/* ── Zone logic ───────────────────────────────────────────────────────────── */
const ZONA_MAP = {
  champions:    { label: 'Champions',        bg: 'rgba(0,82,204,0.15)',    border: 'rgba(0,82,204,0.4)',    badge: 'rgba(29,78,216,0.55)',  text: '#bfdbfe' },
  ascenso:      { label: 'Ascenso directo',  bg: 'rgba(16,185,129,0.15)',  border: 'rgba(16,185,129,0.4)',  badge: 'rgba(6,95,70,0.55)',    text: '#a7f3d0' },
  europa:       { label: 'Europa League',    bg: 'rgba(255,140,0,0.15)',   border: 'rgba(255,140,0,0.4)',   badge: 'rgba(180,83,9,0.55)',   text: '#fed7aa' },
  conference:   { label: 'Conference',       bg: 'rgba(0,168,107,0.15)',   border: 'rgba(0,168,107,0.4)',  badge: 'rgba(6,95,70,0.55)',    text: '#a7f3d0' },
  playoff:      { label: 'Playoff',          bg: 'rgba(128,0,128,0.15)',   border: 'rgba(128,0,128,0.4)',  badge: 'rgba(88,28,135,0.55)',  text: '#e9d5ff' },
  descenso:     { label: 'Descenso',         bg: 'rgba(212,63,63,0.15)',   border: 'rgba(212,63,63,0.4)',  badge: 'rgba(153,27,27,0.55)',  text: '#fecaca' },
  ucl_octavos:  { label: 'Octavos directos', bg: 'rgba(16,185,129,0.10)',  border: 'rgba(16,185,129,0.30)', badge: 'rgba(6,78,59,0.70)',   text: '#6ee7b7' },
  ucl_playoff:  { label: 'Playoff',          bg: 'rgba(234,179,8,0.10)',   border: 'rgba(234,179,8,0.30)',  badge: 'rgba(113,63,18,0.70)', text: '#fde68a' },
  ucl_eliminado:{ label: 'Eliminado',        bg: 'rgba(239,68,68,0.09)',   border: 'rgba(239,68,68,0.28)',  badge: 'rgba(127,29,29,0.70)', text: '#fca5a5' },
}

const ZONA_OVERRIDE = { 'Real Sociedad': ZONA_MAP.europa }

function getZona(pos, nombre, ligaId = 1) {
  if (ligaId === 28) {
    if (pos == null) return null
    if (pos <= 8)  return ZONA_MAP.ucl_octavos
    if (pos <= 24) return ZONA_MAP.ucl_playoff
    return ZONA_MAP.ucl_eliminado
  }
  if (ligaId === 1 && nombre && ZONA_OVERRIDE[nombre]) return ZONA_OVERRIDE[nombre]
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
  if (ligaId === 33) {
    if (pos <= 2) return ZONA_MAP.ascenso
    if (pos <= 6) return ZONA_MAP.playoff
    if (pos >= 19) return ZONA_MAP.descenso
    return null
  }
  if (ligaId === 29) {
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
  const dim     = size === 'sm' ? 40 : 48
  const fs      = size === 'sm' ? '11px' : '13px'
  return (
    <div style={{
      position: 'relative', width: `${dim}px`, height: `${dim}px`, minWidth: `${dim}px`,
      flexShrink: 0, borderRadius: '10px', overflow: 'hidden',
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

/* ── PlayerMini (top goleadores dentro de la card) ───────────────────────── */
function PlayerMini({ jugador }) {
  const [errored, setErrored] = useState(false)
  const initials = (jugador.nombre || '')
    .split(' ').filter(Boolean).map(w => w[0]).join('').slice(0, 2).toUpperCase()
  const apellido = (jugador.nombre || '').split(' ').pop()

  return (
    <div className="flex items-center gap-1 bg-slate-800/70 rounded-lg px-1.5 py-1 shrink-0">
      <div className="w-5 h-5 rounded-full bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center shrink-0 overflow-hidden">
        {jugador.foto_url && !errored ? (
          <img
            src={jugador.foto_url} alt="" referrerPolicy="no-referrer"
            className="w-full h-full object-cover"
            onError={() => setErrored(true)}
          />
        ) : (
          <span className="text-[8px] font-black text-cyan-400">{initials}</span>
        )}
      </div>
      <span className="text-[10px] text-slate-400 truncate max-w-[56px]">{apellido}</span>
      <span className="text-[11px] font-black text-white ml-0.5">{jugador.goles}</span>
    </div>
  )
}

/* ── TeamCard ─────────────────────────────────────────────────────────────── */
function TeamCard({ equipo, liga = { id: 1 }, pos }) {
  const navigate = useNavigate()
  const color    = teamColor(equipo.nombre)
  const zona     = getZona(pos, equipo.nombre, liga.id)
  const topGoleadores = equipo.top_goleadores || []

  return (
    <button
      onClick={() => navigate(`/equipos/${equipo.id}`)}
      className="relative w-full text-left rounded-2xl border transition-all duration-200
        hover:scale-[1.02] hover:shadow-lg hover:shadow-slate-950/60 hover:brightness-110"
      style={{
        background:  zona ? zona.bg     : '#0f172a',
        borderColor: zona ? zona.border : 'rgba(30,41,59,1)',
        borderWidth:  '1px',
        borderStyle:  'solid',
      }}
    >
      {/* Badge zona */}
      {zona && (
        <span
          className="absolute top-2.5 right-2.5 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full"
          style={{ background: zona.badge, color: zona.text }}
        >
          {zona.label}
        </span>
      )}

      <div className="p-4">
        {/* Header: escudo + posición + nombre + puntos */}
        <div className="flex items-center gap-3">
          <TeamShield nombre={equipo.nombre} escudo_url={equipo.escudo_url} size="sm" />
          <div className="flex-1 min-w-0 pr-20">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className="text-xs font-bold rounded-full px-2 py-0.5 shrink-0"
                style={{ background: `${color}18`, color }}
              >
                {pos}º
              </span>
              <p className="text-sm font-bold text-white truncate">{equipo.nombre}</p>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              {equipo.puntos != null ? `${equipo.puntos} pts` : liga.nombre || ''}
            </p>
          </div>
        </div>

        {/* Top 3 goleadores */}
        {topGoleadores.length > 0 && (
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-700/40">
            <span className="text-slate-500 text-xs shrink-0">⚽</span>
            <div className="flex gap-1.5 flex-wrap">
              {topGoleadores.map(g => (
                <PlayerMini key={g.id} jugador={g} />
              ))}
            </div>
          </div>
        )}
      </div>
    </button>
  )
}

/* ── Skeleton ─────────────────────────────────────────────────────────────── */
function EquiposSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
          <div className="flex items-center gap-4 mb-3">
            <div className="skeleton w-10 h-10 rounded-xl shrink-0" />
            <div className="flex-1 flex flex-col gap-2">
              <div className="skeleton h-3 w-28 rounded" />
              <div className="skeleton h-2.5 w-16 rounded" />
            </div>
          </div>
          <div className="flex gap-2">
            {[0, 1, 2].map(j => <div key={j} className="skeleton h-7 w-24 rounded-lg" />)}
          </div>
        </div>
      ))}
    </div>
  )
}

/* ── UCL Legend ───────────────────────────────────────────────────────────── */
const UCL_LEGEND = [
  { zona: ZONA_MAP.ucl_octavos,   rango: '1–8',   desc: 'Clasificados directos a octavos de final' },
  { zona: ZONA_MAP.ucl_playoff,   rango: '9–24',  desc: 'Acceden a la ronda de playoff' },
  { zona: ZONA_MAP.ucl_eliminado, rango: '25–36', desc: 'Eliminados de todas las competiciones europeas' },
]

function UCLLegend() {
  return (
    <div className="mt-5 rounded-2xl border border-slate-800/60 bg-slate-900/40 px-5 py-4">
      <p className="text-[11px] font-black uppercase tracking-widest text-slate-500 mb-3">Leyenda</p>
      <div className="flex flex-col sm:flex-row gap-2.5">
        {UCL_LEGEND.map(({ zona, rango, desc }) => (
          <div
            key={rango}
            className="flex items-center gap-3 flex-1 rounded-xl px-3 py-2.5"
            style={{ background: zona.bg, border: `1px solid ${zona.border}` }}
          >
            <span
              className="text-[11px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap shrink-0"
              style={{ background: zona.badge, color: zona.text }}
            >
              {rango}
            </span>
            <div>
              <p className="text-xs font-semibold" style={{ color: zona.text }}>{zona.label}</p>
              <p className="text-[11px] text-slate-500 leading-tight mt-0.5">{desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Page ─────────────────────────────────────────────────────────────────── */
export default function Equipos() {
  const { ligaId, ligaActual } = useLiga()
  const [listaEquipos, setListaEquipos] = useState([])
  const [errorLista, setErrorLista]     = useState(false)
  const [loadingLista, setLoadingLista] = useState(true)

  useEffect(() => {
    setListaEquipos([])
    setLoadingLista(true)
    setErrorLista(false)
    getEquipos(ligaId)
      .then(data => setListaEquipos(data.equipos || []))
      .catch(() => setErrorLista(true))
      .finally(() => setLoadingLista(false))
  }, [ligaId])

  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      <div className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
          Equipos <span className="text-cyan-400">{ligaActual.nombre}</span>
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Temporada 2025/26 · {listaEquipos.length} equipos
        </p>
      </div>

      {/* ── Sección: Fase de Liga ── */}
      {ligaId === 28 && (
        <div className="flex items-center gap-3 mb-5">
          <h2 className="text-lg font-black text-white tracking-tight whitespace-nowrap">Fase de Liga</h2>
          <div className="flex-1 h-px bg-slate-800" />
          <span className="text-[11px] text-slate-600 whitespace-nowrap">36 equipos</span>
        </div>
      )}

      {loadingLista ? (
        <EquiposSkeleton />
      ) : errorLista ? (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/5 px-6 py-8 text-center">
          <p className="text-red-400 font-semibold text-sm">No se pudieron cargar los equipos.</p>
          <p className="text-slate-500 text-xs mt-1">Verifica que el backend está corriendo en localhost:8001.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {listaEquipos.map((equipo, i) => (
              <div key={equipo.id} className="animate-fade-up" style={{ animationDelay: `${i * 40}ms` }}>
                <TeamCard equipo={equipo} liga={ligaActual} pos={i + 1} />
              </div>
            ))}
          </div>
          {ligaId === 28 && <UCLLegend />}
        </>
      )}

      {/* ── Sección: Eliminatorias (solo Champions) ── */}
      {ligaId === 28 && (
        <>
          <div className="flex items-center gap-3 mt-10 mb-6">
            <h2 className="text-lg font-black text-white tracking-tight whitespace-nowrap">Eliminatorias</h2>
            <div className="flex-1 h-px bg-slate-800" />
            <span className="text-[10px] font-bold px-2.5 py-1 rounded-full
                             bg-cyan-400/8 text-cyan-400/70 border border-cyan-400/15">
              UCL 25/26
            </span>
          </div>
          <UCLEliminatorias ligaId={ligaId} />
        </>
      )}
    </main>
  )
}
