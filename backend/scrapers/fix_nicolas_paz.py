"""
Fix regates/pases% de Nicolás Paz (Serie A 25/26, Como)

Descarga todas las stats de Sofascore para la Serie A 25/26,
busca a Nicolás Paz con la _norm mejorada y hace UPDATE directo en Supabase.

Uso (desde backend/):
  conda activate xcout
  python scrapers/fix_nicolas_paz.py
"""

import sys
import time
import logging
import unicodedata
from pathlib import Path

from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

SESSION       = requests.Session(impersonate="chrome124")
TOURNAMENT_ID = 23
SEASON_ID     = None
DB_LIGA_ID    = 26
DB_TEMPORADA  = "2526"
PAGE_SIZE     = 100
REQUEST_DELAY = 0.8
API           = "https://api.sofascore.com/api/v1"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":  "application/json",
    "Referer": "https://www.sofascore.com/",
}

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


TARGET_NORM = _norm("Nico Paz")   # → "nico paz"


def discover_season_id() -> int:
    url = f"{API}/unique-tournament/{TOURNAMENT_ID}/seasons"
    r   = SESSION.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    seasons = r.json().get("seasons", [])
    for s in seasons:
        name = s.get("name", "")
        if "25/26" in name or "2025" in name:
            log.info("Season encontrado: id=%d  (%s)", s["id"], name)
            return s["id"]
    fallback = seasons[0]["id"]
    log.warning("Usando primera temporada: id=%d  (%s)", fallback, seasons[0].get("name", ""))
    return fallback


def fetch_all_stats(season_id: int) -> list[dict]:
    log.info("Descargando stats Serie A desde Sofascore...")
    url    = f"{API}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/statistics"
    params = {"limit": PAGE_SIZE, "order": "-goals", "accumulation": "total", "group": "summary"}

    r           = SESSION.get(url, headers=HEADERS, params={**params, "offset": 0}, timeout=15)
    r.raise_for_status()
    data        = r.json()
    total_pages = data.get("pages", 1)
    results     = data.get("results", [])
    log.info("  %d páginas (~%d jugadores)", total_pages, total_pages * PAGE_SIZE)

    for page in range(1, total_pages):
        time.sleep(REQUEST_DELAY)
        r = SESSION.get(url, headers=HEADERS, params={**params, "offset": page * PAGE_SIZE}, timeout=15)
        if r.status_code != 200:
            log.warning("  HTTP %d en página %d — saltando", r.status_code, page)
            continue
        results.extend(r.json().get("results", []))

    log.info("  Total registros: %d", len(results))
    return results


def find_player(ss_rows: list[dict]) -> dict | None:
    for r in ss_rows:
        jugador  = r.get("player") or {}
        nombre_n = _norm(jugador.get("name", ""))
        if nombre_n == TARGET_NORM:
            equipo = (r.get("team") or {}).get("name", "")
            log.info("ENCONTRADO: nombre='%s'  equipo='%s'", jugador.get("name"), equipo)
            log.info("  successfulDribbles       = %s", r.get("successfulDribbles"))
            log.info("  accuratePassesPercentage = %s", r.get("accuratePassesPercentage"))
            return r
    return None


def get_jugador_id() -> int | None:
    res = (
        supabase.table("jugadores")
        .select("id, nombre, equipo_id")
        .ilike("nombre", "%Paz%")
        .limit(5)
        .execute()
    )
    if not res.data:
        log.warning("No se encontró Nicolás Paz en tabla jugadores.")
        return None
    for r in res.data:
        log.info("  DB jugador: id=%d  nombre='%s'", r["id"], r["nombre"])
    return res.data[0]["id"]


def run():
    log.info("=" * 55)
    log.info(" Fix Nicolás Paz — regates y pases%%  Serie A 25/26")
    log.info("=" * 55)
    log.info("TARGET_NORM = '%s'", TARGET_NORM)

    season_id = SEASON_ID if SEASON_ID is not None else discover_season_id()
    ss_rows   = fetch_all_stats(season_id)
    row       = find_player(ss_rows)

    if not row:
        log.error("Nicolás Paz NO encontrado en Sofascore. Comprueba el nombre.")
        return

    regates         = row.get("successfulDribbles")
    pases_pct       = row.get("accuratePassesPercentage")
    pases_redondeado = round(pases_pct) if pases_pct is not None else None

    jid = get_jugador_id()
    if not jid:
        return

    payload = {}
    if regates is not None:
        payload["regates"] = regates
    if pases_redondeado is not None:
        payload["pases_completados"] = pases_redondeado

    if not payload:
        log.warning("Sofascore no tiene datos para este jugador.")
        return

    log.info("Actualizando jid=%d: %s", jid, payload)
    res = (
        supabase.table("estadisticas_jugador")
        .update(payload)
        .eq("jugador_id", jid)
        .eq("temporada", DB_TEMPORADA)
        .eq("liga_id", DB_LIGA_ID)
        .execute()
    )
    log.info("Actualizado: %d fila(s).", len(res.data))

    # Verificación
    ver = (
        supabase.table("estadisticas_jugador")
        .select("regates, pases_completados")
        .eq("jugador_id", jid)
        .eq("temporada", DB_TEMPORADA)
        .eq("liga_id", DB_LIGA_ID)
        .execute()
    )
    if ver.data:
        d = ver.data[0]
        log.info("VERIFICADO: regates=%s  pases_completados=%s", d.get("regates"), d.get("pases_completados"))

    log.info("=" * 55)


if __name__ == "__main__":
    run()
