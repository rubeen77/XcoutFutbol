import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip,
} from 'recharts'

const MAX_VALUES = {
  goles: 35, asistencias: 20, xG: 28, xA: 15,
  pases_completados: 95, regates: 120, recuperaciones: 80,
}

const LABELS = {
  goles: 'Goles', asistencias: 'Asistencias', xG: 'xG', xA: 'xA',
  pases_completados: 'Pases %', regates: 'Regates',
  recuperaciones: 'Recup.',
}

function CustomTooltip({ active, payload }) {
  if (active && payload?.length) {
    const { metric, raw } = payload[0].payload
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm shadow-2xl">
        <p className="text-slate-400 text-xs">{LABELS[metric] || metric}</p>
        <p className="text-cyan-400 font-black text-base">{raw}</p>
      </div>
    )
  }
  return null
}

export default function PlayerRadarChart({ metricas, color = '#22d3ee' }) {
  // Sólo renderizar las 8 métricas base; ignorar minutos, per-90, etc.
  const data = Object.entries(metricas)
    .filter(([key]) => key in MAX_VALUES)
    .map(([key, value]) => {
      const num = Number(value)
      const pct = Number.isFinite(num)
        ? Math.min(100, Math.round((num / MAX_VALUES[key]) * 100))
        : 0
      return { metric: key, label: LABELS[key] || key, value: pct, raw: Number.isFinite(num) ? num : 0 }
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
