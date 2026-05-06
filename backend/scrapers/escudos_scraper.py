"""
Escudos Scraper — obtiene URLs de escudos de los 20 equipos de LaLiga
desde Transfermarkt y actualiza escudo_url en la tabla equipos de Supabase.

La URL del escudo se deriva del ID de equipo de TM (no requiere
visitar páginas de plantilla):
  https://tmssl.akamaized.net/images/wappen/normal/{tm_id}.png

Uso:
    python backend/scrapers/escudos_scraper.py
"""

import re
import sys
import unicodedata
import logging
from pathlib import Path

import cloudscraper
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

TEMPORADA    = "2526"
TM_BASE      = "https://www.transfermarkt.es"
TM_LIGA_CODE = "ES1"
TM_SEASON    = 2025
CDN_BASE     = "https://tmssl.akamaized.net/images/wappen/normal"

_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)


def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def _get(url: str):
    try:
        r = _scraper.get(url, timeout=20)
        if r.status_code != 200:
            log.warning("HTTP %d para %s", r.status_code, url)
            return None
        return BeautifulSoup(r.content, "lxml")
    except Exception as e:
        log.warning("Error en %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Paso 1: obtener IDs de equipo desde la página de LaLiga en TM
# ---------------------------------------------------------------------------

def get_tm_teams() -> list[dict]:
    log.info("[1/3] Obteniendo equipos de LaLiga desde Transfermarkt...")
    url = f"{TM_BASE}/laliga/startseite/wettbewerb/{TM_LIGA_CODE}/saison_id/{TM_SEASON}"
    soup = _get(url)
    if not soup:
        raise RuntimeError("No se pudo cargar la página de LaLiga en Transfermarkt")

    teams, seen = [], set()
    for a in soup.select("td.hauptlink a[href*='/startseite/verein/']"):
        href = a.get("href", "")
        m = re.search(r"/startseite/verein/(\d+)", href)
        if not m:
            continue
        tm_id = m.group(1)
        name  = a.text.strip()
        if tm_id in seen:
            continue
        seen.add(tm_id)
        teams.append({"name": name, "tm_id": tm_id})

    log.info("      %d equipos encontrados en TM.", len(teams))
    return teams


# ---------------------------------------------------------------------------
# Paso 2: cruzar con equipos de Supabase
# ---------------------------------------------------------------------------

def _words(text: str) -> set:
    return set(_norm(text).split())


def match_teams(tm_teams: list[dict]) -> list[dict]:
    log.info("[2/3] Cruzando con equipos de Supabase (temporada %s)...", TEMPORADA)
    res = (
        supabase.table("equipos")
        .select("id, nombre")
        .eq("temporada", TEMPORADA)
        .execute()
    )
    supa_teams = res.data or []
    log.info("      %d equipos en Supabase.", len(supa_teams))

    matched    = []
    used_tm_ids = set()

    for s in supa_teams:
        s_norm  = _norm(s["nombre"])
        s_words = _words(s["nombre"])
        best = None

        # 1. Match exacto
        for t in tm_teams:
            if t["tm_id"] not in used_tm_ids and _norm(t["name"]) == s_norm:
                best = t
                break

        # 2. Substring (uno contiene al otro)
        if not best:
            for t in tm_teams:
                if t["tm_id"] in used_tm_ids:
                    continue
                t_norm = _norm(t["name"])
                if s_norm in t_norm or t_norm in s_norm:
                    best = t
                    break

        # 3. Subconjunto de palabras — maneja "de" intercalado
        #    "Atletico Madrid" subset de "Atletico de Madrid" → match
        if not best:
            for t in tm_teams:
                if t["tm_id"] in used_tm_ids:
                    continue
                t_words = _words(t["name"])
                if s_words.issubset(t_words) or t_words.issubset(s_words):
                    best = t
                    break

        if best:
            used_tm_ids.add(best["tm_id"])
            escudo_url = f"{CDN_BASE}/{best['tm_id']}.png"
            matched.append({
                "id":         s["id"],
                "nombre":     s["nombre"],
                "tm_name":    best["name"],
                "tm_id":      best["tm_id"],
                "escudo_url": escudo_url,
            })
            log.info("  ✓  %-30s  ←→  %-30s  (ID %s)", s["nombre"], best["name"], best["tm_id"])
        else:
            log.warning("  ✗  Sin match para: %s", s["nombre"])

    return matched


# ---------------------------------------------------------------------------
# Paso 3: upsert en Supabase
# ---------------------------------------------------------------------------

def upsert_escudos(matched: list[dict]) -> int:
    log.info("[3/3] Actualizando escudo_url en Supabase...")
    n = 0
    for m in matched:
        supabase.table("equipos") \
            .update({"escudo_url": m["escudo_url"]}) \
            .eq("id", m["id"]) \
            .execute()
        n += 1
    log.info("      %d equipos actualizados.", n)
    return n


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 52)
    log.info(" Escudos Scraper -- LaLiga %s", TEMPORADA)
    log.info("=" * 52)

    tm_teams = get_tm_teams()
    matched  = match_teams(tm_teams)
    updated  = upsert_escudos(matched)

    log.info("=" * 52)
    log.info(" RESUMEN")
    log.info("  Equipos TM       : %d", len(tm_teams))
    log.info("  Matches          : %d", len(matched))
    log.info("  Actualizados     : %d", updated)
    log.info("=" * 52)


if __name__ == "__main__":
    run()
