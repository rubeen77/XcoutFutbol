"""
Sofascore Stats Scraper — regates y pases% para Bundesliga 2025/26

Campos obtenidos:
  successfulDribbles       -> regates
  accuratePassesPercentage -> pases_completados

Si SEASON_ID es None, se descubre automaticamente desde la API de Sofascore
buscando la temporada "25/26" del torneo 35 (Bundesliga).

Uso (desde backend/):
  python scrapers/sofascore_bundesliga_scraper.py
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

TOURNAMENT_ID = 35      # Bundesliga en Sofascore
SEASON_ID     = None    # Se descubre automaticamente si es None
DB_LIGA_ID    = 25
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


def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


# --- Descubrimiento del season_id --------------------------------------------

def discover_season_id() -> int:
    """
    Llama a /unique-tournament/{TOURNAMENT_ID}/seasons y devuelve el id
    de la temporada 2025/26 (nombre contiene '25/26' o '2025').
    """
    url = f"{API}/unique-tournament/{TOURNAMENT_ID}/seasons"
    log.info("[season] Consultando temporadas Bundesliga en Sofascore...")
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

    # Fallback: la primera temporada (la mas reciente en Sofascore)
    fallback = seasons[0]["id"]
    log.warning("  No se encontro '25/26' — usando la primera: id=%d  (%s)",
                fallback, seasons[0].get("name", ""))
    return fallback


# --- Fetch de stats -----------------------------------------------------------

def fetch_all_stats(season_id: int) -> list[dict]:
    log.info("[1/4] Descargando stats de temporada desde Sofascore Bundesliga...")
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
    log.info("      Paginas totales: %d  (~%d jugadores)", total_pages, total_pages * PAGE_SIZE)

    for page in range(1, total_pages):
        time.sleep(REQUEST_DELAY)
        r = SESSION.get(url, headers=HEADERS, params={**params, "offset": page * PAGE_SIZE}, timeout=15)
        if r.status_code != 200:
            log.warning("      HTTP %d en pagina %d -- saltando", r.status_code, page)
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


# --- Carga desde Supabase ----------------------------------------------------

def load_supabase_stats() -> list[dict]:
    log.info("[2/4] Leyendo estadisticas existentes en Supabase Bundesliga...")
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


# --- Cruce y merge -----------------------------------------------------------

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


# --- Upsert ------------------------------------------------------------------

def upsert_stats(rows: list[dict]) -> int:
    log.info("[4/4] Actualizando regates y pases%% en Supabase Bundesliga...")
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


# --- Verificacion ------------------------------------------------------------

def verify():
    log.info("")
    log.info("[VERIFY] Jugadores clave Bundesliga:")
    for name in ("Kane", "Kimmich", "Musiala"):
        res = (supabase.table("jugadores").select("id, nombre")
               .ilike("nombre", f"%{name}%").limit(1).execute())
        if not res.data:
            log.info("  %-25s -> no en DB", name)
            continue
        jid = res.data[0]["id"]
        nom = res.data[0]["nombre"]
        est = (supabase.table("estadisticas_jugador")
               .select("regates, pases_completados, intercepciones, entradas, xg, goles")
               .eq("jugador_id", jid).eq("temporada", DB_TEMPORADA)
               .eq("liga_id", DB_LIGA_ID).execute())
        if est.data:
            d = est.data[0]
            log.info("  %-25s  reg=%-4s  pases%%=%-5s  int=%-4s  entr=%-4s  xG=%s",
                     nom, d.get("regates"), d.get("pases_completados"),
                     d.get("intercepciones"), d.get("entradas"), d.get("xg"))
        else:
            log.info("  %-25s -> sin stats Bundesliga", nom)


# --- Entrypoint --------------------------------------------------------------

def run():
    season_id = SEASON_ID if SEASON_ID is not None else discover_season_id()

    log.info("=" * 60)
    log.info(" Sofascore Bundesliga Stats Scraper -- %s", DB_TEMPORADA)
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
