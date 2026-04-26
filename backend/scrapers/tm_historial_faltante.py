"""
tm_historial_faltante.py
------------------------
Carga el historial multi-temporada de valor de mercado SOLO para los
jugadores que tienen menos de 2 entradas en valor_mercado_historia.

Flujo:
  1. Consulta Supabase → jugadores con < 2 entradas (los "incompletos")
  2. Lee sus tm_url directamente desde la columna jugadores.tm_url
     (sin necesidad de re-scrapear las plantillas de TM)
  3. Scraping del historial solo para esos jugadores (~1 req/jugador)
  4. Upsert en valor_mercado_historia

Nota: la columna tm_url se rellena cuando se ejecuta transfermarkt_scraper.py.
Si está vacía para algún jugador, ese jugador se omite en este script.

Uso:
  cd backend
  python scrapers/tm_historial_faltante.py
"""

import re
import sys
import time
import logging
import requests
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.supabase_client import supabase
from scrapers.transfermarkt_scraper import HEADERS, _date_to_temporada

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

BATCH          = 50
DELAY_NORMAL   = 2.5   # segundos entre requests
DELAY_RATELIMIT = 90.0 # pausa al recibir 405/429
MAX_REINTENTOS = 3


# ---------------------------------------------------------------------------
# Paso 1: jugadores incompletos con su tm_url ya en Supabase
# ---------------------------------------------------------------------------

def get_jugadores_a_procesar() -> list[dict]:
    """
    Devuelve lista de {jugador_id, tm_url} para jugadores con < 2 entradas
    en valor_mercado_historia que además tienen tm_url guardada en Supabase.
    """
    log.info("[1/3] Consultando Supabase...")

    res_hist = (
        supabase.table("valor_mercado_historia")
        .select("jugador_id, temporada")
        .execute()
    )
    conteo: Counter = Counter(r["jugador_id"] for r in res_hist.data)

    res_jugadores = (
        supabase.table("jugadores")
        .select("id, tm_url")
        .not_.is_("tm_url", "null")   # solo los que tienen URL guardada
        .execute()
    )

    todos_con_url = {r["id"]: r["tm_url"] for r in res_jugadores.data}
    total_bd      = supabase.table("jugadores").select("id", count="exact").execute().count

    completos     = sum(1 for jid, n in conteo.items() if n >= 2)
    incompletos_1 = {jid for jid, n in conteo.items() if n < 2}
    sin_historia  = set(todos_con_url.keys()) - set(conteo.keys())
    a_procesar    = (incompletos_1 | sin_historia) & set(todos_con_url.keys())

    log.info("      Total jugadores en BD         : %s", total_bd)
    log.info("      Con historial completo (≥2)   : %d", completos)
    log.info("      Con 1 entrada (solo actual)   : %d", len(incompletos_1))
    log.info("      Sin ninguna entrada           : %d", len(sin_historia))
    log.info("      Con tm_url disponible         : %d", len(todos_con_url))
    log.info("      → A procesar                  : %d", len(a_procesar))

    return [{"jugador_id": jid, "tm_url": todos_con_url[jid]} for jid in a_procesar]


# ---------------------------------------------------------------------------
# Scraping del historial con reintentos
# ---------------------------------------------------------------------------

def _scrape_historial(tm_url: str, jugador_id: int) -> list[dict]:
    m = re.search(r"/spieler/(\d+)", tm_url)
    if not m:
        log.warning("  No se pudo extraer ID de TM desde: %s", tm_url)
        return []
    pid     = m.group(1)
    api_url = f"https://www.transfermarkt.es/ceapi/marketValueDevelopment/graph/{pid}"

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            r = requests.get(api_url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                entries = r.json().get("list", [])
                by_temp: dict[str, float] = {}
                for e in entries:
                    temp = _date_to_temporada(e.get("datum_mw", ""))
                    y    = e.get("y")
                    if temp and y is not None:
                        by_temp[temp] = round(float(y) / 1_000_000, 3)
                return [{"temporada": t, "valor": v} for t, v in by_temp.items()]

            elif r.status_code in (405, 429):
                log.warning("  HTTP %d jugador_id=%d (intento %d/%d) — pausa %.0fs",
                            r.status_code, jugador_id, intento, MAX_REINTENTOS, DELAY_RATELIMIT)
                time.sleep(DELAY_RATELIMIT)
            else:
                log.warning("  HTTP %d jugador_id=%d", r.status_code, jugador_id)
                return []
        except Exception as e:
            log.warning("  Error jugador_id=%d: %s", jugador_id, e)
            return []

    log.warning("  jugador_id=%d agotó reintentos", jugador_id)
    return []


# ---------------------------------------------------------------------------
# Carga del historial y upsert
# ---------------------------------------------------------------------------

def cargar_historial(jugadores: list[dict]) -> int:
    total_j   = len(jugadores)
    hist_rows = []
    hist_total = 0

    log.info("[2/3] Scraping historial para %d jugadores...", total_j)

    for i, r in enumerate(jugadores, 1):
        time.sleep(DELAY_NORMAL)
        entries = _scrape_historial(r["tm_url"], r["jugador_id"])

        if not entries:
            log.info("  [%d/%d] jugador_id=%d → sin datos", i, total_j, r["jugador_id"])
        else:
            for e in entries:
                hist_rows.append({
                    "jugador_id": int(r["jugador_id"]),
                    "temporada":  e["temporada"],
                    "valor":      e["valor"],
                })
            log.info("  [%d/%d] jugador_id=%d → %d temporadas",
                     i, total_j, r["jugador_id"], len(entries))

        # Flush siempre — incluso si este jugador no tenía datos
        if i % BATCH == 0 or i == total_j:
            if hist_rows:
                supabase.table("valor_mercado_historia").upsert(
                    hist_rows, on_conflict="jugador_id,temporada"
                ).execute()
                hist_total += len(hist_rows)
                log.info("  → Batch insertado: %d filas (total: %d)",
                         len(hist_rows), hist_total)
                hist_rows = []

    return hist_total


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 56)
    log.info(" TM Historial Faltante — leyendo tm_url desde Supabase")
    log.info("=" * 56)

    jugadores = get_jugadores_a_procesar()

    if not jugadores:
        log.info("Nada que procesar: todos los jugadores tienen historial completo")
        log.info("o ninguno tiene tm_url guardada. Ejecuta primero transfermarkt_scraper.py")
        return

    total = cargar_historial(jugadores)

    log.info("=" * 56)
    log.info(" RESUMEN")
    log.info("  Jugadores procesados             : %d", len(jugadores))
    log.info("  Filas insertadas/actualizadas    : %d", total)
    log.info("=" * 56)


if __name__ == "__main__":
    run()
