"""
Porteros Scraper — portero_paradas, portero_goles_encajados, portero_paradas_pct

Fuente: API de Sofascore (endpoint individual por jugador, sin autenticación)
  1. Obtiene todos los porteros de LaLiga 2526 vía season stats filtrado por posición GK
  2. Cruza con jugadores de Supabase por nombre normalizado
  3. Consulta el endpoint individual de cada portero para obtener saves / goalsConceded
  4. Calcula portero_paradas_pct = saves / (saves + goalsConceded) * 100
  5. Hace UPDATE en estadisticas_jugador (temporada='2526')

Uso:
  python backend/scrapers/porteros_scraper.py
"""

import sys
import time
import logging
import unicodedata
from pathlib import Path

from curl_cffi import requests as cffi

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

import io
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace"))],
)
log = logging.getLogger(__name__)

TOURNAMENT_ID = 8        # LaLiga uniqueTournament en Sofascore
SEASON_ID     = 77559    # LaLiga 25/26
DB_LIGA_ID    = 1
DB_TEMPORADA  = "2526"
REQUEST_DELAY = 1.0      # segundos entre consultas individuales

API     = "https://api.sofascore.com/api/v1"
SESSION = cffi.Session(impersonate="chrome124")
HEADERS = {
    "Referer": "https://www.sofascore.com/",
    "Accept":  "application/json",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


# ─── 1. Obtener porteros de Sofascore ─────────────────────────────────────────

def fetch_ss_goalkeepers() -> list[dict]:
    """Devuelve lista de {ss_id, nombre, equipo} para todos los porteros de la temporada."""
    log.info("[1/4] Obteniendo porteros de Sofascore...")
    url = f"{API}/unique-tournament/{TOURNAMENT_ID}/season/{SEASON_ID}/statistics"
    params = {
        "limit":        100,
        "order":        "-minutesPlayed",
        "accumulation": "total",
        "group":        "summary",
        "filters":      "position.in.G",
        "offset":       0,
    }
    r = SESSION.get(url, params=params, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} al obtener porteros")

    results = r.json().get("results", [])
    porteros = []
    for row in results:
        jugador = row.get("player") or {}
        equipo  = row.get("team")   or {}
        ss_id   = jugador.get("id")
        nombre  = jugador.get("name", "")
        if ss_id and nombre:
            porteros.append({
                "ss_id":  ss_id,
                "nombre": nombre,
                "equipo": equipo.get("name", ""),
            })

    log.info("    %d porteros en Sofascore.", len(porteros))
    return porteros


# ─── 2. Stats individuales ────────────────────────────────────────────────────

def fetch_keeper_stats(ss_id: int) -> dict:
    """Obtiene saves y goalsConceded para un portero concreto."""
    url = (f"{API}/player/{ss_id}/unique-tournament/{TOURNAMENT_ID}"
           f"/season/{SEASON_ID}/statistics/overall")
    r = SESSION.get(url, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        return {}
    return r.json().get("statistics", {})


# ─── 3. Cargar jugadores de Supabase ─────────────────────────────────────────

def load_supabase_goalkeepers() -> tuple[dict, dict, dict]:
    """
    Carga porteros (posicion='GK') de Supabase.
    Devuelve tres mapas para matching:
      full_map  : (nombre_norm, equipo_norm) → jugador_id
      name_map  : nombre_norm → jugador_id
      last_map  : apellido_norm → jugador_id
    """
    log.info("[2/4] Cargando porteros de Supabase...")
    res = (
        supabase.table("jugadores")
        .select("id, nombre, posicion, equipos(nombre)")
        .eq("posicion", "GK")
        .execute()
    )

    full_map: dict = {}
    name_map: dict = {}
    last_map: dict = {}

    for r in res.data or []:
        jid   = r["id"]
        name  = _norm(r.get("nombre") or "")
        team  = _norm((r.get("equipos") or {}).get("nombre") or "")
        if not name:
            continue
        full_map[(name, team)] = jid
        if name not in name_map:
            name_map[name] = jid
        last = name.split()[-1]
        if last and last not in last_map:
            last_map[last] = jid

    log.info("    %d porteros en Supabase.", len(name_map))
    return full_map, name_map, last_map


def _resolve(nombre_ss: str, equipo_ss: str,
             full_map: dict, name_map: dict, last_map: dict) -> "int | None":
    p = _norm(nombre_ss)
    e = _norm(equipo_ss)
    return (
        full_map.get((p, e)) or
        name_map.get(p) or
        (last_map.get(p.split()[-1]) if p else None)
    )


# ─── 4. Construir datos + actualizar Supabase ──────────────────────────────────

def scrape_and_update(porteros_ss: list[dict],
                      full_map: dict, name_map: dict, last_map: dict) -> int:
    log.info("[3/4] Consultando stats individuales y actualizando Supabase...")
    ok = sin_match = sin_datos = err = 0

    for i, gk in enumerate(porteros_ss, 1):
        ss_id  = gk["ss_id"]
        nombre = gk["nombre"]
        equipo = gk["equipo"]

        jid = _resolve(nombre, equipo, full_map, name_map, last_map)
        if not jid:
            sin_match += 1
            log.info("  [%2d/%2d] %-25s → sin match en DB", i, len(porteros_ss), nombre)
            time.sleep(REQUEST_DELAY)
            continue

        stats = fetch_keeper_stats(ss_id)
        time.sleep(REQUEST_DELAY)

        saves  = stats.get("saves")
        goals  = stats.get("goalsConceded")

        if saves is None and goals is None:
            sin_datos += 1
            log.info("  [%2d/%2d] %-25s → sin datos en Sofascore", i, len(porteros_ss), nombre)
            continue

        pct = None
        if saves is not None and goals is not None:
            total_shots = saves + goals
            if total_shots > 0:
                pct = round(saves / total_shots * 100, 1)

        data = {}
        if saves is not None:
            data["portero_paradas"] = int(saves)
        if goals is not None:
            data["portero_goles_encajados"] = int(goals)
        if pct is not None:
            data["portero_paradas_pct"] = pct

        try:
            supabase.table("estadisticas_jugador") \
                .update(data) \
                .eq("jugador_id", jid) \
                .eq("temporada", DB_TEMPORADA) \
                .eq("liga_id", DB_LIGA_ID) \
                .execute()
            ok += 1
            log.info("  [%2d/%2d] %-25s paradas=%-4s GA=%-3s sv%%=%-5s",
                     i, len(porteros_ss), nombre,
                     data.get("portero_paradas"),
                     data.get("portero_goles_encajados"),
                     data.get("portero_paradas_pct"))
        except Exception as e:
            err += 1
            log.warning("  Error jid=%d: %s", jid, e)

    log.info("    Actualizados: %d | Sin match: %d | Sin datos: %d | Errores: %d",
             ok, sin_match, sin_datos, err)
    return ok


# ─── 5. Verificación ──────────────────────────────────────────────────────────

def verify():
    log.info("")
    log.info("[4/4] Verificación de porteros clave:")
    for name in ("Joan Garcia", "Oblak", "Raya", "Remiro", "Lunin"):
        res = (supabase.table("jugadores")
               .select("id, nombre")
               .ilike("nombre", f"%{name}%")
               .limit(1).execute())
        if not res.data:
            continue
        jid = res.data[0]["id"]
        nom = res.data[0]["nombre"]
        est = (supabase.table("estadisticas_jugador")
               .select("portero_paradas, portero_goles_encajados, portero_paradas_pct, minutos")
               .eq("jugador_id", jid).eq("temporada", DB_TEMPORADA).execute())
        if est.data:
            d = est.data[0]
            log.info("  %-25s  paradas=%-4s  GA=%-3s  sv%%=%-5s  min=%s",
                     nom,
                     d.get("portero_paradas"),
                     d.get("portero_goles_encajados"),
                     d.get("portero_paradas_pct"),
                     d.get("minutos"))
        else:
            log.info("  %-25s  → sin estadísticas para %s.", nom, DB_TEMPORADA)


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def run():
    log.info("=" * 58)
    log.info(" Porteros Scraper -- LaLiga %s (Sofascore)", DB_TEMPORADA)
    log.info(" Campos: portero_paradas, portero_goles_encajados, portero_paradas_pct")
    log.info("=" * 58)

    porteros_ss            = fetch_ss_goalkeepers()
    full_map, name_map, last_map = load_supabase_goalkeepers()
    updated                = scrape_and_update(porteros_ss, full_map, name_map, last_map)
    verify()

    log.info("")
    log.info("=" * 58)
    log.info(" RESUMEN: %d porteros actualizados de %d en Sofascore",
             updated, len(porteros_ss))
    log.info("=" * 58)


if __name__ == "__main__":
    run()
