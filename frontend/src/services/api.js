const BASE_URL = 'http://localhost:8080'

async function apiFetch(path) {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json()
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
    posicion:      POS_MAP[raw.posicion] || raw.posicion || '',
    edad:          raw.edad   || 0,
    nacionalidad:  raw.nacionalidad || '',
    foto_url:      raw.foto_url     || null,
    valor_mercado: raw.valor_mercado ?? null,
    metricas: {
      goles,
      asistencias,
      xG:                stats.xg  || 0,
      xA:                stats.xa  || 0,
      pases_completados: stats.pases_completados || 0,
      regates:           stats.regates           || 0,
      recuperaciones:    stats.recuperaciones    || 0,
      minutos_jugados:   minutos,
      goles_por_90:      stats.goles_por_90        ?? p90(goles, minutos),
      asistencias_por_90:stats.asistencias_por_90  ?? p90(asistencias, minutos),
      ga_por_90:         stats.ga_por_90           ?? p90(goles + asistencias, minutos),
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
    posicion:      POS_MAP[j.posicion] || j.posicion || '',
    edad:          j.edad   || 0,
    valor_mercado: j.valor_mercado ?? null,
    metricas: {
      goles,
      asistencias,
      xG:                r.xg  || 0,
      xA:                r.xa  || 0,
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
    orden:     filtros.orden     || 'goles',
    orden_dir: filtros.orden_dir || 'desc',
  })
  if (filtros.liga_id)           params.set('liga_id', filtros.liga_id)
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
  return apiFetch(`/equipos?liga_id=${liga_id}`)
}

/** Partidos, opcionalmente filtrados por jornada. */
export async function getPartidos(jornada) {
  const params = new URLSearchParams({ liga_id: 1, temporada: '2526' })
  if (jornada != null) params.set('jornada', jornada)
  return apiFetch(`/partidos?${params}`)
}
