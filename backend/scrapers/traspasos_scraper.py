"""
Transfermarkt Scraper — historial de traspasos por jugador

Fuente: https://www.transfermarkt.es/spieler/transfers/spieler/{tm_id}

Estrategia:
  1. Leer jugadores con tm_url de la liga indicada (liga_id)
  2. Por cada jugador: GET página de traspasos → extraer filas
  3. Normalizar tipo y cantidad
  4. Upsert en tabla `traspasos` (ON CONFLICT DO NOTHING)

Uso (desde backend/):
  conda activate xcout
  python scrapers/traspasos_scraper.py
"""

import re
import sys
import time
import random
import logging
import unicodedata
from pathlib import Path
from typing import Optional

import cloudscraper
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

LIGA_ID       = 1        # 1=LaLiga, 24=Premier, 25=Bundesliga
TEMPORADA     = "2526"   # temporada actual de los jugadores en Supabase
DELAY_MIN     = 3.0      # segundos mínimos entre requests
DELAY_MAX     = 5.0      # segundos máximos entre requests
BATCH_SIZE    = 50       # filas por upsert

# Poner DEBUG = True para inspeccionar el HTML del primer jugador y salir
DEBUG         = True

TM_BASE = "https://www.transfermarkt.es"

_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(url: str) -> Optional[BeautifulSoup]:
    try:
        r = _scraper.get(url, timeout=25)
        if r.status_code != 200:
            log.warning("  HTTP %d -> %s", r.status_code, url)
            return None
        return BeautifulSoup(r.content, "lxml")
    except Exception as e:
        log.warning("  Error GET %s: %s", url, e)
        return None


def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def _parse_cantidad(text: str) -> float:
    """Devuelve el valor en millones o 0.0 si no hay coste."""
    if not text:
        return 0.0
    t = text.strip().lower().replace(".", "").replace(",", ".")
    # libre / sin coste / préstamo sin coste
    if any(w in t for w in ("gratis", "libre", "sin coste", "ablösefrei", "free")):
        return 0.0
    m = re.search(r"([\d]+\.?\d*)\s*(mill|mio|m\b)", t)
    if m:
        return round(float(m.group(1)), 2)
    m = re.search(r"([\d]+\.?\d*)\s*(mil|k\b|tsd)", t)
    if m:
        return round(float(m.group(1)) / 1000, 3)
    return 0.0


_TIPO_MAP = [
    # orden importa: más específico primero
    (r"fin.{0,10}ces",          "fin de cesión"),
    (r"ces[ií]",                "cesión"),
    (r"pr[eé]st",               "cesión"),
    (r"loan",                   "cesión"),
    (r"libre|gratis|free|ablös","libre"),
    (r"traspaso|transfer|sold", "traspaso"),
]


def _parse_tipo(text: str) -> str:
    t = text.strip().lower() if text else ""
    for pattern, tipo in _TIPO_MAP:
        if re.search(pattern, t):
            return tipo
    return "traspaso"


def _year_to_temporada(year_str: str) -> Optional[str]:
    """'23/24' o '2023' → '2324'"""
    s = year_str.strip()
    # formato "23/24" o "2023/24"
    m = re.match(r"(\d{2,4})/(\d{2})", s)
    if m:
        a = m.group(1)[-2:]
        b = m.group(2)
        return a + b
    # solo año: "2023" → temporada que empieza ese año
    m = re.match(r"(\d{4})", s)
    if m:
        y = int(m.group(1))
        return f"{str(y)[2:]}{str(y + 1)[2:]}"
    return None


# ---------------------------------------------------------------------------
# Paso 1: cargar jugadores con tm_url de la liga indicada
# ---------------------------------------------------------------------------

def load_jugadores() -> list[dict]:
    log.info("[1/3] Leyendo jugadores con tm_url de liga_id=%d...", LIGA_ID)

    eq_res = (
        supabase.table("equipos").select("id")
        .eq("liga_id", LIGA_ID).eq("temporada", TEMPORADA).execute()
    )
    eq_ids = [e["id"] for e in (eq_res.data or [])]
    log.info("      %d equipos en la liga.", len(eq_ids))

    jugadores = []
    for i in range(0, len(eq_ids), 50):
        res = (
            supabase.table("jugadores")
            .select("id, nombre, tm_url")
            .in_("equipo_id", eq_ids[i : i + 50])
            .not_.is_("tm_url", "null")
            .execute()
        )
        jugadores.extend(res.data or [])

    log.info("      %d jugadores con tm_url.", len(jugadores))
    return jugadores


# ---------------------------------------------------------------------------
# Paso 2: scraping de traspasos por jugador
# ---------------------------------------------------------------------------

def _tm_id_from_url(tm_url: str) -> Optional[str]:
    m = re.search(r"/spieler/(\d+)", tm_url)
    return m.group(1) if m else None


def _debug_html(soup: BeautifulSoup, url: str) -> None:
    print("\n" + "=" * 70)
    print(f"DEBUG URL: {url}")
    print("=" * 70)

    # Todas las clases de <div> y <table> presentes en la página
    clases_div   = sorted({c for el in soup.find_all("div",   class_=True) for c in el["class"]})
    clases_table = sorted({c for el in soup.find_all("table", class_=True) for c in el["class"]})
    print(f"\nClases de <div>   ({len(clases_div)}): {clases_div}")
    print(f"Clases de <table> ({len(clases_table)}): {clases_table}")

    # Primeros 4000 caracteres del HTML para ver la estructura
    print("\n--- HTML (primeros 4000 chars) ---")
    print(soup.prettify()[:4000])
    print("=" * 70 + "\n")


def scrape_traspasos(jugador: dict, debug: bool = False) -> list[dict]:
    tm_id = _tm_id_from_url(jugador["tm_url"])
    if not tm_id:
        log.warning("  No se pudo extraer tm_id de %s", jugador["tm_url"])
        return []

    url  = f"{TM_BASE}/spieler/transfers/spieler/{tm_id}"
    soup = _get(url)
    if not soup:
        return []

    if debug:
        _debug_html(soup, url)

    rows = []
    # Transfermarkt agrupa los traspasos por temporada en bloques
    for block in soup.select("div.transfer-record"):
        # cabecera de bloque: temporada
        season_el = block.select_one("div.transfer-record__season, span.transfer-record__season")
        temporada = None
        if season_el:
            temporada = _year_to_temporada(season_el.text)

        for row in block.select("div.transfer-record__row, li.transfer-record__list-item"):
            origen_el  = row.select_one(".transfer-record__old-club a, .transfer-record__origin a")
            destino_el = row.select_one(".transfer-record__new-club a, .transfer-record__destination a")
            tipo_el    = row.select_one(".transfer-record__type, .transfer-record__label")
            fee_el     = row.select_one(".transfer-record__fee, .transfer-record__transfer-fee")

            club_origen  = origen_el.text.strip()  if origen_el  else ""
            club_destino = destino_el.text.strip() if destino_el else ""
            tipo_raw     = tipo_el.text.strip()    if tipo_el    else ""
            fee_raw      = fee_el.text.strip()     if fee_el     else ""

            if not club_origen and not club_destino:
                continue

            rows.append({
                "jugador_id":   jugador["id"],
                "club_origen":  club_origen,
                "club_destino": club_destino,
                "temporada":    temporada,
                "tipo":         _parse_tipo(tipo_raw),
                "cantidad":     _parse_cantidad(fee_raw),
            })

    # Fallback: tabla clásica si el HTML usa estructura de tabla
    if not rows:
        rows = _scrape_table_fallback(soup, jugador["id"])

    return rows


def _scrape_table_fallback(soup: BeautifulSoup, jugador_id: int) -> list[dict]:
    """Estructura alternativa: <table class='auflistung'> con filas de traspasos."""
    rows = []
    for table in soup.select("table.auflistung, div.responsive-table table"):
        for tr in table.select("tbody tr"):
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue

            # columnas habituales: temporada | club_origen | club_destino | tipo | fee
            temporada    = _year_to_temporada(tds[0].text.strip())
            club_origen  = tds[1].text.strip()
            club_destino = tds[2].text.strip()
            tipo_raw     = tds[3].text.strip() if len(tds) > 3 else ""
            fee_raw      = tds[4].text.strip() if len(tds) > 4 else ""

            if not club_origen and not club_destino:
                continue

            rows.append({
                "jugador_id":   jugador_id,
                "club_origen":  club_origen,
                "club_destino": club_destino,
                "temporada":    temporada,
                "tipo":         _parse_tipo(tipo_raw),
                "cantidad":     _parse_cantidad(fee_raw),
            })
    return rows


# ---------------------------------------------------------------------------
# Paso 3: upsert en Supabase
# ---------------------------------------------------------------------------

def upsert_traspasos(rows: list[dict]) -> int:
    if not rows:
        return 0
    # ON CONFLICT DO NOTHING: la tabla debe tener unique(jugador_id, club_origen, club_destino, temporada)
    res = (
        supabase.table("traspasos")
        .upsert(rows, on_conflict="jugador_id,club_origen,club_destino,temporada",
                ignore_duplicates=True)
        .execute()
    )
    return len(res.data or [])


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 60)
    log.info(" Traspasos Scraper — liga_id=%d  temporada=%s", LIGA_ID, TEMPORADA)
    log.info("=" * 60)

    jugadores   = load_jugadores()
    total       = len(jugadores)
    total_filas = 0
    buffer: list[dict] = []

    for i, jug in enumerate(jugadores, 1):
        log.info("[%d/%d] %s", i, total, jug["nombre"])
        es_primero = (i == 1)
        filas = scrape_traspasos(jug, debug=(DEBUG and es_primero))
        log.info("       %d traspasos encontrados", len(filas))

        if DEBUG and es_primero:
            log.info("  Modo DEBUG activo: saliendo tras el primer jugador.")
            return

        buffer.extend(filas)

        if len(buffer) >= BATCH_SIZE or i == total:
            insertados = upsert_traspasos(buffer)
            total_filas += insertados
            log.info("  → Batch upsert: %d filas insertadas (total acum.: %d)",
                     insertados, total_filas)
            buffer = []

        if i < total:
            delay = random.uniform(DELAY_MIN, DELAY_MAX)
            time.sleep(delay)

    log.info("=" * 60)
    log.info(" RESUMEN")
    log.info("  Jugadores procesados : %d", total)
    log.info("  Traspasos insertados : %d", total_filas)
    log.info("=" * 60)


if __name__ == "__main__":
    run()
