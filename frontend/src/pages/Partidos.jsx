import { useState, useEffect, useCallback } from 'react'
import { getPartidos, getPartidoDetalle, getPartidosPorEquipo } from '../services/api'

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
    .filter(p => p.estado === 'finalizado' && p.goles_local != null && p.goles_visitante != null)
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
  const sz = size === 'lg' ? 'w-16 h-16' : 'w-14 h-14'
  const tx = size === 'lg' ? 'text-base'  : 'text-sm'
  const showImg = escudo_url && !errored
  return (
    <div className={`relative ${sz} rounded-xl bg-gradient-to-br ${teamGradient(nombre)}
                    border border-white/10 flex items-center justify-center shrink-0 overflow-hidden`}>
      {!showImg && (
        <span className={`${tx} font-black text-white tracking-tight`}>{initials(nombre)}</span>
      )}
      {showImg && (
        <img src={escudo_url} alt={nombre} referrerPolicy="no-referrer"
             className="absolute inset-0 w-full h-full object-contain p-1.5"
             onError={() => setErrored(true)} />
      )}
    </div>
  )
}

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3.5 text-center">
      <p className="text-2xl font-black text-white tabular-nums leading-none">{value}</p>
      <p className="text-xs text-slate-500 mt-1">{label}</p>
      {sub && <p className="text-[10px] text-slate-600 mt-0.5">{sub}</p>}
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

function PartidoModal({ partidoId, onClose }) {
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
          getPartidosPorEquipo(lidId),
          getPartidosPorEquipo(vidId),
        ])
        if (cancelled) return
        setPartLoc(rL.partidos || [])
        setPartVis(rV.partidos || [])
      })
      .catch(e => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setCargando(false) })

    return () => { cancelled = true }
  }, [partidoId])

  useEffect(() => {
    const fn = e => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', fn)
    return () => document.removeEventListener('keydown', fn)
  }, [onClose])

  const local       = detalle?.local?.nombre     || '—'
  const visitante   = detalle?.visitante?.nombre || '—'
  const localId     = detalle?.local?.id     || detalle?.equipo_local
  const visitanteId = detalle?.visitante?.id || detalle?.equipo_visitante
  const finalizado  = detalle?.estado === 'finalizado'
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
            {detalle ? `Jornada ${detalle.jornada} · LaLiga 2025/26` : 'Cargando…'}
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

function PartidoCard({ partido, onClick }) {
  const local      = partido.local?.nombre     || '—'
  const visitante  = partido.visitante?.nombre || '—'
  const finalizado = partido.estado === 'finalizado'

  return (
    <button
      onClick={() => onClick(partido.id)}
      className="w-full text-left rounded-2xl border border-slate-800 bg-slate-900
                 transition-all duration-200 overflow-hidden cursor-pointer group
                 hover:border-cyan-500/40 hover:bg-slate-800/60 hover:scale-[1.005]"
    >
      <div className="p-4 sm:p-5">
        <div className="flex items-center gap-3 sm:gap-4">

          {/* Local */}
          <div className="flex-1 flex items-center gap-2 sm:gap-3 justify-end">
            <span className="text-sm font-semibold text-white text-right leading-tight hidden sm:block
                             group-hover:text-cyan-400 transition-colors">
              {local}
            </span>
            <span className="text-xs font-bold text-white sm:hidden">{initials(local)}</span>
            <Escudo nombre={local} escudo_url={partido.local?.escudo_url} />
          </div>

          {/* Marcador */}
          <div className="flex flex-col items-center shrink-0 min-w-[64px]">
            {finalizado ? (
              <div className="flex items-center gap-1.5">
                <span className="text-2xl font-black tabular-nums text-white">{partido.goles_local}</span>
                <span className="text-lg font-bold text-slate-600">–</span>
                <span className="text-2xl font-black tabular-nums text-white">{partido.goles_visitante}</span>
              </div>
            ) : (
              <span className="text-lg font-black text-slate-500">vs</span>
            )}
            <span className={`text-[10px] font-medium mt-0.5 px-2 py-0.5 rounded-full ${
              finalizado ? 'text-slate-500 bg-slate-800' : 'text-amber-400 bg-amber-400/10'
            }`}>
              {finalizado ? 'FIN' : 'PENDIENTE'}
            </span>
          </div>

          {/* Visitante */}
          <div className="flex-1 flex items-center gap-2 sm:gap-3">
            <Escudo nombre={visitante} escudo_url={partido.visitante?.escudo_url} />
            <span className="text-sm font-semibold text-white leading-tight hidden sm:block
                             group-hover:text-cyan-400 transition-colors">
              {visitante}
            </span>
            <span className="text-xs font-bold text-white sm:hidden">{initials(visitante)}</span>
          </div>

          {/* Chevron */}
          <div className="shrink-0 ml-1">
            <svg className="w-4 h-4 text-slate-600 group-hover:text-cyan-400 transition-colors"
                 fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>

        <div className="flex justify-center mt-2">
          <span className="text-[11px] text-slate-600 capitalize">{formatFechaCorta(partido.fecha)}</span>
        </div>
      </div>
    </button>
  )
}

// ─── Página ───────────────────────────────────────────────────────────────────

export default function Partidos() {
  const [jornada,   setJornada]   = useState(null)
  const [partidos,  setPartidos]  = useState([])
  const [loading,   setLoading]   = useState(true)
  const [cambiando, setCambiando] = useState(false)
  const [error,     setError]     = useState(null)
  const [modalId,   setModalId]   = useState(null)

  // Fase 1: jornada más reciente con 'finalizado'
  useEffect(() => {
    getPartidos(null, { estado: 'finalizado' })
      .then(res => {
        const lista = res.partidos || []
        const maxJ  = lista.length > 0 ? Math.max(...lista.map(p => p.jornada)) : 1
        setJornada(maxJ)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  // Fase 2: cargar la jornada seleccionada
  useEffect(() => {
    if (jornada === null) return
    setCambiando(true)
    getPartidos(jornada)
      .then(res => { setPartidos(res.partidos || []); setError(null) })
      .catch(e => setError(e.message))
      .finally(() => { setLoading(false); setCambiando(false) })
  }, [jornada])

  const cerrarModal = useCallback(() => setModalId(null), [])

  const totalGoles = partidos.reduce((s, p) => s + (p.goles_local ?? 0) + (p.goles_visitante ?? 0), 0)
  const ocupado    = loading || cambiando

  return (
    <div className="min-h-screen bg-[#080C10] text-white px-4 py-8">
      <div className="max-w-2xl mx-auto">

        {/* Cabecera */}
        <div className="mb-6">
          <h1 className="text-2xl font-black tracking-tight">Partidos</h1>
          <p className="text-slate-500 text-sm mt-1">Temporada 2025/26 · LaLiga</p>
        </div>

        {/* Selector de jornada */}
        <div className="flex items-center gap-3 mb-5">
          <button
            onClick={() => setJornada(j => Math.max(1, j - 1))}
            disabled={ocupado || !jornada || jornada <= 1}
            className="w-9 h-9 rounded-lg border border-slate-700 text-slate-400
                       hover:border-cyan-500/50 hover:text-cyan-400
                       disabled:opacity-30 disabled:cursor-not-allowed
                       transition-colors flex items-center justify-center font-bold text-lg"
          >‹</button>

          <div className="flex-1 flex justify-center">
            <select
              value={jornada ?? ''}
              onChange={e => setJornada(Number(e.target.value))}
              disabled={ocupado}
              className="bg-slate-900 border border-slate-700 text-white text-sm font-semibold
                         rounded-lg px-4 py-2 focus:outline-none focus:border-cyan-500/50
                         cursor-pointer disabled:opacity-50"
            >
              {jornada === null && <option value="">Cargando…</option>}
              {Array.from({ length: TOTAL_JORNADAS }, (_, i) => i + 1).map(j => (
                <option key={j} value={j}>Jornada {j}</option>
              ))}
            </select>
          </div>

          <button
            onClick={() => setJornada(j => Math.min(TOTAL_JORNADAS, j + 1))}
            disabled={ocupado || !jornada || jornada >= TOTAL_JORNADAS}
            className="w-9 h-9 rounded-lg border border-slate-700 text-slate-400
                       hover:border-cyan-500/50 hover:text-cyan-400
                       disabled:opacity-30 disabled:cursor-not-allowed
                       transition-colors flex items-center justify-center font-bold text-lg"
          >›</button>
        </div>

        {/* Stat cards */}
        {!loading && !error && jornada && (
          <div className="grid grid-cols-3 gap-3 mb-6">
            <StatCard label="Partidos" value={partidos.length} />
            <StatCard label="Goles"    value={totalGoles} />
            <StatCard label="Jornada"  value={`${jornada} / ${TOTAL_JORNADAS}`} />
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

      </div>

      {/* Modal */}
      {modalId !== null && <PartidoModal partidoId={modalId} onClose={cerrarModal} />}
    </div>
  )
}
