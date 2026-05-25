"""
Champions League Fase de Liga — Partidos por jornada (Sofascore)

Carga las 8 jornadas de la fase de liga UCL 25/26 en la tabla partidos.

Diferencias respecto a sofascore_jornadas_scraper.py (LaLiga):
  - tournament_id=7, season_id=76953 (fijos — no hay auto-discover)
  - liga_id=28, MAX_JORNADA=8
  - curl_cffi con impersonate chrome124 (más robusto para Sofascore UCL)
  - Aliases UCL: nombres Sofascore → nombres en BD (liga_id=28)

Endpoints Sofascore:
  GET /api/v1/unique-tournament/7/season/76953/events/round/{round}

Uso (desde backend/):
  conda activate xcout
  python scrapers/sofascore_champions_partidos.py         # jornadas 1-8
  python scrapers/sofascore_champions_partidos.py 3       # solo jornada 3
  python scrapers/sofascore_champions_partidos.py 1 4     # jornadas 1 a 4
"""

import sys
import difflib
import logging
import time
import unicodedata
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

TOURNAMENT_ID = 7
SEASON_ID     = 76953   # Champions League 25/26 — fijo
DB_LIGA_ID    = 28
DB_TEMPORADA  = "2526"
MAX_JORNADA   = 8       # Fase de liga: 8 jornadas
REQUEST_DELAY = 1.0     # segundos entre requests

SESSION = requests.Session(impersonate="chrome124")

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

# Nombre Sofascore normalizado → nombre BD normalizado (liga_id=28)
SS_ALIASES: dict[str, str] = {
    # Nombre diferente entre Sofascore y BD
    "internazionale":               "inter",
    "bayer leverkusen":             "bayer 04 leverkusen",
    "sl benfica":                   "benfica",
    "club brugge":                  "club brugge kv",
    "monaco":                       "as monaco",
    "union saint-gilloise":         "royale union saint-gilloise",
    "union sg":                     "royale union saint-gilloise",
    "slavia prague":                "sk slavia praha",
    "sk slavia prague":             "sk slavia praha",
    "napoli":                       "ssc napoli",
    "liverpool":                    "liverpool fc",
    "marseille":                    "olympique de marseille",
    "bodo/glimt":                   "bodo/glimt",
    "fk bodo/glimt":               "bodo/glimt",
    # Equipos UCL 25/26 no en otras ligas de la BD
    "feyenoord":                    "feyenoord rotterdam",
    "ac milan":                     "ac milan",
    "aston villa":                  "aston villa",
    "celtic":                       "celtic glasgow",
    "celtic fc":                    "celtic glasgow",
    "young boys":                   "bsc young boys",
    "bsc young boys":               "bsc young boys",
    "rb leipzig":                   "rb leipzig",
    "rasenballsport leipzig":       "rb leipzig",
    "red star belgrade":            "roter stern belgrad",
    "crvena zvezda":                "roter stern belgrad",
    "shakhtar donetsk":             "shakhtar donetsk",
    "slovan bratislava":            "sk slovan bratislava",
    "girona":                       "girona fc",
    "girona fc":                    "girona fc",
    "dinamo zagreb":                "gnk dinamo zagreb",
    "gnk dinamo zagreb":            "gnk dinamo zagreb",
    "sturm graz":                   "sk sturm graz",
    "brest":                        "stade brestois 29",
    "stade brestois":               "stade brestois 29",
    "bologna":                      "fc bologna",
    "bologna fc 1909":              "fc bologna",
    "vfb stuttgart":                "vfb stuttgart",
    "stuttgart":                    "vfb stuttgart",
    "sparta prague":                "ac sparta prag",
    "ac sparta prague":             "ac sparta prag",
    "lille":                        "losc lille",
    "losc":                         "losc lille",
    "losc lille":                   "losc lille",
    "psv":                          "psv eindhoven",
    "psv eindhoven":                "psv eindhoven",
}


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _get(endpoint: str) -> Optional[dict]:
    url = f"{API}/{endpoint.lstrip('/')}"
    try:
        r = SESSION.get(url, headers=HEADERS, timeout=15)
        if r.status_code in (404, 403):
            log.debug("HTTP %d: %s", r.status_code, endpoint)
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("Error en %s: %s", endpoint, e)
        return None


def _ts_to_iso(ts: Optional[int]) -> Optional[str]:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


# ── Normalización ─────────────────────────────────────────────────────────────

_CHAR_MAP = str.maketrans({
    'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G',
    'ş': 's', 'Ş': 'S', 'ð': 'd', 'Ð': 'D',
    'þ': 'th', 'ø': 'o', 'Ø': 'O',
    'æ': 'ae', 'Æ': 'Ae', 'ł': 'l', 'Ł': 'L',
    'ß': 'ss', "'": '', '’': '', '‘': '',
    '-': ' ', '–': ' ', '—': ' ',
})

def _norm(text: str) -> str:
    if not text:
        return ""
    text = str(text).translate(_CHAR_MAP)
    nfkd = unicodedata.normalize("NFKD", text)
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


_STRIP_TOKENS = {"fc", "cf", "cd", "rcd", "ud", "sd", "rc", "sc", "ac", "afc", "sfc", "fk", "sk"}

def _strip_tokens(name_norm: str) -> str:
    words = [w for w in name_norm.split() if w not in _STRIP_TOKENS]
    return " ".join(words)


# ── Cache de equipos ──────────────────────────────────────────────────────────

_equipo_cache: dict[str, int] = {}
_equipo_keys:  list[str]      = []


def _load_equipo_cache():
    global _equipo_cache, _equipo_keys
    if _equipo_cache:
        return

    res = (
        supabase.table("equipos")
        .select("id, nombre")
        .eq("liga_id", DB_LIGA_ID)
        .execute()
    )
    for r in (res.data or []):
        key = _norm(r["nombre"])
        if key and key not in _equipo_cache:
            _equipo_cache[key] = r["id"]

    _equipo_keys = list(_equipo_cache.keys())
    log.info("Cache equipos UCL: %d entradas.", len(_equipo_cache))


def _resolve_equipo(nombre_ss: str) -> Optional[int]:
    """
    Resuelve nombre Sofascore → equipo_id en la BD (liga_id=28).
    Cascada: alias manual → exacto → sin tokens → difflib (0.72).
    """
    if not nombre_ss:
        return None
    _load_equipo_cache()
    n = _norm(nombre_ss)

    # 1. Alias manual
    alias_target = SS_ALIASES.get(n)
    if alias_target:
        n_alias = _norm(alias_target)
        if n_alias in _equipo_cache:
            return _equipo_cache[n_alias]

    # 2. Exacto
    if n in _equipo_cache:
        return _equipo_cache[n]

    # 3. Sin tokens genéricos
    n_stripped = _strip_tokens(n)
    if n_stripped:
        if n_stripped in _equipo_cache:
            return _equipo_cache[n_stripped]
        for key, eid in _equipo_cache.items():
            if _strip_tokens(key) == n_stripped:
                return eid

    # 4. difflib
    if _equipo_keys:
        matches = difflib.get_close_matches(n, _equipo_keys, n=1, cutoff=0.72)
        if not matches and n_stripped:
            stripped_keys = [_strip_tokens(k) for k in _equipo_keys]
            close = difflib.get_close_matches(n_stripped, stripped_keys, n=1, cutoff=0.72)
            if close:
                idx = stripped_keys.index(close[0])
                matches = [_equipo_keys[idx]]
        if matches:
            log.debug("  difflib '%s' → '%s'", n, matches[0])
            return _equipo_cache[matches[0]]

    log.warning("  Equipo no resuelto: '%s'", nombre_ss)
    return None


# ── Jornadas ──────────────────────────────────────────────────────────────────

def get_round_events(jornada: int) -> list[dict]:
    data = _get(
        f"unique-tournament/{TOURNAMENT_ID}/season/{SEASON_ID}/events/round/{jornada}"
    )
    return (data or {}).get("events", [])


def parse_match(raw: dict, jornada: int) -> dict:
    status     = raw.get("status", {})
    home       = raw.get("homeTeam", {})
    away       = raw.get("awayTeam", {})
    home_score = raw.get("homeScore", {})
    away_score = raw.get("awayScore", {})

    estado_type = status.get("type", "notstarted")
    estado      = ESTADO_MAP.get(estado_type, "programado")

    if estado == "finalizado":
        goles_local = home_score.get("normaltime", home_score.get("current"))
        goles_visit = away_score.get("normaltime", away_score.get("current"))
    else:
        goles_local = home_score.get("current")
        goles_visit = away_score.get("current")

    return {
        "sofascore_id":            raw.get("id"),
        "liga_id":                 DB_LIGA_ID,
        "temporada":               DB_TEMPORADA,
        "jornada":                 jornada,
        "fecha":                   _ts_to_iso(raw.get("startTimestamp")),
        "equipo_local":            _resolve_equipo(home.get("name", "")),
        "equipo_visitante":        _resolve_equipo(away.get("name", "")),
        "equipo_local_nombre":     home.get("name"),    # para log de NULLs
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
    log.info("=" * 62)
    log.info(" Champions League Partidos — temporada=%s  J%d→J%d",
             DB_TEMPORADA, jornada_ini, jornada_fin)
    log.info(" tournament_id=%d  season_id=%d  liga_id=%d",
             TOURNAMENT_ID, SEASON_ID, DB_LIGA_ID)
    log.info("=" * 62)

    _load_equipo_cache()

    total_partidos  = 0
    total_guardados = 0
    nulos_local     = 0
    nulos_visit     = 0

    for jornada in range(jornada_ini, jornada_fin + 1):
        raw_events = get_round_events(jornada)

        if not raw_events:
            log.info("J%d — Sin eventos (jornada no disponible aún).", jornada)
            continue

        matches = [parse_match(e, jornada) for e in raw_events]

        nl = sum(1 for m in matches if m["equipo_local"]    is None)
        nv = sum(1 for m in matches if m["equipo_visitante"] is None)
        nulos_local += nl
        nulos_visit += nv

        guardados = save_matches(matches)
        total_partidos  += len(matches)
        total_guardados += guardados

        log.info(
            "J%d — %d partidos, %d guardados%s",
            jornada, len(matches), guardados,
            f"  ⚠ {nl + nv} equipo(s) NULL" if (nl + nv) else "",
        )

        for m in matches:
            if m["equipo_local"] is None:
                log.warning("    local NULL   : '%s'", m["equipo_local_nombre"])
            if m["equipo_visitante"] is None:
                log.warning("    visitante NULL: '%s'", m["equipo_visitante_nombre"])

        time.sleep(REQUEST_DELAY)

    log.info("")
    log.info("=" * 62)
    log.info(" RESUMEN")
    log.info("  Jornadas procesadas : %d", jornada_fin - jornada_ini + 1)
    log.info("  Partidos totales    : %d", total_partidos)
    log.info("  Partidos guardados  : %d", total_guardados)
    log.info("  NULLs equipo_local  : %d", nulos_local)
    log.info("  NULLs equipo_visit  : %d", nulos_visit)
    log.info("=" * 62)

    if nulos_local + nulos_visit > 0:
        log.warning("")
        log.warning("Hay equipos sin resolver. Añade los nombres que aparecen")
        log.warning("en los ⚠ al dict SS_ALIASES de este script y vuelve a ejecutar.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 0:
        run()
    elif len(args) == 1:
        j = int(args[0])
        run(j, j)
    else:
        run(int(args[0]), int(args[1]))
