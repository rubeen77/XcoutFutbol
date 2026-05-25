"""
Sofascore Champions League — detalle individual por jugador (liga_id=28)

Obtiene minutesPlayed, expectedAssists y calcula per-90 llamando al
endpoint individual de cada jugador de la UCL.

Endpoint individual:
  GET /api/v1/player/{ss_player_id}/unique-tournament/7/season/{season_id}/statistics/overall

Flujo:
  1. Descubrir season_id 25/26 automaticamente
  2. Descargar lista paginada de stats (group=summary) para extraer
     los sofascore_player_id de cada jugador
  3. Cargar jugadores UCL desde Supabase y cruzar por nombre normalizado
  4. Por cada jugador cruzado, llamar al endpoint individual
  5. Extraer: minutesPlayed, expectedAssists
  6. Calcular goles_por_90, asistencias_por_90, ga_por_90
  7. Upsert en estadisticas_jugador (preserva campos existentes)

Tiempo estimado: ~25 min para 878 jugadores con delay de 1.5s

Uso (desde backend/):
  conda activate xcout
  python scrapers/sofascore_champions_detalle.py
"""

import sys
import time
import logging
import unicodedata
from pathlib import Path

from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

SESSION = requests.Session(impersonate="chrome124")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

TOURNAMENT_ID  = 7
SEASON_ID      = None   # se descubre automaticamente
DB_LIGA_ID     = 28
DB_TEMPORADA   = "2526"
PAGE_SIZE      = 100
DELAY          = 1.5    # segundos entre peticiones individuales
DELAY_LIST     = 0.8    # segundos entre paginas del listado
BATCH_UPSERT   = 50     # filas por upsert

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":  "application/json",
    "Referer": "https://www.sofascore.com/",
}

API = "https://api.sofascore.com/api/v1"

_CHAR_MAP = str.maketrans({
    'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G',
    'ş': 's', 'Ş': 'S', 'ð': 'd', 'Ð': 'D',
    'þ': 'th', 'ø': 'o', 'Ø': 'O',
    'æ': 'ae', 'Æ': 'Ae', 'ł': 'l', 'Ł': 'L',
    'ß': 'ss', "'": '', '‘': '', '’': '',
    '-': ' ', '–': ' ', '—': ' ',
})


def _norm(text: str) -> str:
    if not text:
        return ""
    text = str(text).translate(_CHAR_MAP)
    nfkd = unicodedata.normalize("NFKD", text)
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def _safe_int(v) -> "int | None":
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _safe_float(v, dec: int = 2) -> "float | None":
    if v is None:
        return None
    try:
        return round(float(v), dec)
    except (TypeError, ValueError):
        return None


def _per90(value, minutos) -> "float | None":
    if value is None or minutos is None or minutos < 1:
        return None
    return round(value / (minutos / 90.0), 3)


# ---------------------------------------------------------------------------
# Paso 1: Descubrir season_id
# ---------------------------------------------------------------------------

def discover_season_id() -> int:
    url = f"{API}/unique-tournament/{TOURNAMENT_ID}/seasons"
    log.info("[season] Buscando season_id 25/26 para Champions League...")
    r = SESSION.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()

    for s in r.json().get("seasons", []):
        name = s.get("name", "")
        if "25/26" in name or "2025" in name:
            log.info("  -> season_id=%d  (%s)", s["id"], name)
            return s["id"]

    fallback = r.json()["seasons"][0]["id"]
    log.warning("  No se encontro '25/26' — usando primera: id=%d", fallback)
    return fallback


# ---------------------------------------------------------------------------
# Paso 2: Mapa nombre_norm -> sofascore_player_id desde la lista paginada
# ---------------------------------------------------------------------------

def build_ss_id_map(season_id: int) -> dict[str, int]:
    """
    Descarga la lista paginada de stats (group=summary) y devuelve
    {nombre_norm: sofascore_player_id}.
    Si un jugador aparece en varios equipos (transferencia), se guarda
    el último registro (más minutos suele estar al final).
    """
    log.info("[1/4] Descargando lista de jugadores Sofascore para extraer IDs...")
    url    = f"{API}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/statistics"
    params = {
        "limit":        PAGE_SIZE,
        "order":        "-rating",
        "accumulation": "total",
        "group":        "summary",
    }

    r = SESSION.get(url, headers=HEADERS, params={**params, "offset": 0}, timeout=15)
    r.raise_for_status()
    data        = r.json()
    total_pages = data.get("pages", 1)
    all_rows    = data.get("results", [])

    for page in range(1, total_pages):
        time.sleep(DELAY_LIST)
        r = SESSION.get(url, headers=HEADERS,
                        params={**params, "offset": page * PAGE_SIZE}, timeout=15)
        if r.status_code != 200:
            log.warning("  HTTP %d en pagina %d — saltando", r.status_code, page)
            continue
        all_rows.extend(r.json().get("results", []))

    # nombre_norm -> ss_player_id  y  (nombre_norm, equipo_norm) -> ss_player_id
    exact_map: dict[tuple, int] = {}
    name_map:  dict[str, int]   = {}

    for row in all_rows:
        jugador = row.get("player") or {}
        equipo  = row.get("team")   or {}
        ss_id   = jugador.get("id")
        nombre  = jugador.get("name", "")
        if not ss_id or not nombre:
            continue
        nn = _norm(nombre)
        en = _norm(equipo.get("name", ""))
        exact_map[(nn, en)] = ss_id
        name_map[nn] = ss_id  # el ultimo gana (no importa para este caso)

    log.info("  %d jugadores con ID en Sofascore (de %d filas)", len(name_map), len(all_rows))
    return exact_map, name_map


# ---------------------------------------------------------------------------
# Paso 3: Cargar jugadores UCL desde Supabase
# ---------------------------------------------------------------------------

def load_supabase_players() -> list[dict]:
    """
    Devuelve lista de dicts con:
      jugador_id, goles, asistencias, nombre_norm, equipo_norm
    """
    log.info("[2/4] Cargando jugadores UCL desde Supabase...")
    res = (
        supabase.table("estadisticas_jugador")
        .select(
            "jugador_id, goles, asistencias, "
            "jugadores(nombre, equipos(nombre))"
        )
        .eq("temporada", DB_TEMPORADA)
        .eq("liga_id", DB_LIGA_ID)
        .execute()
    )

    players = []
    for r in (res.data or []):
        jug = r.get("jugadores") or {}
        eq  = jug.get("equipos") or {}
        players.append({
            "jugador_id":  r["jugador_id"],
            "goles":       r.get("goles") or 0,
            "asistencias": r.get("asistencias") or 0,
            "nombre_norm": _norm(jug.get("nombre", "")),
            "equipo_norm": _norm(eq.get("nombre", "")),
        })

    log.info("  %d jugadores en Supabase.", len(players))
    return players


# ---------------------------------------------------------------------------
# Paso 4: Peticion individual por jugador
# ---------------------------------------------------------------------------

def fetch_player_stats(ss_player_id: int, season_id: int) -> dict:
    """
    Llama al endpoint individual y devuelve el dict de statistics.
    Devuelve {} si hay error o la respuesta no tiene datos.
    """
    url = f"{API}/player/{ss_player_id}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/statistics/overall"
    try:
        r = SESSION.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json().get("statistics") or {}
    except Exception as e:
        log.warning("  Error player_id=%d: %s", ss_player_id, e)
        return {}


# ---------------------------------------------------------------------------
# Paso 5: Loop principal y upsert
# ---------------------------------------------------------------------------

def run():
    season_id = SEASON_ID if SEASON_ID is not None else discover_season_id()

    log.info("=" * 68)
    log.info(" UCL Detalle Individual — liga_id=%d  temporada=%s", DB_LIGA_ID, DB_TEMPORADA)
    log.info(" tournament_id=%d  season_id=%d", TOURNAMENT_ID, season_id)
    log.info("=" * 68)

    exact_map, name_map = build_ss_id_map(season_id)
    players             = load_supabase_players()

    log.info("[3/4] Consultando endpoint individual por jugador...")
    log.info("  Total jugadores: %d | delay: %.1fs | estimado: ~%.0f min",
             len(players), DELAY, len(players) * DELAY / 60)

    rows_ok    = []
    sin_ss_id  = 0
    sin_datos  = 0
    sin_min    = 0

    for i, p in enumerate(players, 1):
        # Resolver sofascore_player_id
        ss_id = (
            exact_map.get((p["nombre_norm"], p["equipo_norm"])) or
            name_map.get(p["nombre_norm"])
        )
        if not ss_id:
            sin_ss_id += 1
            continue

        time.sleep(DELAY)
        stats = fetch_player_stats(ss_id, season_id)

        if not stats:
            sin_datos += 1
            continue

        minutos = _safe_int(stats.get("minutesPlayed"))
        if minutos is None:
            sin_min += 1
            # Aun asi guardamos xa si esta disponible
            xa = _safe_float(stats.get("expectedAssists"))
            if xa is None:
                continue
            rows_ok.append({
                "jugador_id": p["jugador_id"],
                "temporada":  DB_TEMPORADA,
                "liga_id":    DB_LIGA_ID,
                "xa":         xa,
            })
            continue

        goles       = p["goles"]
        asistencias = p["asistencias"]
        xa          = _safe_float(stats.get("expectedAssists"))
        ga_raw      = (
            (goles or 0) + (asistencias or 0)
            if (goles is not None or asistencias is not None) else None
        )

        rows_ok.append({
            "jugador_id":         p["jugador_id"],
            "temporada":          DB_TEMPORADA,
            "liga_id":            DB_LIGA_ID,
            "minutos":            minutos,
            "xa":                 xa,
            "goles_por_90":       _per90(goles,       minutos),
            "asistencias_por_90": _per90(asistencias, minutos),
            "ga_por_90":          _per90(ga_raw,      minutos),
        })

        if i % 50 == 0:
            log.info("  Progreso: %d/%d  (ok=%d, sin_id=%d, sin_datos=%d)",
                     i, len(players), len(rows_ok), sin_ss_id, sin_datos)

    log.info("  Completado: %d con datos | %d sin SS ID | %d sin datos API | %d sin minutos",
             len(rows_ok), sin_ss_id, sin_datos, sin_min)

    # --- Upsert en Supabase ---
    log.info("[4/4] Guardando en Supabase...")
    if not rows_ok:
        log.info("  Nada que guardar.")
        return

    total = 0
    for i in range(0, len(rows_ok), BATCH_UPSERT):
        res = (
            supabase.table("estadisticas_jugador")
            .upsert(rows_ok[i:i + BATCH_UPSERT], on_conflict="jugador_id,temporada,liga_id")
            .execute()
        )
        total += len(res.data)

    log.info("  %d filas actualizadas.", total)

    log.info("")
    log.info("=" * 68)
    log.info(" RESUMEN")
    log.info("  Jugadores procesados  : %d", len(players))
    log.info("  Con datos completos   : %d", len(rows_ok))
    log.info("  Sin Sofascore ID      : %d", sin_ss_id)
    log.info("  Sin respuesta API     : %d", sin_datos)
    log.info("  Sin minutesPlayed     : %d", sin_min)
    log.info("  Filas upsertadas      : %d", total)
    log.info("=" * 68)


if __name__ == "__main__":
    run()
