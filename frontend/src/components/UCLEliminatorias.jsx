import { useState, useEffect } from 'react'
import { getEliminatorias } from '../services/api'

function EscudoMini({ src, nombre }) {
  const [err, setErr] = useState(false)
  return (
    <div className="w-8 h-8 min-w-[32px] rounded-lg bg-slate-800 border border-slate-700/50
                    flex items-center justify-center overflow-hidden shrink-0">
      {src && !err
        ? <img src={src} alt="" referrerPolicy="no-referrer"
               className="w-full h-full object-contain p-0.5"
               onError={() => setErr(true)} />
        : <span className="text-[9px] font-black text-slate-500">
            {(nombre || '??').slice(0, 2).toUpperCase()}
          </span>
      }
    </div>
  )
}

function TeamRow({ nombre, escudo, winner, score }) {
  return (
    <div className="flex items-center gap-2.5">
      <EscudoMini src={escudo} nombre={nombre} />
      <span className={`flex-1 text-sm font-semibold truncate ${winner ? 'text-cyan-400' : 'text-slate-300'}`}>
        {nombre || '?'}
      </span>
      {score != null && (
        <span className={`text-xl font-black tabular-nums w-7 text-right shrink-0
                          ${winner ? 'text-cyan-400' : 'text-slate-400'}`}>
          {score}
        </span>
      )}
    </div>
  )
}

function CruceCard({ cruce, esFinal = false }) {
  const {
    equipo_local, equipo_visitante, escudo_local, escudo_visitante, ganador,
    goles_local_ida, goles_visitante_ida,
    goles_local_vuelta, goles_visitante_vuelta,
    penaltis_local, penaltis_visitante,
  } = cruce

  const tieneIda    = goles_local_ida    != null
  const tieneVuelta = !esFinal && goles_local_vuelta != null

  const globalL = tieneIda ? (goles_local_ida || 0)    + (tieneVuelta ? goles_local_vuelta    || 0 : 0) : null
  const globalV = tieneIda ? (goles_visitante_ida || 0) + (tieneVuelta ? goles_visitante_vuelta || 0 : 0) : null

  const ganaL = ganador != null && ganador === equipo_local
  const ganaV = ganador != null && ganador === equipo_visitante

  return (
    <div className={`rounded-2xl border flex flex-col gap-3 p-4 ${
      esFinal
        ? 'border-amber-400/30 bg-gradient-to-b from-amber-500/5 to-slate-900/60'
        : 'border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-colors'
    }`}>
      <TeamRow nombre={equipo_local}    escudo={escudo_local}    winner={ganaL} score={globalL} />

      <div className="border-t border-slate-800/60 pt-2.5">
        {!tieneIda ? (
          <p className="text-[11px] text-slate-600 text-center">Pendiente</p>
        ) : esFinal ? (
          <p className="text-center text-base font-black text-slate-300 tabular-nums">
            {goles_local_ida}&nbsp;–&nbsp;{goles_visitante_ida}
            {penaltis_local != null && (
              <span className="text-[11px] font-medium text-amber-400/80 ml-2">
                ({penaltis_local}–{penaltis_visitante} p.)
              </span>
            )}
          </p>
        ) : (
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span>
              Ida&nbsp;
              <b className="text-slate-400 tabular-nums">{goles_local_ida}–{goles_visitante_ida}</b>
            </span>
            {tieneVuelta
              ? <span>Vuelta&nbsp;<b className="text-slate-400 tabular-nums">{goles_local_vuelta}–{goles_visitante_vuelta}</b></span>
              : <span className="text-amber-400/60 italic">Vuelta pendiente</span>
            }
            {penaltis_local != null && (
              <span className="text-amber-400/80">Pen.&nbsp;{penaltis_local}–{penaltis_visitante}</span>
            )}
          </div>
        )}
      </div>

      <TeamRow nombre={equipo_visitante} escudo={escudo_visitante} winner={ganaV} score={globalV} />
    </div>
  )
}

function RondaSection({ ronda, cruces }) {
  const esFinal = ronda === 'Final'
  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h3 className="text-base font-black text-white tracking-tight">{ronda}</h3>
        <div className="flex-1 h-px bg-slate-800" />
        {esFinal
          ? <span className="text-[10px] font-bold px-2.5 py-1 rounded-full
                             bg-amber-400/10 text-amber-400 border border-amber-400/25">
              30 mayo · Budapest
            </span>
          : <span className="text-[11px] text-slate-600">
              {cruces.length} {cruces.length === 1 ? 'cruce' : 'cruces'}
            </span>
        }
      </div>
      <div className={`grid grid-cols-1 gap-3 ${esFinal ? 'max-w-xs mx-auto' : 'sm:grid-cols-2'}`}>
        {cruces.map((c, i) => <CruceCard key={c.id ?? i} cruce={c} esFinal={esFinal} />)}
      </div>
    </div>
  )
}

export default function UCLEliminatorias({ ligaId = 28 }) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    setLoading(true); setError(null)
    getEliminatorias(ligaId)
      .then(d => setData(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [ligaId])

  if (loading) return (
    <div className="flex justify-center py-16">
      <div className="w-8 h-8 border-2 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin" />
    </div>
  )
  if (error) return (
    <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm text-center">
      Error al cargar eliminatorias: {error}
    </div>
  )
  if (!data?.rondas?.length) return (
    <p className="text-slate-500 text-center py-12 text-sm">Sin datos de eliminatorias disponibles.</p>
  )

  return (
    <div className="flex flex-col gap-8">
      {data.rondas.map(({ ronda, cruces }) => (
        <RondaSection key={ronda} ronda={ronda} cruces={cruces} />
      ))}
    </div>
  )
}
