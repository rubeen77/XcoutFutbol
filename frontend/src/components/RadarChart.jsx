import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip,
} from 'recharts'

export const ALL_MAX_VALUES = {
  goles: 35, asistencias: 20, xG: 28, xA: 15,
  pases_completados: 95, regates: 120, recuperaciones: 80,
  intercepciones: 100, entradas: 80,
  tiros_totales: 120, tiros_a_puerta: 60,
  portero_paradas: 100, portero_goles_encajados: 50, portero_paradas_pct: 1,
  minutos_jugados: 3420, goles_por_90: 1.2, asistencias_por_90: 0.8, ga_por_90: 1.8,
}

export const ALL_LABELS = {
  goles: 'Goles', asistencias: 'Asistencias', xG: 'xG', xA: 'xA',
  pases_completados: 'Pases %', regates: 'Regates', recuperaciones: 'Recup.',
  intercepciones: 'Intercepciones', entradas: 'Entradas',
  tiros_totales: 'Tiros', tiros_a_puerta: 'Tiros puerta',
  portero_paradas: 'Paradas', portero_goles_encajados: 'Goles enc.',
  portero_paradas_pct: 'Paradas %',
  minutos_jugados: 'Minutos', goles_por_90: 'G/90', asistencias_por_90: 'A/90', ga_por_90: 'G+A/90',
}

const AXES_BY_POS = {
  'Portero':         ['portero_paradas_pct', 'portero_goles_encajados', 'portero_paradas', 'recuperaciones', 'minutos_jugados'],
  'Defensa Central': ['intercepciones', 'entradas', 'recuperaciones', 'goles', 'asistencias', 'pases_completados'],
  'Centrocampista':  ['recuperaciones', 'intercepciones', 'entradas', 'pases_completados', 'goles', 'asistencias'],
  'Extremo':         ['goles', 'asistencias', 'regates', 'tiros_a_puerta', 'pases_completados', 'recuperaciones'],
  'Mediapunta':      ['goles', 'asistencias', 'regates', 'tiros_a_puerta', 'pases_completados', 'recuperaciones'],
  'Delantero':       ['goles', 'asistencias', 'tiros_totales', 'tiros_a_puerta', 'xG', 'goles_por_90'],
}

const DEFAULT_AXES = ['goles', 'asistencias', 'xG', 'recuperaciones', 'pases_completados', 'regates', 'tiros_a_puerta']

export function getAxes(posicion) {
  return AXES_BY_POS[posicion] ?? DEFAULT_AXES
}

function CustomTooltip({ active, payload }) {
  if (active && payload?.length) {
    const { metric, raw } = payload[0].payload
    const display = metric === 'portero_paradas_pct'
      ? `${Math.round(raw * 100)}%`
      : raw
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm shadow-2xl">
        <p className="text-slate-400 text-xs">{ALL_LABELS[metric] || metric}</p>
        <p className="text-cyan-400 font-black text-base">{display}</p>
      </div>
    )
  }
  return null
}

export default function PlayerRadarChart({ metricas, color = '#22d3ee', axes }) {
  const activeAxes = axes ?? DEFAULT_AXES
  const data = activeAxes
    .filter(key => key in ALL_MAX_VALUES)
    .map(key => {
      const num = Number(metricas[key] ?? 0)
      const pct = Number.isFinite(num)
        ? Math.min(100, Math.round((num / ALL_MAX_VALUES[key]) * 100))
        : 0
      return { metric: key, label: ALL_LABELS[key] || key, value: pct, raw: Number.isFinite(num) ? num : 0 }
    })

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
        <PolarGrid stroke="#1e293b" strokeDasharray="4 4" />
        <PolarAngleAxis
          dataKey="label"
          tick={{ fill: '#64748b', fontSize: 11, fontWeight: 600, fontFamily: 'Space Grotesk' }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Radar
          dataKey="value"
          stroke={color}
          fill={color}
          fillOpacity={0.15}
          strokeWidth={2}
          dot={{ r: 3, fill: color, strokeWidth: 0 }}
          activeDot={{ r: 5, fill: color, strokeWidth: 0 }}
          isAnimationActive={true}
          animationDuration={700}
          animationEasing="ease-out"
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}
