import { useState, useEffect } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { equipos } from '../data/equipos'
import { jugadores } from '../data/jugadores'
import { getEquipos } from '../services/api'

/* ── helpers ──────────────────────────────────────────────────────────────── */
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

/* ── custom tooltip for LineChart ─────────────────────────────────────────── */
function PtsTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs">
      <p className="text-slate-400 mb-0.5">J{label}</p>
      <p className="text-cyan-400 font-bold text-sm">{payload[0].value} pts</p>
    </div>
  )
}

/* ── TeamCard ─────────────────────────────────────────────────────────────── */
function TeamCard({ equipo, selected, onClick }) {
  const racha = equipo.racha.slice(-3)
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-2xl border transition-all duration-200
        bg-slate-900 hover:bg-slate-800/70 hover:scale-[1.02]
        hover:shadow-lg hover:shadow-slate-950/60
        ${selected
          ? 'border-cyan-500/60 shadow-md shadow-cyan-950/40'
          : 'border-slate-800 hover:border-slate-700'
        }`}
    >
      <div className="p-4 flex items-center gap-4">
        {/* Shield placeholder */}
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 font-black text-sm"
          style={{ background: `${equipo.color}18`, color: equipo.color, border: `1.5px solid ${equipo.color}40` }}
        >
          {equipo.abrev}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="text-xs font-bold rounded-full px-2 py-0.5"
              style={{ background: `${equipo.color}18`, color: equipo.color }}
            >
              #{equipo.posicion}
            </span>
            <p className="text-sm font-semibold text-white truncate">{equipo.nombre}</p>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">{equipo.partidos} partidos</p>
        </div>

        {/* Points + form */}
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <span className="text-xl font-black text-white tabular-nums leading-none">
            {equipo.puntos}
            <span className="text-xs font-normal text-slate-500 ml-0.5">pts</span>
          </span>
          <div className="flex gap-1">
            {racha.map((r, i) => (
              <span key={i} className={`w-5 h-5 rounded-full text-[10px] font-black flex items-center justify-center ${rachaColor(r)}`}>
                {rachaLabel(r)}
              </span>
            ))}
          </div>
        </div>
      </div>
    </button>
  )
}

/* ── StatBlock ────────────────────────────────────────────────────────────── */
function StatBlock({ label, value, sub, accent }) {
  return (
    <div className="bg-slate-800/50 border border-slate-700/60 rounded-xl p-3 flex flex-col gap-0.5">
      <span className="text-xs text-slate-500">{label}</span>
      <span
        className="text-2xl font-black tabular-nums leading-none"
        style={{ color: accent || '#f1f5f9' }}
      >
        {value}
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
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="w-8 h-8 rounded-full bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center shrink-0">
        <span className="text-xs font-black text-cyan-400">{jugador.nombre.split(' ').map(w => w[0]).join('').slice(0, 2)}</span>
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
          <p className="text-sm font-bold text-cyan-400 tabular-nums">{m.xG.toFixed(1)}</p>
          <p className="text-[10px] text-slate-500">xG</p>
        </div>
      </div>
    </div>
  )
}

/* ── TeamProfile ──────────────────────────────────────────────────────────── */
function TeamProfile({ equipo, onClose }) {
  const chartData = equipo.puntos_jornada.map((pts, i) => ({ j: i + 1, pts }))
  const players = jugadores.filter(j => equipo.jugadores_ids.includes(j.id))

  return (
    <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-900/80 backdrop-blur-sm overflow-hidden animate-fade-up">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center font-black text-xs"
            style={{ background: `${equipo.color}1a`, color: equipo.color, border: `1.5px solid ${equipo.color}50` }}
          >
            {equipo.abrev}
          </div>
          <div>
            <h2 className="text-base font-bold text-white">{equipo.nombre}</h2>
            <p className="text-xs text-slate-500">Temporada 2024/25 · {equipo.partidos} partidos</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="p-5 flex flex-col gap-6">
        {/* Stats grid */}
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Estadísticas</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            <StatBlock label="Goles a favor" value={equipo.goles_favor} sub={`${equipo.goles_contra} en contra`} accent="#4ade80" />
            <StatBlock label="xG a favor" value={equipo.xG_favor.toFixed(1)} sub={`${equipo.xG_contra.toFixed(1)} en contra`} accent="#22d3ee" />
            <StatBlock label="Posesión media" value={`${equipo.posesion}%`} />
            <StatBlock label="Presiones/partido" value={equipo.presiones_partido} sub={`PPDA ${equipo.ppda}`} />
          </div>
        </div>

        {/* W / D / L summary */}
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Resultados</h3>
          <div className="flex gap-2">
            <div className="flex-1 bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 text-center">
              <p className="text-2xl font-black text-emerald-400">{equipo.victorias}</p>
              <p className="text-xs text-slate-400 mt-0.5">Victorias</p>
            </div>
            <div className="flex-1 bg-amber-400/10 border border-amber-400/20 rounded-xl p-3 text-center">
              <p className="text-2xl font-black text-amber-400">{equipo.empates}</p>
              <p className="text-xs text-slate-400 mt-0.5">Empates</p>
            </div>
            <div className="flex-1 bg-red-500/10 border border-red-500/20 rounded-xl p-3 text-center">
              <p className="text-2xl font-black text-red-400">{equipo.derrotas}</p>
              <p className="text-xs text-slate-400 mt-0.5">Derrotas</p>
            </div>
          </div>
        </div>

        {/* Racha last 5 */}
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Últimos 5 partidos</h3>
          <div className="flex gap-2">
            {equipo.racha.map((r, i) => (
              <div key={i} className={`flex-1 rounded-xl py-2 flex flex-col items-center gap-1 ${rachaColor(r)}`}>
                <span className="text-sm font-black">{rachaLabel(r)}</span>
                <span className="text-[10px] opacity-70">J{equipo.partidos - 4 + i}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Points evolution */}
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Evolución de puntos</h3>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis
                  dataKey="j"
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  interval={3}
                  tickFormatter={v => `J${v}`}
                />
                <YAxis
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip content={<PtsTooltip />} cursor={{ stroke: '#334155', strokeWidth: 1 }} />
                <Line
                  type="monotone"
                  dataKey="pts"
                  stroke={equipo.color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: equipo.color, stroke: '#020617', strokeWidth: 2 }}
                  isAnimationActive={true}
                  animationDuration={800}
                  animationEasing="ease-out"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top players */}
        {players.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
              Jugadores destacados
            </h3>
            <div className="flex flex-col gap-2">
              {players.map((j, i) => (
                <PlayerRow key={j.id} jugador={j} index={i} />
              ))}
            </div>
          </div>
        )}
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
            <div className="skeleton h-2.5 w-16 rounded" />
          </div>
          <div className="flex flex-col items-end gap-2 shrink-0">
            <div className="skeleton h-5 w-10 rounded" />
            <div className="skeleton h-4 w-16 rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}

/* ── Page ─────────────────────────────────────────────────────────────────── */
export default function Equipos() {
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getEquipos().catch(() => {}).finally(() => setLoading(false))
  }, [])

  const handleSelect = (id) => {
    setSelected(prev => prev === id ? null : id)
  }

  const selectedEquipo = equipos.find(e => e.id === selected)

  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
          Equipos{' '}
          <span className="text-cyan-400">LaLiga</span>
        </h1>
        <p className="text-sm text-slate-500 mt-1">Temporada 2024/25 · Top 10 clasificación</p>
      </div>

      {loading ? (
        <EquiposSkeleton />
      ) : (
        <div className="flex flex-col gap-3">
          {/* Teams grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {equipos.map((equipo, i) => (
              <div
                key={equipo.id}
                className="animate-fade-up"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <TeamCard
                  equipo={equipo}
                  selected={selected === equipo.id}
                  onClick={() => handleSelect(equipo.id)}
                />
              </div>
            ))}
          </div>

          {/* Inline profile */}
          {selectedEquipo && (
            <TeamProfile
              key={selectedEquipo.id}
              equipo={selectedEquipo}
              onClose={() => setSelected(null)}
            />
          )}
        </div>
      )}
    </main>
  )
}
