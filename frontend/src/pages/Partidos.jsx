import { useState, useEffect, useCallback } from 'react'
import { getPartidos, getPartidoDetalle, getPartidosPorEquipo } from '../services/api'
import { useLiga } from '../contexts/LigaContext'
import UCLEliminatorias from '../components/UCLEliminatorias'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function initials(nombre) {
  return (nombre || '??').split(' ').map(w => w[0]).join('').slice(0, 3).toUpperCase()
}

function formatFechaLarga(fecha) {
  if (!fecha) return ''
  const d = new Date(fecha)
  return d.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

function formatFechaCorta(fecha) {
  if (!fecha) return ''
  const d = new Date(fecha)
  return d.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' })
}

function formatFechaPartido(fecha) {
  if (!fecha) return { dia: null, hora: null }
  const d = new Date(fecha)
  if (isNaN(d.getTime())) return { dia: null, hora: null }
  const dia = d.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'short' })
  const hh = d.getHours(), mm = d.getMinutes()
  const hora = (hh !== 0 || mm !== 0)
    ? `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
    : null
  return { dia: dia.charAt(0).toUpperCase() + dia.slice(1), hora }
}

const GRADIENTS = [
  'from-cyan-500/20 to-blue-600/20',   'from-violet-500/20 to-purple-600/20',
  'from-amber-500/20 to-orange-600/20', 'from-emerald-500/20 to-teal-600/20',
  'from-rose-500/20 to-pink-600/20',   'from-indigo-500/20 to-sky-600/20',
  'from-sky-500/20 to-cyan-600/20',    'from-fuchsia-500/20 to-violet-600/20',
]
function teamGradient(nombre) {
  let h = 0
  for (const c of (nombre || '')) h = (h * 31 + c.charCodeAt(0)) & 0xffff
  return GRADIENTS[h % GRADIENTS.length]
}

const TOTAL_JORNADAS = 38

// ─── Form helpers ─────────────────────────────────────────────────────────────

function rachaColor(r) {
  if (r === 'W') return 'bg-emerald-500 text-white'
  if (r === 'D') return 'bg-amber-400 text-slate-900'
  return 'bg-red-500 text-white'
}

function computeForm(partidos, equipo_id) {
  return partidos
    .filter(p => p.goles_local != null && p.goles_visitante != null)
    .sort((a, b) => (b.jornada || 0) - (a.jornada || 0))
    .slice(0, 5).reverse()
    .map(p => {
      const esLocal = p.equipo_local === equipo_id
      const gf = esLocal ? p.goles_local : p.goles_visitante
      const gc = esLocal ? p.goles_visitante : p.goles_local
      return gf > gc ? 'W' : gf === gc ? 'D' : 'L'
    })
}

// ─── Componentes básicos ──────────────────────────────────────────────────────

function Escudo({ nombre, escudo_url, size = 'md' }) {
  const [errored, setErrored] = useState(false)
  const dim     = size === 'lg' ? 64 : 56
  const showImg = escudo_url && !errored
  return (
    <div
      style={{
        position: 'relative',
        width:    `${dim}px`,
        height:   `${dim}px`,
        minWidth: `${dim}px`,
        flexShrink: 0,
        borderRadius: '12px',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(30,41,59,0.7)',
        border: '1px solid rgba(255,255,255,0.1)',
      }}
    >
      {!showImg && (
        <span style={{ fontSize: size === 'lg' ? '15px' : '13px', fontWeight: 900, color: '#cbd5e1', letterSpacing: '-0.02em' }}>
          {initials(nombre)}
        </span>
      )}
      {showImg && (
        <img
          src={escudo_url} alt={nombre} referrerPolicy="no-referrer"
          style={{ position: 'absolute', inset: '6px', width: 'calc(100% - 12px)', height: 'calc(100% - 12px)', objectFit: 'contain' }}
          onError={() => setErrored(true)}
        />
      )}
    </div>
  )
}

function StatCard({ label, value, icon }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-3.5 text-center flex flex-col items-center gap-0.5">
      {icon && <span className="text-xl leading-none mb-0.5">{icon}</span>}
      <p className="text-2xl font-black text-white tabular-nums leading-none">{value}</p>
      <p className="text-[11px] text-slate-500 mt-0.5">{label}</p>
    </div>
  )
}

// ─── Componentes del detalle ──────────────────────────────────────────────────

function SectionCard({ titulo, accentLocal, accentVisitante, children }) {
  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        {accentLocal  && <span className="text-[10px] font-bold" style={{ color: '#22d3ee' }}>{accentLocal}</span>}
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex-1 text-center">
          {titulo}
        </h4>
        {accentVisitante && <span className="text-[10px] font-bold" style={{ color: '#a78bfa' }}>{accentVisitante}</span>}
      </div>
      {children}
    </div>
  )
}

function ProximamentePlaceholder() {
  return (
    <div className="py-7 flex flex-col items-center gap-2 opacity-40">
      <svg className="w-6 h-6 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M12 6v6l4 2m6-2a10 10 0 11-20 0 10 10 0 0120 0z" />
      </svg>
      <p className="text-xs text-slate-500 font-medium">Disponible próximamente</p>
    </div>
  )
}

function FormCircles({ form }) {
  if (!form.length) return <span className="text-[11px] text-slate-600">Sin datos</span>
  return (
    <div className="flex gap-1">
      {form.map((r, i) => (
        <span key={i} className={`w-6 h-6 rounded-full flex items-center justify-center
                                   text-[10px] font-black ${rachaColor(r)}`}>
          {r === 'W' ? 'V' : r === 'D' ? 'E' : 'D'}
        </span>
      ))}
    </div>
  )
}

function StatRow({ label, local, visitante, suffix = '', invert = false }) {
  const total    = (local + visitante) || 1
  const localWins = invert ? local <= visitante : local >= visitante
  const visWins   = invert ? visitante <= local : visitante >= local
  const localPct  = (local / total) * 100
  return (
    <div>
      <p className="text-[10px] text-slate-500 text-center mb-1">{label}</p>
      <div className="grid items-center gap-2" style={{ gridTemplateColumns: '2.5rem 1fr 2.5rem' }}>
        <span className={`text-right text-sm font-bold tabular-nums ${localWins && local !== visitante ? 'text-cyan-400' : 'text-slate-300'}`}>
          {local}{suffix}
        </span>
        <div className="relative h-2 bg-slate-800 rounded-full overflow-hidden">
          <div className={`absolute left-0 top-0 h-full rounded-l-full ${localWins && local !== visitante ? 'bg-cyan-400' : 'bg-slate-600'}`}
               style={{ width: `${localPct}%` }} />
          <div className={`absolute right-0 top-0 h-full rounded-r-full ${visWins && local !== visitante ? 'bg-violet-400' : 'bg-slate-700'}`}
               style={{ width: `${100 - localPct}%` }} />
        </div>
        <span className={`text-left text-sm font-bold tabular-nums ${visWins && local !== visitante ? 'text-violet-400' : 'text-slate-300'}`}>
          {visitante}{suffix}
        </span>
      </div>
    </div>
  )
}

function XGSummary({ xgLocal, xgVisitante, nombreLocal, nombreVisitante }) {
  const max  = Math.max(xgLocal, xgVisitante, 1)
  const lPct = (xgLocal    / max) * 100
  const vPct = (xgVisitante / max) * 100
  const lWins = xgLocal > xgVisitante
  return (
    <div className="flex flex-col gap-3">
      <div>
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-xs text-slate-400 truncate max-w-[160px]">{nombreLocal}</span>
          <span className={`text-xl font-black tabular-nums ${lWins ? 'text-cyan-400' : 'text-slate-300'}`}>
            {xgLocal.toFixed(2)}
          </span>
        </div>
        <div className="h-2.5 bg-slate-800 rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${lWins ? 'bg-cyan-400' : 'bg-slate-500'}`}
               style={{ width: `${lPct}%` }} />
        </div>
      </div>
      <div>
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-xs text-slate-400 truncate max-w-[160px]">{nombreVisitante}</span>
          <span className={`text-xl font-black tabular-nums ${!lWins ? 'text-violet-400' : 'text-slate-300'}`}>
            {xgVisitante.toFixed(2)}
          </span>
        </div>
        <div className="h-2.5 bg-slate-800 rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${!lWins ? 'bg-violet-400' : 'bg-slate-500'}`}
               style={{ width: `${vPct}%` }} />
        </div>
      </div>
    </div>
  )
}

function ordinal(n) { return n ? `${n}º` : '—' }

// ─── Modal de detalle ─────────────────────────────────────────────────────────

function PartidoModal({ partidoId, onClose, ligaId = 1 }) {
  const [detalle,  setDetalle]  = useState(null)
  const [partLoc,  setPartLoc]  = useState([])
  const [partVis,  setPartVis]  = useState([])
  const [cargando, setCargando] = useState(true)
  const [error,    setError]    = useState(null)

  useEffect(() => {
    let cancelled = false
    setCargando(true); setDetalle(null); setPartLoc([]); setPartVis([])

    getPartidoDetalle(partidoId)
      .then(async d => {
        if (cancelled) return
        setDetalle(d)
        const lidId = d.local?.id     || d.equipo_local
        const vidId = d.visitante?.id || d.equipo_visitante
        const [rL, rV] = await Promise.all([
          getPartidosPorEquipo(lidId, ligaId),
          getPartidosPorEquipo(vidId, ligaId),
        ])
        if (cancelled) return
        setPartLoc(rL.partidos || [])
        setPartVis(rV.partidos || [])
      })
      .catch(e => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setCargando(false) })

    return () => { cancelled = true }
  }, [partidoId, ligaId])

  useEffect(() => {
    const fn = e => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', fn)
    return () => document.removeEventListener('keydown', fn)
  }, [onClose])

  const local       = detalle?.local?.nombre     || '—'
  const visitante   = detalle?.visitante?.nombre || '—'
  const localId     = detalle?.local?.id     || detalle?.equipo_local
  const visitanteId = detalle?.visitante?.id || detalle?.equipo_visitante
  const finalizado  = detalle?.goles_local != null && detalle?.goles_visitante != null
  const tieneXg     = (detalle?.xg_local != null) || (detalle?.xg_visitante != null)

  const formLocal     = computeForm(partLoc, localId)
  const formVisitante = computeForm(partVis, visitanteId)

  const h2h = partLoc.filter(p =>
    p.id !== partidoId && p.estado === 'finalizado' &&
    (
      (p.equipo_local === localId    && p.equipo_visitante === visitanteId) ||
      (p.equipo_local === visitanteId && p.equipo_visitante === localId)
    )
  ).sort((a, b) => (a.jornada || 0) - (b.jornada || 0))

  const localAbrev    = (local    || '').split(' ').filter(w => w.length > 2).slice(0, 2).map(w => w[0]).join('').toUpperCase() || initials(local)
  const visitanteAbrev = (visitante || '').split(' ').filter(w => w.length > 2).slice(0, 2).map(w => w[0]).join('').toUpperCase() || initials(visitante)

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      style={{ background: 'rgba(0,0,0,0.78)', backdropFilter: 'blur(4px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-slate-900 border border-slate-700 rounded-t-2xl sm:rounded-2xl w-full max-w-lg
                      shadow-2xl shadow-black/60 max-h-[92vh] overflow-y-auto">

        {/* Cabecera sticky */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800
                        sticky top-0 bg-slate-900/95 backdrop-blur-sm z-10">
          <span className="text-xs font-semibold text-slate-400">
            {detalle ? `Jornada ${detalle.jornada} · 2025/26` : 'Cargando…'}
          </span>
          <button onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-500
                       hover:text-white hover:bg-slate-800 transition-colors text-xl leading-none">
            ×
          </button>
        </div>

        <div className="p-4 sm:p-5 flex flex-col gap-4">

          {cargando && (
            <div className="flex justify-center py-10">
              <div className="w-7 h-7 border-2 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin" />
            </div>
          )}
          {error && !cargando && (
            <p className="text-red-400 text-sm text-center py-6">Error: {error}</p>
          )}

          {detalle && !cargando && (<>

            {/* ── 1. Resultado ── */}
            <div className="flex items-stretch gap-3">
              <div className="flex flex-col items-center gap-1.5 flex-1 min-w-0">
                <Escudo nombre={local} escudo_url={detalle?.local?.escudo_url} size="lg" />
                <span className="text-xs font-semibold text-white text-center leading-tight line-clamp-2">{local}</span>
                {(detalle.local?.posicion_clasificacion != null || detalle.local?.puntos != null) && (
                  <span className="text-[10px] text-slate-500 tabular-nums">
                    {ordinal(detalle.local.posicion_clasificacion)}
                    {detalle.local.puntos != null ? ` · ${detalle.local.puntos} pts` : ''}
                  </span>
                )}
              </div>

              <div className="flex flex-col items-center justify-center gap-1 shrink-0 w-24">
                {finalizado ? (
                  <div className="flex items-center gap-1.5">
                    <span className="text-4xl font-black text-white tabular-nums leading-none">{detalle.goles_local ?? '—'}</span>
                    <span className="text-xl text-slate-600 font-bold">-</span>
                    <span className="text-4xl font-black text-white tabular-nums leading-none">{detalle.goles_visitante ?? '—'}</span>
                  </div>
                ) : (
                  <span className="text-2xl font-bold text-slate-500">vs</span>
                )}
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                  finalizado ? 'text-cyan-400 bg-cyan-400/10' : 'text-amber-400 bg-amber-400/10'
                }`}>
                  {finalizado ? 'Final' : 'Pendiente'}
                </span>
                <span className="text-[10px] text-slate-600 text-center mt-0.5 capitalize">
                  {formatFechaCorta(detalle.fecha)}
                </span>
              </div>

              <div className="flex flex-col items-center gap-1.5 flex-1 min-w-0">
                <Escudo nombre={visitante} escudo_url={detalle?.visitante?.escudo_url} size="lg" />
                <span className="text-xs font-semibold text-white text-center leading-tight line-clamp-2">{visitante}</span>
                {(detalle.visitante?.posicion_clasificacion != null || detalle.visitante?.puntos != null) && (
                  <span className="text-[10px] text-slate-500 tabular-nums">
                    {ordinal(detalle.visitante.posicion_clasificacion)}
                    {detalle.visitante.puntos != null ? ` · ${detalle.visitante.puntos} pts` : ''}
                  </span>
                )}
              </div>
            </div>

            {/* Fecha larga */}
            {detalle.fecha && (
              <p className="text-center text-[11px] text-slate-600 -mt-1 capitalize">
                {formatFechaLarga(detalle.fecha)}
              </p>
            )}

            {/* ── 2. Forma últimos 5 ── */}
            <SectionCard titulo="Últimos 5 partidos" accentLocal={localAbrev} accentVisitante={visitanteAbrev}>
              {(formLocal.length > 0 || formVisitante.length > 0) ? (
                <div className="flex items-center justify-between gap-2 pt-1">
                  <FormCircles form={formLocal} />
                  <span className="text-[10px] text-slate-600">forma</span>
                  <FormCircles form={formVisitante} />
                </div>
              ) : <ProximamentePlaceholder />}
            </SectionCard>

            {/* ── 3. Head to head ── */}
            <SectionCard titulo="Enfrentamientos esta temporada">
              {h2h.length === 0 ? (
                <p className="text-xs text-slate-500 text-center py-1">Solo se ha jugado este partido</p>
              ) : (
                <div className="space-y-2 pt-1">
                  {h2h.map(p => {
                    const nomL = p.local?.nombre     || `Equipo ${p.equipo_local}`
                    const nomV = p.visitante?.nombre || `Equipo ${p.equipo_visitante}`
                    return (
                      <div key={p.id} className="flex items-center justify-between text-xs">
                        <span className="text-slate-400 truncate flex-1">{nomL}</span>
                        <span className="text-white font-black tabular-nums mx-3 shrink-0">
                          {p.goles_local} – {p.goles_visitante}
                        </span>
                        <span className="text-slate-400 truncate flex-1 text-right">{nomV}</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </SectionCard>

            {/* ── 4. Línea de tiempo ── */}
            <SectionCard titulo="Línea de tiempo">
              <ProximamentePlaceholder />
            </SectionCard>

            {/* ── 5. xG ── */}
            <SectionCard titulo="Expected Goals (xG)" accentLocal={localAbrev} accentVisitante={visitanteAbrev}>
              {tieneXg ? (
                <XGSummary
                  xgLocal={detalle.xg_local ?? 0}
                  xgVisitante={detalle.xg_visitante ?? 0}
                  nombreLocal={local}
                  nombreVisitante={visitante}
                />
              ) : <ProximamentePlaceholder />}
            </SectionCard>

            {/* ── 6. Estadísticas ── */}
            <SectionCard titulo="Estadísticas" accentLocal={localAbrev} accentVisitante={visitanteAbrev}>
              <ProximamentePlaceholder />
            </SectionCard>

            {/* ── 7. Mapa de disparos ── */}
            <SectionCard titulo="Mapa de disparos">
              <ProximamentePlaceholder />
            </SectionCard>

            {/* ── 8. Rendimiento individual ── */}
            <SectionCard titulo="Rendimiento individual">
              <ProximamentePlaceholder />
            </SectionCard>

          </>)}
        </div>
      </div>
    </div>
  )
}

// ─── Card de partido (clickable) ──────────────────────────────────────────────

function stripeColors(partido) {
  const { goles_local: gl, goles_visitante: gv } = partido
  const none = { color: '#1e293b', glow: 'transparent' }
  if (gl == null || gv == null) return { local: none, visitante: none }
  const WIN  = { color: '#10b981', glow: 'rgba(16,185,129,0.12)' }
  const DRAW = { color: '#f59e0b', glow: 'rgba(245,158,11,0.12)'  }
  const LOSE = { color: '#ef4444', glow: 'rgba(239,68,68,0.12)'   }
  if (gl === gv) return { local: DRAW, visitante: DRAW }
  return {
    local:     gl > gv ? WIN : LOSE,
    visitante: gv > gl ? WIN : LOSE,
  }
}

function PartidoCard({ partido, onClick }) {
  const local      = partido.local?.nombre     || '—'
  const visitante  = partido.visitante?.nombre || '—'
  const finalizado = partido.goles_local != null && partido.goles_visitante != null
  const { dia, hora } = formatFechaPartido(partido.fecha)
  const { local: stripeL, visitante: stripeV } = stripeColors(partido)

  return (
    <button
      onClick={() => onClick(partido.id)}
      className="w-full text-left rounded-2xl border border-slate-800 overflow-hidden
                 cursor-pointer group transition-all duration-200
                 hover:scale-[1.005] hover:shadow-xl hover:shadow-black/50
                 hover:border-slate-700"
      style={{
        borderLeft:  `4px solid ${stripeL.color}`,
        borderRight: `4px solid ${stripeV.color}`,
        background: finalizado
          ? `linear-gradient(90deg, ${stripeL.glow} 0%, #0f172a 28%, #0f172a 72%, ${stripeV.glow} 100%)`
          : 'rgba(15,23,42,0.45)',
      }}
    >
      <div className="px-4 py-4">
        {/* Equipos + marcador */}
        <div className="grid items-center gap-2"
             style={{ gridTemplateColumns: '1fr auto 1fr' }}>

          {/* Local */}
          <div className="flex flex-col sm:flex-row items-center sm:justify-end gap-2 sm:gap-3 min-w-0">
            <span className="hidden sm:block text-sm font-semibold text-white text-right leading-tight
                             line-clamp-2 group-hover:text-slate-200 transition-colors">
              {local}
            </span>
            <Escudo nombre={local} escudo_url={partido.local?.escudo_url} size="lg" />
            <span className="sm:hidden text-[11px] font-semibold text-white text-center leading-tight
                             line-clamp-2 w-[72px]">
              {local}
            </span>
          </div>

          {/* Marcador */}
          <div className="flex flex-col items-center px-3 sm:px-5 shrink-0">
            {finalizado ? (
              <>
                <div className="flex items-center gap-1.5">
                  <span className="text-3xl sm:text-4xl font-black tabular-nums text-white leading-none">
                    {partido.goles_local}
                  </span>
                  <span className="text-xl font-black text-slate-700 leading-none">–</span>
                  <span className="text-3xl sm:text-4xl font-black tabular-nums text-white leading-none">
                    {partido.goles_visitante}
                  </span>
                </div>
                <span className="mt-1.5 text-[9px] font-bold uppercase tracking-widest
                                 text-slate-500 bg-slate-800/80 px-2.5 py-0.5 rounded-full">
                  Final
                </span>
              </>
            ) : (
              <>
                <span className="text-2xl font-black text-slate-600 leading-none">vs</span>
                {hora && (
                  <span className="mt-1 text-sm font-bold" style={{ color: '#00E5FF' }}>
                    {hora}
                  </span>
                )}
              </>
            )}
          </div>

          {/* Visitante */}
          <div className="flex flex-col sm:flex-row items-center sm:justify-start gap-2 sm:gap-3 min-w-0">
            <Escudo nombre={visitante} escudo_url={partido.visitante?.escudo_url} size="lg" />
            <span className="hidden sm:block text-sm font-semibold text-white text-left leading-tight
                             line-clamp-2 group-hover:text-slate-200 transition-colors">
              {visitante}
            </span>
            <span className="sm:hidden text-[11px] font-semibold text-white text-center leading-tight
                             line-clamp-2 w-[72px]">
              {visitante}
            </span>
          </div>
        </div>

        {/* Fecha */}
        {dia && (
          <div className="flex items-center justify-center gap-2 mt-3 pt-2.5 border-t border-slate-800/50">
            <span className={`text-[11px] font-medium capitalize ${finalizado ? 'text-slate-500' : 'text-slate-400'}`}>
              {dia}
            </span>
            {!finalizado && hora && (
              <>
                <span className="text-slate-700 text-xs">·</span>
                <span className="text-[11px] font-bold" style={{ color: '#00E5FF' }}>{hora}</span>
              </>
            )}
          </div>
        )}
      </div>
    </button>
  )
}

// ─── Página ───────────────────────────────────────────────────────────────────

export default function Partidos() {
  const { ligaId, ligaActual } = useLiga()
  const [jornada,   setJornada]   = useState(null)
  const [partidos,  setPartidos]  = useState([])
  const [loading,   setLoading]   = useState(true)
  const [cambiando, setCambiando] = useState(false)
  const [error,     setError]     = useState(null)
  const [modalId,   setModalId]   = useState(null)

  // Fase 1: jornada más reciente con resultado (sin filtrar por estado — cada liga usa un valor distinto)
  useEffect(() => {
    setJornada(null)
    setPartidos([])
    setLoading(true)
    getPartidos(null, { liga_id: ligaId })
      .then(res => {
        const lista = (res.partidos || []).filter(p => p.goles_local != null)
        const maxJ  = lista.length > 0 ? Math.max(...lista.map(p => p.jornada)) : 1
        setJornada(maxJ)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [ligaId])

  // Fase 2: cargar la jornada seleccionada
  useEffect(() => {
    if (jornada === null) return
    setCambiando(true)
    getPartidos(jornada, { liga_id: ligaId })
      .then(res => { setPartidos(res.partidos || []); setError(null) })
      .catch(e => setError(e.message))
      .finally(() => { setLoading(false); setCambiando(false) })
  }, [jornada, ligaId])

  const cerrarModal = useCallback(() => setModalId(null), [])

  const totalJornadas = ligaId === 28 ? 8 : ligaId === 29 ? 16 : ligaId === 33 ? 42 : TOTAL_JORNADAS
  const totalGoles    = partidos.reduce((s, p) => s + (p.goles_local ?? 0) + (p.goles_visitante ?? 0), 0)
  const ocupado       = loading || cambiando

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Fondo decorativo */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute top-1/3 -right-32 w-[500px] h-[500px] bg-blue-700/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-1/3 w-[400px] h-[400px] bg-violet-600/4 rounded-full blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{ backgroundImage: 'linear-gradient(rgba(34,211,238,0.4) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,0.4) 1px,transparent 1px)', backgroundSize: '48px 48px' }}
        />
      </div>

      <div className="relative px-4 py-8">

        {/* Lateral izquierdo decorativo */}
        <div className="hidden lg:flex flex-col items-center gap-6 fixed left-6 top-1/2 -translate-y-1/2 pointer-events-none select-none">
          <div className="w-px h-24 bg-gradient-to-b from-transparent via-cyan-500/30 to-transparent" />
          <div className="flex flex-col gap-2 items-center">
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-500/40" />
            <div className="w-1 h-1 rounded-full bg-slate-600/60" />
            <div className="w-1 h-1 rounded-full bg-slate-600/60" />
          </div>
          <span className="text-[10px] font-black tracking-[0.3em] text-slate-700 uppercase"
                style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
            Temporada 25/26
          </span>
          <div className="flex flex-col gap-2 items-center">
            <div className="w-1 h-1 rounded-full bg-slate-600/60" />
            <div className="w-1 h-1 rounded-full bg-slate-600/60" />
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-500/40" />
          </div>
          <div className="w-px h-24 bg-gradient-to-b from-transparent via-cyan-500/30 to-transparent" />
        </div>

        {/* Lateral derecho decorativo */}
        <div className="hidden lg:flex flex-col items-center gap-6 fixed right-6 top-1/2 -translate-y-1/2 pointer-events-none select-none">
          <div className="w-px h-24 bg-gradient-to-b from-transparent via-violet-500/30 to-transparent" />
          <div className="flex flex-col gap-2 items-center">
            <div className="w-1.5 h-1.5 rounded-full bg-violet-500/40" />
            <div className="w-1 h-1 rounded-full bg-slate-600/60" />
            <div className="w-1 h-1 rounded-full bg-slate-600/60" />
          </div>
          <span className="text-[10px] font-black tracking-[0.3em] text-slate-700 uppercase"
                style={{ writingMode: 'vertical-rl' }}>
            {ligaActual?.nombre ?? 'Liga'}
          </span>
          <div className="flex flex-col gap-2 items-center">
            <div className="w-1 h-1 rounded-full bg-slate-600/60" />
            <div className="w-1 h-1 rounded-full bg-slate-600/60" />
            <div className="w-1.5 h-1.5 rounded-full bg-violet-500/40" />
          </div>
          <div className="w-px h-24 bg-gradient-to-b from-transparent via-violet-500/30 to-transparent" />
        </div>

      <div className="max-w-2xl mx-auto">

        {/* Cabecera */}
        <div className="mb-6">
          <h1 className="text-2xl font-black tracking-tight">Partidos</h1>
          <p className="text-slate-500 text-sm mt-1">Temporada 2025/26 · {ligaActual.nombre}</p>
        </div>

        {/* ── Sección: Fase de Liga ── */}
        {ligaId === 28 && (
          <div className="flex items-center gap-3 mb-5">
            <h2 className="text-lg font-black text-white tracking-tight whitespace-nowrap">Fase de Liga</h2>
            <div className="flex-1 h-px bg-slate-800" />
            <span className="text-[11px] text-slate-600 whitespace-nowrap">Jornadas 1–8</span>
          </div>
        )}

        {/* Selector de jornada */}
        <div className="flex items-center gap-2 sm:gap-3 mb-5">
          <button
            onClick={() => setJornada(j => Math.max(1, j - 1))}
            disabled={ocupado || !jornada || jornada <= 1}
            className="w-11 h-11 rounded-xl border border-slate-700 text-slate-300
                       hover:border-cyan-500/60 hover:text-cyan-400 hover:bg-cyan-400/5
                       active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed
                       transition-all duration-150 flex items-center justify-center
                       font-bold text-xl shrink-0"
          >‹</button>

          <div className="flex-1 flex justify-center">
            <div className="relative">
              <select
                value={jornada ?? ''}
                onChange={e => setJornada(Number(e.target.value))}
                disabled={ocupado}
                className="appearance-none bg-slate-900 border border-slate-700 text-white
                           text-sm font-bold rounded-xl pl-5 pr-9 py-2.5
                           focus:outline-none focus:border-cyan-500/60
                           cursor-pointer disabled:opacity-50 text-center"
              >
                {jornada === null && <option value="">Cargando…</option>}
                {Array.from({ length: totalJornadas }, (_, i) => i + 1).map(j => (
                  <option key={j} value={j}>Jornada {j}</option>
                ))}
              </select>
              <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2
                              text-slate-500 text-[10px]">▼</div>
            </div>
          </div>

          <button
            onClick={() => setJornada(j => Math.min(totalJornadas, j + 1))}
            disabled={ocupado || !jornada || jornada >= totalJornadas}
            className="w-11 h-11 rounded-xl border border-slate-700 text-slate-300
                       hover:border-cyan-500/60 hover:text-cyan-400 hover:bg-cyan-400/5
                       active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed
                       transition-all duration-150 flex items-center justify-center
                       font-bold text-xl shrink-0"
          >›</button>
        </div>

        {/* Header de jornada */}
        {!loading && !error && jornada && (
          <div className="flex items-center justify-between bg-slate-900/70 border border-slate-800
                          rounded-2xl px-4 py-3.5 mb-4">
            <div className="flex items-center gap-3">
              <span className="text-3xl leading-none">{ligaActual.emoji}</span>
              <div>
                <p className="text-sm font-bold text-white leading-tight">{ligaActual.nombre}</p>
                <p className="text-[11px] text-slate-500 mt-0.5">Temporada 2025/26</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-4xl font-black tabular-nums leading-none" style={{ color: '#00E5FF' }}>
                {jornada}
              </p>
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mt-0.5">
                Jornada
              </p>
            </div>
          </div>
        )}

        {/* Stat cards */}
        {!loading && !error && jornada && (
          <div className="grid grid-cols-3 gap-3 mb-6">
            <StatCard icon="🏟️" label="Partidos" value={partidos.length} />
            <StatCard icon="⚽" label="Goles"    value={totalGoles} />
            <StatCard icon="📅" label="Jornada"  value={`${jornada}/${totalJornadas}`} />
          </div>
        )}

        {/* Spinner */}
        {ocupado && (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-2 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin" />
          </div>
        )}

        {/* Error */}
        {error && !ocupado && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm text-center">
            Error al cargar partidos: {error}
          </div>
        )}

        {/* Lista */}
        {!ocupado && !error && (
          <div className="space-y-3">
            {partidos.length === 0
              ? <p className="text-slate-500 text-center py-12">Sin partidos en esta jornada.</p>
              : partidos
                  .slice()
                  .sort((a, b) => (a.fecha || '').localeCompare(b.fecha || ''))
                  .map(p => <PartidoCard key={p.id} partido={p} onClick={setModalId} />)
            }
          </div>
        )}

        {/* ── Sección: Eliminatorias (solo Champions) ── */}
        {ligaId === 28 && (
          <>
            <div className="flex items-center gap-3 mt-10 mb-6">
              <h2 className="text-lg font-black text-white tracking-tight whitespace-nowrap">Eliminatorias</h2>
              <div className="flex-1 h-px bg-slate-800" />
              <span className="text-[10px] font-bold px-2.5 py-1 rounded-full
                               bg-cyan-400/8 text-cyan-400/70 border border-cyan-400/15">
                UCL 25/26
              </span>
            </div>
            <UCLEliminatorias ligaId={ligaId} />
          </>
        )}

      </div>

      {/* Modal */}
      {modalId !== null && <PartidoModal partidoId={modalId} onClose={cerrarModal} ligaId={ligaId} />}
    </div>
    </div>
  )
}
