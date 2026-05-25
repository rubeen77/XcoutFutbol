"""
Champions League Scraper — Sofascore como fuente principal (liga_id=28)

Fases:
  1. Descubrir season_id 25/26 automaticamente desde la API de Sofascore
  2. Descargar stats de jugadores (group=summary): goles, asistencias,
     minutos, regates, pases%, entradas, intercepciones, xG, xA
  3. Upsert equipos en Supabase (liga_id=28, temporada='2526')
  4. Upsert jugadores en Supabase
  5. Upsert estadisticas_jugador con per-90 calculados

Uso (desde backend/):
  conda activate xcout
  python scrapers/fbref_champions.py
"""

import sys
import time
import logging
import unicodedata
from datetime import datetime
from pathlib import Path

from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

SESSION = requests.Session(impersonate="chrome124")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

TOURNAMENT_ID = 7       # Champions League en Sofascore
SEASON_ID     = None    # Se descubre automaticamente si es None
DB_LIGA_ID    = 28
DB_TEMPORADA  = "2526"
LIGA_NOMBRE   = "Champions League"
LIGA_PAIS     = "Europa"
MIN_MINUTOS   = 90      # Minutos minimos para insertar estadisticas
PAGE_SIZE     = 100
REQUEST_DELAY = 0.8
FETCH_AGES    = True   # False para omitir en runs rutinarios (edades cambian poco)
DELAY_AGES    = 1.0    # segundos entre peticiones /player/{id}

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

SS_POS_MAP = {
    "G": "Portero",
    "D": "Defensa Central",
    "M": "Centrocampista",
    "F": "Delantero",
}


# --- Helpers ------------------------------------------------------------------

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
    if value is None or minutos is None or minutos < 90:
        return None
    return round(value / (minutos / 90.0), 3)


def _age_from_timestamp(ts) -> "int | None":
    if ts is None:
        return None
    try:
        born  = datetime.fromtimestamp(int(ts))
        today = datetime.today()
        return today.year - born.year - (
            (today.month, today.day) < (born.month, born.day)
        )
    except Exception:
        return None


# --- Fase 1: Descubrimiento del season_id ------------------------------------

def discover_season_id() -> int:
    url = f"{API}/unique-tournament/{TOURNAMENT_ID}/seasons"
    log.info("[season] Consultando temporadas Champions League en Sofascore...")
    r = SESSION.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()

    seasons = r.json().get("seasons", [])
    log.info("  %d temporadas encontradas:", len(seasons))
    for s in seasons[:8]:
        log.info("    id=%-7d  %s", s["id"], s.get("name", ""))

    for s in seasons:
        name = s.get("name", "")
        if "25/26" in name or "2025" in name:
            log.info("  -> Usando season_id=%d  (%s)", s["id"], name)
            return s["id"]

    fallback = seasons[0]["id"]
    log.warning("  No se encontro '25/26' — usando la primera: id=%d  (%s)",
                fallback, seasons[0].get("name", ""))
    return fallback


# --- Fase 2: Descarga de stats -----------------------------------------------

def fetch_all_stats(season_id: int) -> list[dict]:
    log.info("[1/4] Descargando stats desde Sofascore (Champions League, group=summary)...")
    url    = f"{API}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/statistics"
    params = {
        "limit":        PAGE_SIZE,
        "order":        "-goals",
        "accumulation": "total",
        "group":        "summary",
    }

    r = SESSION.get(url, headers=HEADERS, params={**params, "offset": 0}, timeout=15)
    r.raise_for_status()
    data        = r.json()
    total_pages = data.get("pages", 1)
    results     = data.get("results", [])
    log.info("  Paginas totales: %d  (~%d jugadores)", total_pages, total_pages * PAGE_SIZE)

    for page in range(1, total_pages):
        time.sleep(REQUEST_DELAY)
        r = SESSION.get(url, headers=HEADERS, params={**params, "offset": page * PAGE_SIZE}, timeout=15)
        if r.status_code != 200:
            log.warning("  HTTP %d en pagina %d -- saltando", r.status_code, page)
            continue
        results.extend(r.json().get("results", []))
        if page % 5 == 0:
            log.info("  Pagina %d/%d (%d registros)", page, total_pages, len(results))

    log.info("  Total registros Sofascore: %d", len(results))
    return results


# --- Fase 3: Upsert equipos --------------------------------------------------

def upsert_equipos(ss_rows: list[dict]) -> dict[str, int]:
    log.info("[2/4] Procesando equipos...")

    equipos_vistos: dict[str, str] = {}  # nombre_norm -> nombre_original
    for r in ss_rows:
        equipo = r.get("team") or {}
        nombre = equipo.get("name", "")
        if not nombre:
            continue
        nn = _norm(nombre)
        if nn and nn not in equipos_vistos:
            equipos_vistos[nn] = nombre

    rows = [
        {"nombre": nombre, "liga_id": DB_LIGA_ID, "temporada": DB_TEMPORADA}
        for nombre in equipos_vistos.values()
    ]
    log.info("  %d equipos encontrados en Sofascore.", len(rows))

    if not rows:
        log.error("  Sin equipos — abortando.")
        return {}

    supabase.table("equipos").upsert(rows, on_conflict="nombre,liga_id,temporada").execute()

    # Releer para obtener IDs definitivos
    eq_res = (
        supabase.table("equipos")
        .select("id, nombre")
        .eq("liga_id", DB_LIGA_ID)
        .eq("temporada", DB_TEMPORADA)
        .execute()
    )
    equipo_map = {_norm(r["nombre"]): r["id"] for r in (eq_res.data or [])}
    log.info("  %d equipos en Supabase.", len(equipo_map))
    return equipo_map


# --- Fase 4: Upsert jugadores ------------------------------------------------

def upsert_jugadores(ss_rows: list[dict], equipo_map: dict[str, int]) -> "tuple[dict, dict]":
    log.info("[3/4] Procesando jugadores...")

    jugadores_rows = []
    seen: set[tuple] = set()

    for r in ss_rows:
        jugador = r.get("player") or {}
        equipo  = r.get("team")   or {}

        nombre = jugador.get("name", "")
        if not nombre:
            continue

        equipo_id = equipo_map.get(_norm(equipo.get("name", "")))
        if not equipo_id:
            continue

        key = (_norm(nombre), equipo_id)
        if key in seen:
            continue
        seen.add(key)

        posicion = SS_POS_MAP.get(jugador.get("position", ""), jugador.get("position") or None)
        edad     = _age_from_timestamp(jugador.get("dateOfBirthTimestamp"))

        jugadores_rows.append({
            "nombre":    nombre,
            "equipo_id": equipo_id,
            "posicion":  posicion,
            "edad":      edad,
        })

    log.info("  %d jugadores a insertar/actualizar.", len(jugadores_rows))

    BATCH = 100
    for i in range(0, len(jugadores_rows), BATCH):
        supabase.table("jugadores").upsert(
            jugadores_rows[i:i + BATCH],
            on_conflict="nombre,equipo_id",
        ).execute()

    # Construir mapas de resolucion jugador_norm (+ equipo_norm) → jugador_id
    eq_id_to_norm = {v: k for k, v in equipo_map.items()}
    eq_ids        = list(equipo_map.values())
    all_jug       = []
    for i in range(0, len(eq_ids), 50):
        res = (
            supabase.table("jugadores")
            .select("id, nombre, equipo_id")
            .in_("equipo_id", eq_ids[i:i + 50])
            .execute()
        )
        all_jug.extend(res.data or [])

    full_map: dict[tuple, int] = {}
    name_map: dict[str, int]   = {}
    for r in all_jug:
        jid  = r["id"]
        name = _norm(r.get("nombre") or "")
        team = eq_id_to_norm.get(r.get("equipo_id"), "")
        if not name:
            continue
        full_map[(name, team)] = jid
        if name not in name_map:
            name_map[name] = jid

    log.info("  %d jugadores en mapa.", len(name_map))
    return full_map, name_map


# --- Fase extra: Edades via /player/{id} ------------------------------------

def update_edades(
    ss_rows:    list[dict],
    equipo_map: dict[str, int],
    full_map:   dict,
    name_map:   dict,
) -> int:
    """
    El endpoint de stats no incluye dateOfBirthTimestamp.
    Para cada jugador UCL sin edad, llama a /api/v1/player/{ss_id}
    y guarda la edad calculada. Solo procesa los que tienen edad=null.
    """
    log.info("[*] Actualizando edades via Sofascore /player/{id}...")

    # ss_player_id → jugador_id
    ss_to_jid: dict[int, int] = {}
    for r in ss_rows:
        jug   = r.get("player") or {}
        eq    = r.get("team")   or {}
        ss_id = jug.get("id")
        if not ss_id:
            continue
        nn  = _norm(jug.get("name", ""))
        en  = _norm(eq.get("name", ""))
        jid = full_map.get((nn, en)) or name_map.get(nn)
        if jid:
            ss_to_jid[ss_id] = jid

    # Jugadores UCL sin edad en BD
    eq_ids   = list(equipo_map.values())
    sin_edad: set[int] = set()
    for i in range(0, len(eq_ids), 50):
        res = (
            supabase.table("jugadores")
            .select("id")
            .in_("equipo_id", eq_ids[i:i + 50])
            .is_("edad", "null")
            .execute()
        )
        sin_edad.update(r["id"] for r in (res.data or []))

    pendientes = [(ss_id, jid) for ss_id, jid in ss_to_jid.items() if jid in sin_edad]
    log.info("  Sin edad en BD: %d | Con SS ID: %d | Estimado: ~%.0f min",
             len(sin_edad), len(pendientes), len(pendientes) * DELAY_AGES / 60)

    if not pendientes:
        log.info("  Todos los jugadores ya tienen edad. Saltando.")
        return 0

    updates: list[dict] = []
    for i, (ss_id, jid) in enumerate(pendientes, 1):
        time.sleep(DELAY_AGES)
        try:
            r = SESSION.get(f"{API}/player/{ss_id}", headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            player_data = r.json().get("player") or {}
            edad = _age_from_timestamp(player_data.get("dateOfBirthTimestamp"))
            if edad:
                updates.append({"id": jid, "edad": edad})
        except Exception as e:
            log.warning("    player_id=%d error: %s", ss_id, e)

        if i % 50 == 0:
            log.info("    %d/%d procesados  (con edad: %d)", i, len(pendientes), len(updates))

    log.info("  Aplicando UPDATE en Supabase (%d jugadores)...", len(updates))
    ok = 0
    BATCH = 50
    for i in range(0, len(updates), BATCH):
        for row in updates[i:i + BATCH]:
            supabase.table("jugadores").update({"edad": row["edad"]}).eq("id", row["id"]).execute()
            ok += 1
        log.info("    %d/%d actualizados...", min(i + BATCH, len(updates)), len(updates))

    log.info("  Edades actualizadas: %d / %d", ok, len(pendientes))
    return ok


# --- Fase 5: Upsert estadisticas ---------------------------------------------

def build_estadisticas(
    ss_rows:   list[dict],
    full_map:  dict,
    name_map:  dict,
    equipo_map: dict[str, int],
) -> list[dict]:
    rows        = []
    skipped_min = 0
    sin_match   = 0

    for r in ss_rows:
        jugador = r.get("player") or {}
        equipo  = r.get("team")   or {}

        nombre_n = _norm(jugador.get("name", ""))
        equipo_n = _norm(equipo.get("name", ""))

        jid = full_map.get((nombre_n, equipo_n)) or name_map.get(nombre_n)
        if not jid:
            sin_match += 1
            continue

        minutos = _safe_int(r.get("minutesPlayed"))
        if minutos is not None and minutos < MIN_MINUTOS:
            skipped_min += 1
            continue

        goles       = _safe_int(r.get("goals"))
        asistencias = _safe_int(r.get("assists"))
        regates     = _safe_int(r.get("successfulDribbles"))
        entradas    = _safe_int(r.get("tackles"))
        ints        = _safe_int(r.get("interceptions"))
        pases_pct   = (
            round(r["accuratePassesPercentage"])
            if r.get("accuratePassesPercentage") is not None else None
        )
        recuperaciones = (
            (entradas or 0) + (ints or 0)
            if (entradas is not None or ints is not None) else None
        )
        xg = _safe_float(r.get("expectedGoals"))
        xa = _safe_float(r.get("expectedAssists"))

        # G+A para per-90 (None si ambos son None)
        ga_raw = (
            (goles or 0) + (asistencias or 0)
            if (goles is not None or asistencias is not None) else None
        )

        # Campos base que siempre vienen del endpoint summary
        row: dict = {
            "jugador_id":        jid,
            "temporada":         DB_TEMPORADA,
            "liga_id":           DB_LIGA_ID,
            "goles":             goles,
            "asistencias":       asistencias,
            "regates":           regates,
            "pases_completados": pases_pct,
            "entradas":          entradas,
            "xg":                xg,
            "xa":                xa,
        }
        # Solo incluir si no son None: evita sobrescribir con null los valores
        # que sofascore_champions_detalle.py guarda (minutos, per-90, ints)
        if ints           is not None: row["intercepciones"]     = ints
        if recuperaciones is not None: row["recuperaciones"]      = recuperaciones
        if minutos        is not None:
            row["minutos"]            = minutos
            row["goles_por_90"]       = _per90(goles,       minutos)
            row["asistencias_por_90"] = _per90(asistencias, minutos)
            row["ga_por_90"]          = _per90(ga_raw,      minutos)

        rows.append(row)

    log.info("  %d filas stats | %d sin minutos suficientes | %d sin match",
             len(rows), skipped_min, sin_match)
    return rows


def upsert_estadisticas(rows: list[dict]) -> int:
    log.info("[4/4] Guardando estadisticas en Supabase...")
    if not rows:
        log.info("  Nada que insertar.")
        return 0

    # Deduplicar: un registro por jugador_id
    seen: dict[int, int] = {}
    for i, r in enumerate(rows):
        if r["jugador_id"] not in seen:
            seen[r["jugador_id"]] = i
    rows_dedup = [rows[i] for i in seen.values()]

    BATCH = 100
    total = 0
    for i in range(0, len(rows_dedup), BATCH):
        res = (
            supabase.table("estadisticas_jugador")
            .upsert(rows_dedup[i:i + BATCH], on_conflict="jugador_id,temporada,liga_id")
            .execute()
        )
        total += len(res.data)

    log.info("  %d estadisticas guardadas.", total)
    return total


# --- Entrypoint ---------------------------------------------------------------

def run():
    season_id = SEASON_ID if SEASON_ID is not None else discover_season_id()

    log.info("=" * 66)
    log.info(" Champions League Scraper (Sofascore) — liga_id=%d  temporada=%s",
             DB_LIGA_ID, DB_TEMPORADA)
    log.info(" tournament_id=%d  season_id=%d", TOURNAMENT_ID, season_id)
    log.info("=" * 66)

    ss_rows    = fetch_all_stats(season_id)
    equipo_map = upsert_equipos(ss_rows)
    if not equipo_map:
        log.error("Sin equipos. Abortando.")
        return

    full_map, name_map = upsert_jugadores(ss_rows, equipo_map)
    rows_stats         = build_estadisticas(ss_rows, full_map, name_map, equipo_map)
    updated            = upsert_estadisticas(rows_stats)

    edades_ok = 0
    if FETCH_AGES:
        edades_ok = update_edades(ss_rows, equipo_map, full_map, name_map)

    log.info("")
    log.info("=" * 66)
    log.info(" RESUMEN")
    log.info("  Equipos en Supabase     : %d", len(equipo_map))
    log.info("  Jugadores en mapa       : %d", len(name_map))
    log.info("  Estadisticas guardadas  : %d", updated)
    log.info("  Edades actualizadas     : %d", edades_ok)
    log.info("=" * 66)


if __name__ == "__main__":
    run()
