const BASE_URL = 'http://localhost:8001'

async function apiFetch(path, timeoutMs = 8000) {
  const ctrl = new AbortController()
  const tid  = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(`${BASE_URL}${path}`, { signal: ctrl.signal })
    if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
    return res.json()
  } finally {
    clearTimeout(tid)
  }
}

// ─── Mapeo de posición FBref → español ───────────────────────────────────────
const POS_MAP = {
  'FW':    'Delantero',
  'FW,MF': 'Extremo',
  'MF,FW': 'Mediapunta',
  'MF':    'Centrocampista',
  'MF,DF': 'Centrocampista',
  'DF,MF': 'Defensa Central',
  'DF':    'Defensa Central',
  'GK':    'Portero',
}

// La API usa xg/xa (minúsculas); el frontend usa xG/xA (mayúsculas)
const METRIC_KEY_TO_API = { xG: 'xg', xA: 'xa', ga_por_90: 'ga_por_90' }
const METRIC_KEY_FROM_API = { xg: 'xG', xa: 'xA' }

function p90(v, min) {
  return min > 0 ? +((v / min) * 90).toFixed(2) : 0
}

// ─── Adapta un jugador de la API al shape que espera el frontend ──────────────
function adaptarJugador(raw) {
  const stats = raw.stats || {}
  const minutos = stats.minutos || 0
  const goles = stats.goles || 0
  const asistencias = stats.asistencias || 0

  return {
    id:            raw.id,
    nombre:        raw.nombre,
    equipo:        (raw.equipos || {}).nombre || '',
    posicion:      POS_MAP[raw.posicion] || raw.posicion || null,
    edad:          raw.edad   ?? null,
    nacionalidad:  raw.nacionalidad || '',
    foto_url:      raw.foto_url     || null,
    valor_mercado: raw.valor_mercado ?? null,
    metricas: {
      goles,
      asistencias,
      xG:                stats.xg  ?? null,
      xA:                stats.xa  ?? null,
      pases_completados: stats.pases_completados || 0,
      regates:           stats.regates           || 0,
      recuperaciones:    stats.recuperaciones    || 0,
      minutos_jugados:   minutos,
      goles_por_90:      stats.goles_por_90        ?? p90(goles, minutos),
      asistencias_por_90:stats.asistencias_por_90  ?? p90(asistencias, minutos),
      ga_por_90:         stats.ga_por_90           ?? p90(goles + asistencias, minutos),
      portero_paradas:         stats.portero_paradas         ?? null,
      portero_goles_encajados: stats.portero_goles_encajados ?? null,
      portero_paradas_pct:     stats.portero_paradas_pct     ?? null,
    },
  }
}

// ─── Adapta un item del ranking al shape de jugador ───────────────────────────
function adaptarRankingItem(r, metricaFrontend) {
  const j = r.jugadores || {}
  const goles = r.goles || 0
  const asistencias = r.asistencias || 0
  const minutos = r.minutos || 0

  return {
    id:            j.id,
    nombre:        j.nombre || '',
    equipo:        (j.equipos || {}).nombre || '',
    posicion:      POS_MAP[j.posicion] || j.posicion || null,
    edad:          j.edad   ?? null,
    valor_mercado: j.valor_mercado ?? null,
    metricas: {
      goles,
      asistencias,
      xG:                r.xg  ?? null,
      xA:                r.xa  ?? null,
      pases_completados: r.pases_completados || 0,
      regates:           r.regates           || 0,
      recuperaciones:    r.recuperaciones    || 0,
      minutos_jugados:   minutos,
      goles_por_90:      r.goles_por_90        ?? p90(goles, minutos),
      asistencias_por_90:r.asistencias_por_90  ?? p90(asistencias, minutos),
      ga_por_90:         r.ga_por_90           ?? p90(goles + asistencias, minutos),
      // valor_mercado también en metricas para que getMetricVal lo encuentre
      valor_mercado:     j.valor_mercado ?? 0,
      // la métrica ordenada al nivel raíz por si tiene clave distinta
      [metricaFrontend]: r[METRIC_KEY_TO_API[metricaFrontend] ?? metricaFrontend]
                         ?? r[metricaFrontend]
                         ?? 0,
    },
  }
}

// ─── API pública ──────────────────────────────────────────────────────────────

/**
 * Lista de jugadores con filtros opcionales.
 * Devuelve jugadores en el shape que espera el frontend.
 */
export async function getJugadores(filtros = {}) {
  const params = new URLSearchParams({
    limit:     600,
    temporada: '2526',
    liga_id:   filtros.liga_id  || 1,
    orden:     filtros.orden     || 'goles',
    orden_dir: filtros.orden_dir || 'desc',
  })
  if (filtros.equipo_id)         params.set('equipo_id', filtros.equipo_id)
  if (filtros.min_goles != null) params.set('min_goles', filtros.min_goles)
  if (filtros.max_valor != null) params.set('max_valor_mercado', filtros.max_valor)

  const data = await apiFetch(`/jugadores?${params}`)
  return data.jugadores.map(adaptarJugador)
}

/**
 * Perfil completo de un jugador (datos crudos, para la página /jugador/:id).
 */
export async function getJugador(id) {
  return apiFetch(`/jugadores/${id}`)
}

/**
 * Top N jugadores por métrica.
 * metrica acepta los mismos keys que usa el frontend: 'goles', 'xG', 'xA', etc.
 */
export async function getRanking(metrica = 'goles', limit = 20) {
  const apiMetrica = METRIC_KEY_TO_API[metrica] ?? metrica
  const data = await apiFetch(
    `/jugadores/ranking?metrica=${apiMetrica}&limit=${limit}&temporada=2526`
  )
  return data.ranking.map(r => adaptarRankingItem(r, metrica))
}

/** Lista de equipos de una liga. */
export async function getEquipos(liga_id = 1) {
  return apiFetch(`/equipos?liga_id=${liga_id}&temporada=2526`)
}

/** Top N por métrica, filtrado por liga. */
export async function getRankingLiga(metrica = 'goles', liga_id = 1, limit = 20) {
  const apiMetrica = METRIC_KEY_TO_API[metrica] ?? metrica
  const data = await apiFetch(
    `/jugadores/ranking?metrica=${apiMetrica}&limit=${limit}&temporada=2526&liga_id=${liga_id}`
  )
  return data.ranking.map(r => adaptarRankingItem(r, metrica))
}

/** Perfil completo de un equipo (plantilla + partidos + totales). */
export async function getEquipoDetalle(equipo_id) {
  return apiFetch(`/equipos/${equipo_id}?temporada=2526`)
}

/** Detalle para la página /equipos/:id — equipo + clasificación liga + plantilla. */
export async function getEquipoDetallePagina(equipo_id) {
  return apiFetch(`/equipos/${equipo_id}/detalle?temporada=2526`)
}

/** Detalle de un partido por id. */
export async function getPartidoDetalle(id) {
  return apiFetch(`/partidos/${id}`)
}

/** Todos los partidos de un equipo en la temporada actual. */
export async function getPartidosPorEquipo(equipo_id, liga_id = 1) {
  const params = new URLSearchParams({ liga_id, temporada: '2526', equipo_id })
  return apiFetch(`/partidos?${params}`)
}

// ─── Insights ────────────────────────────────────────────────────────────────

// ─── Análisis IA de jornada ───────────────────────────────────────────────────

/** Análisis más reciente guardado para una liga. */
export async function getAnalisisJornada(liga_id = 1, temporada = '2526') {
  const data = await apiFetch(`/insights/analisis?liga_id=${liga_id}&temporada=${temporada}`)
  return data.analisis || null
}

/** Genera (o recupera del caché) el análisis de una jornada concreta. */
export async function generarAnalisis(liga_id, jornada, temporada = '2526') {
  const res = await fetch(`${BASE_URL}/insights/generar-analisis`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ liga_id, jornada, temporada }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Error ${res.status}`)
  }
  return res.json()
}

export async function getInsightsRankings(temporada = '2526', liga_id = 1) {
  return apiFetch(`/insights/rankings?temporada=${temporada}&liga_id=${liga_id}`)
}
export async function getInsightsDatosCuriosos(temporada = '2526', liga_id = 1) {
  return apiFetch(`/insights/datos-curiosos?temporada=${temporada}&liga_id=${liga_id}`)
}
export async function getInsightsQuiz(temporada = '2526', liga_id = 1) {
  return apiFetch(`/insights/quiz?temporada=${temporada}&liga_id=${liga_id}`)
}

/** Partidos, opcionalmente filtrados por jornada y/o estado. */
export async function getPartidos(jornada, { estado, liga_id = 1 } = {}) {
  const params = new URLSearchParams({ liga_id, temporada: '2526' })
  if (jornada != null) params.set('jornada', jornada)
  if (estado)          params.set('estado', estado)
  return apiFetch(`/partidos?${params}`)
}

/** Últimos partidos finalizados de una liga. */
export async function getUltimosPartidos(liga_id = 1, limit = 4) {
  const data = await apiFetch(`/partidos/recientes?liga_id=${liga_id}&limit=${limit}`)
  return data.partidos || []
}

/** Ligas disponibles desde Supabase. */
export async function getLeagues() {
  return apiFetch('/leagues')
}

/** Jugador con más goles de una liga (para la card del hero). */
export async function getTopScorer(liga_id = 1, temporada = '2526') {
  try {
    const data = await apiFetch(`/jugadores/top-scorer?liga_id=${liga_id}&temporada=${temporada}`)
    return data.jugador || null
  } catch {
    return null
  }
}

/** Total de jugadores con estadísticas en una temporada. */
export async function getConteoJugadores(temporada = '2526') {
  try {
    const data = await apiFetch(`/jugadores/count?temporada=${temporada}`)
    return data.count || 0
  } catch {
    return 0
  }
}

/** Cruces de eliminatorias agrupados por ronda (Octavos→Cuartos→Semis→Final). */
export async function getEliminatorias(liga_id = 28, temporada = '2526') {
  return apiFetch(`/partidos/eliminatorias?liga_id=${liga_id}&temporada=${temporada}`)
}

/** Total de partidos registrados en una temporada. */
export async function getConteoPartidos(temporada = '2526') {
  try {
    const data = await apiFetch(`/partidos/count?temporada=${temporada}`)
    return data.count || 0
  } catch {
    return 0
  }
}
