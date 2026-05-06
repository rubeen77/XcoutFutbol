"""
Sofascore Stats Scraper — regates y pases% para Premier League 2025/26

Campos obtenidos:
  successfulDribbles       -> regates
  accuratePassesPercentage -> pases_completados

Uso (desde backend/):
  python scrapers/sofascore_pl_scraper.py
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

TOURNAMENT_ID = 17       # Premier League en Sofascore
SEASON_ID     = 76986   # Premier League 25/26
DB_LIGA_ID    = 24
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


def fetch_all_stats() -> list[dict]:
    log.info("[1/4] Descargando stats de temporada desde Sofascore PL...")
    url    = f"{API}/unique-tournament/{TOURNAMENT_ID}/season/{SEASON_ID}/statistics"
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


def load_supabase_stats() -> list[dict]:
    log.info("[2/4] Leyendo estadisticas existentes en Supabase PL...")
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
    log.info("[4/4] Actualizando regates y pases%% en Supabase PL (batch unico)...")
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
    log.info("[VERIFY] Jugadores clave PL:")
    for name in ("Haaland", "Salah", "Bruno Fernandes"):
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
            log.info("  %-25s -> sin stats PL", nom)


def run():
    log.info("=" * 60)
    log.info(" Sofascore PL Stats Scraper -- Premier League %s", DB_TEMPORADA)
    log.info(" tournament=%d  season=%d  liga_id=%d", TOURNAMENT_ID, SEASON_ID, DB_LIGA_ID)
    log.info("=" * 60)

    ss_rows        = fetch_all_stats()
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
