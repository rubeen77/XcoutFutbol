"""
Escudos Premier League — obtiene las URLs de escudo de los 20 equipos
de Premier League desde Transfermarkt y actualiza escudo_url en Supabase.

La URL del escudo se deriva del ID de equipo de TM:
  https://tmssl.akamaized.net/images/wappen/normal/{tm_id}.png

Misma estrategia que escudos_scraper.py (LaLiga), apuntando a GB1.

Uso (desde backend/):
  conda activate xcout
  python scrapers/escudos_premier.py
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
LIGA_ID      = 24
TM_BASE      = "https://www.transfermarkt.es"
TM_LIGA_CODE = "GB1"          # código Premier League en Transfermarkt
TM_SEASON    = 2025
CDN_BASE     = "https://tmssl.akamaized.net/images/wappen/normal"

# Nombres en Supabase que no matchean por texto con TM → TM ID directo
NOMBRE_OVERRIDE = {
    "manchester utd": "985",  # TM: "Manchester United"
    "wolves":         "543",  # TM: "Wolverhampton Wanderers"
}

_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)


def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def _words(text: str) -> set:
    return set(_norm(text).split())


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
# Paso 1: obtener IDs desde la página de Premier League en TM
# ---------------------------------------------------------------------------

def get_tm_teams() -> list[dict]:
    log.info("[1/3] Obteniendo equipos de Premier League desde Transfermarkt...")
    url = f"{TM_BASE}/premier-league/startseite/wettbewerb/{TM_LIGA_CODE}/saison_id/{TM_SEASON}"
    log.info("      URL: %s", url)
    soup = _get(url)
    if not soup:
        raise RuntimeError("No se pudo cargar la pagina de PL en Transfermarkt")

    teams, seen = [], set()
    for a in soup.select("td.hauptlink a[href*='/startseite/verein/']"):
        href = a.get("href", "")
        m = re.search(r"/startseite/verein/(\d+)", href)
        if not m:
            continue
        tm_id = m.group(1)
        name  = a.text.strip()
        if not name or tm_id in seen:
            continue
        seen.add(tm_id)
        teams.append({"name": name, "tm_id": tm_id})

    log.info("      %d equipos encontrados en TM.", len(teams))
    for t in teams:
        log.info("      ID=%-6s  %s", t["tm_id"], t["name"])
    return teams


# ---------------------------------------------------------------------------
# Paso 2: cruzar con equipos de Supabase (liga_id=24)
# ---------------------------------------------------------------------------

def match_teams(tm_teams: list[dict]) -> list[dict]:
    log.info("[2/3] Cruzando con equipos PL en Supabase (liga_id=%d, temporada=%s)...",
             LIGA_ID, TEMPORADA)
    res = (
        supabase.table("equipos")
        .select("id, nombre")
        .eq("liga_id", LIGA_ID)
        .eq("temporada", TEMPORADA)
        .execute()
    )
    supa_teams = res.data or []
    log.info("      %d equipos en Supabase.", len(supa_teams))

    matched     = []
    used_tm_ids = set()

    for s in supa_teams:
        s_norm  = _norm(s["nombre"])
        s_words = _words(s["nombre"])
        best    = None

        # 0. Override explícito para nombres que difieren demasiado
        if s_norm in NOMBRE_OVERRIDE:
            forced_id = NOMBRE_OVERRIDE[s_norm]
            hit = next((t for t in tm_teams if t["tm_id"] == forced_id), None)
            if hit and hit["tm_id"] not in used_tm_ids:
                best = hit

        # 1. Match exacto normalizado
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

        # 3. Subconjunto de palabras — maneja variantes como
        #    "Man United" / "Manchester Utd" / "Manchester United"
        if not best:
            for t in tm_teams:
                if t["tm_id"] in used_tm_ids:
                    continue
                t_words = _words(t["name"])
                if s_words.issubset(t_words) or t_words.issubset(s_words):
                    best = t
                    break

        # 4. Intersección de palabras significativas (≥2 palabras en común,
        #    ignorando partículas de 2 letras o menos)
        if not best:
            sig = lambda ws: {w for w in ws if len(w) > 2}
            s_sig = sig(s_words)
            for t in tm_teams:
                if t["tm_id"] in used_tm_ids:
                    continue
                t_sig = sig(_words(t["name"]))
                if len(s_sig & t_sig) >= 2:
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
            log.info("  OK  %-30s  <->  %-30s  (ID %s)", s["nombre"], best["name"], best["tm_id"])
        else:
            log.warning("  !!  Sin match para: %s", s["nombre"])

    unmatched = len(supa_teams) - len(matched)
    if unmatched:
        log.warning("      %d equipo(s) sin match — revisar nombres en DB.", unmatched)
    return matched


# ---------------------------------------------------------------------------
# Paso 3: UPDATE en Supabase
# ---------------------------------------------------------------------------

def update_escudos(matched: list[dict]) -> int:
    log.info("[3/3] Actualizando escudo_url en Supabase...")
    n = 0
    for m in matched:
        supabase.table("equipos") \
            .update({"escudo_url": m["escudo_url"]}) \
            .eq("id", m["id"]) \
            .execute()
        n += 1
        log.info("      %-30s  -> %s", m["nombre"], m["escudo_url"])
    log.info("      %d equipos actualizados.", n)
    return n


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 58)
    log.info(" Escudos Premier League -- liga_id=%d  temporada=%s", LIGA_ID, TEMPORADA)
    log.info("=" * 58)

    tm_teams = get_tm_teams()
    if not tm_teams:
        log.error("No se obtuvieron equipos de Transfermarkt. Abortando.")
        return

    matched = match_teams(tm_teams)
    if not matched:
        log.error("Ningun equipo cruzado. Revisa los nombres en Supabase.")
        return

    updated = update_escudos(matched)

    log.info("=" * 58)
    log.info(" RESUMEN")
    log.info("  Equipos en TM      : %d", len(tm_teams))
    log.info("  Matches            : %d / 20", len(matched))
    log.info("  Actualizados       : %d", updated)
    log.info("=" * 58)


if __name__ == "__main__":
    run()
