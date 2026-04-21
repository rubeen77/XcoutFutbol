"""
Sofascore Stats Scraper — regates y pases% para LaLiga 2025/26

FBref (via soccerdata) no expone possession/passing/defense.
FBref directo devuelve 403 (Cloudflare).
Solución: usar el endpoint de estadísticas de temporada de Sofascore.

Campos obtenidos:
  successfulDribbles      → regates
  accuratePassesPercentage → pases_completados  (% de pases completados)

(presiones no está disponible en ninguna fuente gratuita accesible)

Uso:
  python sofascore_stats_scraper.py
"""

import sys
import time
import logging
import unicodedata
from pathlib import Path
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

TOURNAMENT_ID = 8        # LaLiga uniqueTournament en Sofascore
SEASON_ID     = 77559    # LaLiga 25/26
DB_LIGA_ID    = 1
DB_TEMPORADA  = "2526"
PAGE_SIZE     = 100
REQUEST_DELAY = 0.8      # segundos entre páginas

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


# ---------------------------------------------------------------------------
# 1. Descargar todas las estadísticas de temporada desde Sofascore
# ---------------------------------------------------------------------------

def fetch_all_stats() -> list[dict]:
    """
    Pagina por /unique-tournament/{tid}/season/{sid}/statistics
    con group=summary y devuelve todos los registros.
    """
    log.info("[1/4] Descargando stats de temporada desde Sofascore...")
    url    = f"{API}/unique-tournament/{TOURNAMENT_ID}/season/{SEASON_ID}/statistics"
    params = {
        "limit":        PAGE_SIZE,
        "order":        "-goals",
        "accumulation": "total",
        "group":        "summary",
    }

    # Primera página para saber cuántas hay
    r = requests.get(url, headers=HEADERS, params={**params, "offset": 0}, timeout=15)
    r.raise_for_status()
    data  = r.json()
    total_pages = data.get("pages", 1)
    results     = data.get("results", [])
    log.info("      Páginas totales: %d  (~%d jugadores)", total_pages, total_pages * PAGE_SIZE)

    for page in range(1, total_pages):
        time.sleep(REQUEST_DELAY)
        r = requests.get(url, headers=HEADERS, params={**params, "offset": page * PAGE_SIZE}, timeout=15)
        if r.status_code != 200:
            log.warning("      HTTP %d en página %d — saltando", r.status_code, page)
            continue
        results.extend(r.json().get("results", []))
        if page % 10 == 0:
            log.info("      Página %d/%d (%d registros)", page, total_pages, len(results))

    log.info("      Total registros Sofascore: %d", len(results))
    return results


def build_ss_index(ss_rows: list[dict]) -> tuple[dict, dict]:
    """Índice {nombre_norm: {regates, pases_pct}} con fallback por nombre solo."""
    exact  = {}   # (nombre_norm, equipo_norm) → stats
    byname = {}   # nombre_norm → stats  (último gana si hay duplicados)

    for r in ss_rows:
        jugador = r.get("player") or {}
        equipo  = r.get("team")   or {}
        nombre_n = _norm(jugador.get("name", ""))
        equipo_n = _norm(equipo.get("name", ""))

        stats = {
            "regates":          r.get("successfulDribbles"),
            "pases_completados": (
                round(r["accuratePassesPercentage"])
                if r.get("accuratePassesPercentage") is not None else None
            ),
        }
        exact[(nombre_n, equipo_n)] = stats
        byname[nombre_n] = stats

    return exact, byname


# ---------------------------------------------------------------------------
# 2. Leer jugadores existentes en Supabase
# ---------------------------------------------------------------------------

def load_supabase_stats() -> list[dict]:
    log.info("[2/4] Leyendo estadísticas existentes en Supabase...")
    res = (
        supabase.table("estadisticas_jugador")
        .select(
            "jugador_id, temporada, liga_id, "
            "goles, asistencias, xg, xa, minutos, "
            "pases_completados, regates, presiones, recuperaciones, "
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


# ---------------------------------------------------------------------------
# 3. Cruce y merge
# ---------------------------------------------------------------------------

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
            # Campos a actualizar
            "regates":            ss["regates"],
            "pases_completados":  ss["pases_completados"],
            # Preservar todos los campos existentes
            "goles":              r.get("goles"),
            "asistencias":        r.get("asistencias"),
            "xg":                 r.get("xg"),
            "xa":                 r.get("xa"),
            "minutos":            r.get("minutos"),
            "presiones":          r.get("presiones"),
            "recuperaciones":     r.get("recuperaciones"),
            "goles_por_90":       r.get("goles_por_90"),
            "asistencias_por_90": r.get("asistencias_por_90"),
            "ga_por_90":          r.get("ga_por_90"),
        })

    log.info("      Match exacto (nombre+equipo): %d", matched_exact)
    log.info("      Match por nombre solo        : %d", matched_name)
    log.info("      Sin match                    : %d", unmatched)
    log.info("      Filas a actualizar           : %d", len(rows_to_update))
    return rows_to_update


# ---------------------------------------------------------------------------
# 4. Upsert en Supabase
# ---------------------------------------------------------------------------

def upsert_stats(rows: list[dict]) -> int:
    log.info("[4/4] Actualizando regates y pases%% en Supabase (batch unico)...")
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


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 56)
    log.info(" Sofascore Stats Scraper -- LaLiga %s", DB_TEMPORADA)
    log.info(" Campos: regates (successfulDribbles), pases%% (accuratePassesPercentage)")
    log.info("=" * 56)

    ss_rows           = fetch_all_stats()
    exact, byname     = build_ss_index(ss_rows)
    supa_rows         = load_supabase_stats()
    rows_to_update    = merge_stats(supa_rows, exact, byname)
    updated           = upsert_stats(rows_to_update)

    log.info("=" * 56)
    log.info(" RESUMEN")
    log.info("  Jugadores en Sofascore  : %d", len(ss_rows))
    log.info("  Jugadores en Supabase   : %d", len(supa_rows))
    log.info("  Actualizados            : %d", updated)
    log.info("=" * 56)


if __name__ == "__main__":
    run()
