import { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { getEquipos, getEquipoDetalle } from '../services/api'

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

function rachaColor(r) {
  if (r === 'W') return 'bg-emerald-500 text-white'
  if (r === 'D') return 'bg-amber-400 text-slate-900'
  return 'bg-red-500 text-white'
}

function rachaLabel(r) {
  if (r === 'W') return 'V'
  if (r === 'D') return 'E'
  return 'D'
}

function computeStandings(partidos_local = [], partidos_visitante = []) {
  const all = [
    ...partidos_local
      .filter(p => p.goles_local != null && p.goles_visitante != null)
      .map(p => ({ jornada: p.jornada ?? 999, gf: p.goles_local, gc: p.goles_visitante })),
    ...partidos_visitante
      .filter(p => p.goles_local != null && p.goles_visitante != null)
      .map(p => ({ jornada: p.jornada ?? 999, gf: p.goles_visitante, gc: p.goles_local })),
  ].sort((a, b) => a.jornada - b.jornada)

  let pts = 0
  const results = []
  const puntos_jornada = []

  for (const p of all) {
    if (p.gf > p.gc)        { results.push('W'); pts += 3 }
    else if (p.gf === p.gc) { results.push('D'); pts += 1 }
    else                    { results.push('L') }
    puntos_jornada.push(pts)
  }

  return {
    partidos:      all.length,
    victorias:     results.filter(r => r === 'W').length,
    empates:       results.filter(r => r === 'D').length,
    derrotas:      results.filter(r => r === 'L').length,
    racha:         results.slice(-5),
    puntos_jornada,
    puntos:        pts,
  }
}

function adaptarPlantilla(j) {
  const stats = (j.estadisticas_jugador || [])[0] || {}
  return {
    id:       j.id,
    nombre:   j.nombre,
    posicion: POS_MAP[j.posicion] || j.posicion || '',
    metricas: {
      goles:        stats.goles        || 0,
      asistencias:  stats.asistencias  || 0,
      xG:           stats.xg           || 0,
    },
  }
}

/* ── custom tooltip ───────────────────────────────────────────────────────── */
function PtsTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs">
      <p className="text-slate-400 mb-0.5">J{label}</p>
      <p className="text-cyan-400 font-bold text-sm">{payload[0].value} pts</p>
    </div>
  )
}

/* ── TeamShield ───────────────────────────────────────────────────────────── */
function TeamShield({ nombre, escudo_url, size = 'md' }) {
  const [errored, setErrored] = useState(false)
  const color   = teamColor(nombre)
  const abrev   = teamAbrev(nombre)
  const showImg = escudo_url && !errored
  const sz  = size === 'sm' ? 'w-10 h-10 text-xs' : 'w-12 h-12 text-sm'
  return (
    <div
      className={`relative ${sz} rounded-xl flex items-center justify-center shrink-0 font-black overflow-hidden`}
      style={{ background: `${color}18`, color, border: `1.5px solid ${color}40` }}
    >
      {!showImg && abrev}
      {showImg && (
        <img src={escudo_url} alt={nombre} referrerPolicy="no-referrer"
             className="absolute inset-0 w-full h-full object-contain p-1"
             onError={() => setErrored(true)} />
      )}
    </div>
  )
}

/* ── StatBlock ────────────────────────────────────────────────────────────── */
function StatBlock({ label, value, sub, accent }) {
  return (
    <div className="bg-slate-800/50 border border-slate-700/60 rounded-xl p-3 flex flex-col gap-0.5">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-2xl font-black tabular-nums leading-none" style={{ color: accent || '#f1f5f9' }}>
        {value ?? '—'}
      </span>
      {sub && <span className="text-xs text-slate-600">{sub}</span>}
    </div>
  )
}

/* ── PlayerRow ────────────────────────────────────────────────────────────── */
function PlayerRow({ jugador, index }) {
  const m = jugador.metricas
  return (
    <div
      className="flex items-center gap-3 bg-slate-800/40 border border-slate-700/50 rounded-xl p-3 animate-fade-up"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="w-8 h-8 rounded-full bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center shrink-0">
        <span className="text-xs font-black text-cyan-400">
          {jugador.nombre.split(' ').map(w => w[0]).join('').slice(0, 2)}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-white truncate">{jugador.nombre}</p>
        <p className="text-xs text-slate-500">{jugador.posicion}</p>
      </div>
      <div className="flex gap-4 text-right shrink-0">
        <div>
          <p className="text-sm font-bold text-white tabular-nums">{m.goles}</p>
          <p className="text-[10px] text-slate-500">Goles</p>
        </div>
        <div>
          <p className="text-sm font-bold text-white tabular-nums">{m.asistencias}</p>
          <p className="text-[10px] text-slate-500">Asis.</p>
        </div>
        <div>
          <p className="text-sm font-bold text-cyan-400 tabular-nums">{(m.xG ?? 0).toFixed(1)}</p>
          <p className="text-[10px] text-slate-500">xG</p>
        </div>
      </div>
    </div>
  )
}

/* ── TeamCard ─────────────────────────────────────────────────────────────── */
const ZONA_MAP = {
  champions:  { label: 'Champions',      bg: 'rgba(0,82,204,0.15)',   border: 'rgba(0,82,204,0.4)',   badge: 'rgba(0,82,204,0.25)',   text: '#60a5fa' },
  europa:     { label: 'Europa League',  bg: 'rgba(255,140,0,0.15)',  border: 'rgba(255,140,0,0.4)',  badge: 'rgba(255,140,0,0.25)',  text: '#fb923c' },
  conference: { label: 'Conference',     bg: 'rgba(0,168,107,0.15)',  border: 'rgba(0,168,107,0.4)', badge: 'rgba(0,168,107,0.25)', text: '#34d399' },
  descenso:   { label: 'Descenso',       bg: 'rgba(212,63,63,0.15)',  border: 'rgba(212,63,63,0.4)', badge: 'rgba(212,63,63,0.25)', text: '#f87171' },
}

const ZONA_OVERRIDE = {
  'Real Sociedad': ZONA_MAP.europa,
}

function getZona(pos, nombre) {
  if (nombre && ZONA_OVERRIDE[nombre]) return ZONA_OVERRIDE[nombre]
  if (pos == null)      return null
  if (pos <= 4)         return ZONA_MAP.champions
  if (pos === 5)        return ZONA_MAP.europa
  if (pos === 6)        return ZONA_MAP.conference
  if (pos >= 18)        return ZONA_MAP.descenso
  return null
}

function TeamCard({ equipo, selected, onClick }) {
  const color = teamColor(equipo.nombre)
  const abrev = teamAbrev(equipo.nombre)
  const zona  = getZona(equipo.posicion_clasificacion, equipo.nombre)

  const cardBg     = zona ? zona.bg     : undefined
  const cardBorder = selected
    ? 'rgba(34,211,238,0.6)'
    : zona ? zona.border : undefined

  return (
    <button
      onClick={onClick}
      className={`relative w-full text-left rounded-2xl border transition-all duration-200
        hover:scale-[1.02] hover:shadow-lg hover:shadow-slate-950/60
        ${!zona && !selected ? 'bg-slate-900 border-slate-800 hover:bg-slate-800/70 hover:border-slate-700' : ''}
        ${selected && !zona ? 'border-cyan-500/60 shadow-md shadow-cyan-950/40 bg-slate-900' : ''}`}
      style={zona || selected ? {
        background:  cardBg   ?? '#0f172a',
        borderColor: cardBorder,
        borderWidth: '1px',
        borderStyle: 'solid',
      } : undefined}
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

      <div className="p-4 flex items-center gap-4">
        {/* Shield */}
        <TeamShield nombre={equipo.nombre} escudo_url={equipo.escudo_url} />

        {/* Nombre + posición */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {equipo.posicion_clasificacion != null && (
              <span
                className="text-xs font-bold rounded-full px-2 py-0.5 shrink-0"
                style={{ background: `${color}18`, color }}
              >
                #{equipo.posicion_clasificacion}
              </span>
            )}
            <p className="text-sm font-semibold text-white truncate">{equipo.nombre}</p>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            {equipo.puntos != null ? `${equipo.puntos} pts` : 'LaLiga 2025/26'}
          </p>
        </div>

        {/* Chevron */}
        <div className="flex items-center shrink-0">
          <svg
            className={`w-4 h-4 transition-transform duration-200 ${selected ? 'rotate-180 text-cyan-400' : 'text-slate-600'}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
    </button>
  )
}

/* ── TeamModal ────────────────────────────────────────────────────────────── */
function TeamModal({ equipo, detalle, loading, onClose }) {
  const zona        = getZona(equipo.posicion_clasificacion, equipo.nombre)
  const borderColor = zona ? zona.border : 'rgba(0,229,255,0.45)'

  // Cerrar con Escape
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  // Bloquear scroll del body mientras el modal está abierto
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  const color = teamColor(equipo.nombre)
  const abrev = teamAbrev(equipo.nombre)

  const { nombre, plantilla = [], totales_temporada = {}, partidos_local = [], partidos_visitante = [] } =
    detalle ?? {}

  const { partidos, victorias, empates, derrotas, racha, puntos_jornada, puntos } =
    computeStandings(partidos_local, partidos_visitante)

  const jugadoresAdaptados = plantilla
    .map(adaptarPlantilla)
    .sort((a, b) => b.metricas.goles - a.metricas.goles)

  const chartData = puntos_jornada.map((pts, i) => ({ j: i + 1, pts }))

  return (
    /* Overlay */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(2,6,23,0.80)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      {/* Panel modal */}
      <div
        className="animate-modal-in relative flex flex-col rounded-2xl overflow-hidden
                   w-[90vw] max-w-[600px] max-h-[88vh]"
        style={{ background: '#0D1117', border: `1px solid ${borderColor}` }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header fijo */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3">
            <TeamShield nombre={equipo.nombre} escudo_url={equipo.escudo_url} size="sm" />
            <div>
              <h2 className="text-base font-bold text-white">{equipo.nombre}</h2>
              <p className="text-xs text-slate-500">
                Temporada 25/26
                {!loading && detalle && ` · ${partidos} partidos · ${puntos} pts`}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-slate-800 transition-colors shrink-0"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Contenido scrollable */}
        <div className="overflow-y-auto flex-1 p-5 flex flex-col gap-6">
          {loading ? (
            <>
              <div className="skeleton h-4 w-40 rounded" />
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-20 rounded-xl" />)}
              </div>
              <div className="skeleton h-32 rounded-xl" />
            </>
          ) : !detalle ? (
            <p className="text-slate-500 text-sm text-center py-8">No hay datos disponibles.</p>
          ) : (
            <>
              {/* Stats grid */}
              <div>
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Estadísticas</h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  <StatBlock label="Goles"       value={totales_temporada.goles}               accent="#4ade80" />
                  <StatBlock label="Asistencias" value={totales_temporada.asistencias}          accent="#22d3ee" />
                  <StatBlock label="xG"          value={totales_temporada.xg?.toFixed(1)}       accent="#818cf8" />
                  <StatBlock label="xA"          value={totales_temporada.xa?.toFixed(1)}       accent="#fb923c" />
                </div>
              </div>

              {/* W / D / L */}
              {partidos > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Resultados</h3>
                  <div className="flex gap-2">
                    <div className="flex-1 bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 text-center">
                      <p className="text-2xl font-black text-emerald-400">{victorias}</p>
                      <p className="text-xs text-slate-400 mt-0.5">Victorias</p>
                    </div>
                    <div className="flex-1 bg-amber-400/10 border border-amber-400/20 rounded-xl p-3 text-center">
                      <p className="text-2xl font-black text-amber-400">{empates}</p>
                      <p className="text-xs text-slate-400 mt-0.5">Empates</p>
                    </div>
                    <div className="flex-1 bg-red-500/10 border border-red-500/20 rounded-xl p-3 text-center">
                      <p className="text-2xl font-black text-red-400">{derrotas}</p>
                      <p className="text-xs text-slate-400 mt-0.5">Derrotas</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Racha últimos 5 */}
              {racha.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                    Últimos {racha.length} partidos
                  </h3>
                  <div className="flex gap-2">
                    {racha.map((r, i) => (
                      <div key={i} className={`flex-1 rounded-xl py-2 flex flex-col items-center gap-1 ${rachaColor(r)}`}>
                        <span className="text-sm font-black">{rachaLabel(r)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Evolución de puntos */}
              {chartData.length > 1 && (
                <div>
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Evolución de puntos</h3>
                  <div className="h-44">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                        <XAxis
                          dataKey="j"
                          tick={{ fill: '#64748b', fontSize: 10 }}
                          tickLine={false} axisLine={false}
                          interval={3}
                          tickFormatter={v => `J${v}`}
                        />
                        <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
                        <Tooltip content={<PtsTooltip />} cursor={{ stroke: '#334155', strokeWidth: 1 }} />
                        <Line
                          type="monotone" dataKey="pts" stroke={color} strokeWidth={2} dot={false}
                          activeDot={{ r: 4, fill: color, stroke: '#020617', strokeWidth: 2 }}
                          isAnimationActive animationDuration={800} animationEasing="ease-out"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Plantilla */}
              {jugadoresAdaptados.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                    Plantilla — {jugadoresAdaptados.length} jugadores
                  </h3>
                  <div className="flex flex-col gap-2">
                    {jugadoresAdaptados.slice(0, 10).map((j, i) => (
                      <PlayerRow key={j.id} jugador={j} index={i} />
                    ))}
                    {jugadoresAdaptados.length > 10 && (
                      <p className="text-xs text-slate-600 text-center pt-1">
                        +{jugadoresAdaptados.length - 10} jugadores más
                      </p>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── Skeleton ─────────────────────────────────────────────────────────────── */
function EquiposSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="rounded-2xl border border-slate-800 bg-slate-900 p-4 flex items-center gap-4">
          <div className="skeleton w-12 h-12 rounded-xl shrink-0" />
          <div className="flex-1 flex flex-col gap-2">
            <div className="skeleton h-3 w-28 rounded" />
            <div className="skeleton h-2.5 w-20 rounded" />
          </div>
          <div className="skeleton w-4 h-4 rounded shrink-0" />
        </div>
      ))}
    </div>
  )
}

/* ── Page ─────────────────────────────────────────────────────────────────── */
export default function Equipos() {
  const [listaEquipos, setListaEquipos]     = useState([])
  const [errorLista, setErrorLista]         = useState(false)
  const [selected, setSelected]             = useState(null)
  const [detalle, setDetalle]               = useState(null)
  const [loadingLista, setLoadingLista]     = useState(true)
  const [loadingDetalle, setLoadingDetalle] = useState(false)

  const selectedEquipo = listaEquipos.find(e => e.id === selected) ?? null

  // Cargar lista de equipos
  useEffect(() => {
    getEquipos()
      .then(data => setListaEquipos(data.equipos || []))
      .catch(() => setErrorLista(true))
      .finally(() => setLoadingLista(false))
  }, [])

  // Cargar perfil cuando se selecciona un equipo
  useEffect(() => {
    if (!selected) { setDetalle(null); return }
    setLoadingDetalle(true)
    setDetalle(null)
    getEquipoDetalle(selected)
      .then(setDetalle)
      .catch(() => setDetalle(null))
      .finally(() => setLoadingDetalle(false))
  }, [selected])

  const handleSelect = (id) => setSelected(id)
  const handleClose  = ()  => setSelected(null)

  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      <div className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
          Equipos <span className="text-cyan-400">LaLiga</span>
        </h1>
        <p className="text-sm text-slate-500 mt-1">Temporada 2025/26 · {listaEquipos.length} equipos</p>
      </div>

      {loadingLista ? (
        <EquiposSkeleton />
      ) : errorLista ? (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/5 px-6 py-8 text-center">
          <p className="text-red-400 font-semibold text-sm">No se pudieron cargar los equipos.</p>
          <p className="text-slate-500 text-xs mt-1">Verifica que el backend está corriendo en localhost:8000.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {listaEquipos.map((equipo, i) => (
              <div key={equipo.id} className="animate-fade-up" style={{ animationDelay: `${i * 40}ms` }}>
                <TeamCard
                  equipo={equipo}
                  selected={selected === equipo.id}
                  onClick={() => handleSelect(equipo.id)}
                />
              </div>
            ))}
          </div>

          {selected && selectedEquipo && (
            <TeamModal
              key={selected}
              equipo={selectedEquipo}
              detalle={detalle}
              loading={loadingDetalle}
              onClose={handleClose}
            />
          )}
        </div>
      )}
    </main>
  )
}
