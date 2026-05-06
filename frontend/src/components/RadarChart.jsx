import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip,
} from 'recharts'

const MAX_VALUES = {
  goles: 35, asistencias: 20, xG: 28, xA: 15,
  pases_completados: 95, regates: 120, recuperaciones: 80,
  intercepciones: 80, entradas: 100,
  portero_paradas: 150, portero_paradas_pct: 85,
  portero_goles_encajados: 50,
}

const LABELS = {
  goles: 'Goles', asistencias: 'Asistencias', xG: 'xG', xA: 'xA',
  pases_completados: 'Pases %', regates: 'Regates',
  recuperaciones: 'Recup.', intercepciones: 'Intercep.',
  entradas: 'Entradas', portero_paradas: 'Paradas',
  portero_paradas_pct: 'Paradas %',
  portero_goles_encajados: 'Goles enc.',
}

// Métricas donde menos valor = mejor (se invierten en el radar)
const INVERTED = new Set(['portero_goles_encajados'])

function CustomTooltip({ active, payload }) {
  if (active && payload?.length) {
    const { metric, raw } = payload[0].payload
    const isNull = raw == null
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm shadow-2xl">
        <p className="text-slate-400 text-xs">{LABELS[metric] || metric}</p>
        <p className={`font-black text-base ${isNull ? 'text-slate-500' : 'text-cyan-400'}`}>
          {isNull ? 'N/D' : raw}
        </p>
      </div>
    )
  }
  return null
}

export default function PlayerRadarChart({ metricas, keys, color = '#22d3ee' }) {
  const sourceKeys = keys
    ? keys.filter(k => k in MAX_VALUES)
    : Object.keys(metricas).filter(k => k in MAX_VALUES)

  const data = sourceKeys.map(key => {
      const raw = metricas[key] ?? null
      const num = Number(raw)
      const pct = (raw != null && Number.isFinite(num))
        ? INVERTED.has(key)
          ? Math.max(0, Math.min(100, Math.round(((MAX_VALUES[key] - num) / MAX_VALUES[key]) * 100)))
          : Math.min(100, Math.round((num / MAX_VALUES[key]) * 100))
        : 0
      return { metric: key, label: LABELS[key] || key, value: pct, raw }
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
