import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { jugadores as jugadoresFallback } from '../data/jugadores'
import { getJugadores, getConteoJugadores, getConteoPartidos, getTopScorer, getAnalisisJornada, getUltimosPartidos } from '../services/api'
import { useLiga } from '../contexts/LigaContext'
import PlayerCard from '../components/PlayerCard'

function Spinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="w-8 h-8 rounded-full border-2 border-slate-700 border-t-cyan-400 animate-spin" />
    </div>
  )
}

// ─── Animación contador 0 → target ───────────────────────────────────────────
function useCountUp(target, duration = 1000) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (!target) return
    const start = performance.now()
    function step(now) {
      const progress = Math.min((now - start) / duration, 1)
      const eased    = 1 - Math.pow(1 - progress, 3)
      setValue(Math.round(target * eased))
      if (progress < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [target, duration])
  return value
}

// ─── Barra de estadísticas ────────────────────────────────────────────────────
function StatBar({ countJugadores, countPartidos }) {
  const animJugadores = useCountUp(countJugadores)
  const animPartidos  = useCountUp(countPartidos)

  const items = [
    { anim: countJugadores ? animJugadores : null, label: 'jugadores' },
    { anim: 5,                                      label: 'ligas'     },
    { anim: countPartidos  ? animPartidos  : null,  label: 'partidos'  },
  ]

  return (
    <div className="border-b border-slate-800/60 bg-slate-950/80 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-3 divide-x divide-slate-800/60">
          {items.map(({ anim, label }) => (
            <div key={label} className="flex flex-col items-center py-1 px-4">
              <span className="text-3xl sm:text-4xl font-black text-cyan-400 tabular-nums leading-none">
                {anim != null ? anim.toLocaleString() : '—'}
              </span>
              <span className="text-xs text-slate-500 mt-1.5 uppercase tracking-widest font-medium">
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Card máximo goleador del hero (solo desktop) ────────────────────────────
function HeroDecorCard({ jugador, loading, ligaNombre }) {
  if (!loading && !jugador) return null

  function initials(nombre) {
    return nombre ? nombre.split(' ').slice(0, 2).map(n => n[0]).join('').toUpperCase() : '?'
  }

  if (loading) {
    return (
      <div className="bg-slate-900/80 border border-slate-700/50 rounded-2xl p-5 w-72 animate-pulse">
        <div className="flex items-center gap-1.5 mb-4">
          <div className="h-3 bg-slate-800 rounded-full w-28" />
        </div>
        <div className="flex items-center gap-3 mb-5">
          <div className="w-11 h-11 rounded-xl bg-slate-800 shrink-0" />
          <div className="flex-1 space-y-1.5">
            <div className="h-3 bg-slate-800 rounded-full w-3/4" />
            <div className="h-2.5 bg-slate-800 rounded-full w-1/2" />
          </div>
          <div className="w-14 h-8 bg-slate-800 rounded-lg shrink-0" />
        </div>
        <div className="space-y-2.5">
          {[...Array(4)].map((_, i) => (
            <div key={i}>
              <div className="flex justify-between mb-1">
                <div className="h-2.5 bg-slate-800 rounded-full w-12" />
                <div className="h-2.5 bg-slate-800 rounded-full w-6" />
              </div>
              <div className="h-1.5 bg-slate-800 rounded-full" />
            </div>
          ))}
        </div>
        <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between">
          <div className="h-2.5 bg-slate-800 rounded-full w-20" />
          <div className="h-2.5 bg-slate-800 rounded-full w-16" />
        </div>
      </div>
    )
  }

  const bars = [
    { label: 'Goles',  val: jugador.goles       ?? 0,               max: 30, color: 'bg-cyan-400'   },
    { label: 'xG',     val: +(jugador.xg         ?? 0).toFixed(1),  max: 30, color: 'bg-blue-400'   },
    { label: 'Asist.', val: jugador.asistencias  ?? 0,               max: 20, color: 'bg-violet-400' },
    { label: 'xA',     val: +(jugador.xa         ?? 0).toFixed(1),  max: 20, color: 'bg-purple-400' },
  ]
  const equipo  = jugador.equipo || (jugador.equipos || {}).nombre || ''
  const posicion = jugador.posicion || ''

  return (
    <div className="bg-slate-900/80 border border-slate-700/50 rounded-2xl p-5 backdrop-blur shadow-2xl shadow-black/50 w-72">
      {/* Etiqueta */}
      <div className="flex items-center gap-1.5 mb-4">
        <span className="text-yellow-400 text-xs">⚽</span>
        <span className="text-xs font-bold text-yellow-400 uppercase tracking-wider">Máximo goleador</span>
      </div>

      {/* Cabecera jugador */}
      <div className="flex items-center gap-3 mb-5">
        {jugador.foto_url ? (
          <img
            src={jugador.foto_url}
            alt={jugador.nombre}
            className="w-11 h-11 rounded-xl object-cover border border-slate-700/50 shrink-0"
          />
        ) : (
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20
                          border border-cyan-500/20 flex items-center justify-center
                          text-cyan-400 font-black text-sm shrink-0">
            {initials(jugador.nombre)}
          </div>
        )}
        <div className="min-w-0">
          <p className="text-white font-bold text-sm truncate">{jugador.nombre}</p>
          <p className="text-slate-500 text-xs truncate">{equipo}{posicion ? ` · ${posicion}` : ''}</p>
        </div>
        {jugador.valor_mercado != null && (
          <div className="ml-auto text-right shrink-0">
            <p className="text-cyan-400 font-black text-sm">€{jugador.valor_mercado}M</p>
            <p className="text-slate-600 text-xs">valor</p>
          </div>
        )}
      </div>

      {/* Barras */}
      <div className="space-y-2.5">
        {bars.map(b => (
          <div key={b.label}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-500">{b.label}</span>
              <span className="text-white font-bold">{b.val}</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full ${b.color} rounded-full`}
                style={{ width: `${Math.min((b.val / b.max) * 100, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between">
        <span className="text-xs text-slate-600">{ligaNombre} 2025/26</span>
        <span className="text-xs text-cyan-400 font-semibold">{jugador.goles} goles ⚽</span>
      </div>
    </div>
  )
}

// ─── Constantes ───────────────────────────────────────────────────────────────
const POSITION_FILTERS = [
  { value: 'Todas',           icon: '◈',  label: 'Todos' },
  { value: 'Delantero',       icon: '⚽', label: 'Delanteros' },
  { value: 'Extremo',         icon: '⚡', label: 'Extremos' },
  { value: 'Mediapunta',      icon: '🎯', label: 'Mediapuntas' },
  { value: 'Centrocampista',  icon: '⚙️', label: 'Centros' },
  { value: 'Defensa Central', icon: '🛡️', label: 'Defensas' },
  { value: 'Portero',         icon: '🧤', label: 'Porteros' },
]

const RANKING_METRICS = [
  { key: 'goles',             label: 'Goles' },
  { key: 'asistencias',       label: 'Asistencias' },
  { key: 'xG',                label: 'xG' },
  { key: 'xA',                label: 'xA' },
  { key: 'regates',           label: 'Regates' },
  { key: 'pases_completados', label: 'Pases %' },
  { key: 'ga_por_90',         label: 'G+A/90' },
  { key: 'valor_mercado',    label: 'Valor €M' },
]

const PODIO = [
  { text: 'text-yellow-400', bg: 'bg-yellow-400/10', border: 'border-yellow-400/25', bar: 'bg-yellow-400', shadow: 'shadow-yellow-500/20' },
  { text: 'text-slate-300',  bg: 'bg-slate-300/8',   border: 'border-slate-400/20',  bar: 'bg-slate-300',  shadow: 'shadow-slate-400/10' },
  { text: 'text-amber-600',  bg: 'bg-amber-700/10',  border: 'border-amber-700/25',  bar: 'bg-amber-600',  shadow: 'shadow-amber-700/20' },
]

const INITIAL_FILTROS = {
  edadMin: 16, edadMax: 40,
  minGoles: '', minAsistencias: '',
  minXG: '', minXA: '', minMinutos: '',
  maxValor: '',
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getInitials(nombre) {
  return nombre.split(' ').slice(0, 2).map(n => n[0]).join('').toUpperCase()
}

function contarFiltrosActivos(f, posicion) {
  return [
    f.edadMin > 16 || f.edadMax < 40,
    posicion !== 'Todas',
    f.minGoles !== '',
    f.minAsistencias !== '',
    f.minXG !== '',
    f.minXA !== '',
    f.minMinutos !== '',
    f.maxValor !== '',
  ].filter(Boolean).length
}

// ─── Dual range slider ────────────────────────────────────────────────────────
function DualSlider({ minVal, maxVal, onMinChange, onMaxChange, min = 16, max = 40 }) {
  const span  = max - min
  const pctLo = ((minVal - min) / span) * 100
  const pctHi = ((maxVal - min) / span) * 100

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Rango de edad
        </span>
        <span className="text-sm font-black text-white tabular-nums">
          {minVal} — {maxVal} años
        </span>
      </div>
      <div className="relative flex items-center h-5">
        <div className="absolute w-full h-1.5 bg-slate-700 rounded-full pointer-events-none" />
        <div
          className="absolute h-1.5 bg-cyan-400 rounded-full pointer-events-none"
          style={{ left: `${pctLo}%`, right: `${100 - pctHi}%` }}
        />
        <input
          type="range" min={min} max={max} value={minVal}
          onChange={e => onMinChange(Math.min(Number(e.target.value), maxVal - 1))}
          className="absolute w-full h-1.5 appearance-none bg-transparent range-thumb"
          style={{ zIndex: minVal > max - 4 ? 5 : 3 }}
        />
        <input
          type="range" min={min} max={max} value={maxVal}
          onChange={e => onMaxChange(Math.max(Number(e.target.value), minVal + 1))}
          className="absolute w-full h-1.5 appearance-none bg-transparent range-thumb"
          style={{ zIndex: 4 }}
        />
      </div>
      <div className="flex justify-between text-xs text-slate-700 mt-1">
        <span>{min}</span><span>{max}</span>
      </div>
    </div>
  )
}

// ─── Input numérico con label ─────────────────────────────────────────────────
function NumInput({ label, value, onChange, placeholder = '0' }) {
  return (
    <div>
      <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
        {label}
      </label>
      <input
        type="number" min={0} value={value} placeholder={placeholder}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2.5
                   text-sm text-white placeholder-slate-600
                   focus:outline-none focus:border-cyan-500/60 transition-colors
                   [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none
                   [&::-webkit-inner-spin-button]:appearance-none"
      />
    </div>
  )
}

// ─── Vista ranking ────────────────────────────────────────────────────────────
function getMetricVal(j, key) {
  return j.metricas[key] ?? j[key] ?? 0
}

function RankingView({ lista, metricKey }) {
  const maxVal = getMetricVal(lista[0], metricKey) || 1
  return (
    <div className="space-y-2 animate-fade-in">
      {lista.map((j, i) => {
        const val  = getMetricVal(j, metricKey)
        const pct  = maxVal > 0 ? (val / maxVal) * 100 : 0
        const pod  = PODIO[i] ?? null
        const rank = i + 1
        return (
          <Link
            to={`/jugador/${j.id}`}
            key={j.id}
            className={`animate-fade-up flex items-center gap-4 rounded-2xl border p-4
                        transition-all duration-200 will-change-transform
                        hover:scale-[1.01] hover:border-slate-600 group ${
              pod
                ? `${pod.bg} ${pod.border} hover:shadow-lg ${pod.shadow}`
                : 'bg-slate-900 border-slate-800'
            }`}
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <div className="w-9 shrink-0 text-center">
              {rank <= 3
                ? <span className="text-lg">{['🥇','🥈','🥉'][i]}</span>
                : <span className="text-sm font-black text-slate-600 tabular-nums">#{rank}</span>
              }
            </div>
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0
                             text-xs font-black border ${
              pod ? `${pod.bg} ${pod.border} ${pod.text}` : 'bg-slate-800 border-slate-700 text-slate-400'
            }`}>
              {getInitials(j.nombre)}
            </div>
            <div className="flex-1 min-w-0">
              <p className={`font-bold text-sm leading-tight truncate transition-colors
                             group-hover:text-cyan-400 ${pod ? pod.text : 'text-white'}`}>
                {j.nombre}
              </p>
              <p className="text-xs text-slate-500 truncate mt-0.5">{j.equipo}</p>
            </div>
            <span className="hidden sm:block text-xs text-slate-600 shrink-0">{j.posicion}</span>
            <div className="flex items-center gap-3 shrink-0 w-32 sm:w-48">
              <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${pod ? pod.bar : 'bg-cyan-400'}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className={`text-sm font-black tabular-nums w-10 text-right shrink-0 ${
                pod ? pod.text : 'text-cyan-400'
              }`}>{val}</span>
            </div>
          </Link>
        )
      })}
    </div>
  )
}

// ─── Iconos toggle ────────────────────────────────────────────────────────────
function IconCards() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <rect x="3" y="3" width="7" height="7" rx="1.5" strokeWidth={2} />
      <rect x="14" y="3" width="7" height="7" rx="1.5" strokeWidth={2} />
      <rect x="3" y="14" width="7" height="7" rx="1.5" strokeWidth={2} />
      <rect x="14" y="14" width="7" height="7" rx="1.5" strokeWidth={2} />
    </svg>
  )
}
function IconRanking() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M4 6h16M4 10h12M4 14h8M4 18h5" />
    </svg>
  )
}
function IconFilter({ count }) {
  return (
    <div className="relative">
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M3 4h18M7 8h10M11 12h2M11 16h2" />
      </svg>
      {count > 0 && (
        <span className="absolute -top-1.5 -right-1.5 w-3.5 h-3.5 rounded-full bg-cyan-400
                         text-slate-950 text-[9px] font-black flex items-center justify-center">
          {count}
        </span>
      )}
    </div>
  )
}

// ─── Hook: contador animado que arranca al entrar en viewport ─────────────────
function useCountUpOnVisible(target, duration = 1400) {
  const [value, setValue]   = useState(0)
  const [visible, setVisible] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect() } },
      { threshold: 0.3 }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  useEffect(() => {
    if (!visible || !target) return
    const start = performance.now()
    function step(now) {
      const p = Math.min((now - start) / duration, 1)
      const e = 1 - Math.pow(1 - p, 3)
      setValue(Math.round(target * e))
      if (p < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [visible, target, duration])

  return [value, ref]
}

// ─── Sección 1: Stats animadas ────────────────────────────────────────────────
const HOME_STATS = [
  { value: 2200, suffix: '+', label: 'Jugadores' },
  { value: 5,    suffix: '',  label: 'Ligas' },
  { value: 5,    suffix: '',  label: 'Temporadas históricas' },
  { value: 20,   suffix: '+', label: 'Equipos por liga' },
]

function AnimatedStat({ value, suffix, label }) {
  const [anim, ref] = useCountUpOnVisible(value)
  return (
    <div ref={ref} className="flex flex-col items-center py-6 px-4">
      <span className="text-4xl sm:text-5xl font-black text-cyan-400 tabular-nums leading-none">
        {anim.toLocaleString()}{suffix}
      </span>
      <span className="text-xs text-slate-500 mt-2 uppercase tracking-widest font-medium text-center">
        {label}
      </span>
    </div>
  )
}

function StatsAnimadasSection() {
  return (
    <section className="bg-slate-900/50 border-y border-slate-800/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-slate-800/60">
          {HOME_STATS.map(s => <AnimatedStat key={s.label} {...s} />)}
        </div>
      </div>
    </section>
  )
}

// ─── Sección 2: Qué puedes hacer ─────────────────────────────────────────────
const FEATURES = [
  {
    icon: '🔍',
    title: 'Analiza jugadores',
    desc: 'xG, xA, valor de mercado y evolución histórica por temporada para más de 2.200 jugadores.',
    to: '/jugadores',
  },
  {
    icon: '⚡',
    title: 'Scouting inteligente',
    desc: 'Encuentra jugadores similares y compáralos con radar charts interactivos por posición.',
    to: '/scouting',
  },
  {
    icon: '💡',
    title: 'Descubre insights',
    desc: 'Rankings en tiempo real, tendencias y análisis de jornada generados por IA en español.',
    to: '/insights',
  },
]

function QuesPuedesHacerSection() {
  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <h2 className="text-2xl sm:text-3xl font-black text-white mb-2">¿Qué puedes hacer?</h2>
      <p className="text-slate-500 text-sm mb-10">Todo lo que necesitas para analizar el fútbol de otra manera.</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {FEATURES.map(({ icon, title, desc, to }) => (
          <Link
            key={title}
            to={to}
            className="group flex flex-col gap-4 p-6 rounded-2xl
                       bg-slate-900/60 border border-slate-800
                       hover:border-cyan-500/40 hover:bg-slate-900
                       transition-all duration-200"
          >
            <span className="text-4xl">{icon}</span>
            <div>
              <h3 className="text-white font-bold text-base mb-1 group-hover:text-cyan-400 transition-colors">{title}</h3>
              <p className="text-slate-500 text-sm leading-relaxed">{desc}</p>
            </div>
            <span className="text-xs text-cyan-500/60 font-semibold mt-auto group-hover:text-cyan-400 transition-colors">
              Explorar →
            </span>
          </Link>
        ))}
      </div>
    </section>
  )
}

// ─── Sección 3: Preview Insights ──────────────────────────────────────────────
function InsightsPreviewSection() {
  const [analisis, setAnalisis] = useState(null)
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    getAnalisisJornada(1)
      .then(d => setAnalisis(d))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <section className="border-t border-slate-800/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="flex items-end justify-between mb-8">
          <div>
            <h2 className="text-2xl sm:text-3xl font-black text-white mb-1">Análisis de jornada</h2>
            <p className="text-slate-500 text-sm">Generado por IA · LaLiga 2025/26</p>
          </div>
          <Link
            to="/insights"
            className="text-xs font-bold text-cyan-400 hover:text-cyan-300 transition-colors shrink-0"
          >
            Ver todos →
          </Link>
        </div>

        {loading ? (
          <div className="h-32 rounded-2xl bg-slate-900/60 border border-slate-800 animate-pulse" />
        ) : analisis ? (
          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-cyan-500/20 transition-colors">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest">
                Jornada {analisis.jornada}
              </span>
              <span className="text-xs text-slate-600 ml-auto">
                {analisis.created_at ? new Date(analisis.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' }) : ''}
              </span>
            </div>
            {analisis.titulo && (
              <h3 className="text-white font-bold text-lg mb-2">{analisis.titulo}</h3>
            )}
            <p className="text-slate-400 text-sm leading-relaxed line-clamp-3">
              {(analisis.contenido || analisis.analisis || '').slice(0, 240)}…
            </p>
            <Link
              to="/insights"
              className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl
                         bg-cyan-400/10 border border-cyan-400/20 text-cyan-400
                         text-xs font-bold hover:bg-cyan-400/20 transition-colors"
            >
              Leer análisis completo →
            </Link>
          </div>
        ) : (
          <div className="p-8 rounded-2xl bg-slate-900/40 border border-slate-800/60 text-center">
            <span className="text-3xl mb-3 block">📊</span>
            <p className="text-slate-500 text-sm">El análisis de la última jornada aparecerá aquí.</p>
            <Link
              to="/insights"
              className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl
                         bg-slate-800 border border-slate-700 text-slate-300
                         text-xs font-bold hover:text-white transition-colors"
            >
              Ver Insights →
            </Link>
          </div>
        )}
      </div>
    </section>
  )
}

// ─── Sección 4: Ligas disponibles ────────────────────────────────────────────
const LIGAS_DISPLAY = [
  { id: 1,  nombre: 'LaLiga',         logo: 'https://media.api-sports.io/football/leagues/140.png' },
  { id: 24, nombre: 'Premier League', logo: 'https://media.api-sports.io/football/leagues/39.png'  },
  { id: 25, nombre: 'Bundesliga',     logo: 'https://media.api-sports.io/football/leagues/78.png'  },
  { id: 26, nombre: 'Serie A',        logo: 'https://media.api-sports.io/football/leagues/135.png' },
  { id: 27, nombre: 'Ligue 1',        logo: '/logos/ligue1.png' },
]

function LigasDisponiblesSection() {
  return (
    <section className="border-t border-slate-800/60 bg-slate-900/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
        <h2 className="text-2xl sm:text-3xl font-black text-white mb-2">Cobertura disponible</h2>
        <p className="text-slate-500 text-sm mb-10">Las mejores ligas de Europa con datos actualizados en tiempo real.</p>

        <div className="flex flex-wrap items-center justify-center gap-8 sm:gap-12 mb-8">
          {LIGAS_DISPLAY.map(({ id, nombre, logo }) => (
            <div
              key={id}
              className="group flex flex-col items-center gap-2 cursor-default"
            >
              <div className="w-14 h-14 flex items-center justify-center">
                <img
                  src={logo}
                  alt={nombre}
                  className="w-full h-full object-contain grayscale opacity-50
                             group-hover:grayscale-0 group-hover:opacity-100
                             transition-all duration-300"
                />
              </div>
              <span className="text-xs text-slate-600 group-hover:text-slate-400 transition-colors font-medium">
                {nombre}
              </span>
            </div>
          ))}
        </div>

        <p className="text-xs text-slate-700 font-medium">
          Brasileirão y Liga Argentina · Próximamente
        </p>
      </div>
    </section>
  )
}

// ─── Widget últimos partidos ──────────────────────────────────────────────────
function UltimosPartidosWidget({ ligaId }) {
  const [partidos, setPartidos] = useState([])
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    setLoading(true)
    getUltimosPartidos(ligaId, 4)
      .then(setPartidos)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [ligaId])

  return (
    <div className="w-72 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur overflow-hidden">
      <div className="px-4 pt-3 pb-2 flex items-center justify-between">
        <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Últimos partidos</span>
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
      </div>

      {loading ? (
        <div className="px-4 pb-3 space-y-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-7 rounded-lg bg-slate-800/60 animate-pulse" />
          ))}
        </div>
      ) : partidos.length === 0 ? (
        <p className="px-4 pb-4 text-xs text-slate-600">Sin datos disponibles</p>
      ) : (
        <div className="pb-2">
          {partidos.map(p => {
            const local    = p.local?.nombre    ?? '?'
            const visitante = p.visitante?.nombre ?? '?'
            const gl = p.goles_local
            const gv = p.goles_visitante
            const localGana = gl > gv
            const visitaGana = gv > gl
            return (
              <div key={p.id} className="flex items-center gap-2 px-4 py-1.5 hover:bg-slate-800/40 transition-colors">
                <span className={`text-xs font-semibold truncate flex-1 text-right ${localGana ? 'text-white' : 'text-slate-500'}`}>
                  {local}
                </span>
                <span className="text-xs font-black text-cyan-400 tabular-nums shrink-0 w-10 text-center">
                  {gl} - {gv}
                </span>
                <span className={`text-xs font-semibold truncate flex-1 ${visitaGana ? 'text-white' : 'text-slate-500'}`}>
                  {visitante}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ─── Página ───────────────────────────────────────────────────────────────────
export default function Home() {
  const navigate   = useNavigate()
  const filtrosRef = useRef(null)

  const { ligaId, ligaActual } = useLiga()
  const [query,          setQuery]          = useState('')
  const [posicion,       setPosicion]       = useState('Todas')
  const [loading,        setLoading]        = useState(true)
  const [vista,          setVista]          = useState('cards')
  const [metricaRank,    setMetricaRank]    = useState('goles')
  const [jugadores,      setJugadores]      = useState(jugadoresFallback)
  const [fuenteDatos,    setFuenteDatos]    = useState('fallback')

  const [countJugadores, setCountJugadores] = useState(0)
  const [countPartidos,  setCountPartidos]  = useState(0)
  const [topScorer,      setTopScorer]      = useState(null)
  const [loadingTop,     setLoadingTop]     = useState(true)

  // Panel avanzado
  const [panelOpen, setPanelOpen] = useState(false)
  const [draft,     setDraft]     = useState(INITIAL_FILTROS)
  const [filtros,   setFiltros]   = useState(INITIAL_FILTROS)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getJugadores({ liga_id: ligaId })
      .then(data => {
        if (cancelled) return
        setJugadores(data)
        setFuenteDatos('api')
        setLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setJugadores(jugadoresFallback)
        setFuenteDatos('fallback')
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [ligaId])

  useEffect(() => {
    Promise.all([getConteoJugadores(), getConteoPartidos()]).then(([j, p]) => {
      setCountJugadores(j)
      setCountPartidos(p)
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoadingTop(true)
    getTopScorer(ligaId).then(data => {
      if (cancelled) return
      setTopScorer(data)
      setLoadingTop(false)
    })
    return () => { cancelled = true }
  }, [ligaId])

  // ── Aplicar / limpiar ──
  function aplicar() {
    setFiltros({ ...draft })
    setPanelOpen(false)
  }
  function limpiar() {
    setDraft(INITIAL_FILTROS)
    setFiltros(INITIAL_FILTROS)
    setPosicion('Todas')
  }

  function togglePanel() {
    if (!panelOpen) setDraft({ ...filtros })
    setPanelOpen(v => !v)
  }

  function scrollToFiltros() {
    filtrosRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // ── Filtrado combinado ──
  function pasaFiltros(j) {
    const q         = query.toLowerCase()
    const matchText = j.nombre.toLowerCase().includes(q) || j.equipo.toLowerCase().includes(q)
    const matchPos  = posicion === 'Todas' || j.posicion === posicion
    const matchEdad = j.edad >= filtros.edadMin && j.edad <= filtros.edadMax
    const matchG    = filtros.minGoles       === '' || j.metricas.goles        >= Number(filtros.minGoles)
    const matchA    = filtros.minAsistencias === '' || j.metricas.asistencias  >= Number(filtros.minAsistencias)
    const matchXG   = filtros.minXG          === '' || j.metricas.xG           >= Number(filtros.minXG)
    const matchXA   = filtros.minXA          === '' || j.metricas.xA           >= Number(filtros.minXA)
    const matchMin   = filtros.minMinutos === '' || j.metricas.minutos_jugados >= Number(filtros.minMinutos)
    const matchValor = filtros.maxValor   === '' || (j.valor_mercado ?? Infinity) <= Number(filtros.maxValor)
    return matchText && matchPos && matchEdad && matchG && matchA && matchXG && matchXA && matchMin && matchValor
  }

  const filtrados    = jugadores
    .filter(pasaFiltros)
    .sort((a, b) => (b.metricas.goles ?? 0) - (a.metricas.goles ?? 0))
  const rankingLista = [...jugadores]
    .filter(pasaFiltros)
    .sort((a, b) => getMetricVal(b, metricaRank) - getMetricVal(a, metricaRank))
    .slice(0, 10)

  const numFiltros  = contarFiltrosActivos(filtros, posicion)

  return (
    <main className="animate-fade-in">

      {/* ─── Hero ─── */}
      <section className="relative overflow-hidden bg-slate-950 hero-grid">
        <div className="absolute -top-32 -left-32 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-blue-700/5 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/2 right-0 -translate-y-1/2 translate-x-1/2 w-[600px] h-[600px] rounded-full border border-cyan-500/5 pointer-events-none" />
        <div className="absolute bottom-0 left-1/4 w-[300px] h-[300px] bg-violet-600/4 rounded-full blur-3xl pointer-events-none" />
        {/* Grid sutil */}
        <div className="absolute inset-0 opacity-[0.025] pointer-events-none"
          style={{ backgroundImage: 'linear-gradient(rgba(34,211,238,0.5) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,0.5) 1px,transparent 1px)', backgroundSize: '64px 64px' }}
        />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28">
          <div className="flex items-center gap-16">

            {/* Texto */}
            <div className="flex-1 max-w-2xl">
              {!loading && fuenteDatos === 'api' && (
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-cyan-500/20 bg-cyan-500/5 mb-8">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                  <span className="text-cyan-400 text-xs font-semibold tracking-widest uppercase">
                    {ligaActual?.nombre ?? 'Liga'} 2025/26 · {jugadores.length} jugadores
                  </span>
                </div>
              )}

              <h1 className="mb-6 leading-[0.95]">
                <span className="block text-5xl sm:text-7xl font-light text-slate-500 tracking-tight">El fútbol</span>
                <span className="block text-5xl sm:text-7xl font-black text-white tracking-tight">en datos</span>
                <span className="block text-5xl sm:text-7xl font-black text-cyan-400 tracking-tight">reales.</span>
              </h1>

              <p className="text-slate-400 text-lg sm:text-xl max-w-xl leading-relaxed mb-8 font-light">
                Análisis avanzado, scouting inteligente y estadísticas que no encontrarás en ningún otro sitio.
                <span className="text-white font-medium"> En español.</span>
              </p>

              {/* ── Botones CTA ── */}
              <div className="flex flex-wrap gap-3 mb-10">
                <button
                  onClick={scrollToFiltros}
                  className="flex items-center gap-2 px-5 py-3 rounded-2xl text-sm font-bold
                             bg-cyan-400 text-slate-950 hover:bg-cyan-300
                             transition-all duration-150 shadow-lg shadow-cyan-500/25"
                >
                  Explorar jugadores
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                <button
                  onClick={() => navigate('/insights')}
                  className="flex items-center gap-2 px-5 py-3 rounded-2xl text-sm font-bold
                             bg-slate-900/80 border border-slate-700/80 text-white
                             hover:border-cyan-500/40 hover:text-cyan-400
                             transition-all duration-150 backdrop-blur"
                >
                  Ver Insights
                </button>
              </div>

              {/* ── Buscador + botón avanzado ── */}
              <div className="max-w-xl">
                <div className="flex gap-3">
                  <div className="relative flex-1">
                    <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500 pointer-events-none"
                         fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <input
                      type="text"
                      placeholder="Busca un jugador o equipo..."
                      value={query}
                      onChange={e => setQuery(e.target.value)}
                      className="w-full bg-slate-900/80 backdrop-blur border border-slate-700/80 rounded-2xl
                                 pl-12 pr-4 py-4 text-white placeholder-slate-600
                                 focus:outline-none focus:border-cyan-500/60 focus:bg-slate-900
                                 text-base transition-all"
                    />
                  </div>

                  <button
                    onClick={togglePanel}
                    className={`flex items-center gap-2 px-4 py-3 rounded-2xl text-sm font-semibold
                                border transition-all duration-150 shrink-0 ${
                      panelOpen
                        ? 'bg-cyan-400/15 border-cyan-400/40 text-cyan-400'
                        : numFiltros > 0
                        ? 'bg-cyan-400/10 border-cyan-400/30 text-cyan-400'
                        : 'bg-slate-900/80 border-slate-700/80 text-slate-400 hover:text-white hover:border-slate-600'
                    }`}
                  >
                    <IconFilter count={numFiltros} />
                    <span className="hidden sm:inline">Filtros</span>
                  </button>
                </div>

                {/* ── Panel avanzado ── */}
                <div
                  style={{
                    maxHeight: panelOpen ? '700px' : '0',
                    opacity:   panelOpen ? 1 : 0,
                    overflow:  'hidden',
                    transition: 'max-height 0.35s ease, opacity 0.25s ease',
                  }}
                >
                  <div className="mt-3 bg-slate-900/95 backdrop-blur border border-slate-700/60
                                  rounded-2xl p-5 space-y-5 shadow-2xl shadow-black/60">

                    <DualSlider
                      minVal={draft.edadMin}  maxVal={draft.edadMax}
                      onMinChange={v => setDraft(d => ({ ...d, edadMin: v }))}
                      onMaxChange={v => setDraft(d => ({ ...d, edadMax: v }))}
                    />

                    <div>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                        Posición
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {POSITION_FILTERS.map(({ value, icon, label }) => (
                          <button
                            key={value}
                            onClick={() => setPosicion(value)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium
                                        transition-all duration-150 ${
                              posicion === value
                                ? 'bg-cyan-400 text-slate-950'
                                : 'bg-slate-800 border border-slate-700 text-slate-400 hover:text-white'
                            }`}
                          >
                            <span>{icon}</span>{label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                        Mínimo por estadística
                      </p>
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        <NumInput label="Goles"       value={draft.minGoles}       onChange={v => setDraft(d => ({ ...d, minGoles: v }))} />
                        <NumInput label="Asistencias" value={draft.minAsistencias} onChange={v => setDraft(d => ({ ...d, minAsistencias: v }))} />
                        <NumInput label="xG"          value={draft.minXG}          onChange={v => setDraft(d => ({ ...d, minXG: v }))} />
                        <NumInput label="xA"          value={draft.minXA}          onChange={v => setDraft(d => ({ ...d, minXA: v }))} />
                        <NumInput label="Min. jugados" value={draft.minMinutos}    onChange={v => setDraft(d => ({ ...d, minMinutos: v }))} placeholder="0" />
                        <NumInput label="Valor máx. (M€)" value={draft.maxValor}  onChange={v => setDraft(d => ({ ...d, maxValor: v }))} placeholder="200" />
                      </div>
                    </div>

                    <div className="pt-1 border-t border-slate-800 flex items-center justify-between gap-3">
                      <span className="text-xs text-slate-500">
                        {(() => {
                          const preview = jugadores.filter(j => {
                            const matchPos  = posicion === 'Todas' || j.posicion === posicion
                            const matchEdad = j.edad >= draft.edadMin && j.edad <= draft.edadMax
                            const matchG    = draft.minGoles       === '' || j.metricas.goles        >= Number(draft.minGoles)
                            const matchA    = draft.minAsistencias === '' || j.metricas.asistencias  >= Number(draft.minAsistencias)
                            const matchXG   = draft.minXG          === '' || j.metricas.xG           >= Number(draft.minXG)
                            const matchXA   = draft.minXA          === '' || j.metricas.xA           >= Number(draft.minXA)
                            const matchMin   = draft.minMinutos === '' || j.metricas.minutos_jugados >= Number(draft.minMinutos)
                            const matchValor = draft.maxValor   === '' || (j.valor_mercado ?? Infinity) <= Number(draft.maxValor)
                            return matchPos && matchEdad && matchG && matchA && matchXG && matchXA && matchMin && matchValor
                          }).length
                          return `${preview} jugador${preview !== 1 ? 'es' : ''} con estos filtros`
                        })()}
                      </span>
                      <div className="flex gap-2">
                        <button
                          onClick={limpiar}
                          className="px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-400
                                     hover:text-white border border-slate-700 hover:border-slate-500
                                     transition-all duration-150"
                        >
                          Limpiar
                        </button>
                        <button
                          onClick={aplicar}
                          className="px-4 py-1.5 rounded-xl text-xs font-bold bg-cyan-400 text-slate-950
                                     hover:bg-cyan-300 transition-all duration-150 shadow-lg shadow-cyan-500/20"
                        >
                          Aplicar filtros
                        </button>
                      </div>
                    </div>

                  </div>
                </div>
              </div>
            </div>

            {/* Columna derecha — solo desktop */}
            <div className="hidden lg:flex flex-col gap-3 shrink-0">

              {/* Últimos partidos */}
              <UltimosPartidosWidget ligaId={ligaId} />

              {/* Card máximo goleador */}
              <div className="opacity-90">
                <HeroDecorCard
                  jugador={topScorer}
                  loading={loadingTop}
                  ligaNombre={ligaId === 1 ? 'LaLiga' : ligaId === 24 ? 'Premier' : 'Bundesliga'}
                />
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ─── Stats Animadas ─── */}
      <StatsAnimadasSection />

      {/* ─── Qué puedes hacer ─── */}
      <QuesPuedesHacerSection />

      {/* ─── Preview Insights ─── */}
      <InsightsPreviewSection />

      {/* ─── Ligas Disponibles ─── */}
      <LigasDisponiblesSection />

      {/* ─── Filtros + contenido ─── */}
      <section ref={filtrosRef} className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

        {/* Fila de controles */}
        <div className="flex items-start justify-between gap-4 mb-8">
          {vista === 'cards' ? (
            <div className="flex overflow-x-auto scrollbar-hide gap-2 pb-1 flex-1">
              {POSITION_FILTERS.map(({ value, icon, label }) => (
                <button
                  key={value}
                  onClick={() => setPosicion(value)}
                  className={`flex shrink-0 items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-medium
                              transition-all duration-150 ${
                    posicion === value
                      ? 'bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/20'
                      : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-600'
                  }`}
                >
                  <span className="text-base leading-none">{icon}</span>{label}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex overflow-x-auto scrollbar-hide gap-2 pb-1 flex-1">
              {RANKING_METRICS.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setMetricaRank(key)}
                  className={`flex shrink-0 items-center px-3.5 py-2 rounded-full text-sm font-medium
                              transition-all duration-150 ${
                    metricaRank === key
                      ? 'bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/20'
                      : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-600'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          <div className="flex gap-1 p-1 bg-slate-900 border border-slate-800 rounded-xl shrink-0">
            <button onClick={() => setVista('cards')} title="Vista cards"
              className={`p-2 rounded-lg transition-all duration-150 ${
                vista === 'cards' ? 'bg-cyan-400 text-slate-950' : 'text-slate-500 hover:text-white'
              }`}>
              <IconCards />
            </button>
            <button onClick={() => setVista('ranking')} title="Vista ranking"
              className={`p-2 rounded-lg transition-all duration-150 ${
                vista === 'ranking' ? 'bg-cyan-400 text-slate-950' : 'text-slate-500 hover:text-white'
              }`}>
              <IconRanking />
            </button>
          </div>
        </div>

        {/* Filtros activos — badge informativo */}
        {numFiltros > 0 && (
          <div className="flex items-center gap-2 mb-5 animate-fade-in">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
            <span className="text-xs text-cyan-400 font-semibold">
              {numFiltros} filtro{numFiltros !== 1 ? 's' : ''} activo{numFiltros !== 1 ? 's' : ''}
            </span>
            <button onClick={limpiar} className="text-xs text-slate-600 hover:text-slate-400 transition-colors ml-1">
              · Limpiar
            </button>
          </div>
        )}

        {/* ── Vista cards ── */}
        {vista === 'cards' && (
          <>
            <div className="flex items-center gap-2 mb-6">
              {!loading && fuenteDatos === 'api' && (
                <span className="text-slate-600 text-sm">
                  {filtrados.length} jugador{filtrados.length !== 1 ? 'es' : ''}
                </span>
              )}
              {posicion !== 'Todas' && (
                <span className="text-xs text-cyan-400 bg-cyan-400/10 px-2 py-0.5 rounded-full">
                  {posicion}
                </span>
              )}
            </div>

            {loading ? (
              <Spinner />
            ) : filtrados.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {filtrados.map((j, i) => (
                  <div key={j.id} className="animate-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
                    <PlayerCard jugador={j} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-24 text-center">
                <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-3xl mb-4">
                  🔍
                </div>
                <p className="text-white font-bold text-lg">Sin resultados</p>
                <p className="text-slate-500 text-sm mt-1">
                  {numFiltros > 0 ? 'Ningún jugador cumple los filtros activos.' : 'Prueba con otro nombre o equipo.'}
                </p>
                {numFiltros > 0 && (
                  <button onClick={limpiar} className="mt-3 text-xs text-cyan-400 hover:underline">
                    Limpiar filtros
                  </button>
                )}
              </div>
            )}
          </>
        )}

        {/* ── Vista ranking ── */}
        {vista === 'ranking' && (
          <>
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2">
                <span className="text-slate-500 text-sm">Top 10 por</span>
                <span className="text-cyan-400 text-sm font-bold">
                  {RANKING_METRICS.find(m => m.key === metricaRank)?.label}
                </span>
                <span className="text-slate-700 text-xs">· {ligaActual?.nombre ?? 'Liga'} 2025/26</span>
              </div>
              <span className="text-xs text-slate-700">{rankingLista.length} jugadores</span>
            </div>

            {loading ? (
              <Spinner />
            ) : rankingLista.length > 0 ? (
              <RankingView lista={rankingLista} metricKey={metricaRank} />
            ) : (
              <div className="flex flex-col items-center justify-center py-24 text-center">
                <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-3xl mb-4">
                  🔍
                </div>
                <p className="text-white font-bold text-lg">Sin resultados</p>
                <p className="text-slate-500 text-sm mt-1">Ningún jugador cumple los filtros activos.</p>
                <button onClick={limpiar} className="mt-3 text-xs text-cyan-400 hover:underline">
                  Limpiar filtros
                </button>
              </div>
            )}
          </>
        )}

      </section>
    </main>
  )
}
