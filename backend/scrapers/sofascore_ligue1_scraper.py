"""
Sofascore Stats Scraper — regates y pases% para Ligue 1 2025/26

Campos obtenidos:
  successfulDribbles       -> regates
  accuratePassesPercentage -> pases_completados

Si SEASON_ID es None, se descubre automaticamente desde la API de Sofascore
buscando la temporada "25/26" del torneo 34 (Ligue 1).

Uso (desde backend/):
  conda activate xcout
  python scrapers/sofascore_ligue1_scraper.py
"""

import sys
import time
import logging
import unicodedata
from pathlib import Path

from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

SESSION = requests.Session(impersonate="chrome120")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

TOURNAMENT_ID = 34      # Ligue 1 en Sofascore
SEASON_ID     = None    # Se descubre automaticamente si es None
DB_LIGA_ID    = 27
DB_TEMPORADA  = "2526"
PAGE_SIZE     = 100
REQUEST_DELAY = 0.8

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


def _get_with_retry(url, params=None, retries=3, timeout=30):
    for attempt in range(retries):
        try:
            r = SESSION.get(url, headers=HEADERS, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            log.warning("  Intento %d/%d fallido: %s", attempt + 1, retries, e)
            if attempt < retries - 1:
                time.sleep(5)
    raise RuntimeError(f"No se pudo conectar a {url} tras {retries} intentos")


def discover_season_id() -> int:
    url = f"{API}/unique-tournament/{TOURNAMENT_ID}/seasons"
    log.info("[season] Consultando temporadas Ligue 1 en Sofascore...")
    r = _get_with_retry(url)


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
    log.warning("  No se encontro '25/26' -- usando la primera: id=%d  (%s)",
                fallback, seasons[0].get("name", ""))
    return fallback


def fetch_all_stats(season_id: int) -> list[dict]:
    log.info("[1/4] Descargando stats de temporada desde Sofascore Ligue 1...")
    url    = f"{API}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/statistics"
    params = {
        "limit":        PAGE_SIZE,
        "order":        "-goals",
        "accumulation": "total",
        "group":        "summary",
    }

    r = _get_with_retry(url, params={**params, "offset": 0})
    data        = r.json()
    total_pages = data.get("pages", 1)
    results     = data.get("results", [])
    log.info("      Paginas totales: %d  (~%d jugadores)", total_pages, total_pages * PAGE_SIZE)

    for page in range(1, total_pages):
        time.sleep(REQUEST_DELAY)
        try:
            r = _get_with_retry(url, params={**params, "offset": page * PAGE_SIZE})
        except Exception:
            log.warning("      Pagina %d fallida -- saltando", page)
            continue
        results.extend(r.json().get("results", []))
        if page % 5 == 0:
            log.info("      Pagina %d/%d (%d registros)", page, total_pages, len(results))

    log.info("      Total registros Sofascore: %d", len(results))
    return results


def build_ss_index(ss_rows: list[dict]) -> tuple[dict, dict]:
    exact  = {}
    byname = {}

    for r in ss_rows:
        jugador  = r.get("player") or {}
        equipo   = r.get("team")   or {}
        nombre_n = _norm(jugador.get("name", ""))
        equipo_n = _norm(equipo.get("name", ""))

        stats = {
            "regates": r.get("successfulDribbles"),
            "pases_completados": (
                round(r["accuratePassesPercentage"])
                if r.get("accuratePassesPercentage") is not None else None
            ),
        }
        exact[(nombre_n, equipo_n)] = stats
        byname[nombre_n] = stats

    return exact, byname


def load_supabase_stats() -> list[dict]:
    log.info("[2/4] Leyendo estadisticas existentes en Supabase Ligue 1...")
    res = (
        supabase.table("estadisticas_jugador")
        .select(
            "jugador_id, temporada, liga_id, "
            "goles, asistencias, xg, xa, minutos, "
            "pases_completados, regates, presiones, recuperaciones, "
            "intercepciones, entradas, "
            "goles_por_90, asistencias_por_90, ga_por_90, "
            "jugadores(nombre, equipos(nombre))"
        )
        .eq("temporada", DB_TEMPORADA)
        .eq("liga_id", DB_LIGA_ID)
        .execute()
    )
    rows = []
    for r in res.data:
        jug = r.get("jugadores") or {}
        eq  = (jug.get("equipos") or {})
        rows.append({
            **r,
            "nombre_norm": _norm(jug.get("nombre", "")),
            "equipo_norm": _norm(eq.get("nombre", "")),
        })
    log.info("      %d filas en Supabase.", len(rows))
    return rows


def merge_stats(supa_rows: list[dict], exact: dict, byname: dict) -> list[dict]:
    log.info("[3/4] Cruzando nombres Supabase <-> Sofascore...")
    matched_exact = matched_name = unmatched = 0
    rows_to_update = []

    for r in supa_rows:
        key = (r["nombre_norm"], r["equipo_norm"])
        if key in exact:
            ss = exact[key]
            matched_exact += 1
        elif r["nombre_norm"] in byname:
            ss = byname[r["nombre_norm"]]
            matched_name += 1
        else:
            unmatched += 1
            continue

        if ss["regates"] is None and ss["pases_completados"] is None:
            continue

        rows_to_update.append({
            "jugador_id":         r["jugador_id"],
            "temporada":          r["temporada"],
            "liga_id":            r["liga_id"],
            "regates":            ss["regates"],
            "pases_completados":  ss["pases_completados"],
            "goles":              r.get("goles"),
            "asistencias":        r.get("asistencias"),
            "xg":                 r.get("xg"),
            "xa":                 r.get("xa"),
            "minutos":            r.get("minutos"),
            "presiones":          r.get("presiones"),
            "recuperaciones":     r.get("recuperaciones"),
            "intercepciones":     r.get("intercepciones"),
            "entradas":           r.get("entradas"),
            "goles_por_90":       r.get("goles_por_90"),
            "asistencias_por_90": r.get("asistencias_por_90"),
            "ga_por_90":          r.get("ga_por_90"),
        })

    log.info("      Match exacto (nombre+equipo): %d", matched_exact)
    log.info("      Match por nombre solo        : %d", matched_name)
    log.info("      Sin match                    : %d", unmatched)
    log.info("      Filas a actualizar           : %d", len(rows_to_update))
    return rows_to_update


def upsert_stats(rows: list[dict]) -> int:
    log.info("[4/4] Actualizando regates y pases%% en Supabase Ligue 1...")
    if not rows:
        log.info("      Nada que actualizar.")
        return 0

    res = (
        supabase.table("estadisticas_jugador")
        .upsert(rows, on_conflict="jugador_id,temporada,liga_id")
        .execute()
    )
    ok = len(res.data)
    log.info("      %d filas actualizadas.", ok)
    return ok


def verify():
    log.info("")
    log.info("[VERIFY] Jugadores clave Ligue 1:")
    for name in ("Greenwood", "Thauvin", "Tolisso"):
        res = (supabase.table("jugadores").select("id, nombre")
               .ilike("nombre", f"%{name}%").limit(1).execute())
        if not res.data:
            log.info("  %-25s -> no en DB", name)
            continue
        jid = res.data[0]["id"]
        nom = res.data[0]["nombre"]
        est = (supabase.table("estadisticas_jugador")
               .select("regates, pases_completados, xg, goles")
               .eq("jugador_id", jid).eq("temporada", DB_TEMPORADA)
               .eq("liga_id", DB_LIGA_ID).execute())
        if est.data:
            d = est.data[0]
            log.info("  %-25s  reg=%-4s  pases%%=%-5s  xG=%s  goles=%s",
                     nom, d.get("regates"), d.get("pases_completados"),
                     d.get("xg"), d.get("goles"))
        else:
            log.info("  %-25s -> sin stats Ligue 1", nom)


def run():
    season_id = SEASON_ID if SEASON_ID is not None else discover_season_id()

    log.info("=" * 60)
    log.info(" Sofascore Ligue 1 Stats Scraper -- %s", DB_TEMPORADA)
    log.info(" tournament=%d  season=%d  liga_id=%d", TOURNAMENT_ID, season_id, DB_LIGA_ID)
    log.info("=" * 60)

    ss_rows        = fetch_all_stats(season_id)
    exact, byname  = build_ss_index(ss_rows)
    supa_rows      = load_supabase_stats()
    rows_to_update = merge_stats(supa_rows, exact, byname)
    updated        = upsert_stats(rows_to_update)

    verify()

    log.info("")
    log.info("=" * 60)
    log.info(" RESUMEN")
    log.info("  Jugadores en Sofascore  : %d", len(ss_rows))
    log.info("  Jugadores en Supabase   : %d", len(supa_rows))
    log.info("  Actualizados            : %d", updated)
    log.info("=" * 60)


if __name__ == "__main__":
    run()
