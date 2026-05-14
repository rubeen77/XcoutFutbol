"""
Clasificacion Scraper — Sofascore standings para todas las ligas activas.

Endpoint:
  GET https://api.sofascore.com/api/v1/unique-tournament/{tid}/season/{sid}/standings/total

IDs Sofascore:
  LaLiga        : tournament_id=8   (season auto)
  Premier League: tournament_id=17, season_id=76986
  Bundesliga    : tournament_id=35, season_id=77333
  Serie A       : tournament_id=23  (season auto)
  Ligue 1       : tournament_id=34  (season auto)

Uso:
  python clasificacion_scraper.py              # todas las ligas
  python clasificacion_scraper.py --liga 1     # solo LaLiga (db liga_id)
"""

import sys
import time
import logging
import unicodedata
from pathlib import Path
from typing import Optional

from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

SESSION   = requests.Session(impersonate="chrome124")
API       = "https://api.sofascore.com/api/v1"
TEMPORADA = "2526"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":  "application/json",
    "Referer": "https://www.sofascore.com/",
}

# liga_id (Supabase) → config Sofascore
LIGAS_CONFIG = {
    1:  {"tournament_id": 8,  "season_id": None,  "nombre": "LaLiga"},
    24: {"tournament_id": 17, "season_id": 76986, "nombre": "Premier League"},
    25: {"tournament_id": 35, "season_id": 77333, "nombre": "Bundesliga"},
    26: {"tournament_id": 23, "season_id": None,  "nombre": "Serie A"},
    27: {"tournament_id": 34, "season_id": None,  "nombre": "Ligue 1"},
}

DELAY = 2.0   # segundos entre peticiones


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Sin acentos, minúsculas, espacios colapsados."""
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def _get(endpoint: str) -> Optional[dict]:
    url = f"{API}/{endpoint.lstrip('/')}"
    try:
        r = SESSION.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 404:
            log.warning("404: %s", url)
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("Error GET %s: %s", url, e)
        return None


def _get_season_id(tournament_id: int) -> Optional[int]:
    """Busca el season_id de la temporada 2025/26 para un torneo."""
    data = _get(f"unique-tournament/{tournament_id}/seasons")
    if not data:
        return None
    for season in (data.get("seasons") or []):
        year = season.get("year", "")
        # Sofascore puede devolver "2025/2026" o "25/26"
        if "2025" in str(year) and "2026" in str(year):
            return season["id"]
        if str(year) in ("25/26", "2025/26"):
            return season["id"]
    log.warning("No se encontró season 25/26 para tournament_id=%d", tournament_id)
    return None


# ---------------------------------------------------------------------------
# Aliases: nombre normalizado Sofascore → nombre normalizado en BD
# ---------------------------------------------------------------------------

ALIASES = {
    "manchester united": "manchester utd",
    "wolverhampton":     "wolves",
    "fc bayern munchen": "bayern munich",
    "fc st. pauli":      "st pauli",
    "stade rennais":     "rennes",
}


# ---------------------------------------------------------------------------
# Fuzzy match contra equipos en Supabase
# ---------------------------------------------------------------------------

def _resolver_equipo(nombre_sf: str, eq_map: dict[str, int]) -> Optional[int]:
    """Intenta resolver nombre Sofascore → equipo_id en Supabase."""
    n = _norm(nombre_sf)
    # 1. Alias manual
    n = ALIASES.get(n, n)
    # 2. Exacto
    if n in eq_map:
        return eq_map[n]
    # 3. Substring bidireccional
    for k, v in eq_map.items():
        if n in k or k in n:
            return v
    return None


# ---------------------------------------------------------------------------
# Core: actualizar clasificación de una liga
# ---------------------------------------------------------------------------

def actualizar_clasificacion(liga_id: int) -> int:
    """
    Descarga la clasificación de Sofascore y actualiza posicion_clasificacion
    y puntos en la tabla equipos.
    Devuelve el número de equipos actualizados.
    """
    cfg = LIGAS_CONFIG.get(liga_id)
    if not cfg:
        log.error("liga_id=%d no configurada.", liga_id)
        return 0

    tid = cfg["tournament_id"]
    sid = cfg["season_id"]
    nombre_liga = cfg["nombre"]

    # Resolver season_id automáticamente si no está fijo
    if sid is None:
        log.info("[%s] Buscando season_id 25/26...", nombre_liga)
        sid = _get_season_id(tid)
        if sid is None:
            log.error("[%s] No se pudo obtener season_id, abortando.", nombre_liga)
            return 0
        log.info("[%s] season_id encontrado: %d", nombre_liga, sid)
        time.sleep(DELAY)

    # Descargar standings
    log.info("[%s] Descargando clasificación (tid=%d, sid=%d)...", nombre_liga, tid, sid)
    data = _get(f"unique-tournament/{tid}/season/{sid}/standings/total")
    time.sleep(DELAY)

    if not data:
        log.error("[%s] Sin datos de standings.", nombre_liga)
        return 0

    standings = data.get("standings", [])
    if not standings:
        log.warning("[%s] Standings vacíos.", nombre_liga)
        return 0

    # Sofascore puede devolver varias tablas (ej. grupos); usar la primera
    rows = standings[0].get("rows", [])
    if not rows:
        log.warning("[%s] Sin filas en standings[0].", nombre_liga)
        return 0

    log.info("[%s] %d equipos en la clasificación.", nombre_liga, len(rows))

    # Cargar mapa de equipos desde Supabase
    eq_res = (
        supabase.table("equipos")
        .select("id, nombre")
        .eq("liga_id", liga_id)
        .eq("temporada", TEMPORADA)
        .execute()
    )
    eq_map = {_norm(r["nombre"]): r["id"] for r in (eq_res.data or [])}
    log.info("[%s] %d equipos en BD.", nombre_liga, len(eq_map))

    actualizados = 0
    no_resueltos = []

    for row in rows:
        nombre_sf = (row.get("team") or {}).get("name", "")
        posicion  = row.get("position")
        puntos    = row.get("points")

        if posicion is None or puntos is None or not nombre_sf:
            continue

        eq_id = _resolver_equipo(nombre_sf, eq_map)
        if not eq_id:
            no_resueltos.append(nombre_sf)
            continue

        supabase.table("equipos").update({
            "posicion_clasificacion": int(posicion),
            "puntos":                 int(puntos),
        }).eq("id", eq_id).execute()
        actualizados += 1

    if no_resueltos:
        log.warning("[%s] No resueltos (%d): %s", nombre_liga, len(no_resueltos), no_resueltos)
    log.info("[%s] Equipos actualizados: %d / %d", nombre_liga, actualizados, len(rows))
    return actualizados


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(liga_ids: Optional[list[int]] = None):
    """Actualiza clasificaciones de todas las ligas (o solo las indicadas)."""
    ligas = liga_ids or list(LIGAS_CONFIG.keys())
    total = 0
    for liga_id in ligas:
        try:
            n = actualizar_clasificacion(liga_id)
            total += n
        except Exception:
            log.exception("Error actualizando clasificación de liga_id=%d", liga_id)
    log.info("=== Clasificaciones actualizadas: %d equipos en total ===", total)
    return total


if __name__ == "__main__":
    liga_filter = None
    if "--liga" in sys.argv:
        idx = sys.argv.index("--liga")
        liga_filter = [int(sys.argv[idx + 1])]
    run(liga_filter)
