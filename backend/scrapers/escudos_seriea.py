"""
Escudos Serie A — actualiza escudo_url en Supabase para los 20 equipos
de Serie A (liga_id=26, temporada='2526').

Los IDs de Transfermarkt están hardcodeados, no hace falta scraping web.
La URL del escudo se deriva directamente:
  https://tmssl.akamaized.net/images/wappen/normal/{tm_id}.png

Uso (desde backend/):
  conda activate xcout
  python scrapers/escudos_seriea.py
"""

import sys
import unicodedata
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

TEMPORADA = "2526"
LIGA_ID   = 26
CDN_BASE  = "https://tmssl.akamaized.net/images/wappen/normal"

# TM ID por nombre normalizado (clave = _norm del nombre en Supabase)
TM_IDS: dict[str, str] = {
    "inter milan":        "46",
    "internazionale":     "46",
    "ssc napoli":         "6195",
    "napoli":             "6195",
    "ac milan":           "5",
    "milan":              "5",
    "juventus":           "506",
    "as roma":            "12",
    "roma":               "12",
    "como 1907":          "2919",
    "como":               "2919",
    "atalanta bc":        "800",
    "atalanta":           "800",
    "ss lazio":           "398",
    "lazio":              "398",
    "bologna fc":         "1025",
    "bologna":            "1025",
    "sassuolo":           "6574",
    "us sassuolo":        "6574",
    "udinese calcio":     "410",
    "udinese":            "410",
    "parma calcio 1913":  "130",
    "parma":              "130",
    "torino fc":          "416",
    "torino":             "416",
    "genoa cfc":          "252",
    "genoa":              "252",
    "cagliari calcio":    "1390",
    "cagliari":           "1390",
    "acf fiorentina":     "430",
    "fiorentina":         "430",
    "us lecce":           "4849",
    "lecce":              "4849",
    "cremonese":          "3491",
    "us cremonese":       "3491",
    "hellas verona":      "276",
    "verona":             "276",
    "pisa":               "4263",
    "ac pisa":            "4263",
}


def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def load_supabase_teams() -> list[dict]:
    log.info("[1/2] Leyendo equipos Serie A desde Supabase (liga_id=%d, temporada=%s)...",
             LIGA_ID, TEMPORADA)
    res = (
        supabase.table("equipos")
        .select("id, nombre")
        .eq("liga_id", LIGA_ID)
        .eq("temporada", TEMPORADA)
        .execute()
    )
    teams = res.data or []
    log.info("      %d equipos encontrados.", len(teams))
    return teams


def match_and_update(teams: list[dict]) -> int:
    log.info("[2/2] Cruzando con IDs de Transfermarkt y actualizando escudo_url...")
    ok = sin_match = 0

    for t in teams:
        nombre_n = _norm(t["nombre"])
        tm_id    = TM_IDS.get(nombre_n)

        if not tm_id:
            # Fallback: buscar si alguna clave del dict es substring del nombre
            for key, tid in TM_IDS.items():
                if key in nombre_n or nombre_n in key:
                    tm_id = tid
                    break

        if not tm_id:
            log.warning("  !!  Sin TM ID para: %s  (norm='%s')", t["nombre"], nombre_n)
            sin_match += 1
            continue

        escudo_url = f"{CDN_BASE}/{tm_id}.png"
        supabase.table("equipos") \
            .update({"escudo_url": escudo_url}) \
            .eq("id", t["id"]) \
            .execute()
        ok += 1
        log.info("  OK  %-28s  tm_id=%-6s  -> %s", t["nombre"], tm_id, escudo_url)

    if sin_match:
        log.warning("      %d equipo(s) sin match — añadir a TM_IDS.", sin_match)
    return ok


def run():
    log.info("=" * 60)
    log.info(" Escudos Serie A -- liga_id=%d  temporada=%s", LIGA_ID, TEMPORADA)
    log.info("=" * 60)

    teams   = load_supabase_teams()
    updated = match_and_update(teams)

    log.info("=" * 60)
    log.info(" RESUMEN")
    log.info("  Equipos en Supabase : %d", len(teams))
    log.info("  Actualizados        : %d", updated)
    log.info("=" * 60)


if __name__ == "__main__":
    run()
