import { useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, LabelList,
} from 'recharts'
import { useCountUp } from '../hooks/useCountUp'

export default function InsightCard({ insight }) {
  const [expanded, setExpanded] = useState(false)
  const animatedVal = useCountUp(insight.valor, 800)

  return (
    <div
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      onClick={() => setExpanded(e => !e)}
      className={`bg-slate-900 border rounded-2xl p-6 flex flex-col gap-4
                  transition-all duration-200 cursor-pointer select-none ${
        expanded
          ? 'border-cyan-500/40 shadow-xl shadow-black/50 -translate-y-0.5'
          : 'border-slate-800'
      }`}
    >
      {/* Icon + título */}
      <div className="flex gap-3 items-start">
        <div className={`w-10 h-10 rounded-xl border flex items-center justify-center text-xl shrink-0
                         transition-colors duration-200 ${
          expanded
            ? 'bg-cyan-400/15 border-cyan-400/30'
            : 'bg-cyan-400/10 border-cyan-400/20'
        }`}>
          {insight.icono}
        </div>
        <h3 className={`font-bold text-sm leading-snug pt-1 transition-colors duration-200 ${
          expanded ? 'text-white' : 'text-slate-200'
        }`}>
          {insight.titulo}
        </h3>
      </div>

      {/* Big stat */}
      <div className="bg-slate-800/60 rounded-xl px-4 py-3 border border-slate-700/40">
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-black text-cyan-400 leading-none tabular-nums">
            {animatedVal}
          </span>
          <span className="text-slate-500 text-sm">{insight.unidad}</span>
        </div>
      </div>

      {/* Descripción base */}
      <p className="text-slate-400 text-sm leading-relaxed">
        {insight.descripcion}
      </p>

      {/* ── Contenido expandido al hover ── */}
      <div
        style={{
          maxHeight: expanded ? '320px' : '0',
          opacity: expanded ? 1 : 0,
          overflow: 'hidden',
          transition: 'max-height 0.35s ease, opacity 0.25s ease',
        }}
      >
        {/* Texto extendido */}
        <p className="text-slate-300 text-sm leading-relaxed mb-4 pt-1 border-t border-slate-800">
          {insight.descripcion_extendida}
        </p>

        {/* Mini chart top 5 */}
        {insight.top5 && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              {insight.top5Label}
            </p>
            <ResponsiveContainer width="100%" height={insight.top5.length * 30}>
              <BarChart
                layout="vertical"
                data={insight.top5}
                margin={{ top: 0, right: 36, left: 0, bottom: 0 }}
              >
                <XAxis type="number" hide domain={[0, 'dataMax']} />
                <YAxis
                  type="category"
                  dataKey="nombre"
                  width={72}
                  tick={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'Space Grotesk' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Bar
                  dataKey="valor"
                  fill={insight.top5Color || '#22d3ee'}
                  radius={[0, 4, 4, 0]}
                  maxBarSize={14}
                  isAnimationActive={true}
                  animationDuration={600}
                  animationEasing="ease-out"
                >
                  <LabelList
                    dataKey="valor"
                    position="right"
                    style={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'Space Grotesk', fontWeight: 700 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center gap-2 pt-1 border-t border-slate-800 mt-auto">
        <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
        <span className="text-xs text-slate-500 font-medium">{insight.referencia}</span>
        {!expanded && (
          <span className="ml-auto text-xs text-slate-700 hidden sm:inline">Pasa el ratón →</span>
        )}
        {!expanded && (
          <span className="ml-auto text-xs text-slate-700 sm:hidden">Toca →</span>
        )}
      </div>
    </div>
  )
}
