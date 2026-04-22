import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer,
} from 'recharts'
import { jugadores as jugadoresFallback } from '../data/jugadores'
import { getJugadores } from '../services/api'
import PlayerRadarChart from '../components/RadarChart'
import { ScoutingSkeleton } from '../components/Skeletons'

// ─── Constantes ───────────────────────────────────────────────────────────────
const MAX_VALUES = {
  goles: 30, asistencias: 20, xG: 25, xA: 15,
  pases_completados: 95, regates: 9, recuperaciones: 12,
  minutos_jugados: 3600, goles_por_90: 1.2, asistencias_por_90: 0.8, ga_por_90: 1.8,
}

const METRIC_LABELS = {
  goles: 'Goles', asistencias: 'Asistencias', xG: 'xG', xA: 'xA',
  pases_completados: 'Pases %', regates: 'Regates',
  recuperaciones: 'Recuperaciones',
  minutos_jugados: 'Minutos', goles_por_90: 'G/90',
  asistencias_por_90: 'A/90', ga_por_90: 'G+A/90',
}

// Solo las 8 métricas base van al radar
const RADAR_METRICS = ['goles', 'asistencias', 'xG', 'xA', 'pases_completados', 'regates', 'recuperaciones']

const CATEGORIES = [
  { label: 'Ofensiva',   icon: '⚽', metrics: ['goles', 'asistencias', 'xG', 'xA'] },
  { label: 'Creación',   icon: '🎯', metrics: ['pases_completados', 'xA', 'asistencias_por_90'] },
  { label: 'Defensiva',  icon: '🛡️', metrics: ['recuperaciones', 'regates'] },
]

const COLOR_A  = '#22d3ee'   // cyan
const COLOR_B  = '#a78bfa'   // violet
const COLORS   = ['#22d3ee', '#818cf8', '#fb923c']
const MEDALS   = ['🥇', '🥈', '🥉']

// ─── Helpers ──────────────────────────────────────────────────────────────────
function normalizar(metricas) {
  return Object.entries(metricas).map(([k, v]) => v / (MAX_VALUES[k] || 100))
}

function distancia(a, b) {
  const na = normalizar(a.metricas)
  const nb = normalizar(b.metricas)
  return Math.sqrt(na.reduce((acc, v, i) => acc + (v - nb[i]) ** 2, 0))
}

function similitudPct(dist) {
  return Math.max(0, Math.round((1 - dist / 2) * 100))
}

function getInitials(nombre) {
  return nombre.split(' ').slice(0, 2).map(n => n[0]).join('').toUpperCase()
}

// ─── Fila de duelo: similares ─────────────────────────────────────────────────
function DuelRow({ label, refVal, simVal, metricKey }) {
  const max     = MAX_VALUES[metricKey] || 100
  const refPct  = Math.min((refVal / max) * 100, 100)
  const simPct  = Math.min((simVal / max) * 100, 100)
  const refWins = refVal > simVal
  const simWins = simVal > refVal

  return (
    <div className="grid grid-cols-[1fr_5rem_1fr] sm:grid-cols-[1fr_8rem_1fr] items-center gap-2 sm:gap-3 py-3
                    border-b border-slate-800/40 last:border-0">
      <div className="flex items-center justify-end gap-2.5">
        <span className={`font-black text-sm tabular-nums w-8 text-right shrink-0 transition-colors ${
          refWins ? 'text-cyan-400' : 'text-slate-500'}`}>
          {refVal}
        </span>
        <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden" style={{ direction: 'rtl' }}>
          <div className={`h-full rounded-full transition-all duration-500 ${refWins ? 'bg-cyan-400' : 'bg-slate-700'}`}
               style={{ width: `${refPct}%` }} />
        </div>
      </div>
      <p className="text-center text-xs font-semibold text-slate-400 tracking-wide leading-tight">{label}</p>
      <div className="flex items-center gap-2.5">
        <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
          <div className={`h-full rounded-full transition-all duration-500 ${simWins ? 'bg-slate-300' : 'bg-slate-700'}`}
               style={{ width: `${simPct}%` }} />
        </div>
        <span className={`font-black text-sm tabular-nums w-8 shrink-0 transition-colors ${
          simWins ? 'text-white' : 'text-slate-500'}`}>
          {simVal}
        </span>
      </div>
    </div>
  )
}

// ─── Fila comparador: cyan A vs violet B ─────────────────────────────────────
function ComparRow({ label, valA, valB, metricKey }) {
  const max  = MAX_VALUES[metricKey] || 100
  const pctA = Math.min(((valA ?? 0) / max) * 100, 100)
  const pctB = Math.min(((valB ?? 0) / max) * 100, 100)
  const aWins = (valA ?? 0) > (valB ?? 0)
  const bWins = (valB ?? 0) > (valA ?? 0)

  return (
    <div className="grid grid-cols-[1fr_5rem_1fr] sm:grid-cols-[1fr_8rem_1fr] items-center gap-2 sm:gap-3 py-3
                    border-b border-slate-800/40 last:border-0">
      <div className="flex items-center justify-end gap-2.5">
        <span className={`font-black text-sm tabular-nums w-10 text-right shrink-0 ${aWins ? 'text-cyan-400' : 'text-slate-500'}`}>
          {valA ?? '—'}
        </span>
        <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden" style={{ direction: 'rtl' }}>
          <div className={`h-full rounded-full transition-all duration-500 ${aWins ? 'bg-cyan-400' : 'bg-slate-700'}`}
               style={{ width: `${pctA}%` }} />
        </div>
      </div>
      <p className="text-center text-xs font-semibold text-slate-400 tracking-wide leading-tight">{label}</p>
      <div className="flex items-center gap-2.5">
        <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
          <div className={`h-full rounded-full transition-all duration-500 ${bWins ? 'bg-violet-400' : 'bg-slate-700'}`}
               style={{ width: `${pctB}%` }} />
        </div>
        <span className={`font-black text-sm tabular-nums w-10 shrink-0 ${bWins ? 'text-violet-400' : 'text-slate-500'}`}>
          {valB ?? '—'}
        </span>
      </div>
    </div>
  )
}

// ─── Radar con dos jugadores superpuestos ─────────────────────────────────────
function DualRadar({ a, b }) {
  const data = RADAR_METRICS.map(key => ({
    label: METRIC_LABELS[key],
    A: Math.round(((a.metricas[key] ?? 0) / MAX_VALUES[key]) * 100),
    B: Math.round(((b.metricas[key] ?? 0) / MAX_VALUES[key]) * 100),
  }))
  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
        <PolarGrid stroke="#1e293b" strokeDasharray="4 4" />
        <PolarAngleAxis
          dataKey="label"
          tick={{ fill: '#64748b', fontSize: 11, fontWeight: 600, fontFamily: 'Space Grotesk' }}
        />
        <Radar dataKey="A" stroke={COLOR_A} fill={COLOR_A} fillOpacity={0.18} strokeWidth={2}
               dot={{ r: 3, fill: COLOR_A, strokeWidth: 0 }}
               isAnimationActive animationDuration={700} animationEasing="ease-out" />
        <Radar dataKey="B" stroke={COLOR_B} fill={COLOR_B} fillOpacity={0.18} strokeWidth={2}
               dot={{ r: 3, fill: COLOR_B, strokeWidth: 0 }}
               isAnimationActive animationDuration={700} animationEasing="ease-out" />
      </RadarChart>
    </ResponsiveContainer>
  )
}

// ─── Select de jugador reutilizable ───────────────────────────────────────────
function PlayerSelect({ value, onChange, label, color, exclude }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2">
        <span className="w-3 h-1.5 rounded-full inline-block" style={{ backgroundColor: color }} />
        {label}
      </p>
      <select
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="bg-slate-800 border border-slate-700 text-white rounded-xl px-4 py-3
                   text-sm focus:outline-none focus:border-cyan-500 transition-colors
                   w-full font-medium"
      >
        {jugadores.map(j => (
          <option key={j.id} value={j.id} disabled={j.id === exclude}>
            {j.nombre} — {j.equipo}
          </option>
        ))}
      </select>
    </div>
  )
}

// ─── Página ───────────────────────────────────────────────────────────────────
export default function Scouting() {
  const [searchParams]  = useSearchParams()
  const [tab, setTab]   = useState('similares')
  const [jugadores, setJugadores] = useState(jugadoresFallback)

  // ── Tab similares ──
  const [seleccionado, setSeleccionado] = useState(
    Number(searchParams.get('ref')) || jugadoresFallback[0].id
  )
  const [duelId, setDuelId]   = useState(null)
  const [loading, setLoading] = useState(true)

  // ── Tab comparador ──
  const [comparA, setComparA] = useState(jugadoresFallback[0].id)
  const [comparB, setComparB] = useState(jugadoresFallback[1].id)

  useEffect(() => {
    getJugadores().then(setJugadores).catch(() => {})
  }, [])

  useEffect(() => {
    const ref = Number(searchParams.get('ref'))
    if (ref) setSeleccionado(ref)
  }, [searchParams])

  useEffect(() => { setDuelId(null) }, [seleccionado])

  useEffect(() => {
    setLoading(true)
    const t = setTimeout(() => setLoading(false), 1100)
    return () => clearTimeout(t)
  }, [seleccionado])

  const referencia   = jugadores.find(j => j.id === seleccionado) || jugadores[0]
  const similares    = jugadores
    .filter(j => j.id !== referencia.id)
    .map(j => ({ ...j, dist: distancia(referencia, j) }))
    .sort((a, b) => a.dist - b.dist)
    .slice(0, 3)
  const comparados   = [referencia, ...similares]
  const metricas     = Object.keys(referencia.metricas)
  const duelJugador  = similares.find(j => j.id === duelId) ?? similares[0]

  const jugadorA     = jugadores.find(j => j.id === comparA) || jugadores[0]
  const jugadorB     = jugadores.find(j => j.id === comparB) || jugadores[1]
  const mismoJugador = jugadorA.id === jugadorB.id

  return (
    <main className="animate-fade-in max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

      {/* ── Header ── */}
      <div className="mb-8">
        <h1 className="text-3xl font-black text-white mb-1">Scouting</h1>
        <p className="text-slate-400 font-light">
          Encuentra jugadores similares o enfrenta dos perfiles directamente.
        </p>
      </div>

      {/* ── Tabs ── */}
      <div className="flex gap-1 p-1 bg-slate-900 border border-slate-800 rounded-xl w-fit mb-8">
        {[
          { id: 'similares',  label: 'Jugadores similares' },
          { id: 'comparador', label: 'Comparador' },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-150 ${
              tab === t.id
                ? 'bg-cyan-400 text-slate-950 shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ══════════════════════════════════════════════════════════ SIMILARES */}
      {tab === 'similares' && (
        <div className="animate-fade-in space-y-6">
          {/* Selector referencia */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">
              Jugador de referencia
            </p>
            <select
              value={seleccionado}
              onChange={e => setSeleccionado(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 text-white rounded-xl px-4 py-3
                         text-sm focus:outline-none focus:border-cyan-500 transition-colors
                         w-full sm:w-80 font-medium"
            >
              {jugadores.map(j => (
                <option key={j.id} value={j.id}>{j.nombre} — {j.equipo}</option>
              ))}
            </select>
          </div>

          {/* Similar cards + radares (skeleton / real) */}
          {loading ? <ScoutingSkeleton /> : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {similares.map((j, i) => {
                  const selected = duelJugador?.id === j.id
                  return (
                    <button
                      key={j.id}
                      onClick={() => setDuelId(j.id)}
                      style={{ animationDelay: `${i * 80}ms` }}
                      className={`animate-fade-up text-left bg-slate-900 border rounded-2xl p-5
                                  transition-all duration-200 will-change-transform hover:scale-[1.02] ${
                        selected
                          ? 'border-cyan-500/50 shadow-lg shadow-cyan-500/10'
                          : 'border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <span className="text-xl">{MEDALS[i]}</span>
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[i + 1] }} />
                          <span className="text-xs font-bold tabular-nums" style={{ color: COLORS[i + 1] }}>
                            {similitudPct(j.dist)}% similitud
                          </span>
                        </div>
                      </div>
                      <h3 className="font-bold text-white text-base">{j.nombre}</h3>
                      <p className="text-slate-500 text-sm">{j.equipo}</p>
                      <p className="text-slate-600 text-xs mt-1">{j.posicion} · {j.edad} años</p>
                      {j.valor_mercado && (
                        <p className="text-emerald-400 text-sm font-bold mt-2">
                          €{j.valor_mercado}M
                        </p>
                      )}
                      {selected && (
                        <p className="mt-3 text-xs font-semibold text-cyan-400 flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                          Duelo activo
                        </p>
                      )}
                    </button>
                  )
                })}
              </div>

              {/* Radar 4-up */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4">
                  Comparativa de radares
                </p>
                <div className="flex flex-wrap gap-4 mb-6">
                  {comparados.map((j, i) => (
                    <div key={j.id} className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[i] }} />
                      <span className="text-sm text-slate-300 font-medium">{j.nombre}</span>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {comparados.map((j, i) => (
                    <div key={j.id}>
                      <p className="text-center text-xs font-bold mb-1 truncate px-2"
                         style={{ color: COLORS[i] }}>
                        {j.nombre.split(' ')[0]}
                      </p>
                      <PlayerRadarChart metricas={j.metricas} color={COLORS[i]} />
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Duelo métrica */}
          {!loading && duelJugador && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                  Comparativa de métricas
                </p>
                <div className="flex items-center gap-3 text-xs font-semibold">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-1.5 rounded-full bg-cyan-400 inline-block" />
                    <span className="text-cyan-400 truncate max-w-[100px]">{referencia.nombre.split(' ')[0]}</span>
                  </div>
                  <span className="text-slate-700">vs</span>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-1.5 rounded-full bg-slate-300 inline-block" />
                    <span className="text-slate-300 truncate max-w-[100px]">{duelJugador.nombre.split(' ')[0]}</span>
                  </div>
                </div>
              </div>
              <div>
                {metricas.map(m => (
                  <DuelRow
                    key={m}
                    label={METRIC_LABELS[m]}
                    metricKey={m}
                    refVal={referencia.metricas[m]}
                    simVal={duelJugador.metricas[m]}
                  />
                ))}
              </div>
              {(() => {
                const refWins = metricas.filter(m => referencia.metricas[m] > duelJugador.metricas[m]).length
                const simWins = metricas.filter(m => duelJugador.metricas[m] > referencia.metricas[m]).length
                return (
                  <div className="mt-5 pt-4 border-t border-slate-800 flex items-center justify-center gap-6 text-sm">
                    <div className="text-center">
                      <p className="text-2xl font-black text-cyan-400">{refWins}</p>
                      <p className="text-slate-500 text-xs">{referencia.nombre.split(' ')[0]}</p>
                    </div>
                    <span className="text-slate-600 font-bold">métricas ganadas</span>
                    <div className="text-center">
                      <p className="text-2xl font-black text-white">{simWins}</p>
                      <p className="text-slate-500 text-xs">{duelJugador.nombre.split(' ')[0]}</p>
                    </div>
                  </div>
                )
              })()}
            </div>
          )}

          {/* Stats table */}
          {!loading && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                  Comparativa de estadísticas
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-800">
                      <th className="text-left px-6 py-3 text-slate-500 font-semibold text-xs uppercase tracking-wider">
                        Métrica
                      </th>
                      {comparados.map((j, i) => (
                        <th key={j.id}
                            className="text-right px-4 py-3 font-black text-xs uppercase tracking-wider whitespace-nowrap"
                            style={{ color: COLORS[i] }}>
                          {j.nombre.split(' ')[0]}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {metricas.map(m => {
                      const vals = comparados.map(j => j.metricas[m])
                      const max  = Math.max(...vals)
                      return (
                        <tr key={m} className="border-b border-slate-800/40 last:border-0 hover:bg-slate-800/30 transition-colors">
                          <td className="px-6 py-3 text-slate-400 text-sm">{METRIC_LABELS[m] || m}</td>
                          {vals.map((v, i) => (
                            <td key={i} className={`text-right px-4 py-3 font-black tabular-nums text-sm ${
                              v === max ? 'text-cyan-400' : 'text-white'
                            }`}>{v}</td>
                          ))}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════ COMPARADOR */}
      {tab === 'comparador' && (
        <div className="animate-fade-in space-y-6">

          {/* Dos selectores */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <PlayerSelect
              value={comparA}
              onChange={setComparA}
              label="Jugador A"
              color={COLOR_A}
              exclude={comparB}
            />
            <PlayerSelect
              value={comparB}
              onChange={setComparB}
              label="Jugador B"
              color={COLOR_B}
              exclude={comparA}
            />
          </div>

          {mismoJugador ? (
            <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
              <div className="w-14 h-14 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-2xl">
                ⚖️
              </div>
              <p className="text-white font-bold">Selecciona dos jugadores distintos</p>
              <p className="text-slate-500 text-sm">El comparador necesita dos perfiles diferentes.</p>
            </div>
          ) : (
            <>
              {/* Header enfrentado */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
                  {/* Jugador A */}
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-2xl border flex items-center justify-center shrink-0"
                         style={{ backgroundColor: `${COLOR_A}18`, borderColor: `${COLOR_A}30` }}>
                      <span className="text-lg font-black" style={{ color: COLOR_A }}>
                        {getInitials(jugadorA.nombre)}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <p className="font-black text-white text-base leading-tight truncate">{jugadorA.nombre}</p>
                      <p className="text-slate-400 text-sm truncate">{jugadorA.equipo}</p>
                      <p className="text-xs text-slate-600 mt-0.5">{jugadorA.posicion} · {jugadorA.edad} años</p>
                      {jugadorA.valor_mercado && (
                        <p className="text-emerald-400 text-sm font-bold mt-1">€{jugadorA.valor_mercado}M</p>
                      )}
                    </div>
                  </div>

                  {/* vs */}
                  <div className="px-2 flex items-center gap-2.5">
                    <div className="h-px w-10 sm:w-16"
                         style={{ background: `linear-gradient(to left, ${COLOR_A}60, transparent)` }} />
                    <span
                      className="text-2xl font-black tracking-widest text-white shrink-0"
                      style={{ textShadow: '0 0 24px rgba(255,255,255,0.25)' }}
                    >
                      VS
                    </span>
                    <div className="h-px w-10 sm:w-16"
                         style={{ background: `linear-gradient(to right, ${COLOR_B}60, transparent)` }} />
                  </div>

                  {/* Jugador B */}
                  <div className="flex items-center gap-4 justify-end">
                    <div className="min-w-0 text-right">
                      <p className="font-black text-white text-base leading-tight truncate">{jugadorB.nombre}</p>
                      <p className="text-slate-400 text-sm truncate">{jugadorB.equipo}</p>
                      <p className="text-xs text-slate-600 mt-0.5">{jugadorB.edad} años · {jugadorB.posicion}</p>
                      {jugadorB.valor_mercado && (
                        <p className="text-emerald-400 text-sm font-bold mt-1">€{jugadorB.valor_mercado}M</p>
                      )}
                    </div>
                    <div className="w-14 h-14 rounded-2xl border flex items-center justify-center shrink-0"
                         style={{ backgroundColor: `${COLOR_B}18`, borderColor: `${COLOR_B}30` }}>
                      <span className="text-lg font-black" style={{ color: COLOR_B }}>
                        {getInitials(jugadorB.nombre)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Grid radar + métricas */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Radar superpuesto */}
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">
                    Radar comparativo
                  </p>
                  <div className="flex gap-5 mb-2">
                    <span className="flex items-center gap-2 text-xs font-semibold" style={{ color: COLOR_A }}>
                      <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: COLOR_A }} />
                      {jugadorA.nombre.split(' ')[0]}
                    </span>
                    <span className="flex items-center gap-2 text-xs font-semibold" style={{ color: COLOR_B }}>
                      <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: COLOR_B }} />
                      {jugadorB.nombre.split(' ')[0]}
                    </span>
                  </div>
                  <DualRadar a={jugadorA} b={jugadorB} />
                </div>

                {/* Barras métricas */}
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                      Comparativa métrica
                    </p>
                    <div className="flex items-center gap-3 text-xs font-semibold">
                      <span className="flex items-center gap-1.5" style={{ color: COLOR_A }}>
                        <span className="w-3 h-1.5 rounded-full inline-block" style={{ backgroundColor: COLOR_A }} />
                        {jugadorA.nombre.split(' ')[0]}
                      </span>
                      <span className="text-slate-700">vs</span>
                      <span className="flex items-center gap-1.5" style={{ color: COLOR_B }}>
                        <span className="w-3 h-1.5 rounded-full inline-block" style={{ backgroundColor: COLOR_B }} />
                        {jugadorB.nombre.split(' ')[0]}
                      </span>
                    </div>
                  </div>
                  {Object.keys(MAX_VALUES).map(m => (
                    <ComparRow
                      key={m}
                      label={METRIC_LABELS[m]}
                      metricKey={m}
                      valA={jugadorA.metricas[m]}
                      valB={jugadorB.metricas[m]}
                    />
                  ))}
                </div>
              </div>

              {/* Veredicto por categoría */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-5">
                  Veredicto por categoría
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                  {CATEGORIES.map(cat => {
                    const winsA  = cat.metrics.filter(m => (jugadorA.metricas[m] ?? 0) > (jugadorB.metricas[m] ?? 0)).length
                    const winsB  = cat.metrics.filter(m => (jugadorB.metricas[m] ?? 0) > (jugadorA.metricas[m] ?? 0)).length
                    const winner = winsA > winsB ? 'A' : winsB > winsA ? 'B' : 'draw'
                    const winName = winner === 'A' ? jugadorA.nombre.split(' ')[0]
                                  : winner === 'B' ? jugadorB.nombre.split(' ')[0]
                                  : null

                    // Margen normalizado promedio (0-100)
                    const rawMargin = cat.metrics.reduce((sum, m) => {
                      const maxVal = MAX_VALUES[m] || 100
                      return sum + ((jugadorA.metricas[m] ?? 0) - (jugadorB.metricas[m] ?? 0)) / maxVal
                    }, 0) / cat.metrics.length
                    const marginPct = Math.round(Math.abs(rawMargin) * 100)

                    return (
                      <div
                        key={cat.label}
                        className={`rounded-2xl p-5 border transition-all ${
                          winner === 'A' ? 'border-cyan-500/25 bg-cyan-500/5' :
                          winner === 'B' ? 'border-violet-500/25 bg-violet-500/5' :
                          'border-slate-700/60 bg-slate-800/30'
                        }`}
                      >
                        {/* Título */}
                        <div className="flex items-center justify-between mb-4">
                          <div className="flex items-center gap-2">
                            <span className="text-xl">{cat.icon}</span>
                            <p className="font-bold text-white text-sm">{cat.label}</p>
                          </div>
                          {winner !== 'draw' && (
                            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                              winner === 'A'
                                ? 'bg-cyan-400/15 text-cyan-400'
                                : 'bg-violet-400/15 text-violet-400'
                            }`}>
                              +{marginPct}%
                            </span>
                          )}
                        </div>

                        {/* Score */}
                        <div className="flex items-center gap-3 mb-3">
                          <span className={`text-3xl font-black tabular-nums ${
                            winner === 'A' ? 'text-cyan-400' : 'text-slate-500'
                          }`}>{winsA}</span>
                          <span className="text-slate-700 font-bold">—</span>
                          <span className={`text-3xl font-black tabular-nums ${
                            winner === 'B' ? 'text-violet-400' : 'text-slate-500'
                          }`}>{winsB}</span>
                        </div>

                        {/* Ganador */}
                        {winName ? (
                          <p className={`text-xs font-semibold flex items-center gap-1.5 ${
                            winner === 'A' ? 'text-cyan-400' : 'text-violet-400'
                          }`}>
                            <span className="w-1.5 h-1.5 rounded-full inline-block"
                                  style={{ backgroundColor: winner === 'A' ? COLOR_A : COLOR_B }} />
                            Gana {winName}
                          </p>
                        ) : (
                          <p className="text-xs font-semibold text-slate-500">Empate técnico</p>
                        )}
                      </div>
                    )
                  })}
                </div>

                {/* Ganador global */}
                {(() => {
                  const allMetrics = CATEGORIES.flatMap(c => c.metrics)
                  const totalA  = allMetrics.filter(m => (jugadorA.metricas[m] ?? 0) > (jugadorB.metricas[m] ?? 0)).length
                  const totalB  = allMetrics.filter(m => (jugadorB.metricas[m] ?? 0) > (jugadorA.metricas[m] ?? 0)).length
                  const isDraw  = totalA === totalB
                  const winnerJ = totalA > totalB ? jugadorA : jugadorB
                  const winnerColor = winnerJ.id === jugadorA.id ? COLOR_A : COLOR_B
                  const winnerCount = Math.max(totalA, totalB)

                  return (
                    <div className="pt-5 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-center gap-3 text-center">
                      {isDraw ? (
                        <>
                          <span className="text-slate-500 text-sm">Empate técnico</span>
                          <span className="text-slate-700 font-bold tabular-nums">
                            {totalA} — {totalB} métricas
                          </span>
                        </>
                      ) : (
                        <>
                          <span className="text-slate-500 text-sm">Ganador general</span>
                          <span className="font-black text-xl" style={{ color: winnerColor }}>
                            {winnerJ.nombre}
                          </span>
                          <span className="text-xs text-slate-500 bg-slate-800 px-2.5 py-1 rounded-full">
                            {winnerCount} métricas ganadas
                          </span>
                        </>
                      )}
                    </div>
                  )
                })()}
              </div>
            </>
          )}
        </div>
      )}

    </main>
  )
}
