"""
Sofascore Scraper — Partidos en tiempo real para LaLiga

Fuente: API pública de Sofascore (sin autenticación requerida)
        https://api.sofascore.com/api/v1/...

Endpoints usados:
  /sport/football/scheduled-events/{date}  → partidos del día
  /event/{id}                              → detalle de un partido
  /event/{id}/incidents                    → goles, tarjetas, subs

IDs fijos:
  LaLiga uniqueTournament id = 8

Estrategia de actualización:
  - upsert por sofascore_id (columna añadida a la tabla partidos)
  - idempotente: se puede llamar cada 30s sin duplicados
  - los equipos se resuelven contra nuestra tabla 'equipos' por nombre normalizado

Uso:
  python sofascore_scraper.py               # partidos de hoy
  python sofascore_scraper.py 2026-04-20    # fecha concreta
"""

import sys
import logging
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

LALIGA_TOURNAMENT_ID = 8
DB_LIGA_ID           = 1
DB_TEMPORADA         = "2526"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":  "application/json",
    "Referer": "https://www.sofascore.com/",
}

API = "https://api.sofascore.com/api/v1"

# Mapa tipo incidente Sofascore → tipo interno
TIPO_MAP = {
    "goal":         "gol",
    "card":         "tarjeta",
    "substitution": "sustitucion",
    "varDecision":  "var",
    "injuryTime":   "tiempo_anadido",
    "period":       "periodo",
}

# Mapa código de estado Sofascore → estado interno
ESTADO_MAP = {
    "notstarted":   "programado",
    "inprogress":   "en_directo",
    "finished":     "finalizado",
    "postponed":    "aplazado",
    "canceled":     "aplazado",
    "interrupted":  "aplazado",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Sin acentos, minúsculas, espacios colapsados."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def _get(endpoint: str) -> Optional[dict]:
    url = f"{API}/{endpoint.lstrip('/')}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        log.warning("Error en %s: %s", endpoint, e)
        return None


def _ts_to_iso(ts: Optional[int]) -> Optional[str]:
    """Unix timestamp → ISO 8601 UTC."""
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Cache de equipos: nombre_norm → equipo_id en Supabase
# ---------------------------------------------------------------------------

_equipo_cache: dict[str, int] = {}


def _load_equipo_cache():
    global _equipo_cache
    if _equipo_cache:
        return
    res = (
        supabase.table("equipos")
        .select("id, nombre")
        .eq("liga_id", DB_LIGA_ID)
        .eq("temporada", DB_TEMPORADA)
        .execute()
    )
    _equipo_cache = {_norm(r["nombre"]): r["id"] for r in res.data}
    log.info("Cache equipos: %d entradas.", len(_equipo_cache))


def _resolve_equipo(nombre_sofascore: str) -> Optional[int]:
    """Busca el equipo_id por nombre normalizado. Fallback: primera palabra."""
    _load_equipo_cache()
    n = _norm(nombre_sofascore)
    if n in _equipo_cache:
        return _equipo_cache[n]
    # fallback: primera palabra significativa (ej. "Athletic" → "Athletic Club")
    primera = n.split()[0] if n else ""
    for key, eid in _equipo_cache.items():
        if primera and key.startswith(primera):
            return eid
    log.debug("Equipo no encontrado en cache: '%s'", nombre_sofascore)
    return None


# ---------------------------------------------------------------------------
# 1. Partidos del día
# ---------------------------------------------------------------------------

def get_day_matches(fecha: str) -> list[dict]:
    """
    Devuelve todos los partidos de LaLiga para una fecha dada (YYYY-MM-DD).
    Filtra por uniqueTournament.id == LALIGA_TOURNAMENT_ID.
    """
    data = _get(f"sport/football/scheduled-events/{fecha}")
    if not data:
        return []
    events = data.get("events", [])
    laliga = [
        e for e in events
        if e.get("tournament", {}).get("uniqueTournament", {}).get("id") == LALIGA_TOURNAMENT_ID
    ]
    log.info("Partidos LaLiga el %s: %d", fecha, len(laliga))
    return laliga


def parse_match(raw: dict) -> dict:
    """Normaliza un evento de Sofascore al formato de nuestro schema."""
    status     = raw.get("status", {})
    home       = raw.get("homeTeam", {})
    away       = raw.get("awayTeam", {})
    home_score = raw.get("homeScore", {})
    away_score = raw.get("awayScore", {})
    round_info = raw.get("roundInfo", {})

    estado_type = status.get("type", "notstarted")
    estado = ESTADO_MAP.get(estado_type, "programado")

    # Goles: usar 'current' durante el partido, 'normaltime' al finalizar
    goles_local = home_score.get("normaltime") if estado == "finalizado" else home_score.get("current")
    goles_visit = away_score.get("normaltime") if estado == "finalizado" else away_score.get("current")

    return {
        "sofascore_id":              raw.get("id"),
        "liga_id":                   DB_LIGA_ID,
        "temporada":                 DB_TEMPORADA,
        "jornada":                   round_info.get("round"),
        "fecha":                     _ts_to_iso(raw.get("startTimestamp")),
        "equipo_local":              _resolve_equipo(home.get("name", "")),
        "equipo_visitante":          _resolve_equipo(away.get("name", "")),
        "equipo_local_nombre":       home.get("name"),
        "equipo_visitante_nombre":   away.get("name"),
        "goles_local":               goles_local,
        "goles_visitante":           goles_visit,
        "xg_local":                  None,   # Sofascore no expone xG en este endpoint
        "xg_visitante":              None,
        "estado":                    estado,
    }


# ---------------------------------------------------------------------------
# 2. Eventos de un partido (incidentes)
# ---------------------------------------------------------------------------

def get_match_events(sofascore_id: int) -> list[dict]:
    """
    Goles, tarjetas, sustituciones y eventos VAR de un partido.

    Endpoint: GET /event/{id}/incidents

    Returns:
        Lista de dicts con estructura normalizada:
        {
          minuto, minuto_extra, tipo, equipo_local (bool),
          jugador, texto, detalle
        }
    """
    data = _get(f"event/{sofascore_id}/incidents")
    if not data:
        return []

    incidents = data.get("incidents", [])
    eventos = []

    for inc in incidents:
        tipo_raw  = inc.get("incidentType", "")
        tipo      = TIPO_MAP.get(tipo_raw, tipo_raw)

        if tipo in ("periodo", "tiempo_anadido"):
            continue    # no son eventos de juego relevantes

        jugador_data = inc.get("player") or inc.get("playerIn") or {}

        evento = {
            "minuto":         inc.get("time"),
            "minuto_extra":   inc.get("addedTime"),
            "tipo":           tipo,
            "es_local":       inc.get("isHome"),
            "jugador":        jugador_data.get("name"),
            "jugador_id_ss":  jugador_data.get("id"),
            "texto":          inc.get("text", ""),
            "detalle":        _parse_detalle(tipo_raw, inc),
        }

        # Para sustituciones, añadir jugador que sale
        if tipo_raw == "substitution":
            jugador_sale = inc.get("playerOut", {})
            evento["jugador_sale"] = jugador_sale.get("name")

        eventos.append(evento)

    log.info("  Eventos cargados: %d", len(eventos))
    return eventos


def _parse_detalle(tipo_raw: str, inc: dict) -> str:
    """Genera texto descriptivo según el tipo de incidente."""
    if tipo_raw == "goal":
        if inc.get("goalType") == "penalty":
            return "penalti"
        if inc.get("goalType") == "own":
            return "propia_puerta"
        return "gol"
    if tipo_raw == "card":
        color = inc.get("incidentClass", "")
        return "roja" if "red" in color.lower() else "amarilla"
    if tipo_raw == "varDecision":
        return inc.get("incidentClass", "var")
    if tipo_raw == "substitution":
        jugador_entra = (inc.get("playerIn") or {}).get("name", "")
        jugador_sale  = (inc.get("playerOut") or {}).get("name", "")
        return f"{jugador_entra} por {jugador_sale}"
    return ""


# ---------------------------------------------------------------------------
# 3. Guardar partidos en Supabase
# ---------------------------------------------------------------------------

def save_matches(matches: list[dict]) -> int:
    """
    Upsert de partidos en la tabla 'partidos' por sofascore_id.
    Idempotente: se puede llamar repetidamente sin duplicados.
    Solo guarda los campos del schema (excluye campos auxiliares _nombre).
    """
    if not matches:
        return 0

    rows = []
    for m in matches:
        rows.append({
            "sofascore_id":    m["sofascore_id"],
            "liga_id":         m["liga_id"],
            "temporada":       m["temporada"],
            "jornada":         m["jornada"],
            "fecha":           m["fecha"],
            "equipo_local":    m["equipo_local"],
            "equipo_visitante": m["equipo_visitante"],
            "goles_local":     m["goles_local"],
            "goles_visitante": m["goles_visitante"],
            "xg_local":        m["xg_local"],
            "xg_visitante":    m["xg_visitante"],
            "estado":          m["estado"],
        })

    res = (
        supabase.table("partidos")
        .upsert(rows, on_conflict="sofascore_id")
        .execute()
    )
    return len(res.data)


# ---------------------------------------------------------------------------
# 4. Orquestador principal
# ---------------------------------------------------------------------------

def run(fecha: Optional[str] = None) -> list[dict]:
    """
    Carga partidos de LaLiga para la fecha dada (hoy por defecto),
    los guarda en Supabase y devuelve la lista con eventos incluidos.
    """
    if not fecha:
        fecha = date.today().isoformat()

    log.info("=" * 52)
    log.info(" Sofascore Scraper -- LaLiga %s", fecha)
    log.info("=" * 52)

    _load_equipo_cache()

    raw_matches = get_day_matches(fecha)
    if not raw_matches:
        log.info("Sin partidos de LaLiga para %s.", fecha)
        return []

    matches = [parse_match(r) for r in raw_matches]

    # Guardar en Supabase
    n_saved = save_matches(matches)
    log.info("Partidos guardados/actualizados: %d", n_saved)

    # Enriquecer con eventos (solo partidos en directo o finalizados)
    for match in matches:
        estado = match["estado"]
        if estado in ("en_directo", "finalizado"):
            match["eventos"] = get_match_events(match["sofascore_id"])
        else:
            match["eventos"] = []

    return matches


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def _print_match(m: dict):
    local   = m.get("equipo_local_nombre", "?")
    visit   = m.get("equipo_visitante_nombre", "?")
    gl      = m.get("goles_local")
    gv      = m.get("goles_visitante")
    estado  = m.get("estado", "?")
    jornada = m.get("jornada", "?")
    fecha   = m.get("fecha", "")[:16] if m.get("fecha") else "?"

    marcador = f"{gl}-{gv}" if gl is not None else "vs"
    log.info("  J%s | %s | %s %s %s [%s]",
             jornada, fecha, local, marcador, visit, estado)

    for ev in m.get("eventos", []):
        jugador  = ev.get("jugador") or ""
        detalle  = ev.get("detalle") or ev.get("texto") or ""
        minuto   = ev.get("minuto", "?")
        extra    = f"+{ev['minuto_extra']}" if ev.get("minuto_extra") else ""
        lado     = "LOCAL" if ev.get("es_local") else "VISIT"
        log.info("    %s%s' [%s] %s — %s — %s",
                 minuto, extra, lado, ev.get("tipo", ""), jugador, detalle)


if __name__ == "__main__":
    fecha_arg = sys.argv[1] if len(sys.argv) > 1 else None
    partidos  = run(fecha_arg)

    log.info("")
    log.info("=" * 52)
    log.info(" RESUMEN")
    log.info("=" * 52)
    for m in partidos:
        _print_match(m)
