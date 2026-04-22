import { Link } from 'react-router-dom'

// top  → cian brillante (≈ top 25%)
// good → cian normal    (≈ top 50%)
// ok   → amber          (≈ bottom 10% cutoff; por debajo → rojo)
const THRESHOLDS = {
  goles:             { max: 30,   top: 12,   good: 5,    ok: 2 },
  asistencias:       { max: 20,   top: 7,    good: 3,    ok: 1 },
  xG:                { max: 25,   top: 10,   good: 4,    ok: 1.5 },
  xA:                { max: 15,   top: 6,    good: 3,    ok: 1 },
  pases_completados: { max: 95,   top: 86,   good: 74,   ok: 58 },
  regates:           { max: 9,    top: 4,    good: 2,    ok: 0.5 },
  recuperaciones:    { max: 12,   top: 6,    good: 3,    ok: 0.8 },
  goles_por_90:      { max: 1.2,  top: 0.55, good: 0.28, ok: 0.07 },
  asistencias_por_90:{ max: 0.8,  top: 0.38, good: 0.18, ok: 0.04 },
  ga_por_90:         { max: 1.8,  top: 0.85, good: 0.42, ok: 0.1 },
}

const METRIC_LABELS = {
  goles: 'Goles', asistencias: 'Asist.', xG: 'xG', xA: 'xA',
  pases_completados: 'Pases %', regates: 'Regates',
  recuperaciones: 'Recup.',
  goles_por_90: 'G/90', asistencias_por_90: 'A/90', ga_por_90: 'G+A/90',
}

const POSICION_METRICS = {
  'Delantero':       ['goles', 'xG', 'asistencias', 'recuperaciones'],
  'Extremo':         ['goles', 'regates', 'asistencias', 'xG'],
  'Mediapunta':      ['asistencias', 'xA', 'goles', 'pases_completados'],
  'Centrocampista':  ['pases_completados', 'recuperaciones', 'regates', 'asistencias'],
  'Defensa Central': ['recuperaciones', 'pases_completados', 'goles', 'xG'],
  'Lateral':         ['asistencias', 'regates', 'recuperaciones', 'pases_completados'],
  'Portero':         ['pases_completados', 'recuperaciones', 'goles', 'xG'],
}

const POSICION_BADGE = {
  'Delantero':       'text-orange-400 bg-orange-400/10',
  'Extremo':         'text-yellow-400 bg-yellow-400/10',
  'Mediapunta':      'text-purple-400 bg-purple-400/10',
  'Centrocampista':  'text-cyan-400 bg-cyan-400/10',
  'Defensa Central': 'text-blue-400 bg-blue-400/10',
  'Lateral':         'text-indigo-400 bg-indigo-400/10',
  'Portero':         'text-slate-400 bg-slate-400/10',
}

// Gradient combos for the avatar based on first initial
const AVATAR_GRADIENTS = [
  'from-cyan-500/30 to-blue-600/30',
  'from-violet-500/30 to-purple-600/30',
  'from-amber-500/30 to-orange-600/30',
  'from-emerald-500/30 to-teal-600/30',
  'from-rose-500/30 to-pink-600/30',
  'from-indigo-500/30 to-blue-600/30',
]

function getColor(key, value) {
  const t = THRESHOLDS[key]
  if (!t)              return { text: 'text-slate-400', bar: 'bg-slate-600' }
  if (value >= t.top)  return { text: 'text-cyan-300',  bar: 'bg-cyan-300' }
  if (value >= t.good) return { text: 'text-cyan-400',  bar: 'bg-cyan-400' }
  if (value >= t.ok)   return { text: 'text-amber-400', bar: 'bg-amber-400' }
  return                      { text: 'text-red-400',   bar: 'bg-red-500' }
}

function getInitials(nombre) {
  return nombre.split(' ').slice(0, 2).map(n => n[0]).join('').toUpperCase()
}

function MetricRow({ metricKey, value }) {
  const t = THRESHOLDS[metricKey]
  const pct = t ? Math.min((value / t.max) * 100, 100) : 50
  const { text, bar } = getColor(metricKey, value)

  return (
    <div className="flex items-center gap-2.5">
      <span className="text-slate-500 text-xs font-medium w-14 shrink-0 tabular-nums">
        {METRIC_LABELS[metricKey]}
      </span>
      <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${bar}`}
          style={{ width: `${pct}%`, transition: 'width 0.6s ease' }}
        />
      </div>
      <span className={`text-xs font-bold tabular-nums w-7 text-right ${text}`}>
        {value}
      </span>
    </div>
  )
}

export default function PlayerCard({ jugador }) {
  const initials = getInitials(jugador.nombre)
  const metrics  = POSICION_METRICS[jugador.posicion] || ['goles', 'asistencias', 'xG', 'regates']
  const gradient = AVATAR_GRADIENTS[jugador.nombre.charCodeAt(0) % AVATAR_GRADIENTS.length]
  const badgeClass = POSICION_BADGE[jugador.posicion] || 'text-slate-400 bg-slate-400/8'

  return (
    <Link to={`/jugador/${jugador.id}`} className="block group">
      <div className="relative bg-slate-900 border border-slate-800 rounded-2xl p-5 h-full
                      transition-all duration-200 will-change-transform
                      hover:border-cyan-500/40 hover:bg-slate-800/50
                      hover:scale-[1.02] hover:shadow-xl hover:shadow-cyan-950/60">

        {/* Avatar + name */}
        <div className="flex items-center gap-3 mb-4">
          <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${gradient} border border-white/5
                          flex items-center justify-center shrink-0`}>
            <span className="text-sm font-black text-white">{initials}</span>
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-bold text-white text-sm leading-tight truncate
                           group-hover:text-cyan-400 transition-colors">
              {jugador.nombre}
            </h3>
            <p className="text-slate-500 text-xs mt-0.5 truncate">{jugador.equipo}</p>
          </div>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${
            jugador.edad < 25  ? 'text-cyan-400 bg-cyan-400/10' :
            jugador.edad <= 33 ? 'text-amber-400 bg-amber-400/10' :
                                 'text-red-400 bg-red-400/10'
          }`}>
            {jugador.edad}a
          </span>
        </div>

        {/* Position */}
        <div className="mb-3.5">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${badgeClass}`}>
            {jugador.posicion}
          </span>
        </div>

        {/* Metrics */}
        <div className="space-y-2.5">
          {metrics.map(m => (
            <MetricRow key={m} metricKey={m} value={jugador.metricas[m]} />
          ))}
        </div>

        {/* Rate stats strip */}
        <div className="mt-3.5 pt-3 border-t border-slate-800/60 grid grid-cols-4 gap-1 text-center">
          {[
            { key: 'minutos_jugados', label: 'Min' },
            { key: 'goles_por_90',    label: 'G/90' },
            { key: 'asistencias_por_90', label: 'A/90' },
            { key: 'ga_por_90',       label: 'G+A/90' },
          ].map(({ key, label }) => {
            const val = jugador.metricas[key]
            const { text } = getColor(key, val)
            return (
              <div key={key} className="flex flex-col gap-0.5">
                <span className={`text-xs font-black tabular-nums leading-none ${
                  key === 'minutos_jugados' ? 'text-slate-300' : text
                }`}>
                  {key === 'minutos_jugados' ? val?.toLocaleString('es') : val}
                </span>
                <span className="text-slate-600 text-[10px]">{label}</span>
              </div>
            )
          })}
        </div>

        {/* Footer */}
        <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex justify-between items-center">
          <span className="text-xs text-slate-600">{jugador.nacionalidad}</span>
          <span className="text-xs text-slate-600 group-hover:text-cyan-400 transition-colors font-medium">
            Ver perfil →
          </span>
        </div>
      </div>
    </Link>
  )
}
