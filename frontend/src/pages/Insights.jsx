import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts'
import { insights, datoSemana } from '../data/insights'
import InsightCard from '../components/InsightCard'
import { InsightsSkeleton } from '../components/Skeletons'

// ─── Datos: Jugadores en forma ────────────────────────────────────────────────
const JUGADORES_FORMA = [
  { nombre: 'Vinícius Jr.', equipo: 'Real Madrid', nota: 8.4, ga: 5, tendencia: 'sube', notaAnterior: 7.1 },
  { nombre: 'Lewandowski',  equipo: 'Barcelona',   nota: 8.1, ga: 4, tendencia: 'sube', notaAnterior: 7.8 },
  { nombre: 'Oyarzabal',   equipo: 'R. Sociedad',  nota: 7.9, ga: 3, tendencia: 'sube', notaAnterior: 6.8 },
  { nombre: 'Pedri',       equipo: 'Barcelona',    nota: 7.7, ga: 2, tendencia: 'baja', notaAnterior: 8.2 },
  { nombre: 'Griezmann',   equipo: 'Atlético',     nota: 7.5, ga: 3, tendencia: 'sube', notaAnterior: 7.0 },
]

// ─── Datos: Equipos en racha ──────────────────────────────────────────────────
const EQUIPOS_RACHA = {
  mejoran: [
    { nombre: 'Real Sociedad', antes: 1.0, ahora: 2.4 },
    { nombre: 'Villarreal',    antes: 1.2, ahora: 2.2 },
    { nombre: 'Celta de Vigo', antes: 0.8, ahora: 1.8 },
  ],
  empeoran: [
    { nombre: 'Sevilla FC',  antes: 2.2, ahora: 0.6 },
    { nombre: 'Valencia CF', antes: 1.6, ahora: 0.4 },
    { nombre: 'Getafe CF',   antes: 1.4, ahora: 0.8 },
  ],
}

// ─── Datos: Análisis editorial ───────────────────────────────────────────────
const ANALISIS_JORNADA = {
  titulo: 'El Clásico en datos',
  subtitulo: 'Real Madrid 3 – 2 Barcelona · Jornada 32',
  fecha: 'Actualizado cada lunes',
  parrafos: [
    'El Bernabéu rugió como en los viejos tiempos, pero los números cuentan una historia diferente a la del marcador. El Barcelona dominó el partido durante 65 minutos con una posesión del 62% y generó un xG de 2.8, casi idéntico al del Madrid. Ganó el que tuvo a Courtois y a la suerte de su lado.',
    'Vinícius Jr. fue el factor diferencial, no tanto por sus goles sino por cómo desorganizó al Barça defensivamente. Cada vez que recibía balón, el bloque catalán perdía su forma y aparecían los espacios que Bellingham explotó con inteligencia. 11 regates intentados, 8 completados. Un espectáculo.',
    'El dato que más llama la atención es el rendimiento de Pedri. 94 pases, 91% de precisión, y aun así su equipo perdió. Controló el tempo, pero el fútbol moderno no se gana solo con el balón. La diferencia estuvo en las transiciones: el Madrid convirtió 3 de sus 4 contraataques en ocasiones claras.',
    'En el balance final, el Madrid fue más efectivo y el Barça más brillante. Y eso, en un Clásico, siempre lo decide el marcador.',
  ],
  stats: [
    { label: 'Posesión Barça', valor: '62%', color: 'cyan' },
    { label: 'xG Madrid',      valor: '2.4', color: 'slate' },
    { label: 'xG Barça',       valor: '2.8', color: 'slate' },
    { label: 'Regates Vini',   valor: '8/11', color: 'cyan' },
  ],
}

const DATO_NO_VISTE = {
  titulo: 'El Madrid ganó el Clásico sin rematar más que el Barça',
  dato: '4',
  unidad: 'remates del Madrid entre los tres palos',
  contexto: 'El Barça tuvo 7. Y perdió.',
  explicacion: 'Mientras el Barça acumulaba posesión y ocasiones, el Madrid fue quirúrgico. Solo necesitó 4 remates a puerta para marcar 3. Una efectividad del 75% que no se ve ni en FIFA. Ancelotti lleva años diciendo que su equipo no juega bonito, juega ganando. Esta jornada fue el resumen perfecto de esa filosofía.',
}

// ─── Datos: Quiz ─────────────────────────────────────────────────────────────
const QUIZ_JUGADORES = [
  {
    nombre: 'Vinícius Jr.',
    stats: { goles: 23, asistencias: 9, xG: 19.1, equipo: 'Real Madrid', posicion: 'Extremo izq.', nacionalidad: '🇧🇷 Brasil' },
    opciones: ['Kylian Mbappé', 'Vinícius Jr.', 'Raphinha', 'Nico Williams'],
  },
  {
    nombre: 'Robert Lewandowski',
    stats: { goles: 26, asistencias: 5, xG: 22.4, equipo: 'FC Barcelona', posicion: 'Delantero centro', nacionalidad: '🇵🇱 Polonia' },
    opciones: ['Alvaro Morata', 'Antoine Griezmann', 'Robert Lewandowski', 'En-Nesyri'],
  },
  {
    nombre: 'Jude Bellingham',
    stats: { goles: 19, asistencias: 11, xG: 16.2, equipo: 'Real Madrid', posicion: 'Mediapunta', nacionalidad: '🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra' },
    opciones: ['Pedri', 'Frenkie de Jong', 'Jude Bellingham', 'Dani Olmo'],
  },
  {
    nombre: 'Pedri',
    stats: { goles: 8, asistencias: 12, xG: 6.8, equipo: 'FC Barcelona', posicion: 'Centrocampista', nacionalidad: '🇪🇸 España' },
    opciones: ['Gavi', 'Pedri', 'Isco', 'Mikel Merino'],
  },
  {
    nombre: 'Antoine Griezmann',
    stats: { goles: 17, asistencias: 14, xG: 14.8, equipo: 'Atlético de Madrid', posicion: 'Segunda punta', nacionalidad: '🇫🇷 Francia' },
    opciones: ['Alvaro Morata', 'Antoine Griezmann', 'Memphis Depay', 'Riquelme'],
  },
  {
    nombre: 'Takefusa Kubo',
    stats: { goles: 13, asistencias: 10, xG: 10.4, equipo: 'Real Sociedad', posicion: 'Extremo der.', nacionalidad: '🇯🇵 Japón' },
    opciones: ['Oyarzabal', 'Takefusa Kubo', 'Baena', 'Brais Méndez'],
  },
  {
    nombre: 'Kylian Mbappé',
    stats: { goles: 21, asistencias: 7, xG: 18.3, equipo: 'Real Madrid', posicion: 'Delantero centro', nacionalidad: '🇫🇷 Francia' },
    opciones: ['Kylian Mbappé', 'Vinícius Jr.', 'Endrick', 'Joselu'],
  },
  {
    nombre: 'Alejandro Baena',
    stats: { goles: 9, asistencias: 13, xG: 7.6, equipo: 'Villarreal CF', posicion: 'Mediocampista', nacionalidad: '🇪🇸 España' },
    opciones: ['Dani Parejo', 'Manu Trigueros', 'Alejandro Baena', 'Álex Baena'],
  },
  {
    nombre: 'Mikel Oyarzabal',
    stats: { goles: 15, asistencias: 8, xG: 13.1, equipo: 'Real Sociedad', posicion: 'Extremo izq.', nacionalidad: '🇪🇸 España' },
    opciones: ['Mikel Oyarzabal', 'Ander Herrera', 'Brais Méndez', 'Iago Aspas'],
  },
  {
    nombre: 'Iago Aspas',
    stats: { goles: 14, asistencias: 9, xG: 11.8, equipo: 'RC Celta de Vigo', posicion: 'Delantero', nacionalidad: '🇪🇸 España' },
    opciones: ['En-Nesyri', 'Willian José', 'Iago Aspas', 'Borja Iglesias'],
  },
]

const MENSAJES_RACHA_ROTA = [
  '¡Se acabó la racha! Y tenías tanta esperanza...',
  'Error de bulto. Vuelve a intentarlo.',
  '¿Seguro que sigues el fútbol? 😅',
  'Eso no lo habría fallado ni mi abuela.',
  'La estadística no miente. Tú sí.',
]

// ─── Componente Quiz ──────────────────────────────────────────────────────────
function QuizJugador() {
  const [indice, setIndice]           = useState(() => Math.floor(Math.random() * QUIZ_JUGADORES.length))
  const [seleccion, setSeleccion]     = useState(null)
  const [racha, setRacha]             = useState(0)
  const [maxRacha, setMaxRacha]       = useState(0)
  const [mensaje, setMensaje]         = useState(null)
  const [shake, setShake]             = useState(false)

  const jugador   = QUIZ_JUGADORES[indice]
  const respondido = seleccion !== null
  const correcto   = seleccion === jugador.nombre

  function responder(opcion) {
    if (respondido) return
    setSeleccion(opcion)
    if (opcion === jugador.nombre) {
      const nueva = racha + 1
      setRacha(nueva)
      setMaxRacha(m => Math.max(m, nueva))
      setMensaje(null)
    } else {
      setMensaje(MENSAJES_RACHA_ROTA[Math.floor(Math.random() * MENSAJES_RACHA_ROTA.length)])
      setRacha(0)
      setShake(true)
      setTimeout(() => setShake(false), 600)
    }
  }

  function siguiente() {
    const siguientes = QUIZ_JUGADORES
      .map((_, i) => i)
      .filter(i => i !== indice)
    setIndice(siguientes[Math.floor(Math.random() * siguientes.length)])
    setSeleccion(null)
    setMensaje(null)
  }

  const iniciales = jugador.nombre.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()

  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden transition-all duration-300 ${shake ? 'animate-[wiggle_0.4s_ease]' : ''}`}>

      {/* Barra superior: racha */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-slate-800/30">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Racha actual</span>
          <span className={`text-lg font-black tabular-nums transition-all duration-300 ${racha > 0 ? 'text-cyan-400' : 'text-slate-600'}`}>
            {racha}
            {racha >= 3 && ' 🔥'}
            {racha >= 5 && '🔥'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-600">Mejor racha:</span>
          <span className="text-xs font-black text-slate-400 tabular-nums">{maxRacha}</span>
        </div>
      </div>

      <div className="p-6 sm:p-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

          {/* ─ Panel izquierdo: estadísticas ─ */}
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-5">
              ¿De quién son estos datos?
            </p>

            <div className="grid grid-cols-2 gap-3 mb-6">
              {[
                { label: 'Goles',        valor: jugador.stats.goles },
                { label: 'Asistencias',  valor: jugador.stats.asistencias },
                { label: 'xG',           valor: jugador.stats.xG },
                { label: 'Posición',     valor: jugador.stats.posicion },
                { label: 'Equipo',       valor: jugador.stats.equipo },
                { label: 'Nac.',         valor: jugador.stats.nacionalidad },
              ].map(s => (
                <div key={s.label} className="bg-slate-800/60 border border-slate-700/40 rounded-xl px-4 py-3">
                  <p className="text-xs text-slate-500 mb-0.5">{s.label}</p>
                  <p className="text-sm font-bold text-white leading-snug">{s.valor}</p>
                </div>
              ))}
            </div>

            {/* Reveal tras responder */}
            {respondido && (
              <div className={`rounded-2xl border p-5 flex items-center gap-4 transition-all duration-500 ${
                correcto
                  ? 'bg-emerald-500/10 border-emerald-500/30'
                  : 'bg-rose-500/10 border-rose-500/30'
              }`}>
                {/* Avatar con iniciales */}
                <div className={`w-14 h-14 rounded-full flex items-center justify-center text-lg font-black shrink-0 ${
                  correcto ? 'bg-emerald-400/20 text-emerald-400' : 'bg-rose-400/20 text-rose-400'
                }`}>
                  {iniciales}
                </div>
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-wider mb-0.5 ${correcto ? 'text-emerald-500' : 'text-rose-500'}`}>
                    {correcto ? '¡Correcto!' : 'Era...'}
                  </p>
                  <p className="text-lg font-black text-white">{jugador.nombre}</p>
                  {mensaje && <p className="text-xs text-slate-500 mt-1 italic">{mensaje}</p>}
                </div>
              </div>
            )}
          </div>

          {/* ─ Panel derecho: opciones ─ */}
          <div className="flex flex-col justify-between gap-4">
            <div className="grid grid-cols-1 gap-3">
              {jugador.opciones.map(op => {
                const esCorrecta  = op === jugador.nombre
                const esElegida   = op === seleccion
                let estilo = 'bg-slate-800/40 border-slate-700/50 text-slate-300 hover:bg-slate-800 hover:border-slate-600 hover:text-white'
                if (respondido) {
                  if (esCorrecta)       estilo = 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                  else if (esElegida)   estilo = 'bg-rose-500/15 border-rose-500/40 text-rose-300'
                  else                  estilo = 'bg-slate-800/20 border-slate-800 text-slate-600'
                }
                return (
                  <button
                    key={op}
                    onClick={() => responder(op)}
                    disabled={respondido}
                    className={`w-full text-left px-5 py-3.5 rounded-xl border font-semibold text-sm
                                transition-all duration-200 flex items-center justify-between gap-3
                                disabled:cursor-default ${estilo}`}
                  >
                    <span>{op}</span>
                    {respondido && esCorrecta && (
                      <svg viewBox="0 0 20 20" className="w-4 h-4 fill-current text-emerald-400 shrink-0">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 00-1.414 0L8 12.586 4.707 9.293a1 1 0 00-1.414 1.414l4 4a1 1 0 001.414 0l8-8a1 1 0 000-1.414z" clipRule="evenodd"/>
                      </svg>
                    )}
                    {respondido && esElegida && !esCorrecta && (
                      <svg viewBox="0 0 20 20" className="w-4 h-4 fill-current text-rose-400 shrink-0">
                        <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/>
                      </svg>
                    )}
                  </button>
                )
              })}
            </div>

            {respondido && (
              <button
                onClick={siguiente}
                className="w-full py-3.5 rounded-xl bg-cyan-400 text-slate-950 font-black text-sm
                           hover:bg-cyan-300 active:scale-95 transition-all duration-150"
              >
                Siguiente jugador →
              </button>
            )}
          </div>

        </div>
      </div>
    </div>
  )
}

// ─── Datos: xG infravalorados ─────────────────────────────────────────────────
const XG_DATA = {
  sobreRinde: { nombre: 'Lewandowski', equipo: 'Barcelona',  goles: 26, xg: 19.2, diff: 6.8 },
  bajoRinde:  { nombre: 'En-Nesyri',   equipo: 'Sevilla FC', goles:  9, xg: 15.4, diff: 6.4 },
}

// ─── Ligas disponibles ───────────────────────────────────────────────────────
const LIGAS = [
  { id: 'laliga',      nombre: 'LaLiga',      flag: '🇪🇸', activa: true },
  { id: 'premier',     nombre: 'Premier',     flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', activa: false },
  { id: 'bundesliga',  nombre: 'Bundesliga',  flag: '🇩🇪', activa: false },
  { id: 'seriea',      nombre: 'Serie A',     flag: '🇮🇹', activa: false },
  { id: 'ligue1',      nombre: 'Ligue 1',     flag: '🇫🇷', activa: false },
]

// ─── Tooltip del BarChart del dato de la semana ──────────────────────────────
function DatoTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 shadow-2xl">
      <p className="text-slate-400 text-xs font-semibold mb-2 uppercase tracking-wider">{label}</p>
      {payload.map(p => (
        <div key={p.name} className="flex items-center gap-2 text-sm">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.fill }} />
          <span className="text-slate-400 capitalize">{p.name}</span>
          <span className="font-black text-white ml-auto pl-4">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Página ──────────────────────────────────────────────────────────────────
export default function Insights() {
  const [ligaSel, setLigaSel] = useState('laliga')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const t = setTimeout(() => setLoading(false), 1300)
    return () => clearTimeout(t)
  }, [ligaSel])

  const ligaActual = LIGAS.find(l => l.id === ligaSel)

  return (
    <main className="animate-fade-in max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-12">

      {/* ── Header + selector de liga ── */}
      <div>
        <h1 className="text-3xl font-black text-white mb-1">Insights</h1>
        <p className="text-slate-400 font-light mb-6">
          Los datos más llamativos de la temporada. Sin filtros, con opinión.
        </p>

        {/* Liga pills */}
        <div className="flex overflow-x-auto scrollbar-hide gap-2 pb-1">
          {LIGAS.map(liga => {
            const seleccionada = ligaSel === liga.id
            return (
              <button
                key={liga.id}
                onClick={() => liga.activa && setLigaSel(liga.id)}
                title={!liga.activa ? 'Próximamente' : undefined}
                className={`flex shrink-0 items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold
                            transition-all duration-150 ${
                  seleccionada
                    ? 'bg-cyan-400 text-slate-950 shadow-md shadow-cyan-500/20'
                    : liga.activa
                    ? 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-600'
                    : 'bg-slate-900/50 border border-slate-800/50 text-slate-700 cursor-not-allowed'
                }`}
              >
                <span>{liga.flag}</span>
                <span>{liga.nombre}</span>
                {!liga.activa && (
                  <span className="text-xs font-normal text-slate-600 ml-0.5">·  pronto</span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Cards de insights ── */}
      <div>
        <div className="flex items-center gap-3 mb-6">
          <span className="text-lg">{ligaActual?.flag}</span>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
            {ligaActual?.nombre} · Temporada 2024/25
          </p>
        </div>

        {loading ? <InsightsSkeleton /> : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {insights.map((insight, i) => (
              <div key={insight.id} className="animate-fade-up" style={{ animationDelay: `${i * 70}ms` }}>
                <InsightCard insight={insight} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ══════════════════════════════════════════════════════════════════════
          ── Jugadores en forma esta semana ──
      ══════════════════════════════════════════════════════════════════════ */}
      {!loading && (
        <div>
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1.5 h-5 rounded-full bg-cyan-400" />
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
              Jugadores en forma esta semana
            </p>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            {/* Cabecera */}
            <div className="grid grid-cols-[1.5rem_1fr_auto_auto_auto] gap-x-4 px-6 py-3 border-b border-slate-800">
              <span />
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Jugador</span>
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider text-right">G+A</span>
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider text-right">Nota media</span>
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider text-right">Tendencia</span>
            </div>

            {JUGADORES_FORMA.map((j, i) => {
              const diff = (j.nota - j.notaAnterior).toFixed(1)
              const sube = j.tendencia === 'sube'
              return (
                <div
                  key={j.nombre}
                  className={`grid grid-cols-[1.5rem_1fr_auto_auto_auto] gap-x-4 px-6 py-4 items-center
                              transition-colors duration-150 hover:bg-slate-800/40 ${
                    i < JUGADORES_FORMA.length - 1 ? 'border-b border-slate-800/60' : ''
                  }`}
                >
                  {/* Posición */}
                  <span className={`text-sm font-black tabular-nums ${i === 0 ? 'text-cyan-400' : 'text-slate-600'}`}>
                    {i + 1}
                  </span>

                  {/* Jugador */}
                  <div>
                    <p className="text-sm font-bold text-white">{j.nombre}</p>
                    <p className="text-xs text-slate-500">{j.equipo} · últimas 3 jornadas</p>
                  </div>

                  {/* G+A */}
                  <span className="text-sm font-black text-white tabular-nums text-right">{j.ga}</span>

                  {/* Nota */}
                  <span className="text-sm font-black text-cyan-400 tabular-nums text-right">{j.nota.toFixed(1)}</span>

                  {/* Tendencia */}
                  <div className={`flex items-center justify-end gap-1 ${sube ? 'text-emerald-400' : 'text-rose-400'}`}>
                    <svg viewBox="0 0 10 10" className="w-3 h-3" fill="currentColor">
                      {sube
                        ? <polygon points="5,1 9,9 1,9" />
                        : <polygon points="5,9 9,1 1,1" />}
                    </svg>
                    <span className="text-xs font-bold tabular-nums">
                      {sube ? '+' : ''}{diff}
                    </span>
                  </div>
                </div>
              )
            })}

            {/* Leyenda inferior */}
            <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/60">
              <p className="text-xs text-slate-600">
                Nota media de las últimas 3 jornadas · Flecha compara vs las 3 jornadas anteriores · G+A = goles + asistencias
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          ── Equipos en racha ──
      ══════════════════════════════════════════════════════════════════════ */}
      {!loading && (
        <div>
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1.5 h-5 rounded-full bg-cyan-400" />
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
              Equipos en racha
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

            {/* Mejoran */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="flex items-center gap-2 px-5 py-4 border-b border-slate-800 bg-emerald-500/5">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Los que más mejoran</span>
                <span className="ml-auto text-xs text-slate-600">últimas 5 jornadas</span>
              </div>
              {EQUIPOS_RACHA.mejoran.map((eq, i) => {
                const mejora = (eq.ahora - eq.antes).toFixed(1)
                const pct = Math.round((eq.ahora / 3) * 100)
                return (
                  <div
                    key={eq.nombre}
                    className={`px-5 py-4 ${i < EQUIPOS_RACHA.mejoran.length - 1 ? 'border-b border-slate-800/60' : ''}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-bold text-white">{eq.nombre}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500 tabular-nums">{eq.antes} pts/PJ</span>
                        <span className="text-slate-700">→</span>
                        <span className="text-sm font-black text-emerald-400 tabular-nums">{eq.ahora} pts/PJ</span>
                        <span className="text-xs font-bold text-emerald-400">(+{mejora})</span>
                      </div>
                    </div>
                    {/* Barra de progreso visual */}
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-400 rounded-full transition-all duration-700"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Empeoran */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="flex items-center gap-2 px-5 py-4 border-b border-slate-800 bg-rose-500/5">
                <span className="w-2 h-2 rounded-full bg-rose-400" />
                <span className="text-xs font-semibold text-rose-400 uppercase tracking-wider">Los que más empeoran</span>
                <span className="ml-auto text-xs text-slate-600">últimas 5 jornadas</span>
              </div>
              {EQUIPOS_RACHA.empeoran.map((eq, i) => {
                const caida = (eq.antes - eq.ahora).toFixed(1)
                const pctAntes = Math.round((eq.antes / 3) * 100)
                const pctAhora = Math.round((eq.ahora / 3) * 100)
                return (
                  <div
                    key={eq.nombre}
                    className={`px-5 py-4 ${i < EQUIPOS_RACHA.empeoran.length - 1 ? 'border-b border-slate-800/60' : ''}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-bold text-white">{eq.nombre}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500 tabular-nums">{eq.antes} pts/PJ</span>
                        <span className="text-slate-700">→</span>
                        <span className="text-sm font-black text-rose-400 tabular-nums">{eq.ahora} pts/PJ</span>
                        <span className="text-xs font-bold text-rose-400">(-{caida})</span>
                      </div>
                    </div>
                    {/* Barra doble: antes vs ahora */}
                    <div className="relative h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="absolute left-0 top-0 h-full bg-slate-600 rounded-full"
                        style={{ width: `${pctAntes}%` }}
                      />
                      <div
                        className="absolute left-0 top-0 h-full bg-rose-400 rounded-full transition-all duration-700"
                        style={{ width: `${pctAhora}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>

          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          ── El más infravalorado (xG) ──
      ══════════════════════════════════════════════════════════════════════ */}
      {!loading && (
        <div>
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1.5 h-5 rounded-full bg-cyan-400" />
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
              El más infravalorado
            </p>
          </div>

          {/* Explicación xG */}
          <div className="mb-5 bg-slate-800/40 border border-slate-700/40 rounded-xl px-5 py-3 flex gap-3 items-start">
            <span className="text-lg mt-0.5">💡</span>
            <p className="text-sm text-slate-400 leading-relaxed">
              <strong className="text-slate-300">¿Qué es el xG?</strong>{' '}
              El <em>Expected Goals</em> (xG) mide la calidad de cada remate según dónde se lanza, con qué pie, y cómo llegó el balón.
              Un xG de 0.3 significa que ese remate se convierte en gol un 30% de las veces.
              Si un jugador marca más goles de los que su xG predice, es un rematador extraordinario.
              Si marca menos, o tiene mala suerte o no aprovecha sus ocasiones.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

            {/* Sobre-rinde */}
            <div className="relative overflow-hidden bg-slate-900 border border-emerald-500/30 rounded-2xl p-7">
              <div className="absolute -top-10 -right-10 w-48 h-48 bg-emerald-500/5 rounded-full blur-2xl pointer-events-none" />
              <div className="relative">
                <div className="flex items-center gap-2 mb-4">
                  <span className="bg-emerald-400/15 border border-emerald-400/30 text-emerald-400 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
                    Le deben más goles
                  </span>
                </div>
                <h3 className="text-2xl font-black text-white mb-0.5">{XG_DATA.sobreRinde.nombre}</h3>
                <p className="text-slate-500 text-sm mb-6">{XG_DATA.sobreRinde.equipo}</p>

                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl px-4 py-3 text-center">
                    <p className="text-2xl font-black text-white">{XG_DATA.sobreRinde.goles}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Goles reales</p>
                  </div>
                  <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl px-4 py-3 text-center">
                    <p className="text-2xl font-black text-slate-400">{XG_DATA.sobreRinde.xg}</p>
                    <p className="text-xs text-slate-500 mt-0.5">xG esperado</p>
                  </div>
                  <div className="bg-emerald-400/10 border border-emerald-400/30 rounded-xl px-4 py-3 text-center">
                    <p className="text-2xl font-black text-emerald-400">+{XG_DATA.sobreRinde.diff}</p>
                    <p className="text-xs text-emerald-600 mt-0.5">sobre xG</p>
                  </div>
                </div>

                <p className="text-sm text-slate-400 mt-5 leading-relaxed">
                  Marca {XG_DATA.sobreRinde.diff} goles más de lo que sus ocasiones merecen estadísticamente.
                  Definición, posicionamiento e inteligencia que los datos no siempre capturan.
                </p>
              </div>
            </div>

            {/* Bajo-rinde */}
            <div className="relative overflow-hidden bg-slate-900 border border-rose-500/30 rounded-2xl p-7">
              <div className="absolute -top-10 -right-10 w-48 h-48 bg-rose-500/5 rounded-full blur-2xl pointer-events-none" />
              <div className="relative">
                <div className="flex items-center gap-2 mb-4">
                  <span className="bg-rose-400/15 border border-rose-400/30 text-rose-400 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
                    La mala suerte en persona
                  </span>
                </div>
                <h3 className="text-2xl font-black text-white mb-0.5">{XG_DATA.bajoRinde.nombre}</h3>
                <p className="text-slate-500 text-sm mb-6">{XG_DATA.bajoRinde.equipo}</p>

                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl px-4 py-3 text-center">
                    <p className="text-2xl font-black text-white">{XG_DATA.bajoRinde.goles}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Goles reales</p>
                  </div>
                  <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl px-4 py-3 text-center">
                    <p className="text-2xl font-black text-slate-400">{XG_DATA.bajoRinde.xg}</p>
                    <p className="text-xs text-slate-500 mt-0.5">xG esperado</p>
                  </div>
                  <div className="bg-rose-400/10 border border-rose-400/30 rounded-xl px-4 py-3 text-center">
                    <p className="text-2xl font-black text-rose-400">-{XG_DATA.bajoRinde.diff}</p>
                    <p className="text-xs text-rose-600 mt-0.5">bajo xG</p>
                  </div>
                </div>

                <p className="text-sm text-slate-400 mt-5 leading-relaxed">
                  El modelo dice que debería llevar {XG_DATA.bajoRinde.xg} goles y solo tiene {XG_DATA.bajoRinde.goles}.
                  Genera ocasiones de calidad elite pero el gol no quiere entrar. O es mala puntería, o es mala suerte.
                </p>
              </div>
            </div>

          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          ── ¿Adivinas quién es? ──
      ══════════════════════════════════════════════════════════════════════ */}
      {!loading && (
        <div>
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1.5 h-5 rounded-full bg-cyan-400" />
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
              ¿Adivinas quién es?
            </p>
          </div>
          <QuizJugador />
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          ── Análisis de la jornada ──
      ══════════════════════════════════════════════════════════════════════ */}
      {!loading && (
        <div>
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1.5 h-5 rounded-full bg-cyan-400" />
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
              Análisis de la jornada
            </p>
          </div>

          <div className="relative overflow-hidden bg-slate-900 border border-slate-800 rounded-2xl">
            {/* Glow de fondo */}
            <div className="absolute -top-24 -right-24 w-96 h-96 bg-cyan-500/4 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -bottom-16 -left-16 w-72 h-72 bg-indigo-600/4 rounded-full blur-3xl pointer-events-none" />

            <div className="relative p-7 sm:p-10">
              {/* Cabecera */}
              <div className="flex flex-wrap items-start justify-between gap-3 mb-8">
                <div>
                  <h2 className="text-2xl sm:text-3xl font-black text-white leading-tight mb-1">
                    {ANALISIS_JORNADA.titulo}
                  </h2>
                  <p className="text-slate-500 text-sm">{ANALISIS_JORNADA.subtitulo}</p>
                </div>
                {/* Badges */}
                <div className="flex flex-wrap items-center gap-2 mt-0.5">
                  <span className="flex items-center gap-1.5 bg-slate-800 border border-slate-700/60 text-slate-500 text-xs px-3 py-1.5 rounded-full">
                    <svg viewBox="0 0 16 16" className="w-3 h-3 fill-current text-cyan-500/70" xmlns="http://www.w3.org/2000/svg">
                      <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 2.5a1 1 0 1 1 0 2 1 1 0 0 1 0-2zM7 7h2v5H7V7z"/>
                    </svg>
                    Generado con IA
                  </span>
                  <span className="text-slate-600 text-xs px-2 py-1.5">
                    {ANALISIS_JORNADA.fecha}
                  </span>
                </div>
              </div>

              {/* Stats clave */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
                {ANALISIS_JORNADA.stats.map(s => (
                  <div key={s.label} className="bg-slate-800/60 border border-slate-700/40 rounded-xl px-4 py-3 text-center">
                    <p className={`text-xl font-black tabular-nums ${s.color === 'cyan' ? 'text-cyan-400' : 'text-white'}`}>
                      {s.valor}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5 leading-tight">{s.label}</p>
                  </div>
                ))}
              </div>

              {/* Texto editorial */}
              <div className="space-y-4 border-t border-slate-800 pt-7">
                {ANALISIS_JORNADA.parrafos.map((p, i) => (
                  <p key={i} className="text-slate-300 text-sm sm:text-base leading-relaxed">
                    {p}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          ── El dato que no viste ──
      ══════════════════════════════════════════════════════════════════════ */}
      {!loading && (
        <div>
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1.5 h-5 rounded-full bg-cyan-400" />
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
              El dato que no viste
            </p>
          </div>

          <div className="relative overflow-hidden bg-slate-900 border border-cyan-500/20 rounded-2xl p-7 sm:p-10">
            <div className="absolute -top-16 -left-16 w-72 h-72 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

            <div className="relative flex flex-col sm:flex-row gap-8 items-start">

              {/* Dato numérico grande */}
              <div className="shrink-0 flex flex-col items-center sm:items-start">
                <div className="bg-cyan-400/10 border border-cyan-400/25 rounded-2xl px-8 py-6 text-center min-w-[120px]">
                  <span className="text-6xl sm:text-7xl font-black text-cyan-400 tabular-nums leading-none">
                    {DATO_NO_VISTE.dato}
                  </span>
                  <p className="text-xs text-slate-400 mt-2 leading-snug max-w-[100px] mx-auto">
                    {DATO_NO_VISTE.unidad}
                  </p>
                </div>
                <p className="text-xs text-slate-600 mt-2 text-center sm:text-left italic">
                  {DATO_NO_VISTE.contexto}
                </p>
              </div>

              {/* Texto */}
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2 mb-4">
                  <span className="flex items-center gap-1.5 bg-slate-800 border border-slate-700/60 text-slate-500 text-xs px-3 py-1.5 rounded-full">
                    <svg viewBox="0 0 16 16" className="w-3 h-3 fill-current text-cyan-500/70">
                      <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 2.5a1 1 0 1 1 0 2 1 1 0 0 1 0-2zM7 7h2v5H7V7z"/>
                    </svg>
                    Generado con IA
                  </span>
                </div>
                <h3 className="text-xl sm:text-2xl font-black text-white leading-tight mb-4">
                  {DATO_NO_VISTE.titulo}
                </h3>
                <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
                  {DATO_NO_VISTE.explicacion}
                </p>
              </div>

            </div>
          </div>
        </div>
      )}

      {/* ── Dato de la semana ── */}
      {!loading && <div>
        <div className="flex items-center gap-2 mb-5">
          <div className="w-1.5 h-5 rounded-full bg-cyan-400" />
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
            Dato de la semana
          </p>
        </div>

        <div className="relative overflow-hidden bg-slate-900 border border-slate-800
                        rounded-2xl p-7 sm:p-10">
          {/* Glow */}
          <div className="absolute -top-20 -left-20 w-80 h-80 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-20 right-0 w-64 h-64 bg-blue-600/5 rounded-full blur-3xl pointer-events-none" />

          <div className="relative grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            {/* Texto */}
            <div>
              <h2 className="text-2xl sm:text-3xl font-black text-white leading-tight mb-4">
                {datoSemana.titulo}
              </h2>
              <p className="text-slate-400 leading-relaxed mb-6 text-sm sm:text-base">
                {datoSemana.bajada}
              </p>

              {/* Stat grande */}
              <div className="bg-slate-800/60 border border-slate-700/40 rounded-2xl px-6 py-5 inline-block">
                <span className="text-5xl font-black text-cyan-400 tabular-nums">
                  {datoSemana.stat}
                </span>
                <p className="text-slate-400 text-sm mt-1">{datoSemana.unidad}</p>
                <p className="text-slate-600 text-xs mt-0.5">{datoSemana.contexto}</p>
              </div>
            </div>

            {/* Gráfica */}
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4">
                Goles vs xG — Top 5 goleadores LaLiga 24/25
              </p>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart
                  data={datoSemana.chart}
                  barCategoryGap="25%"
                  barGap={3}
                  margin={{ top: 0, right: 8, left: -20, bottom: 0 }}
                >
                  <CartesianGrid vertical={false} stroke="#1e293b" />
                  <XAxis
                    dataKey="nombre"
                    tick={{ fill: '#64748b', fontSize: 11, fontFamily: 'Space Grotesk', fontWeight: 600 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#64748b', fontSize: 11, fontFamily: 'Space Grotesk' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip content={<DatoTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                  <Legend
                    wrapperStyle={{ fontSize: 12, color: '#94a3b8', fontFamily: 'Space Grotesk', paddingTop: 12 }}
                    formatter={v => v.charAt(0).toUpperCase() + v.slice(1)}
                  />
                  <Bar dataKey="goles" name="goles" fill="#22d3ee" radius={[4,4,0,0]} isAnimationActive animationDuration={700} animationEasing="ease-out" />
                  <Bar dataKey="xG"    name="xG"    fill="#6366f1" radius={[4,4,0,0]} isAnimationActive animationDuration={700} animationEasing="ease-out" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>}

    </main>
  )
}
