"""
Sofascore Jornadas Scraper — Carga completa de LaLiga 2025/26 por jornada

Diferencias con sofascore_scraper.py (que opera por fecha):
  - Itera jornadas 1..38 usando el endpoint by-round de Sofascore
  - Detecta automáticamente el season_id de 2025/26
  - Matching de equipos mejorado: normalización + aliases + difflib

Uso:
  python sofascore_jornadas_scraper.py           # todas las jornadas
  python sofascore_jornadas_scraper.py 1 10      # jornadas 1 a 10
  python sofascore_jornadas_scraper.py 31        # solo jornada 31

Endpoints Sofascore:
  GET /unique-tournament/8/seasons
  GET /unique-tournament/8/season/{season_id}/events/round/{round}
"""

import sys
import difflib
import logging
import time
import unicodedata
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

LALIGA_TOURNAMENT_ID = 8
DB_LIGA_ID           = 1
DB_TEMPORADA         = "2526"
MAX_JORNADA          = 38
REQUEST_DELAY        = 0.8   # segundos entre requests (evitar rate-limit)

# Fallback si la API de seasons devuelve 403 — actualizar si cambia la temporada
SEASON_ID_FALLBACK   = 68410

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer":         "https://www.sofascore.com/",
    "Origin":          "https://www.sofascore.com",
}

API = "https://api.sofascore.com/api/v1"

ESTADO_MAP = {
    "notstarted":  "programado",
    "inprogress":  "en_directo",
    "finished":    "finalizado",
    "postponed":   "aplazado",
    "canceled":    "aplazado",
    "interrupted": "aplazado",
}

# Aliases manuales: nombre Sofascore normalizado → nombre DB normalizado (aproximado)
# Clave ya sin acentos y en minúsculas; valor también sin acentos.
SS_ALIASES: dict[str, str] = {
    "fc barcelona":              "barcelona",
    "real madrid cf":            "real madrid",
    "atletico de madrid":        "atletico madrid",
    "atletico madrid":           "atletico madrid",
    "athletic club":             "athletic club",
    "athletic bilbao":           "athletic club",
    "real sociedad cf":          "real sociedad",
    "real betis balompie":       "real betis",
    "real betis balomipie":      "real betis",
    "celta vigo":                "celta vigo",
    "deportivo alaves":          "alaves",
    "alaves":                    "alaves",
    "rayo vallecano de madrid":  "rayo vallecano",
    "club atletico osasuna":     "osasuna",
    "ca osasuna":                "osasuna",
    "getafe cf":                 "getafe",
    "villarreal cf":             "villarreal",
    "valencia cf":               "valencia",
    "sevilla fc":                "sevilla",
    "rcd mallorca":              "mallorca",
    "ud las palmas":             "las palmas",
    "girona fc":                 "girona",
    "cd leganes":                "leganes",
    "real valladolid cf":        "real valladolid",
    "rcd espanyol":              "espanyol",
    "espanyol":                  "espanyol",
    "cd espanyol":               "espanyol",
}


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _get(endpoint: str) -> Optional[dict]:
    url = f"{API}/{endpoint.lstrip('/')}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code in (404, 403):
            log.debug("HTTP %d: %s", r.status_code, endpoint)
            return None
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        log.warning("Error en %s: %s", endpoint, e)
        return None


def _ts_to_iso(ts: Optional[int]) -> Optional[str]:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


# ── Normalización ─────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    """Sin acentos, minúsculas, espacios colapsados."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


# Prefijos/sufijos genéricos que Sofascore añade pero la DB omite
_STRIP_TOKENS = {"fc", "cf", "cd", "rcd", "ud", "sd", "rc", "sc", "ac", "afc", "sfc"}

def _strip_suffixes(name_norm: str) -> str:
    """Elimina tokens genéricos de club para mejorar el matching."""
    words = [w for w in name_norm.split() if w not in _STRIP_TOKENS]
    return " ".join(words)


# ── Cache de equipos ──────────────────────────────────────────────────────────

_equipo_cache: dict[str, int] = {}   # nombre_norm → id
_equipo_keys:  list[str]      = []   # lista de claves para difflib


def _load_equipo_cache():
    global _equipo_cache, _equipo_keys
    if _equipo_cache:
        return

    # Cargar la temporada actual Y todas las demás para cubrir máxima variedad
    res = (
        supabase.table("equipos")
        .select("id, nombre, liga_id")
        .eq("liga_id", DB_LIGA_ID)
        .execute()
    )
    seen: set[str] = set()
    for r in res.data:
        key = _norm(r["nombre"])
        if key and key not in seen:
            seen.add(key)
            _equipo_cache[key] = r["id"]

    _equipo_keys = list(_equipo_cache.keys())
    log.info("Cache equipos: %d entradas únicas.", len(_equipo_cache))
    if log.isEnabledFor(logging.DEBUG):
        for k in sorted(_equipo_keys):
            log.debug("  '%s' → %d", k, _equipo_cache[k])


def _resolve_equipo(nombre_ss: str) -> Optional[int]:
    """
    Resuelve el nombre de un equipo Sofascore al id de nuestra tabla equipos.
    Estrategia en cascada:
      1. Alias manual (SS_ALIASES)
      2. Coincidencia exacta normalizada
      3. Sin prefijos/sufijos genéricos
      4. difflib (umbral 0.72)
    """
    if not nombre_ss:
        return None
    _load_equipo_cache()
    n = _norm(nombre_ss)

    # 1. Alias manual → clave normalizada de la DB
    alias_target = SS_ALIASES.get(n)
    if alias_target and alias_target in _equipo_cache:
        return _equipo_cache[alias_target]

    # 2. Coincidencia exacta
    if n in _equipo_cache:
        return _equipo_cache[n]

    # 3. Sin prefijos genéricos
    n_stripped = _strip_suffixes(n)
    if n_stripped and n_stripped in _equipo_cache:
        return _equipo_cache[n_stripped]

    # Comprobar también versión recortada de las claves DB
    for key, eid in _equipo_cache.items():
        if _strip_suffixes(key) == n_stripped and n_stripped:
            return eid

    # 4. difflib — el más parecido con umbral mínimo
    if _equipo_keys:
        candidates = difflib.get_close_matches(n, _equipo_keys, n=1, cutoff=0.72)
        if not candidates and n_stripped:
            stripped_keys = [_strip_suffixes(k) for k in _equipo_keys]
            close = difflib.get_close_matches(n_stripped, stripped_keys, n=1, cutoff=0.72)
            if close:
                # recuperar el id correspondiente al índice
                idx = stripped_keys.index(close[0])
                candidates = [_equipo_keys[idx]]
        if candidates:
            log.debug("  difflib '%s' → '%s'", n, candidates[0])
            return _equipo_cache[candidates[0]]

    log.warning("  ⚠ Equipo no resuelto: '%s' (norm='%s')", nombre_ss, n)
    return None


# ── Season ID ─────────────────────────────────────────────────────────────────

def get_season_id() -> int:
    """
    Obtiene el season_id de LaLiga 2025/26 desde la API de Sofascore.
    Devuelve SEASON_ID_FALLBACK si la API no responde o no encuentra la temporada.
    """
    data = _get(f"unique-tournament/{LALIGA_TOURNAMENT_ID}/seasons")
    if not data:
        log.warning("No se pudo obtener la lista de temporadas. Usando fallback id=%d.", SEASON_ID_FALLBACK)
        return SEASON_ID_FALLBACK

    for season in data.get("seasons", []):
        year = season.get("year", "")
        if "2025" in year and "2026" in year:
            sid = season["id"]
            log.info("Temporada 2025/26 encontrada: id=%d ('%s')", sid, year)
            return sid

    # Fallback: temporada más reciente
    seasons = data.get("seasons", [])
    if seasons:
        sid = seasons[0]["id"]
        log.warning("Temporada 2025/26 no encontrada explícitamente. Usando la más reciente: id=%d", sid)
        return sid

    log.warning("Sin temporadas disponibles. Usando fallback id=%d.", SEASON_ID_FALLBACK)
    return SEASON_ID_FALLBACK


# ── Jornadas ──────────────────────────────────────────────────────────────────

def get_round_matches(season_id: int, jornada: int) -> list[dict]:
    """
    Devuelve los partidos de una jornada concreta.
    Endpoint: GET /unique-tournament/{tid}/season/{sid}/events/round/{round}
    """
    data = _get(
        f"unique-tournament/{LALIGA_TOURNAMENT_ID}/season/{season_id}/events/round/{jornada}"
    )
    if not data:
        return []
    return data.get("events", [])


def parse_match(raw: dict) -> dict:
    status     = raw.get("status", {})
    home       = raw.get("homeTeam", {})
    away       = raw.get("awayTeam", {})
    home_score = raw.get("homeScore", {})
    away_score = raw.get("awayScore", {})
    round_info = raw.get("roundInfo", {})

    estado_type = status.get("type", "notstarted")
    estado      = ESTADO_MAP.get(estado_type, "programado")

    if estado == "finalizado":
        goles_local = home_score.get("normaltime") if home_score.get("normaltime") is not None else home_score.get("current")
        goles_visit = away_score.get("normaltime") if away_score.get("normaltime") is not None else away_score.get("current")
    else:
        goles_local = home_score.get("current")
        goles_visit = away_score.get("current")

    eq_local   = _resolve_equipo(home.get("name", ""))
    eq_visit   = _resolve_equipo(away.get("name", ""))

    return {
        "sofascore_id":            raw.get("id"),
        "liga_id":                 DB_LIGA_ID,
        "temporada":               DB_TEMPORADA,
        "jornada":                 round_info.get("round"),
        "fecha":                   _ts_to_iso(raw.get("startTimestamp")),
        "equipo_local":            eq_local,
        "equipo_visitante":        eq_visit,
        "equipo_local_nombre":     home.get("name"),
        "equipo_visitante_nombre": away.get("name"),
        "goles_local":             goles_local,
        "goles_visitante":         goles_visit,
        "xg_local":                None,
        "xg_visitante":            None,
        "estado":                  estado,
    }


# ── Guardado ──────────────────────────────────────────────────────────────────

def save_matches(matches: list[dict]) -> int:
    if not matches:
        return 0

    rows = [
        {
            "sofascore_id":     m["sofascore_id"],
            "liga_id":          m["liga_id"],
            "temporada":        m["temporada"],
            "jornada":          m["jornada"],
            "fecha":            m["fecha"],
            "equipo_local":     m["equipo_local"],
            "equipo_visitante": m["equipo_visitante"],
            "goles_local":      m["goles_local"],
            "goles_visitante":  m["goles_visitante"],
            "xg_local":         m["xg_local"],
            "xg_visitante":     m["xg_visitante"],
            "estado":           m["estado"],
        }
        for m in matches
    ]

    res = (
        supabase.table("partidos")
        .upsert(rows, on_conflict="sofascore_id")
        .execute()
    )
    return len(res.data)


# ── Entrypoint ────────────────────────────────────────────────────────────────

def run(jornada_ini: int = 1, jornada_fin: int = MAX_JORNADA):
    log.info("=" * 60)
    log.info(" Sofascore Jornadas — LaLiga %s  (J%d → J%d)", DB_TEMPORADA, jornada_ini, jornada_fin)
    log.info("=" * 60)

    _load_equipo_cache()
    season_id = get_season_id()

    total_partidos = 0
    total_guardados = 0
    nulos_local = 0
    nulos_visit = 0

    for jornada in range(jornada_ini, jornada_fin + 1):
        raw_events = get_round_matches(season_id, jornada)

        if not raw_events:
            log.info("J%-2d — Sin datos (fin de jornadas disponibles).", jornada)
            # Paramos si 3 jornadas consecutivas vacías
            # (ya gestionado en el bucle de abajo)
            break

        matches = [parse_match(e) for e in raw_events]

        # Estadísticas de NULLs
        nulos_l = sum(1 for m in matches if m["equipo_local"]    is None)
        nulos_v = sum(1 for m in matches if m["equipo_visitante"] is None)
        nulos_local += nulos_l
        nulos_visit += nulos_v

        guardados = save_matches(matches)
        total_partidos  += len(matches)
        total_guardados += guardados

        log.info(
            "J%-2d — %d partidos, %d guardados%s",
            jornada,
            len(matches),
            guardados,
            f"  ⚠ {nulos_l+nulos_v} NULLs equipo" if (nulos_l + nulos_v) else "",
        )

        # Mostrar detalle de partidos no resueltos para diagnóstico
        for m in matches:
            if m["equipo_local"] is None:
                log.warning("    local NULL: '%s'", m["equipo_local_nombre"])
            if m["equipo_visitante"] is None:
                log.warning("    visit NULL: '%s'", m["equipo_visitante_nombre"])

        time.sleep(REQUEST_DELAY)

    log.info("")
    log.info("=" * 60)
    log.info(" RESUMEN")
    log.info("  Jornadas procesadas : %d", jornada_fin - jornada_ini + 1)
    log.info("  Partidos totales    : %d", total_partidos)
    log.info("  Partidos guardados  : %d", total_guardados)
    log.info("  NULLs equipo_local  : %d", nulos_local)
    log.info("  NULLs equipo_visit  : %d", nulos_visit)
    log.info("=" * 60)

    if nulos_local + nulos_visit > 0:
        log.warning("")
        log.warning("Hay NULLs sin resolver. Añade los nombres que aparecen en ⚠")
        log.warning("al dict SS_ALIASES en este script y vuelve a ejecutar.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 0:
        run()
    elif len(args) == 1:
        j = int(args[0])
        run(j, j)
    else:
        run(int(args[0]), int(args[1]))
