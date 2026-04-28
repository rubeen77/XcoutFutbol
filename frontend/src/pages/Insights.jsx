import { useState, useEffect, useCallback } from 'react'
import {
  getInsightsRankings,
  getInsightsDatosCuriosos,
  getInsightsQuiz,
} from '../services/api'

// ─── Helpers ──────────────────────────────────────────────────────────────────

const POS_MAP = {
  FW: 'Delantero', 'FW,MF': 'Extremo', 'MF,FW': 'Mediapunta',
  MF: 'Centrocampista', 'MF,DF': 'Centrocampista',
  'DF,MF': 'Defensa Central', DF: 'Defensa Central', GK: 'Portero',
}
function posLabel(raw) { return POS_MAP[raw] || raw || '—' }

const QUIZ_STATS_BY_POS = {
  GK:      ['minutos', 'xg', 'recuperaciones'],
  DF:      ['minutos', 'goles', 'asistencias', 'recuperaciones', 'xg', 'pases_completados'],
  'DF,MF': ['minutos', 'goles', 'asistencias', 'recuperaciones', 'xg', 'pases_completados'],
  MF:      ['minutos', 'goles', 'asistencias', 'xg', 'regates', 'pases_completados'],
  'MF,DF': ['minutos', 'goles', 'asistencias', 'xg', 'regates', 'pases_completados'],
  'MF,FW': ['minutos', 'goles', 'asistencias', 'xg', 'regates', 'g90', 'recuperaciones', 'pases_completados'],
  'FW,MF': ['minutos', 'goles', 'asistencias', 'xg', 'regates', 'g90', 'pases_completados'],
  FW:      ['minutos', 'goles', 'asistencias', 'xg', 'g90', 'pases_completados'],
}

function buildStatDisplay(quiz, respondido) {
  if (!quiz) return []
  const s = quiz.stats
  const ALL = {
    minutos:           { label: 'Minutos',        val: s.minutos || null, fmt: v => v.toLocaleString('es') },
    goles:             { label: 'Goles',           val: s.goles   || null },
    asistencias:       { label: 'Asistencias',     val: s.asistencias || null },
    xg:                { label: 'xG',              val: s.xg      || null },
    recuperaciones:    { label: 'Recuperaciones',  val: s.recuperaciones || null },
    regates:           { label: 'Regates',         val: s.regates || null },
    pases_completados: { label: 'Pases %',         val: s.pases_completados || null },
    g90:               { label: 'G/90',            val: s.goles_por_90 || null },
  }
  const keys = QUIZ_STATS_BY_POS[quiz.posicion] || ['minutos', 'goles', 'asistencias', 'xg', 'g90']
  const result = [{ label: 'Posición', val: posLabel(quiz.posicion) }]
  for (const key of keys) {
    const entry = ALL[key]
    if (entry?.val != null) {
      result.push({ label: entry.label, val: entry.fmt ? entry.fmt(entry.val) : entry.val })
    }
  }
  result.push({ label: 'Equipo', val: respondido ? quiz.equipo : '???' })
  return result
}

function initials(nombre) {
  return (nombre || '??').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
}

const GRADIENTS = [
  'from-cyan-500/30 to-blue-600/30',    'from-violet-500/30 to-purple-600/30',
  'from-amber-500/30 to-orange-600/30', 'from-emerald-500/30 to-teal-600/30',
  'from-rose-500/30 to-pink-600/30',    'from-indigo-500/30 to-sky-600/30',
  'from-sky-500/30 to-cyan-600/30',     'from-fuchsia-500/30 to-violet-600/30',
]
function teamGrad(nombre) {
  let h = 0
  for (const c of (nombre || '')) h = (h * 31 + c.charCodeAt(0)) & 0xffff
  return GRADIENTS[h % GRADIENTS.length]
}

const MENSAJES_FAIL = [
  '¡Se acabó la racha! Y tenías tanta esperanza...',
  'Error de bulto. Vuelve a intentarlo.',
  '¿Seguro que sigues el fútbol? 😅',
  'Eso no lo habría fallado ni mi abuela.',
  'La estadística no miente. Tú sí.',
]

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton({ h = 'h-5', w = 'w-full' }) {
  return <div className={`${h} ${w} bg-slate-800 rounded-lg animate-pulse`} />
}

// ─── RANKINGS ─────────────────────────────────────────────────────────────────

const TABS = [
  { key: 'goleadores',     label: 'Goleadores',     metrica: 'goles',          unidad: 'goles' },
  { key: 'asistentes',     label: 'Asistentes',     metrica: 'asistencias',    unidad: 'asis.' },
  { key: 'sobre_xg',       label: 'Sobre xG',       metrica: 'sobre_xg',       unidad: '+xG'   },
  { key: 'regates',        label: 'Regates',        metrica: 'regates',        unidad: 'reg.'  },
  { key: 'recuperaciones', label: 'Recuperaciones', metrica: 'recuperaciones', unidad: 'rec.'  },
  { key: 'g90',            label: 'G/90',           metrica: 'goles_por_90',   unidad: 'g/90'  },
]

const MAX_REF = {
  goles: 30, asistencias: 20, sobre_xg: 15,
  regates: 200, recuperaciones: 300, goles_por_90: 1.2,
}

function PlayerRankRow({ jugador, pos, metricaKey, unidad }) {
  const valor = jugador[metricaKey] ?? 0
  const pct   = Math.min((valor / (MAX_REF[metricaKey] || Math.max(valor, 1))) * 100, 100)

  return (
    <div className="flex items-center gap-3 py-3 px-4 border-b border-slate-800/60 last:border-0
                    hover:bg-slate-800/30 transition-colors group">
      <span className={`text-sm font-black w-5 shrink-0 tabular-nums ${pos === 1 ? 'text-cyan-400' : 'text-slate-600'}`}>
        {pos}
      </span>

      <div className={`relative w-9 h-12 rounded-xl bg-gradient-to-br ${teamGrad(jugador.nombre)}
                       border border-white/5 shrink-0 overflow-hidden flex items-center justify-center`}>
        <span className="text-xs font-black text-white">{initials(jugador.nombre)}</span>
        {jugador.foto_url && (
          <img src={jugador.foto_url} alt={jugador.nombre} referrerPolicy="no-referrer"
               className="absolute inset-0 w-full h-full object-cover object-top"
               onError={e => e.currentTarget.remove()} />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-white truncate group-hover:text-cyan-400 transition-colors">
          {jugador.nombre}
        </p>
        <p className="text-xs text-slate-500 truncate">{jugador.equipo}</p>
      </div>

      <div className="flex items-center gap-2 shrink-0 w-32">
        <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden hidden sm:block">
          <div className="h-full bg-cyan-400 rounded-full" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-sm font-black text-cyan-300 tabular-nums text-right">
          {typeof valor === 'number' && !Number.isInteger(valor) ? valor.toFixed(2) : valor}
          <span className="text-[10px] text-slate-500 ml-0.5">{unidad}</span>
        </span>
      </div>
    </div>
  )
}

function RankingsSection() {
  const [tab,      setTab]      = useState('goleadores')
  const [rankings, setRankings] = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)

  useEffect(() => {
    getInsightsRankings()
      .then(d => setRankings(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const tabInfo = TABS.find(t => t.key === tab)
  const lista   = rankings?.[tab] || []

  return (
    <section>
      <div className="flex items-center gap-2 mb-5">
        <div className="w-1.5 h-5 rounded-full bg-cyan-400 shrink-0" />
        <h2 className="text-sm font-bold text-slate-400 uppercase tracking-widest">Rankings</h2>
      </div>

      <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1 mb-4">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-150 ${
              tab === t.key
                ? 'bg-cyan-400 text-slate-950'
                : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-600'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        {loading && (
          <div className="p-4 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-3 px-1">
                <Skeleton h="h-4" w="w-4" /><Skeleton h="h-9" w="w-9" />
                <div className="flex-1 space-y-1.5"><Skeleton h="h-3.5" w="w-40" /><Skeleton h="h-3" w="w-24" /></div>
                <Skeleton h="h-3.5" w="w-16" />
              </div>
            ))}
          </div>
        )}
        {error && !loading && <p className="text-red-400 text-sm text-center p-6">{error}</p>}
        {!loading && !error && lista.length === 0 && <p className="text-slate-500 text-sm text-center p-6">Sin datos.</p>}
        {!loading && !error && lista.map((j, i) => (
          <PlayerRankRow key={j.id ?? j.nombre} jugador={j} pos={i + 1}
            metricaKey={tabInfo.metrica} unidad={tabInfo.unidad} />
        ))}
      </div>
    </section>
  )
}

// ─── DATOS CURIOSOS ───────────────────────────────────────────────────────────

function DatoCard({ icono, titulo, valor, desc, color = 'text-cyan-400' }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 hover:border-cyan-500/30 transition-colors">
      <div className="flex items-start gap-3 mb-3">
        <span className="text-xl shrink-0">{icono}</span>
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest leading-tight">{titulo}</p>
      </div>
      <p className={`text-3xl font-black tabular-nums leading-none mb-2 ${color}`}>{valor}</p>
      <p className="text-xs text-slate-400 leading-relaxed">{desc}</p>
    </div>
  )
}

function DatosCuriososSection() {
  const [datos,   setDatos]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    getInsightsDatosCuriosos()
      .then(d => setDatos(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <section>
      <div className="flex items-center gap-2 mb-5">
        <div className="w-1.5 h-5 rounded-full bg-amber-400 shrink-0" />
        <h2 className="text-sm font-bold text-slate-400 uppercase tracking-widest">El dato que no viste</h2>
      </div>

      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
              <Skeleton h="h-4" w="w-32" /><Skeleton h="h-9" w="w-24" />
              <Skeleton h="h-3" w="w-full" /><Skeleton h="h-3" w="w-3/4" />
            </div>
          ))}
        </div>
      )}
      {error && !loading && <p className="text-red-400 text-sm text-center p-6">{error}</p>}

      {!loading && !error && datos && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {datos.mejor_sobre_xg && (
            <DatoCard icono="📈" titulo="Más goles sobre su xG"
              valor={`+${datos.mejor_sobre_xg.diferencia.toFixed(2)}`}
              desc={`${datos.mejor_sobre_xg.jugador} (${datos.mejor_sobre_xg.equipo}) supera sus xG en ${datos.mejor_sobre_xg.diferencia.toFixed(1)} goles — ${datos.mejor_sobre_xg.goles} reales frente a ${datos.mejor_sobre_xg.xg} esperados.`}
              color="text-emerald-400" />
          )}
          {datos.peor_xg && (
            <DatoCard icono="🎯" titulo="Más xG sin convertir"
              valor={`${datos.peor_xg.diferencia.toFixed(2)} xG`}
              desc={`${datos.peor_xg.jugador} (${datos.peor_xg.equipo}) acumula ${datos.peor_xg.xg} de xG con solo ${datos.peor_xg.goles} goles. Le deben ${datos.peor_xg.diferencia.toFixed(1)} goles.`}
              color="text-rose-400" />
          )}
          {datos.jornada_max_goles && (
            <DatoCard icono="💥" titulo="Jornada más goleadora"
              valor={`J${datos.jornada_max_goles.jornada}`}
              desc={`La jornada ${datos.jornada_max_goles.jornada} fue la más prolífica con ${datos.jornada_max_goles.goles} goles en total — ${(datos.jornada_max_goles.goles / 10).toFixed(1)} de media por partido.`}
              color="text-amber-400" />
          )}
          {datos.mejor_equipo_casa && (
            <DatoCard icono="🏠" titulo="Rey de su estadio"
              valor={`${datos.mejor_equipo_casa.goles} goles`}
              desc={`${datos.mejor_equipo_casa.nombre} es el equipo más goleador como local con ${datos.mejor_equipo_casa.goles} goles en casa esta temporada.`}
              color="text-violet-400" />
          )}
        </div>
      )}
    </section>
  )
}

// ─── QUIZ ─────────────────────────────────────────────────────────────────────

function QuizSection() {
  const [quiz,      setQuiz]      = useState(null)
  const [seleccion, setSeleccion] = useState(null)
  const [racha,     setRacha]     = useState(0)
  const [maxRacha,  setMaxRacha]  = useState(0)
  const [mensaje,   setMensaje]   = useState(null)
  const [shake,     setShake]     = useState(false)
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState(null)

  const cargar = useCallback(() => {
    setLoading(true); setSeleccion(null); setMensaje(null); setQuiz(null)
    getInsightsQuiz()
      .then(d => setQuiz(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { cargar() }, [cargar])

  function responder(opcion) {
    if (seleccion || !quiz) return
    setSeleccion(opcion)
    if (opcion === quiz.nombre) {
      const nueva = racha + 1
      setRacha(nueva)
      setMaxRacha(m => Math.max(m, nueva))
    } else {
      setMensaje(MENSAJES_FAIL[Math.floor(Math.random() * MENSAJES_FAIL.length)])
      setRacha(0)
      setShake(true)
      setTimeout(() => setShake(false), 500)
    }
  }

  const respondido = seleccion !== null
  const correcto   = seleccion === quiz?.nombre

  const statDisplay = buildStatDisplay(quiz, respondido)

  return (
    <section>
      <div className="flex items-center gap-2 mb-5">
        <div className="w-1.5 h-5 rounded-full bg-violet-400 shrink-0" />
        <h2 className="text-sm font-bold text-slate-400 uppercase tracking-widest">
          Quiz — ¿Adivina el jugador?
        </h2>
      </div>

      <div className={`bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden
                       transition-all ${shake ? 'scale-[0.99] border-red-500/40' : ''}`}>

        {/* Barra racha */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-slate-800/30">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Racha</span>
            <span className={`text-lg font-black tabular-nums transition-colors ${racha > 0 ? 'text-cyan-400' : 'text-slate-600'}`}>
              {racha}{racha >= 3 ? ' 🔥' : ''}
            </span>
          </div>
          <span className="text-xs text-slate-600">Mejor: <span className="text-slate-400 font-bold">{maxRacha}</span></span>
        </div>

        <div className="p-6">
          {loading && (
            <div className="flex justify-center py-12">
              <div className="w-8 h-8 border-2 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin" />
            </div>
          )}
          {error && !loading && <p className="text-red-400 text-sm text-center py-8">{error}</p>}

          {!loading && !error && quiz && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

              {/* Panel izquierdo: stats */}
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-5">
                  ¿De quién son estos datos?
                </p>

                <div className="flex items-center gap-4 mb-5">
                  <div className="relative w-14 h-[4.67rem] rounded-xl overflow-hidden shrink-0
                                  bg-gradient-to-br from-slate-700 to-slate-800 border border-white/5
                                  flex items-center justify-center">
                    {respondido ? (
                      <>
                        <span className="text-sm font-black text-white">{initials(quiz.nombre)}</span>
                        {quiz.foto_url && (
                          <img src={quiz.foto_url} alt={quiz.nombre} referrerPolicy="no-referrer"
                               className="absolute inset-0 w-full h-full object-cover object-top"
                               onError={e => e.currentTarget.remove()} />
                        )}
                      </>
                    ) : (
                      <span className="text-2xl select-none">❓</span>
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-bold text-white">
                      {respondido ? quiz.nombre : '???'}
                    </p>
                    <p className="text-xs text-slate-500">
                      {respondido ? `${quiz.equipo} · ${posLabel(quiz.posicion)}` : 'LaLiga 2025/26'}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {statDisplay.map(s => (
                    <div key={s.label} className="bg-slate-800/60 border border-slate-700/40 rounded-xl px-4 py-3">
                      <p className="text-xs text-slate-500 mb-0.5">{s.label}</p>
                      <p className="text-base font-black text-white">{s.val ?? '—'}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Panel derecho: opciones */}
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-5">
                  Elige el jugador
                </p>

                <div className="space-y-3">
                  {(quiz.opciones || []).map(opcion => {
                    const esCorrecta    = opcion === quiz.nombre
                    const esSeleccionada = opcion === seleccion
                    let cls = 'border-slate-700 bg-slate-800/40 text-slate-300 hover:border-cyan-500/50 hover:text-white'
                    if (respondido) {
                      if (esCorrecta)          cls = 'border-emerald-500/60 bg-emerald-500/10 text-emerald-400'
                      else if (esSeleccionada) cls = 'border-red-500/60 bg-red-500/10 text-red-400'
                      else                     cls = 'border-slate-800 text-slate-600 cursor-default'
                    }
                    return (
                      <button key={opcion} onClick={() => responder(opcion)} disabled={respondido}
                        className={`w-full text-left px-5 py-4 rounded-xl border text-sm font-semibold
                                   transition-all duration-150 disabled:cursor-default ${cls}`}>
                        {opcion}
                        {respondido && esCorrecta    && <span className="ml-2">✓</span>}
                        {respondido && esSeleccionada && !esCorrecta && <span className="ml-2">✗</span>}
                      </button>
                    )
                  })}
                </div>

                {respondido && (
                  <>
                    <div className={`mt-5 p-4 rounded-xl text-sm font-semibold text-center ${
                      correcto
                        ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                        : 'bg-red-500/10 border border-red-500/30 text-red-400'
                    }`}>
                      {correcto ? `¡Correcto! Racha: ${racha} 🎯` : (mensaje || 'Incorrecto.')}
                    </div>
                    <button onClick={cargar}
                      className="mt-3 w-full py-3 rounded-xl bg-slate-800 border border-slate-700
                                 text-slate-300 text-sm font-semibold hover:bg-slate-700 hover:text-white transition-colors">
                      Siguiente jugador →
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

// ─── PLACEHOLDER IA ───────────────────────────────────────────────────────────

function AnalisisIASection() {
  return (
    <section>
      <div className="flex items-center gap-2 mb-5">
        <div className="w-1.5 h-5 rounded-full bg-slate-700 shrink-0" />
        <h2 className="text-sm font-bold text-slate-600 uppercase tracking-widest">
          Análisis de jornada con IA
        </h2>
      </div>
      <div className="bg-slate-900/50 border border-dashed border-slate-700/50 rounded-2xl p-8 text-center">
        <div className="w-12 h-12 rounded-full bg-slate-800 border border-slate-700/60
                        flex items-center justify-center mx-auto mb-4">
          <svg className="w-6 h-6 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707
                 m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0
                 v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
        <p className="text-slate-500 font-semibold text-sm mb-1">Disponible próximamente</p>
        <p className="text-slate-600 text-xs max-w-xs mx-auto">
          Análisis narrativo de cada jornada generado automáticamente desde los datos reales de la temporada.
        </p>
      </div>
    </section>
  )
}

// ─── Página ───────────────────────────────────────────────────────────────────

export default function Insights() {
  return (
    <main className="min-h-screen bg-[#080C10] text-white">
      <div className="max-w-4xl mx-auto px-4 py-10 space-y-14">

        <div>
          <h1 className="text-3xl font-black text-white mb-1">Insights</h1>
          <p className="text-slate-400 text-sm font-light">
            Los datos más llamativos de la temporada. Calculados en tiempo real.
          </p>
          <div className="mt-3 inline-flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-full px-3 py-1.5">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-xs font-semibold text-slate-400">LaLiga · Temporada 2025/26</span>
          </div>
        </div>

        <RankingsSection />
        <DatosCuriososSection />
        <QuizSection />
        <AnalisisIASection />

      </div>
    </main>
  )
}
