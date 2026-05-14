"""
Sofascore Ligue 1 Partidos Scraper — actualiza goles nulos en tabla partidos

La Fase 6 de fbref_ligue1.py insertó los partidos con goles=NULL porque
FBref no tenía los resultados. Este script los completa con resultados de
Sofascore jornada a jornada.

Estrategia:
  1. Carga partidos de Ligue 1 que tienen goles_local IS NULL desde Supabase
  2. Construye un índice (equipo_local_id, equipo_visitante_id, jornada) → id
  3. Descarga resultados jornada a jornada desde Sofascore (tournament_id=34)
  4. Resuelve nombres Sofascore → IDs de la DB
  5. Para cada partido finalizado que coincida, hace UPDATE de goles + estado

Uso (desde backend/):
  conda activate xcout
  python scrapers/sofascore_ligue1_partidos.py          # todas las jornadas
  python scrapers/sofascore_ligue1_partidos.py 1 10     # jornadas 1-10
  python scrapers/sofascore_ligue1_partidos.py 15       # solo jornada 15
"""

import sys
import time
import difflib
import logging
import unicodedata
from pathlib import Path
from typing import Optional

from curl_cffi import requests as cffi_requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

TOURNAMENT_ID  = 34        # Ligue 1 en Sofascore
SEASON_ID      = None      # Se descubre automáticamente si es None
DB_LIGA_ID     = 27
DB_TEMPORADA   = "2526"
MAX_JORNADA    = 34        # Ligue 1: 18 equipos → 34 jornadas
REQUEST_DELAY  = 1.0       # segundos entre requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer":         "https://www.sofascore.com/",
    "Origin":          "https://www.sofascore.com",
}

API = "https://api.sofascore.com/api/v1"

# Mapa nombre Sofascore normalizado → nombre DB normalizado
# Los nombres DB vienen de FBref (fase 1 de fbref_ligue1.py)
SS_ALIASES: dict[str, str] = {
    # PSG
    "paris saint-germain":     "paris saint-germain",
    "psg":                     "paris saint-germain",
    # Marseille
    "olympique de marseille":  "marseille",
    "olympique marseille":     "marseille",
    # Lyon
    "olympique lyonnais":      "lyon",
    "olympique de lyon":       "lyon",
    # Monaco
    "as monaco":               "monaco",
    # Lens
    "rc lens":                 "lens",
    # Lille
    "lille osc":               "lille",
    # Rennes
    "stade rennais fc":        "rennes",
    "stade rennais":           "rennes",
    # Nice
    "ogc nice":                "nice",
    # Reims
    "stade de reims":          "reims",
    # Brest
    "stade brestois 29":       "brest",
    "stade brestois":          "brest",
    # Toulouse
    "toulouse fc":             "toulouse",
    # Montpellier
    "montpellier hsc":         "montpellier",
    # Strasbourg
    "rc strasbourg alsace":    "strasbourg",
    "rc strasbourg":           "strasbourg",
    # Nantes
    "fc nantes":               "nantes",
    # Auxerre
    "aj auxerre":              "auxerre",
    # Angers
    "angers sco":              "angers",
    # Saint-Étienne
    "as saint-etienne":        "saint-etienne",
    "as saint etienne":        "saint-etienne",
    "saint-etienne":           "saint-etienne",
    # Le Havre
    "le havre ac":             "le havre",
    "le havre":                "le havre",
    # Cobertura 2526 (posibles nuevos ascendidos)
    "havre ac":                "le havre",
}

# ── HTTP con reintentos ────────────────────────────────────────────────────────

_session = cffi_requests.Session(impersonate="chrome120")


def _get(endpoint: str, retries: int = 3) -> Optional[dict]:
    url = f"{API}/{endpoint.lstrip('/')}"
    for attempt in range(retries):
        try:
            r = _session.get(url, headers=HEADERS, timeout=30)
            if r.status_code in (404, 403):
                log.debug("HTTP %d: %s", r.status_code, url)
                return None
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning("  Intento %d/%d fallido (%s): %s", attempt + 1, retries, endpoint, e)
            if attempt < retries - 1:
                time.sleep(5)
    return None


# ── Normalización ─────────────────────────────────────────────────────────────

_CHAR_MAP = str.maketrans({
    'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G',
    'ş': 's', 'Ş': 'S', 'ð': 'd', 'Ð': 'D',
    'þ': 'th', 'ø': 'o', 'Ø': 'O',
    'æ': 'ae', 'Æ': 'Ae', 'œ': 'oe', 'Œ': 'Oe',
    'ł': 'l', 'Ł': 'L', 'ß': 'ss',
    "'": '', '’': '', '‘': '',
    '-': ' ', '–': ' ', '—': ' ',
})


def _norm(text: str) -> str:
    if not text:
        return ""
    text = str(text).translate(_CHAR_MAP)
    nfkd = unicodedata.normalize("NFKD", text)
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


# ── Season ID ─────────────────────────────────────────────────────────────────

def discover_season_id() -> int:
    log.info("[season] Buscando season_id Ligue 1 25/26 en Sofascore...")
    data = _get(f"unique-tournament/{TOURNAMENT_ID}/seasons")
    if not data:
        raise RuntimeError("No se pudo obtener la lista de temporadas de Sofascore")

    seasons = data.get("seasons", [])
    log.info("  %d temporadas disponibles:", len(seasons))
    for s in seasons[:8]:
        log.info("    id=%-7d  %s", s["id"], s.get("name", ""))

    for s in seasons:
        name = s.get("name", "")
        if "25/26" in name or "2025" in name:
            log.info("  → Usando season_id=%d  (%s)", s["id"], name)
            return s["id"]

    fallback = seasons[0]["id"]
    log.warning("  No se encontró '25/26' — usando la más reciente: id=%d  (%s)",
                fallback, seasons[0].get("name", ""))
    return fallback


# ── Cache de equipos DB ────────────────────────────────────────────────────────

_equipo_cache: dict[str, int] = {}   # nombre_norm → id
_equipo_keys:  list[str]      = []


def _load_equipo_cache():
    global _equipo_cache, _equipo_keys
    if _equipo_cache:
        return
    res = (
        supabase.table("equipos")
        .select("id, nombre")
        .eq("liga_id", DB_LIGA_ID)
        .eq("temporada", DB_TEMPORADA)
        .execute()
    )
    for r in (res.data or []):
        k = _norm(r["nombre"])
        if k:
            _equipo_cache[k] = r["id"]
    _equipo_keys = list(_equipo_cache.keys())
    log.info("  Cache equipos DB: %d entradas → %s", len(_equipo_cache), sorted(_equipo_cache.keys()))


def _resolve_equipo(nombre_ss: str) -> Optional[int]:
    """
    Resuelve nombre Sofascore → equipo_id de nuestra DB.
    Cascada: alias manual → exacto normalizado → difflib (cutoff 0.72).
    """
    if not nombre_ss:
        return None
    _load_equipo_cache()
    n = _norm(nombre_ss)

    # 1. Alias manual
    alias = SS_ALIASES.get(n)
    if alias:
        n_alias = _norm(alias)
        if n_alias in _equipo_cache:
            return _equipo_cache[n_alias]

    # 2. Exacto normalizado
    if n in _equipo_cache:
        return _equipo_cache[n]

    # 3. Contención parcial (ej. "brest" en "stade brestois")
    for key, eid in _equipo_cache.items():
        if n in key or key in n:
            return eid

    # 4. difflib
    if _equipo_keys:
        close = difflib.get_close_matches(n, _equipo_keys, n=1, cutoff=0.72)
        if close:
            log.debug("    difflib '%s' → '%s'", n, close[0])
            return _equipo_cache[close[0]]

    log.warning("    ⚠ Equipo no resuelto: '%s' (norm='%s')", nombre_ss, n)
    return None


# ── Diagnóstico de partidos nulos ─────────────────────────────────────────────

def load_null_partidos() -> list[dict]:
    """Carga y loguea los partidos sin resultado. Devuelve la lista de filas."""
    log.info("[1] Cargando partidos sin resultado en Supabase (Ligue 1 %s)...", DB_TEMPORADA)
    res = (
        supabase.table("partidos")
        .select("id, equipo_local, equipo_visitante, jornada")
        .eq("liga_id", DB_LIGA_ID)
        .eq("temporada", DB_TEMPORADA)
        .is_("goles_local", "null")
        .execute()
    )
    rows = res.data or []
    log.info("  %d partidos con goles nulos.", len(rows))

    all_eq_ids = {r["equipo_local"] for r in rows} | {r["equipo_visitante"] for r in rows}
    eq_names: dict[int, str] = {}
    if all_eq_ids:
        eq_res = (
            supabase.table("equipos")
            .select("id, nombre")
            .in_("id", list(all_eq_ids))
            .execute()
        )
        eq_names = {e["id"]: e["nombre"] for e in (eq_res.data or [])}

    log.info("  Detalle:")
    for r in sorted(rows, key=lambda x: x["jornada"] or 0):
        log.info("    id=%-6d  J%-3s  %s vs %s",
                 r["id"], r["jornada"] or "?",
                 eq_names.get(r["equipo_local"],  f"eq#{r['equipo_local']}"),
                 eq_names.get(r["equipo_visitante"], f"eq#{r['equipo_visitante']}"))
    return rows


# ── Fetch de jornadas ─────────────────────────────────────────────────────────

def fetch_round(season_id: int, jornada: int) -> list[dict]:
    data = _get(f"unique-tournament/{TOURNAMENT_ID}/season/{season_id}/events/round/{jornada}")
    return (data or {}).get("events", [])


def parse_event(raw: dict) -> Optional[dict]:
    """
    Extrae del evento Sofascore:
      - equipo_local_nombre, equipo_visitante_nombre
      - jornada
      - goles_local, goles_visitante  (solo si estado=finished)
      - finished: bool
    """
    status     = raw.get("status", {})
    estado_ss  = status.get("type", "notstarted")
    finished   = (estado_ss == "finished")

    home       = raw.get("homeTeam", {})
    away       = raw.get("awayTeam", {})
    home_score = raw.get("homeScore", {})
    away_score = raw.get("awayScore", {})
    round_info = raw.get("roundInfo", {})

    if finished:
        # normaltime es el resultado al final del tiempo reglamentario
        goles_local = (
            home_score.get("normaltime")
            if home_score.get("normaltime") is not None
            else home_score.get("current")
        )
        goles_visit = (
            away_score.get("normaltime")
            if away_score.get("normaltime") is not None
            else away_score.get("current")
        )
    else:
        goles_local = None
        goles_visit = None

    return {
        "home_nombre": home.get("name", ""),
        "away_nombre": away.get("name", ""),
        "jornada":     round_info.get("round"),
        "goles_local": goles_local,
        "goles_visit": goles_visit,
        "finished":    finished,
    }


# ── Actualización directa en Supabase ────────────────────────────────────────

def update_partido_directo(
    loc_id: int, vis_id: int, jornada: Optional[int],
    goles_local: int, goles_visit: int
) -> int:
    """
    UPDATE directo con todos los filtros. Devuelve nº de filas actualizadas.
    Primero intenta con jornada; si no actualiza nada, lo intenta sin jornada.
    """
    payload = {
        "goles_local":     goles_local,
        "goles_visitante": goles_visit,
        "estado":          "jugado",
    }
    base = (
        supabase.table("partidos")
        .update(payload)
        .eq("liga_id",          DB_LIGA_ID)
        .eq("temporada",        DB_TEMPORADA)
        .eq("equipo_local",     loc_id)
        .eq("equipo_visitante", vis_id)
        .is_("goles_local",     "null")
    )

    # Intento 1: con jornada exacta
    if jornada is not None:
        res = base.eq("jornada", jornada).execute()
        if res.data:
            return len(res.data)

    # Intento 2: sin jornada (por si el número de jornada no coincide)
    res2 = (
        supabase.table("partidos")
        .update(payload)
        .eq("liga_id",          DB_LIGA_ID)
        .eq("temporada",        DB_TEMPORADA)
        .eq("equipo_local",     loc_id)
        .eq("equipo_visitante", vis_id)
        .is_("goles_local",     "null")
        .execute()
    )
    return len(res2.data)


# ── Runner principal ───────────────────────────────────────────────────────────

def run(jornada_ini: int = 1, jornada_fin: int = MAX_JORNADA):
    log.info("=" * 60)
    log.info(" Sofascore Ligue 1 Partidos — %s  (J%d → J%d)",
             DB_TEMPORADA, jornada_ini, jornada_fin)
    log.info("=" * 60)

    season_id = SEASON_ID if SEASON_ID is not None else discover_season_id()
    log.info("  season_id=%d  tournament_id=%d  liga_id=%d",
             season_id, TOURNAMENT_ID, DB_LIGA_ID)

    _load_equipo_cache()
    null_rows = load_null_partidos()

    if not null_rows:
        log.info("No hay partidos con goles nulos. Nada que hacer.")
        return

    # Solo procesar las jornadas que tienen filas nulas (más eficiente)
    null_jornadas = sorted(
        j for j in {r["jornada"] for r in null_rows if r["jornada"] is not None}
        if jornada_ini <= j <= jornada_fin
    )
    # Si hay filas sin jornada, incluir todas las jornadas del rango
    has_null_jornada = any(r["jornada"] is None for r in null_rows)
    if has_null_jornada:
        null_jornadas = list(range(jornada_ini, jornada_fin + 1))

    if not null_jornadas:
        log.warning("  Las jornadas nulas (%s) están fuera del rango J%d-J%d.",
                    {r["jornada"] for r in null_rows}, jornada_ini, jornada_fin)
        return

    log.info("  Jornadas a procesar: %s", null_jornadas)

    total_eventos   = 0
    total_ok        = 0
    total_no_match  = 0
    total_no_team   = 0
    jornadas_vacias = 0

    log.info("")
    log.info("[2] Procesando %d jornadas con datos nulos...", len(null_jornadas))

    for jornada in null_jornadas:
        events = fetch_round(season_id, jornada)

        if not events:
            jornadas_vacias += 1
            log.info("  J%-2d — sin datos", jornada)
            if jornadas_vacias >= 3:
                log.info("  3 jornadas vacías consecutivas — fin.")
                break
            time.sleep(REQUEST_DELAY)
            continue

        jornadas_vacias = 0
        ok_jornada = no_match = no_team = 0

        for raw in events:
            ev = parse_event(raw)
            if not ev or not ev["finished"]:
                continue
            if ev["goles_local"] is None or ev["goles_visit"] is None:
                continue

            total_eventos += 1

            loc_id = _resolve_equipo(ev["home_nombre"])
            vis_id = _resolve_equipo(ev["away_nombre"])

            if not loc_id or not vis_id:
                no_team      += 1
                total_no_team += 1
                log.warning("  J%-2d  ⚠ equipo no resuelto: '%s' vs '%s'",
                            jornada, ev["home_nombre"], ev["away_nombre"])
                continue

            # UPDATE directo con fallback sin jornada
            try:
                n = update_partido_directo(
                    loc_id, vis_id, ev["jornada"],
                    ev["goles_local"], ev["goles_visit"],
                )
            except Exception as e:
                log.warning("  J%-2d  Error UPDATE '%s' vs '%s': %s",
                            jornada, ev["home_nombre"], ev["away_nombre"], e)
                n = 0

            if n > 0:
                ok_jornada   += 1
                total_ok     += 1
                log.info("  J%-2d  ✓ %s %d-%d %s",
                         jornada,
                         ev["home_nombre"], ev["goles_local"],
                         ev["goles_visit"], ev["away_nombre"])
            else:
                no_match      += 1
                total_no_match += 1
                log.debug("  J%-2d  sin fila DB: '%s' vs '%s'  (loc=%d vis=%d j=%s)",
                          jornada, ev["home_nombre"], ev["away_nombre"],
                          loc_id, vis_id, ev["jornada"])

        log.info("  J%-2d — eventos=%d  OK=%d  sin_match=%d  sin_equipo=%d",
                 jornada, len(events), ok_jornada, no_match, no_team)
        time.sleep(REQUEST_DELAY)

    # ── Verificación final ────────────────────────────────────────────────────
    log.info("")
    log.info("[VERIFY] Partidos con goles nulos restantes...")
    res = (
        supabase.table("partidos")
        .select("id", count="exact")
        .eq("liga_id",  DB_LIGA_ID)
        .eq("temporada", DB_TEMPORADA)
        .is_("goles_local", "null")
        .execute()
    )
    restantes = res.count or 0
    log.info("  Todavía sin resultado: %d", restantes)
    if restantes:
        log.warning("  → Revisa el log de diagnóstico [1] para ver qué equipos/jornadas son.")
        if total_no_team:
            log.warning("  → Añade aliases en SS_ALIASES para los ⚠ y vuelve a ejecutar.")

    log.info("")
    log.info("=" * 60)
    log.info(" RESUMEN")
    log.info("  Jornadas procesadas     : %d", len(null_jornadas))
    log.info("  Eventos finalizados SS  : %d", total_eventos)
    log.info("  Partidos actualizados   : %d", total_ok)
    log.info("  Sin coincidencia en DB  : %d", total_no_match)
    log.info("  Equipo no resuelto      : %d", total_no_team)
    log.info("  Todavía sin resultado   : %d", restantes)
    log.info("=" * 60)


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 0:
        run()
    elif len(args) == 1:
        j = int(args[0])
        run(j, j)
    else:
        run(int(args[0]), int(args[1]))
