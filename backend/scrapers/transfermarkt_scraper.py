"""
Transfermarkt Scraper — fotos y valor de mercado para LaLiga 2025/26

Fuente: Transfermarkt.es (scraping directo con requests + BeautifulSoup)
Soccerdata no incluye Transfermarkt en la version instalada.

Estrategia (mínimo de requests):
  1. 1 request  → LaLiga page → 20 IDs de equipo
  2. 20 requests → plantilla de cada equipo → nombre, foto, valor actual
  3. Cruce por nombre normalizado con jugadores en Supabase
  4. 1 request  → upsert batch jugadores (foto + valor)
  5. 1 request  → upsert batch valor_mercado_historia (valor temporada actual)
  Total: ~23 requests HTTP

Historial multi-temporada: requiere 1 request por jugador (~586).
Implementado pero desactivado por defecto (CARGAR_HISTORIAL = False).
Activar solo en ejecuciones nocturnas con rate limit.
"""

import re
import sys
import time
import logging
import datetime
import unicodedata
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

TEMPORADA        = "2526"
LIGA_ID          = 1
TM_SEASON        = 2025          # año de inicio de la temporada en Transfermarkt
TM_LIGA_CODE     = "ES1"         # código de LaLiga en Transfermarkt
CARGAR_HISTORIAL = True           # activar para cargar historial multi-temporada
REQUEST_DELAY    = 2.0            # segundos entre requests (evitar ban)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language":   "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding":   "gzip, deflate, br",
    "Connection":        "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":    "document",
    "Sec-Fetch-Mode":    "navigate",
    "Sec-Fetch-Site":    "none",
    "Sec-Fetch-User":    "?1",
    "sec-ch-ua":         '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile":  "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Referer":           "https://www.transfermarkt.es/",
}

TM_BASE = "https://www.transfermarkt.es"

# Sesión compartida: mantiene cookies entre requests como un navegador real
_session = requests.Session()
_session.headers.update(HEADERS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Sin acentos, minúsculas, espacios colapsados."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def _parse_valor(text: str) -> Optional[float]:
    """
    Convierte texto TM a millones de euros:
      "18,00 mill."  → 18.0
      "500 mil"      → 0.5
      "-"            → None
    """
    if not text or text.strip() in ("-", ""):
        return None
    text = text.strip().lower().replace(",", ".")
    m = re.search(r"([\d.]+)\s*(mill|mio|m\b)", text)
    if m:
        return round(float(m.group(1)), 2)
    m = re.search(r"([\d.]+)\s*(mil|k\b|tsd)", text)
    if m:
        return round(float(m.group(1)) / 1000, 3)
    m = re.search(r"([\d.]+)", text)
    if m:
        return round(float(m.group(1)), 2)
    return None


def _get(url: str) -> Optional[BeautifulSoup]:
    try:
        r = _session.get(url, timeout=15)
        if r.status_code != 200:
            log.warning("  HTTP %d para %s", r.status_code, url)
            return None
        return BeautifulSoup(r.content, "lxml")
    except Exception as e:
        log.warning("  Error en %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Paso 1: obtener IDs y slugs de los 20 equipos de LaLiga
# ---------------------------------------------------------------------------

def get_team_ids() -> list[dict]:
    log.info("[1/5] Obteniendo equipos de LaLiga desde Transfermarkt...")
    url = f"{TM_BASE}/laliga/startseite/wettbewerb/{TM_LIGA_CODE}/saison_id/{TM_SEASON}"
    soup = _get(url)
    if not soup:
        raise RuntimeError("No se pudo cargar la página de LaLiga en Transfermarkt")

    teams = []
    seen = set()
    for a in soup.select("td.hauptlink a[href*='/startseite/verein/']"):
        href = a.get("href", "")
        m = re.search(r"(/[^/]+/startseite/verein/(\d+))", href)
        if not m:
            continue
        slug_path = m.group(1)
        team_id   = m.group(2)
        name      = a.text.strip()
        if team_id in seen:
            continue
        seen.add(team_id)
        teams.append({
            "name":    name,
            "tm_id":   team_id,
            "kader_url": f"{TM_BASE}{slug_path.replace('/startseite/', '/kader/')}/saison_id/{TM_SEASON}",
        })

    log.info("      %d equipos encontrados.", len(teams))
    return teams


# ---------------------------------------------------------------------------
# Paso 2: scraping de plantilla de cada equipo
# ---------------------------------------------------------------------------

def scrape_squad(team: dict) -> list[dict]:
    soup = _get(team["kader_url"])
    if not soup:
        return []

    players = []
    for row in soup.select("table.items tbody tr.odd, table.items tbody tr.even"):
        name_el  = row.select_one("td.hauptlink a")
        img_el   = row.select_one("img.bilderrahmen-fixed")
        val_el   = row.select_one("td.rechts.hauptlink")
        player_a = row.select("td.hauptlink a")

        if not name_el:
            continue

        name  = name_el.text.strip()
        foto  = None
        if img_el:
            foto = img_el.get("data-src") or img_el.get("src")
            # Cambiar tamaño medium → big para mayor calidad
            if foto:
                foto = foto.replace("/medium/", "/big/")

        valor = _parse_valor(val_el.text if val_el else "")

        # URL del perfil del jugador (para historial)
        player_url = None
        for a in player_a:
            href = a.get("href", "")
            if "/profil/spieler/" in href:
                player_url = TM_BASE + href
                break

        players.append({
            "nombre":       name,
            "nombre_norm":  _norm(name),
            "equipo_tm":    team["name"],
            "foto_url":     foto,
            "valor_mercado": valor,
            "player_url":   player_url,
        })

    return players


def scrape_all_squads(teams: list[dict]) -> pd.DataFrame:
    log.info("[2/5] Scraping plantillas (%d equipos)...", len(teams))
    all_players = []
    for i, team in enumerate(teams, 1):
        log.info("      [%d/%d] %s", i, len(teams), team["name"])
        players = scrape_squad(team)
        log.info("           %d jugadores", len(players))
        all_players.extend(players)
        if i < len(teams):
            time.sleep(REQUEST_DELAY)

    df = pd.DataFrame(all_players)
    log.info("      Total: %d jugadores con datos de TM.", len(df))
    return df


# ---------------------------------------------------------------------------
# Paso 3 (opcional): historial multi-temporada por jugador
# ---------------------------------------------------------------------------

# Abreviaturas de mes en varios idiomas que usa TM
_MONTH_ABBR = {
    "jan": 1, "ene": 1, "feb": 2, "mar": 3, "mär": 3, "abr": 4, "apr": 4,
    "may": 5, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "aug": 8,
    "sep": 9, "okt": 10, "oct": 10, "nov": 11, "dic": 12, "dez": 12, "dec": 12,
}


def _date_to_temporada(date_str: str) -> Optional[str]:
    """
    Convierte una fecha TM en código de temporada YYZZ.
    Julio–diciembre → inicio de temporada; enero–junio → fin de temporada.
      "Sep 12, 2023" → "2324"   (temporada 2023/24)
      "Mar 15, 2024" → "2324"   (temporada 2023/24, antes de julio)
    """
    s = date_str.strip()
    for fmt in ("%b %d, %Y", "%b. %d, %Y", "%d. %b %Y", "%d. %b. %Y",
                "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            d = datetime.datetime.strptime(s, fmt)
            y = d.year - (1 if d.month < 7 else 0)
            return f"{str(y)[2:]}{str(y + 1)[2:]}"
        except ValueError:
            pass

    # Fallback: buscar mes abreviado + año 4 dígitos en el texto
    low = s.lower()
    year_m = re.search(r"(\d{4})", s)
    if not year_m:
        return None
    year = int(year_m.group(1))
    month = 9   # por defecto septiembre si no reconocemos el mes
    for abbr, num in _MONTH_ABBR.items():
        if abbr in low:
            month = num
            break
    y = year - (1 if month < 7 else 0)
    return f"{str(y)[2:]}{str(y + 1)[2:]}"


def scrape_market_history(player_url: str) -> list[dict]:
    """
    Extrae historial de valor de mercado via ceapi de TM.
    Devuelve lista de {temporada: 'YYZZ', valor: float (millones €)}.
    Deduplica por temporada: conserva el último valor registrado en cada una.
    """
    m = re.search(r"/spieler/(\d+)", player_url)
    if not m:
        return []
    player_id = m.group(1)

    api_url = f"https://www.transfermarkt.es/ceapi/marketValueDevelopment/graph/{player_id}"
    try:
        r = requests.get(api_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            log.warning("  ceapi HTTP %d para jugador %s", r.status_code, player_id)
            return []
        entries = r.json().get("list", [])
    except Exception as e:
        log.warning("  ceapi error jugador %s: %s", player_id, e)
        return []

    # Agrupar por temporada: el último valor de cada temporada gana
    by_temp: dict[str, float] = {}
    for entry in entries:
        datum = entry.get("datum_mw", "")
        y     = entry.get("y")
        if not datum or y is None:
            continue
        temp = _date_to_temporada(datum)
        if temp:
            by_temp[temp] = round(float(y) / 1_000_000, 3)

    return [{"temporada": t, "valor": v} for t, v in by_temp.items()]


# ---------------------------------------------------------------------------
# Paso 4: cruce con jugadores en Supabase
# ---------------------------------------------------------------------------

def load_supabase_jugadores() -> pd.DataFrame:
    log.info("[3/5] Leyendo jugadores desde Supabase...")
    res = (
        supabase.table("jugadores")
        .select("id, nombre, equipo_id, equipos(nombre)")
        .execute()
    )
    rows = []
    for r in res.data:
        eq = (r.get("equipos") or {})
        rows.append({
            "jugador_id":   r["id"],
            "nombre":       r["nombre"],
            "nombre_norm":  _norm(r["nombre"]),
            "equipo_id":    r["equipo_id"],
            "equipo_nombre": eq.get("nombre", ""),
            "equipo_norm":  _norm(eq.get("nombre", "")),
        })
    df = pd.DataFrame(rows)
    log.info("      %d jugadores en Supabase.", len(df))
    return df


def match_players(df_supa: pd.DataFrame, df_tm: pd.DataFrame) -> pd.DataFrame:
    """
    Une Supabase con TM por nombre normalizado.
    Primero intenta match exacto; fallback por nombre solo.
    """
    log.info("[4/5] Cruzando nombres Supabase <-> Transfermarkt...")

    # Índices de TM
    exact_idx  = {(r["nombre_norm"], _norm(r["equipo_tm"])): i
                  for i, r in df_tm.iterrows()}
    name_idx   = {}
    for i, r in df_tm.iterrows():
        name_idx.setdefault(r["nombre_norm"], i)   # primero gana

    matched_exact = matched_name = unmatched = 0
    tm_idx_list = []

    for _, row in df_supa.iterrows():
        key = (row["nombre_norm"], row["equipo_norm"])
        if key in exact_idx:
            tm_idx_list.append(exact_idx[key])
            matched_exact += 1
        elif row["nombre_norm"] in name_idx:
            tm_idx_list.append(name_idx[row["nombre_norm"]])
            matched_name += 1
        else:
            tm_idx_list.append(None)
            unmatched += 1

    log.info("      Match exacto (nombre+equipo): %d", matched_exact)
    log.info("      Match por nombre solo        : %d", matched_name)
    log.info("      Sin match                    : %d", unmatched)

    # Construir DataFrame combinado
    merged_rows = []
    for (_, supa_row), tm_i in zip(df_supa.iterrows(), tm_idx_list):
        if tm_i is None:
            continue
        tm_row = df_tm.loc[tm_i]
        merged_rows.append({
            "jugador_id":    supa_row["jugador_id"],
            "nombre":        supa_row["nombre"],       # requerido NOT NULL
            "equipo_id":     supa_row["equipo_id"],
            "foto_url":      tm_row["foto_url"],
            "valor_mercado": tm_row["valor_mercado"],
            "player_url":    tm_row["player_url"],
        })

    return pd.DataFrame(merged_rows)


# ---------------------------------------------------------------------------
# Paso 5: upsert en Supabase
# ---------------------------------------------------------------------------

def upsert_jugadores(df: pd.DataFrame) -> int:
    log.info("[5/5] Actualizando jugadores (foto + valor) en Supabase...")
    df_validos = df[df["foto_url"].notna() | df["valor_mercado"].notna()].copy()
    log.info("      %d jugadores con datos para actualizar.", len(df_validos))

    rows = []
    for _, r in df_validos.iterrows():
        row = {
            "id":     int(r["jugador_id"]),
            "nombre": r["nombre"],          # NOT NULL — requerido en upsert
        }
        if pd.notna(r.get("foto_url")):
            row["foto_url"] = r["foto_url"]
        if pd.notna(r.get("valor_mercado")):
            row["valor_mercado"] = float(r["valor_mercado"])
        if pd.notna(r.get("player_url")):
            row["tm_url"] = r["player_url"]
        rows.append(row)

    res = supabase.table("jugadores").upsert(rows, on_conflict="id").execute()
    log.info("      %d jugadores actualizados.", len(res.data))
    return len(res.data)


def upsert_historial(df: pd.DataFrame) -> int:
    """Inserta el valor actual como entrada del historial para TEMPORADA."""
    log.info("      Insertando historial de valor (temporada actual)...")
    df_val = df[df["valor_mercado"].notna()].copy()

    rows = [
        {
            "jugador_id": int(r["jugador_id"]),
            "temporada":  TEMPORADA,
            "valor":      float(r["valor_mercado"]),
        }
        for _, r in df_val.iterrows()
    ]
    res = (
        supabase.table("valor_mercado_historia")
        .upsert(rows, on_conflict="jugador_id,temporada")
        .execute()
    )
    log.info("      %d entradas de historial insertadas.", len(res.data))
    return len(res.data)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 52)
    log.info(" Transfermarkt Scraper -- LaLiga %s", TEMPORADA)
    log.info("=" * 52)

    teams       = get_team_ids()
    df_tm       = scrape_all_squads(teams)
    df_supa     = load_supabase_jugadores()
    df_merged   = match_players(df_supa, df_tm)

    jugadores_ok = upsert_jugadores(df_merged)
    historial_ok = upsert_historial(df_merged)

    if CARGAR_HISTORIAL:
        jugadores_con_url = df_merged[df_merged["player_url"].notna()]
        total_j = len(jugadores_con_url)
        log.info("Cargando historial multi-temporada (%d jugadores, ~%ds)...",
                 total_j, int(total_j * REQUEST_DELAY))

        BATCH = 50
        hist_rows = []
        hist_total = 0

        for i, (_, r) in enumerate(jugadores_con_url.iterrows(), 1):
            time.sleep(REQUEST_DELAY)
            entries = scrape_market_history(r["player_url"])
            for e in entries:
                hist_rows.append({
                    "jugador_id": int(r["jugador_id"]),
                    "temporada":  e["temporada"],
                    "valor":      e["valor"],
                })

            if i % BATCH == 0 or i == total_j:
                if hist_rows:
                    supabase.table("valor_mercado_historia").upsert(
                        hist_rows, on_conflict="jugador_id,temporada"
                    ).execute()
                    hist_total += len(hist_rows)
                    log.info("  [%d/%d] Batch insertado: %d entradas (total: %d)",
                             i, total_j, len(hist_rows), hist_total)
                    hist_rows = []
                else:
                    log.info("  [%d/%d] Sin entradas en este batch.", i, total_j)

        log.info("Historial multi-temporada completado: %d entradas totales.", hist_total)

    log.info("=" * 52)
    log.info(" RESUMEN")
    log.info("  Jugadores TM scrapeados        : %d", len(df_tm))
    log.info("  Jugadores en Supabase          : %d", len(df_supa))
    log.info("  Matches encontrados            : %d", len(df_merged))
    log.info("  Jugadores actualizados (foto+valor): %d", jugadores_ok)
    log.info("  Historial insertado            : %d", historial_ok)
    log.info("=" * 52)


if __name__ == "__main__":
    run()
