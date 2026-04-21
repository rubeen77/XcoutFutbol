"""
API-Football Scraper — Partidos en directo, eventos y alineaciones

Docs:   https://www.api-football.com/documentation-v3
Tier:   Free (100 req/día). Usar con criterio.
Config: API_FOOTBALL_KEY en backend/.env

IDs relevantes:
  Liga LaLiga 2025/26 → fixture_league_id=140, season=2025
  API base: https://v3.football.api-sports.io

Funciones principales:
  get_live_matches()           → partidos de LaLiga en curso ahora mismo
  get_match_events(fixture_id) → goles, tarjetas, subs minuto a minuto
  get_lineups(fixture_id)      → alineaciones titular/suplente por equipo
  save_today_matches()         → persiste partidos del día en Supabase

Uso típico:
  from scrapers.api_football import get_live_matches, save_today_matches
  save_today_matches()
"""

import os
import sys
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

API_KEY       = os.environ.get("API_FOOTBALL_KEY", "")
API_BASE      = "https://v3.football.api-sports.io"
LALIGA_ID     = 140       # ID de LaLiga en API-Football
SEASON        = 2025      # temporada vigente (año de inicio)
DB_LIGA_ID    = 1         # id de LaLiga en nuestra tabla 'ligas'
DB_TEMPORADA  = "2526"    # clave de temporada en nuestro schema

# Mapa estado API-Football → estado nuestro schema
ESTADO_MAP = {
    "NS":  "programado",   # Not Started
    "1H":  "en_directo",   # First Half
    "HT":  "en_directo",   # Half Time
    "2H":  "en_directo",   # Second Half
    "ET":  "en_directo",   # Extra Time
    "P":   "en_directo",   # Penalty
    "FT":  "finalizado",   # Full Time
    "AET": "finalizado",   # After Extra Time
    "PEN": "finalizado",   # After Penalties
    "PST": "aplazado",     # Postponed
    "CANC": "aplazado",    # Cancelled
    "ABD": "aplazado",     # Abandoned
    "AWD": "finalizado",   # Technical Win
    "WO":  "finalizado",   # WalkOver
    "LIVE": "en_directo",
}

TIPO_EVENTO_MAP = {
    "Goal":          "gol",
    "Card":          "tarjeta",
    "subst":         "sustitucion",
    "Var":           "var",
    "Missed Penalty": "penalti_fallado",
}


# ---------------------------------------------------------------------------
# Cliente HTTP base
# ---------------------------------------------------------------------------

class APIFootballClient:
    """Wrapper mínimo sobre la API v3 de API-Football."""

    def __init__(self):
        if not API_KEY or API_KEY == "tu_api_key_aqui":
            raise EnvironmentError(
                "API_FOOTBALL_KEY no configurada. "
                "Añade tu clave en backend/.env y reinicia."
            )
        self.session = requests.Session()
        self.session.headers.update({
            "x-rapidapi-host": "v3.football.api-sports.io",
            "x-rapidapi-key":  API_KEY,
        })

    def get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        try:
            r = self.session.get(url, params=params or {}, timeout=10)
            r.raise_for_status()
            data = r.json()
            errors = data.get("errors", {})
            if errors:
                log.error("API-Football error en %s: %s", endpoint, errors)
                return {}
            remaining = r.headers.get("x-ratelimit-requests-remaining", "?")
            log.debug("  [API] %s | requests restantes hoy: %s", endpoint, remaining)
            return data
        except requests.RequestException as e:
            log.error("HTTP error en %s: %s", endpoint, e)
            return {}

    def status(self) -> dict:
        """Verifica la clave y muestra cuántas requests quedan hoy."""
        data = self.get("status")
        if data:
            info = data.get("response", {})
            plan = info.get("subscription", {})
            reqs = info.get("requests", {})
            log.info(
                "API-Football OK | plan=%s | usadas=%s/%s",
                plan.get("plan", "?"),
                reqs.get("current", "?"),
                reqs.get("limit_day", "?"),
            )
        return data


# ---------------------------------------------------------------------------
# 1. Partidos en directo
# ---------------------------------------------------------------------------

def get_live_matches(client: APIFootballClient) -> list[dict]:
    """
    Devuelve todos los partidos de LaLiga que están en curso ahora mismo.

    Endpoint: GET /fixtures?live=all&league=140&season=2025
    Responde en tiempo real, actualizable cada 15 segundos.

    Returns:
        Lista de dicts con estructura normalizada:
        {
          fixture_id, jornada, fecha, estado,
          equipo_local_nombre, equipo_visitante_nombre,
          goles_local, goles_visitante,
          xg_local, xg_visitante, minuto
        }
    """
    log.info("Obteniendo partidos de LaLiga en directo...")
    data = client.get("fixtures", {"live": "all", "league": LALIGA_ID, "season": SEASON})
    fixtures = data.get("response", [])
    log.info("  %d partidos en directo.", len(fixtures))
    return [_parse_fixture(f) for f in fixtures]


def get_today_matches(client: APIFootballClient) -> list[dict]:
    """
    Partidos de LaLiga programados para hoy (en directo + por empezar).

    Endpoint: GET /fixtures?date=YYYY-MM-DD&league=140&season=2025
    """
    today = date.today().isoformat()
    log.info("Obteniendo partidos de LaLiga para hoy (%s)...", today)
    data = client.get("fixtures", {"date": today, "league": LALIGA_ID, "season": SEASON})
    fixtures = data.get("response", [])
    log.info("  %d partidos hoy.", len(fixtures))
    return [_parse_fixture(f) for f in fixtures]


def _parse_fixture(f: dict) -> dict:
    """Normaliza un fixture de la API al formato de nuestro schema."""
    fix   = f.get("fixture", {})
    teams = f.get("teams", {})
    goals = f.get("goals", {})
    score = f.get("score", {})
    league = f.get("league", {})

    estado_api = fix.get("status", {}).get("short", "NS")

    return {
        "fixture_id":            fix.get("id"),
        "jornada":               league.get("round", "").replace("Regular Season - ", ""),
        "fecha":                 fix.get("date"),
        "estado":                ESTADO_MAP.get(estado_api, "programado"),
        "estado_api":            estado_api,
        "minuto":                fix.get("status", {}).get("elapsed"),
        "equipo_local_nombre":   teams.get("home", {}).get("name"),
        "equipo_visitante_nombre": teams.get("away", {}).get("name"),
        "equipo_local_id_api":   teams.get("home", {}).get("id"),
        "equipo_visitante_id_api": teams.get("away", {}).get("id"),
        "goles_local":           goals.get("home"),
        "goles_visitante":       goals.get("away"),
        # xG solo disponible en el endpoint de estadísticas, no en el fixture base
        "xg_local":              None,
        "xg_visitante":          None,
        "venue":                 fix.get("venue", {}).get("name"),
        "referee":               fix.get("referee"),
    }


# ---------------------------------------------------------------------------
# 2. Eventos de un partido
# ---------------------------------------------------------------------------

def get_match_events(client: APIFootballClient, fixture_id: int) -> list[dict]:
    """
    Goles, tarjetas, sustituciones y eventos VAR de un partido.

    Endpoint: GET /fixtures/events?fixture={id}

    Returns:
        Lista de dicts:
        {
          minuto, minuto_extra, equipo, jugador,
          tipo, detalle, descripcion
        }
    """
    log.info("Cargando eventos del fixture %d...", fixture_id)
    data = client.get("fixtures/events", {"fixture": fixture_id})
    eventos_raw = data.get("response", [])

    eventos = []
    for ev in eventos_raw:
        time_block  = ev.get("time", {})
        team_block  = ev.get("team", {})
        player_b    = ev.get("player", {})
        assist_b    = ev.get("assist", {})
        tipo_raw    = ev.get("type", "")
        detalle     = ev.get("detail", "")

        eventos.append({
            "minuto":       time_block.get("elapsed"),
            "minuto_extra": time_block.get("extra"),
            "equipo":       team_block.get("name"),
            "jugador":      player_b.get("name"),
            "jugador_id_api": player_b.get("id"),
            "asistencia":   assist_b.get("name"),
            "tipo":         TIPO_EVENTO_MAP.get(tipo_raw, tipo_raw.lower()),
            "detalle":      detalle,
            # Detalle específico por tipo
            "es_penal":     detalle in ("Penalty", "Missed Penalty"),
            "es_propia":    detalle == "Own Goal",
            "color_tarjeta": detalle if tipo_raw == "Card" else None,
        })

    log.info("  %d eventos cargados.", len(eventos))
    return eventos


# ---------------------------------------------------------------------------
# 3. Alineaciones
# ---------------------------------------------------------------------------

def get_lineups(client: APIFootballClient, fixture_id: int) -> dict:
    """
    Titulares, suplentes y esquema táctico de ambos equipos.

    Endpoint: GET /fixtures/lineups?fixture={id}

    Returns:
        {
          "local":     {"equipo", "esquema", "titulares": [...], "suplentes": [...]},
          "visitante": {"equipo", "esquema", "titulares": [...], "suplentes": [...]}
        }
    """
    log.info("Cargando alineaciones del fixture %d...", fixture_id)
    data = client.get("fixtures/lineups", {"fixture": fixture_id})
    lineups_raw = data.get("response", [])

    if len(lineups_raw) < 2:
        log.warning("  Alineaciones no disponibles aun para fixture %d.", fixture_id)
        return {}

    def _parse_lineup(raw: dict, rol: str) -> dict:
        return {
            "equipo":    raw.get("team", {}).get("name"),
            "esquema":   raw.get("formation"),
            "titulares": [
                {
                    "nombre":    p.get("player", {}).get("name"),
                    "numero":    p.get("player", {}).get("number"),
                    "posicion":  p.get("player", {}).get("pos"),
                    "jugador_id_api": p.get("player", {}).get("id"),
                }
                for p in raw.get("startXI", [])
            ],
            "suplentes": [
                {
                    "nombre":    p.get("player", {}).get("name"),
                    "numero":    p.get("player", {}).get("number"),
                    "posicion":  p.get("player", {}).get("pos"),
                    "jugador_id_api": p.get("player", {}).get("id"),
                }
                for p in raw.get("substitutes", [])
            ],
        }

    result = {
        "local":     _parse_lineup(lineups_raw[0], "local"),
        "visitante": _parse_lineup(lineups_raw[1], "visitante"),
    }
    log.info(
        "  %s (%s) vs %s (%s)",
        result["local"]["equipo"],    result["local"]["esquema"],
        result["visitante"]["equipo"], result["visitante"]["esquema"],
    )
    return result


# ---------------------------------------------------------------------------
# 4. Guardar partidos del día en Supabase
# ---------------------------------------------------------------------------

def _resolve_equipo_id(nombre: str) -> Optional[int]:
    """Busca el equipo en Supabase por nombre (normalizado)."""
    if not nombre:
        return None
    res = (
        supabase.table("equipos")
        .select("id")
        .eq("temporada", DB_TEMPORADA)
        .eq("liga_id", DB_LIGA_ID)
        .ilike("nombre", f"%{nombre.split()[0]}%")   # match parcial por primera palabra
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]["id"]
    return None


def save_today_matches(client: Optional[APIFootballClient] = None) -> int:
    """
    Descarga los partidos de hoy de LaLiga y los persiste en la tabla `partidos`.
    Hace upsert por fixture_id para que sea idempotente (puede llamarse cada 15s).

    Devuelve el número de partidos insertados/actualizados.
    """
    if client is None:
        client = APIFootballClient()

    matches = get_today_matches(client)
    if not matches:
        log.info("Sin partidos hoy.")
        return 0

    rows = []
    for m in matches:
        # Resolver IDs de equipo en nuestra BD (match parcial por nombre)
        equipo_local_id    = _resolve_equipo_id(m["equipo_local_nombre"])
        equipo_visitante_id = _resolve_equipo_id(m["equipo_visitante_nombre"])

        # Parsear jornada como entero si es posible
        try:
            jornada = int(m["jornada"])
        except (TypeError, ValueError):
            jornada = None

        # Parsear fecha ISO a timestamptz
        fecha_str = m.get("fecha")
        fecha = None
        if fecha_str:
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).isoformat()
            except ValueError:
                fecha = fecha_str

        rows.append({
            "liga_id":           DB_LIGA_ID,
            "temporada":         DB_TEMPORADA,
            "jornada":           jornada,
            "fecha":             fecha,
            "equipo_local":      equipo_local_id,
            "equipo_visitante":  equipo_visitante_id,
            "goles_local":       m.get("goles_local"),
            "goles_visitante":   m.get("goles_visitante"),
            "xg_local":          m.get("xg_local"),
            "xg_visitante":      m.get("xg_visitante"),
            "estado":            m.get("estado", "programado"),
        })

    res = (
        supabase.table("partidos")
        .upsert(rows, on_conflict="liga_id,temporada,fecha,equipo_local,equipo_visitante")
        .execute()
    )
    n = len(res.data)
    log.info("Partidos guardados/actualizados en Supabase: %d", n)
    return n


# ---------------------------------------------------------------------------
# Entrypoint — para test manual con API key real
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 52)
    log.info(" API-Football — LaLiga %d/%d", SEASON, SEASON + 1)
    log.info("=" * 52)

    client = APIFootballClient()
    client.status()

    log.info("")
    log.info("--- Partidos de hoy ---")
    n = save_today_matches(client)
    log.info("Total partidos: %d", n)

    log.info("")
    log.info("--- Partidos en directo ahora ---")
    live = get_live_matches(client)
    if live:
        for m in live:
            log.info(
                "  %s %s-%s %s  [%s min]",
                m["equipo_local_nombre"],
                m["goles_local"],
                m["goles_visitante"],
                m["equipo_visitante_nombre"],
                m.get("minuto", "-"),
            )

        # Mostrar eventos y alineaciones del primer partido en directo
        first_id = live[0]["fixture_id"]
        log.info("")
        log.info("--- Eventos fixture %d ---", first_id)
        events = get_match_events(client, first_id)
        for ev in events:
            log.info(
                "  min %s | %s | %s | %s",
                ev["minuto"], ev["tipo"], ev["jugador"], ev["detalle"]
            )

        log.info("")
        log.info("--- Alineaciones fixture %d ---", first_id)
        lineups = get_lineups(client, first_id)
        for rol in ("local", "visitante"):
            equipo = lineups.get(rol, {})
            log.info(
                "  %s [%s]: %s",
                equipo.get("equipo", "?"),
                equipo.get("esquema", "?"),
                ", ".join(p["nombre"] for p in equipo.get("titulares", []))
            )
    else:
        log.info("  No hay partidos en directo ahora mismo.")

    log.info("=" * 52)


if __name__ == "__main__":
    run()
