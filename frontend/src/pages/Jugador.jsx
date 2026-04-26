import { useState, useMemo, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts'
import { jugadores as jugadoresFallback } from '../data/jugadores'
import { getJugador } from '../services/api'
import PlayerRadarChart from '../components/RadarChart'
import { JugadorSkeleton } from '../components/Skeletons'
import { useCountUp } from '../hooks/useCountUp'

// ─── Constantes ──────────────────────────────────────────────────────────────
const THRESHOLDS = {
  goles:             { max: 35,   good: 20,  ok: 8  },
  asistencias:       { max: 20,   good: 12,  ok: 5  },
  xG:                { max: 28,   good: 15,  ok: 6  },
  xA:                { max: 15,   good: 8,   ok: 3  },
  pases_completados: { max: 95,   good: 85,  ok: 74 },
  regates:           { max: 120,  good: 60,  ok: 25 },
  recuperaciones:    { max: 80,   good: 40,  ok: 18 },
  goles_por_90:      { max: 1.2,  good: 0.6, ok: 0.3 },
  asistencias_por_90:{ max: 0.8,  good: 0.4, ok: 0.2 },
  ga_por_90:         { max: 1.8,  good: 0.9, ok: 0.5 },
}

const METRICA_LABELS = {
  goles: 'Goles', asistencias: 'Asistencias', xG: 'xG', xA: 'xA',
  pases_completados: 'Pases %', regates: 'Regates',
  recuperaciones: 'Recuperaciones',
  minutos_jugados: 'Minutos jugados',
  goles_por_90: 'Goles / 90 min',
  asistencias_por_90: 'Asistencias / 90 min',
  ga_por_90: 'G+A / 90 min',
}

const SIN_BARRA = new Set(['minutos_jugados'])

const p90 = (val, min) => +(((val / min) * 90).toFixed(2))

// ─── Mapeo posición FBref → español ──────────────────────────────────────────
const POS_MAP = {
  'FW': 'Delantero', 'FW,MF': 'Extremo', 'MF,FW': 'Mediapunta',
  'MF': 'Centrocampista', 'MF,DF': 'Centrocampista',
  'DF,MF': 'Defensa Central', 'DF': 'Defensa Central', 'GK': 'Portero',
}

function fmtTemporada(t) {
  if (t && t.length === 4) return `${t.slice(0, 2)}/${t.slice(2)}`
  return t ?? ''
}

function adaptarPerfilJugador(raw) {
  const stats = raw.estadisticas_jugador || []
  const sortedStats = [...stats].sort((a, b) => (a.temporada ?? '').localeCompare(b.temporada ?? ''))
  const latest = sortedStats.at(-1) || {}
  const temporadaActual = latest.temporada ?? null

  const estadisticas_por_temporada = sortedStats.length > 0
    ? sortedStats.map(s => {
        const goles  = s.goles        ?? null
        const asists = s.asistencias  ?? null
        const mins   = s.minutos      ?? null
        return {
          temporada:          fmtTemporada(s.temporada),
          actual:             s.temporada === temporadaActual,
          equipo:             raw.equipos?.nombre || '',
          goles,
          asistencias:        asists,
          xG:                 s.xg               ?? null,
          xA:                 s.xa               ?? null,
          pases_completados:  s.pases_completados ?? null,
          regates:            s.regates           ?? null,
          recuperaciones:     s.recuperaciones    ?? null,
          minutos_jugados:    mins,
          goles_por_90:       s.goles_por_90        ?? (mins && goles != null ? p90(goles, mins)          : null),
          asistencias_por_90: s.asistencias_por_90  ?? (mins && asists != null ? p90(asists, mins)        : null),
          ga_por_90:          s.ga_por_90            ?? (mins && goles != null && asists != null ? p90(goles + asists, mins) : null),
        }
      })
    : null

  const minutos = latest.minutos || 0
  const goles   = latest.goles   || 0
  const asis    = latest.asistencias || 0

  const metricas = {
    goles,
    asistencias:        asis,
    xG:                 latest.xg           || 0,
    xA:                 latest.xa           || 0,
    pases_completados:  latest.pases_completados || 0,
    regates:            latest.regates      || 0,
    recuperaciones:     latest.recuperaciones || 0,
    minutos_jugados:    minutos,
    goles_por_90:       latest.goles_por_90        ?? p90(goles, minutos),
    asistencias_por_90: latest.asistencias_por_90  ?? p90(asis, minutos),
    ga_por_90:          latest.ga_por_90           ?? p90(goles + asis, minutos),
  }

  const evolucion_valor = (raw.valor_mercado_historia || []).length > 0
    ? [...raw.valor_mercado_historia]
        .sort((a, b) => (a.temporada ?? '').localeCompare(b.temporada ?? ''))
        .map(h => ({ temporada: fmtTemporada(h.temporada), valor: h.valor }))
    : null

  return {
    id:           raw.id,
    nombre:       raw.nombre,
    posicion:     POS_MAP[raw.posicion] || raw.posicion || '',
    edad:         raw.edad   || 0,
    nacionalidad: raw.nacionalidad || '',
    foto_url:     raw.foto_url     || null,
    valor_mercado: raw.valor_mercado ?? null,
    equipo:       raw.equipos?.nombre || '',
    metricas,
    estadisticas_por_temporada,
    evolucion_valor,
    carrera:         null,
    ultimos_partidos: null,
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function metricColor(key, value) {
  const t = THRESHOLDS[key]
  if (!t) return 'text-slate-300'
  if (value >= t.good) return 'text-cyan-400'
  if (value >= t.ok)   return 'text-amber-400'
  return 'text-red-400'
}

function getInitials(nombre) {
  return nombre.split(' ').slice(0, 2).map(n => n[0]).join('').toUpperCase()
}

// Construye un objeto metricas completo a partir de una fila del historial
// Coerce null → 0 para que radar/barras no reciban NaN
function metricasDesdeTemporada(t) {
  const g   = t.goles           ?? 0
  const a   = t.asistencias     ?? 0
  const min = t.minutos_jugados ?? 0
  return {
    goles:              g,
    asistencias:        a,
    xG:                 t.xG               ?? 0,
    xA:                 t.xA               ?? 0,
    pases_completados:  t.pases_completados ?? 0,
    regates:            t.regates           ?? 0,
    recuperaciones:     t.recuperaciones    ?? 0,
    minutos_jugados:    min,
    goles_por_90:       t.goles_por_90        ?? (min ? p90(g, min) : 0),
    asistencias_por_90: t.asistencias_por_90  ?? (min ? p90(a, min) : 0),
    ga_por_90:          t.ga_por_90            ?? (min ? p90(g + a, min) : 0),
  }
}

// ─── Marca de agua para capturas de pantalla ─────────────────────────────────
function Watermark() {
  return (
    <div className="absolute top-3 right-4 flex items-center gap-1.5 pointer-events-none select-none"
         style={{ opacity: 0.2 }}>
      {/* Mini X */}
      <svg viewBox="0 0 14 14" className="w-3 h-3" fill="none">
        <defs>
          <linearGradient id="wg1" x1="2" y1="2" x2="12" y2="12" gradientUnits="userSpaceOnUse">
            <stop offset="0%"   stopColor="#22d3ee" stopOpacity="0.7" />
            <stop offset="50%"  stopColor="#ffffff" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.7" />
          </linearGradient>
          <linearGradient id="wg2" x1="12" y1="2" x2="2" y2="12" gradientUnits="userSpaceOnUse">
            <stop offset="0%"   stopColor="#22d3ee" stopOpacity="0.7" />
            <stop offset="50%"  stopColor="#ffffff" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.7" />
          </linearGradient>
        </defs>
        <circle cx="7" cy="7" r="6"
          stroke="#22d3ee" strokeWidth="0.6" strokeOpacity="0.5"
          strokeDasharray="2.5 3" fill="none" />
        <line x1="3" y1="3" x2="11" y2="11" stroke="url(#wg1)" strokeWidth="1.6" strokeLinecap="round" />
        <line x1="11" y1="3" x2="3" y2="11" stroke="url(#wg2)" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="7" cy="7" r="0.9" fill="white" fillOpacity="0.95" />
      </svg>
      <span className="text-white text-[10px] font-black tracking-tight"
            style={{ letterSpacing: '-0.02em' }}>
        Xcout
      </span>
    </div>
  )
}

// ─── Sub-componentes ─────────────────────────────────────────────────────────
function BarTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 shadow-2xl">
      <p className="text-slate-400 text-xs font-semibold mb-2 uppercase tracking-wider">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 text-sm">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.fill }} />
          <span className="text-slate-400 capitalize">{p.name}</span>
          <span className="font-black text-white ml-auto pl-4">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

const TIPO_META = {
  traspaso: { label: null,       color: null },
  libre:    { label: 'Libre',    color: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20' },
  cesion:   { label: 'Cedido',   color: 'text-amber-400  bg-amber-400/10  border-amber-400/20'  },
  cantera:  { label: 'Cantera',  color: 'text-slate-400  bg-slate-800     border-slate-700'     },
}

function TimelineItem({ item, isLast }) {
  const meta = TIPO_META[item.tipo] ?? TIPO_META.cantera
  return (
    <div className="flex gap-4">
      {/* Dot + line */}
      <div className="flex flex-col items-center shrink-0">
        <div className={`w-3 h-3 rounded-full border-2 mt-0.5 shrink-0 transition-colors ${
          item.actual
            ? 'bg-cyan-400 border-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.5)]'
            : 'bg-slate-900 border-slate-600'
        }`} />
        {!isLast && <div className="w-px flex-1 bg-slate-800 mt-1 min-h-[2rem]" />}
      </div>

      {/* Content */}
      <div className={`flex-1 pb-6 ${isLast ? 'pb-0' : ''}`}>
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className={`font-bold text-sm leading-tight ${item.actual ? 'text-white' : 'text-slate-300'}`}>
                {item.club}
              </p>
              {item.actual && (
                <span className="text-[10px] font-bold text-cyan-400 bg-cyan-400/10
                                 border border-cyan-400/20 px-1.5 py-0.5 rounded-full">
                  Actual
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5 tabular-nums">{item.temporadas}</p>
            {item.valor != null && (
              <p className="text-[11px] text-slate-600 mt-0.5 tabular-nums">
                Valor: €{item.valor}M
              </p>
            )}
          </div>

          {/* Badge / cantidad */}
          <div className="shrink-0">
            {item.tipo === 'traspaso' && item.cantidad != null ? (
              <span className="text-cyan-400 font-black text-sm tabular-nums">
                €{item.cantidad}M
              </span>
            ) : meta.label ? (
              <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${meta.color}`}>
                {meta.label}
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Últimos partidos ─────────────────────────────────────────────────────────
function notaMeta(nota) {
  if (nota >= 7) return { text: 'text-emerald-400', bg: 'bg-emerald-400/10 border-emerald-400/20' }
  if (nota >= 5) return { text: 'text-amber-400',   bg: 'bg-amber-400/10  border-amber-400/20'  }
  return             { text: 'text-red-400',     bg: 'bg-red-400/10    border-red-400/20'    }
}

function resultMeta(resultado) {
  const [g, c] = resultado.split('-').map(Number)
  if (g > c) return { color: 'text-emerald-400', bg: 'bg-emerald-400/10' }
  if (g === c) return { color: 'text-amber-400',  bg: 'bg-amber-400/10'  }
  return             { color: 'text-red-400',    bg: 'bg-red-400/10'    }
}

function MatchRow({ partido, index }) {
  const nota   = notaMeta(partido.nota)
  const result = resultMeta(partido.resultado)
  return (
    <div
      className="animate-fade-up flex items-center gap-3 sm:gap-4 py-4
                 border-b border-slate-800/50 last:border-0"
      style={{ animationDelay: `${index * 35}ms` }}
    >
      {/* Nota grande */}
      <div className={`w-12 h-12 rounded-xl border flex items-center justify-center shrink-0 ${nota.bg}`}>
        <span className={`text-lg font-black tabular-nums leading-none ${nota.text}`}>
          {partido.nota}
        </span>
      </div>

      {/* Rival + resultado */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-sm font-semibold text-white truncate">{partido.rival}</p>
          <span className={`text-xs font-black tabular-nums px-1.5 py-0.5 rounded-md ${result.bg} ${result.color}`}>
            {partido.resultado}
          </span>
          {!partido.titular && (
            <span className="text-[10px] font-semibold text-slate-500 bg-slate-800 border border-slate-700 px-1.5 py-0.5 rounded">
              SUP
            </span>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-0.5">
          J{partido.jornada} · {partido.minutos}'
        </p>
      </div>

      {/* Stats del partido */}
      <div className="flex items-center gap-3 sm:gap-5 shrink-0">
        <div className="text-center">
          <p className="text-sm font-black text-white tabular-nums leading-none">{partido.goles}</p>
          <p className="text-[10px] text-slate-600 mt-0.5">G</p>
        </div>
        <div className="text-center">
          <p className="text-sm font-black text-white tabular-nums leading-none">{partido.asistencias}</p>
          <p className="text-[10px] text-slate-600 mt-0.5">A</p>
        </div>
        <div className="text-center hidden sm:block">
          <p className="text-sm font-black text-cyan-400 tabular-nums leading-none">{partido.xG}</p>
          <p className="text-[10px] text-slate-600 mt-0.5">xG</p>
        </div>
        <div className="text-center hidden sm:block">
          <p className="text-sm font-black text-slate-300 tabular-nums leading-none">{partido.pases}%</p>
          <p className="text-[10px] text-slate-600 mt-0.5">Pases</p>
        </div>
      </div>
    </div>
  )
}

function ValorTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs">
      <p className="text-slate-400 mb-0.5">{label}</p>
      <p className="text-emerald-400 font-bold text-sm">€{payload[0].value}M</p>
    </div>
  )
}

function StatPill({ label, value, sub }) {
  const animated = useCountUp(value, 750)
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl px-5 py-4 flex flex-col gap-1 min-w-0">
      <span className="text-slate-500 text-xs font-semibold uppercase tracking-wider truncate">{label}</span>
      <span className="text-3xl font-black text-white tabular-nums leading-none">{animated}</span>
      {sub && <span className="text-slate-600 text-xs">{sub}</span>}
    </div>
  )
}

// ─── Página principal ─────────────────────────────────────────────────────────
export default function Jugador() {
  const { id }             = useParams()
  const [jugador, setJugador] = useState(null)
  const [loading, setLoading] = useState(true)
  const [temporadaSel, setTemporadaSel] = useState(null)

  useEffect(() => {
    setLoading(true)
    setJugador(null)
    getJugador(Number(id))
      .then(raw => setJugador(adaptarPerfilJugador(raw)))
      .catch(() => {
        const fallback = jugadoresFallback.find(j => j.id === Number(id)) ?? null
        setJugador(fallback)
      })
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (jugador?.estadisticas_por_temporada) {
      const temps = jugador.estadisticas_por_temporada
      const def = (temps.find(t => t.actual) ?? temps.at(-1))?.temporada ?? null
      setTemporadaSel(def)
    }
  }, [jugador])

  const historia = jugador?.estadisticas_por_temporada
    ? { temporadas: jugador.estadisticas_por_temporada }
    : null

  // Lista de temporadas de más reciente a más antigua
  const temporadasDisponibles = useMemo(
    () => historia ? [...historia.temporadas].reverse().map(t => t.temporada) : [],
    [historia]
  )

  // Fila del historial seleccionada
  const temporadaData = historia?.temporadas.find(t => t.temporada === temporadaSel)

  // Métricas activas (cambian con el selector)
  const metricasActivas = useMemo(() => {
    if (temporadaData) return metricasDesdeTemporada(temporadaData)
    return jugador?.metricas ?? {}
  }, [temporadaData, jugador])

  if (loading) return <JugadorSkeleton />

  if (!jugador) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-3xl mb-4">
          ❌
        </div>
        <h2 className="text-xl font-bold text-white mb-2">Jugador no encontrado</h2>
        <Link to="/" className="text-cyan-400 hover:underline text-sm">← Volver</Link>
      </div>
    )
  }

  const initials          = getInitials(jugador.nombre)
  const equipoActivo      = temporadaData?.equipo ?? jugador.equipo
  const partidosActivos   = temporadaData?.partidos ?? null
  const esActual          = temporadaData?.actual ?? !historia
  const labelTemporada    = temporadaSel ?? '—'

  return (
    <main className="animate-fade-in max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">

      {/* ── Back ── */}
      <Link to="/" className="inline-flex items-center gap-1.5 text-slate-500 hover:text-white
                               transition-colors text-sm font-medium group">
        <svg className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform"
             fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Jugadores
      </Link>

      {/* ── Header ── */}
      <div className="relative overflow-hidden bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8">
        <div className="absolute -top-16 -right-16 w-64 h-64 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="relative flex flex-col sm:flex-row gap-6 sm:items-start">
          {/* Avatar */}
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-cyan-500/25 to-blue-700/25
                          border border-cyan-500/20 flex items-center justify-center shrink-0">
            <span className="text-2xl font-black text-cyan-400">{initials}</span>
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            {/* Nombre */}
            <h1 className="text-3xl sm:text-4xl font-black text-white tracking-tight mb-2">
              {jugador.nombre}
            </h1>

            {/* Meta fija */}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm mb-4">
              <span className="bg-slate-800 text-slate-300 font-semibold px-2.5 py-0.5 rounded-full text-xs">
                {jugador.posicion}
              </span>
              <span className="text-slate-700">·</span>
              <span className="text-slate-400">{jugador.edad} años</span>
              <span className="text-slate-700">·</span>
              <span className="text-slate-400">{jugador.nacionalidad}</span>
            </div>

            {/* ── Selector de temporada ── */}
            {temporadasDisponibles.length > 0 && (
              <div className="flex overflow-x-auto scrollbar-hide items-center gap-2 pb-0.5">
                <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider mr-1">
                  Temporada
                </span>
                {temporadasDisponibles.map(t => {
                  const esEsta = t === temporadaSel
                  const estaActual = historia?.temporadas.find(s => s.temporada === t)?.actual
                  return (
                    <button
                      key={t}
                      onClick={() => setTemporadaSel(t)}
                      className={`relative shrink-0 px-3 py-1 rounded-full text-xs font-bold transition-all duration-150 ${
                        esEsta
                          ? 'bg-cyan-400 text-slate-950 shadow-md shadow-cyan-500/20'
                          : 'bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700'
                      }`}
                    >
                      {t}
                      {estaActual && (
                        <span className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full border border-slate-900 ${
                          esEsta ? 'bg-slate-950' : 'bg-cyan-400'
                        }`} />
                      )}
                    </button>
                  )
                })}
              </div>
            )}

            {/* Equipo + partidos de la temporada seleccionada */}
            <div className="flex items-center gap-3 mt-3 text-sm">
              <span className="text-cyan-400 font-bold">{equipoActivo}</span>
              {partidosActivos && (
                <>
                  <span className="text-slate-700">·</span>
                  <span className="text-slate-400">{partidosActivos} partidos</span>
                </>
              )}
              {esActual && (
                <span className="text-xs font-semibold text-cyan-400 bg-cyan-400/10
                                 px-2 py-0.5 rounded-full border border-cyan-400/20">
                  Temporada actual
                </span>
              )}
            </div>
          </div>

          {/* Scouting CTA */}
          <Link to={`/scouting?ref=${jugador.id}`}
                className="shrink-0 self-start w-fit px-4 py-2.5
                           bg-cyan-400/10 hover:bg-cyan-400/20
                           border border-cyan-400/20 hover:border-cyan-400/40
                           text-cyan-400 rounded-xl text-sm font-semibold
                           transition-all duration-150">
            Ver similares →
          </Link>
        </div>
      </div>

      {/* ── Stats destacadas (reactivas) ── */}
      <div>
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">
          Temporada {labelTemporada}
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatPill label="Goles"       value={metricasActivas.goles}       sub="en la temporada" />
          <StatPill label="Asistencias" value={metricasActivas.asistencias} sub="en la temporada" />
          <StatPill label="xG"          value={metricasActivas.xG}          sub="expected goals" />
          <StatPill label="xA"          value={metricasActivas.xA}          sub="expected assists" />
        </div>
      </div>

      {/* ── Valor de mercado ── */}
      {jugador.valor_mercado && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4">
            Valor de mercado
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 items-center">
            {/* Valor actual destacado */}
            <div className="flex flex-col gap-1">
              <div className="flex items-end gap-2">
                <span className="text-5xl font-black text-emerald-400 tabular-nums leading-none">
                  {jugador.valor_mercado}
                </span>
                <span className="text-2xl font-black text-emerald-400/60 mb-1">M€</span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Estimación Transfermarkt · Temporada 2024/25
              </p>
              {jugador.evolucion_valor && jugador.evolucion_valor.length >= 2 && (() => {
                const prev = jugador.evolucion_valor.at(-2).valor
                const curr = jugador.evolucion_valor.at(-1).valor
                const diff = curr - prev
                const sign = diff >= 0 ? '+' : ''
                return (
                  <span className={`text-sm font-bold mt-1 ${diff >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {sign}{diff}M€ vs temporada anterior
                  </span>
                )
              })()}
            </div>

            {/* Gráfica evolución */}
            {jugador.evolucion_valor && (
              <div className="h-36">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={jugador.evolucion_valor}
                    margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis
                      dataKey="temporada"
                      tick={{ fill: '#64748b', fontSize: 9 }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={v => v.slice(0, 4)}
                    />
                    <YAxis
                      tick={{ fill: '#64748b', fontSize: 9 }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={v => `${v}M`}
                    />
                    <Tooltip content={<ValorTooltip />} cursor={{ stroke: '#334155', strokeWidth: 1 }} />
                    <Line
                      type="monotone"
                      dataKey="valor"
                      stroke="#4ade80"
                      strokeWidth={2}
                      dot={{ r: 3, fill: '#4ade80', stroke: '#020617', strokeWidth: 2 }}
                      activeDot={{ r: 5, fill: '#4ade80', stroke: '#020617', strokeWidth: 2 }}
                      isAnimationActive
                      animationDuration={700}
                      animationEasing="ease-out"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Carrera (timeline de clubes) ── */}
      {jugador.carrera?.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-6">
            Carrera
          </p>
          <div>
            {[...jugador.carrera].reverse().map((item, i, arr) => (
              <TimelineItem key={i} item={item} isLast={i === arr.length - 1} />
            ))}
          </div>
          <div className="mt-5 pt-4 border-t border-slate-800 flex flex-wrap gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-px bg-cyan-400 rounded-full inline-block" />
              Cantidad de traspaso en cian
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full border-2 border-slate-600 bg-slate-900 inline-block" />
              Cedido / Libre / Cantera con badge
            </span>
          </div>
        </div>
      )}

      {/* ── Últimos partidos ── */}
      {jugador.ultimos_partidos?.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
          {/* Header */}
          <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between gap-4 flex-wrap">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
              Últimos partidos
            </p>
            <div className="flex items-center gap-3 text-xs font-semibold">
              <span className="flex items-center gap-1.5 text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />7+
              </span>
              <span className="flex items-center gap-1.5 text-amber-400">
                <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />5–7
              </span>
              <span className="flex items-center gap-1.5 text-red-400">
                <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />–5
              </span>
              <span className="hidden sm:flex items-center gap-3 pl-2 border-l border-slate-800 text-slate-600 font-normal">
                <span>G · A · xG · Pases%</span>
              </span>
            </div>
          </div>

          {/* Rows */}
          <div className="px-6">
            {jugador.ultimos_partidos.map((p, i) => (
              <MatchRow key={i} partido={p} index={i} />
            ))}
          </div>

          {/* Footer resumen */}
          {(() => {
            const ps = jugador.ultimos_partidos
            const g  = ps.reduce((s, p) => s + p.goles, 0)
            const a  = ps.reduce((s, p) => s + p.asistencias, 0)
            const avgNota = (ps.reduce((s, p) => s + p.nota, 0) / ps.length).toFixed(1)
            const avgMeta = notaMeta(parseFloat(avgNota))
            return (
              <div className="px-6 py-3 border-t border-slate-800 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                <span>Últimos {ps.length} partidos</span>
                <span className="text-slate-700">·</span>
                <span><span className="text-white font-bold">{g}G {a}A</span></span>
                <span className="text-slate-700">·</span>
                <span>
                  Nota media{' '}
                  <span className={`font-black ${avgMeta.text}`}>{avgNota}</span>
                </span>
              </div>
            )
          })()}
        </div>
      )}

      {/* ── Gráfica de evolución (SIEMPRE muestra toda la carrera) ── */}
      {historia && (
        <div className="relative bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <Watermark />
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-6">
            Evolución por temporada — Goles &amp; Asistencias
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart
              data={historia.temporadas}
              barCategoryGap="30%"
              barGap={4}
              margin={{ top: 0, right: 8, left: -20, bottom: 0 }}
            >
              <CartesianGrid vertical={false} stroke="#1e293b" />
              <XAxis
                dataKey="temporada"
                tick={{ fill: '#64748b', fontSize: 11, fontFamily: 'Space Grotesk', fontWeight: 600 }}
                axisLine={false} tickLine={false}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 11, fontFamily: 'Space Grotesk' }}
                axisLine={false} tickLine={false}
              />
              <Tooltip content={<BarTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Legend
                wrapperStyle={{ fontSize: 12, color: '#94a3b8', fontFamily: 'Space Grotesk', paddingTop: 16 }}
                formatter={(v) => v.charAt(0).toUpperCase() + v.slice(1)}
              />
              <Bar dataKey="goles"       name="goles"       fill="#22d3ee" radius={[4,4,0,0]} isAnimationActive animationDuration={700} animationEasing="ease-out" />
              <Bar dataKey="asistencias" name="asistencias" fill="#818cf8" radius={[4,4,0,0]} isAnimationActive animationDuration={700} animationEasing="ease-out" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Radar + métricas (reactivos) ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Radar */}
        <div className="relative bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <Watermark />
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4">
            Perfil de rendimiento — {labelTemporada}
          </p>
          <PlayerRadarChart metricas={metricasActivas} />
        </div>

        {/* Metric bars */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-5">
            Métricas {labelTemporada}
          </p>
          <div className="space-y-1">
            {Object.entries(metricasActivas).map(([key, value]) => {
              const label = METRICA_LABELS[key]
              if (!label) return null
              const t        = THRESHOLDS[key]
              const pct      = t ? Math.min((value / t.max) * 100, 100) : 0
              const col      = metricColor(key, value)
              const barColor = col.includes('cyan')  ? 'bg-cyan-400'
                             : col.includes('amber') ? 'bg-amber-400'
                             : col.includes('red')   ? 'bg-red-500'
                             : 'bg-slate-600'
              const showBar  = !SIN_BARRA.has(key) && t
              return (
                <div key={key}
                     className="flex items-center gap-3 py-2.5 border-b border-slate-800/50 last:border-0">
                  <span className="text-slate-400 text-sm flex-1 min-w-0 truncate">{label}</span>
                  {showBar ? (
                    <div className="w-28 h-1.5 bg-slate-800 rounded-full overflow-hidden shrink-0">
                      <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
                    </div>
                  ) : (
                    <div className="w-28 shrink-0" />
                  )}
                  <span className={`text-sm font-black w-12 text-right tabular-nums ${
                    SIN_BARRA.has(key) ? 'text-slate-300' : col
                  }`}>
                    {key === 'minutos_jugados' ? value.toLocaleString('es') : value}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── Tabla de estadísticas por temporada ── */}
      {historia && (() => {
        const filas = [
          ...historia.temporadas.filter(t => t.actual),
          ...[...historia.temporadas].filter(t => !t.actual).reverse(),
        ]

        // Mostrar xG/xA solo si alguna fila histórica tiene dato real
        const historicas = filas.filter(t => !t.actual)
        const showXG = historicas.some(t => t.xG != null)
        const showXA = historicas.some(t => t.xA != null)

        const thCls = "text-right first:text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap first:pl-6 last:pr-6"
        const rowCls = (sel) => `border-b border-slate-800/40 last:border-0 cursor-pointer transition-colors ${
          sel ? 'bg-cyan-400/5' : 'hover:bg-slate-800/40'
        }`
        const TdNum = ({ v, k }) => (
          <td className={`px-4 py-3 text-right font-bold tabular-nums last:pr-6 ${v != null ? metricColor(k, v) : 'text-slate-700'}`}>
            {v != null ? v : ''}
          </td>
        )

        return (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-800">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                Estadísticas por temporada
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800">
                    {['Temporada','Equipo','Min','Goles','Asist.'].map(h => (
                      <th key={h} className={thCls}>{h}</th>
                    ))}
                    {showXG && <th className={thCls}>xG</th>}
                    {showXA && <th className={thCls}>xA</th>}
                    {['G/90','A/90','Pases %','Regates','Recup.'].map(h => (
                      <th key={h} className={thCls}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filas.map((t) => (
                    <tr
                      key={t.temporada}
                      onClick={() => setTemporadaSel(t.temporada)}
                      className={rowCls(t.temporada === temporadaSel)}
                    >
                      <td className="pl-6 pr-4 py-3 font-bold text-white whitespace-nowrap">
                        {t.temporada}
                        {t.actual && (
                          <span className="ml-2 text-xs font-semibold text-cyan-400 bg-cyan-400/10 px-1.5 py-0.5 rounded-full">
                            actual
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-400 whitespace-nowrap">{t.equipo}</td>
                      <td className="px-4 py-3 text-right text-slate-400 tabular-nums text-xs">
                        {t.minutos_jugados?.toLocaleString('es') ?? ''}
                      </td>
                      <TdNum v={t.goles}              k="goles" />
                      <TdNum v={t.asistencias}        k="asistencias" />
                      {showXG && <TdNum v={t.xG}      k="xG" />}
                      {showXA && <TdNum v={t.xA}      k="xA" />}
                      <TdNum v={t.goles_por_90}       k="goles_por_90" />
                      <TdNum v={t.asistencias_por_90} k="asistencias_por_90" />
                      <TdNum v={t.actual ? t.pases_completados : null} k="pases_completados" />
                      <TdNum v={t.actual ? t.regates          : null} k="regates" />
                      <TdNum v={t.actual ? t.recuperaciones   : null} k="recuperaciones" />
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="px-6 py-3 text-xs text-slate-600 border-t border-slate-800">
              Haz clic en una fila para seleccionar la temporada.
            </p>
          </div>
        )
      })()}

    </main>
  )
}
