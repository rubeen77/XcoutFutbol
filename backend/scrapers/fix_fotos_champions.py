"""
fix_fotos_champions.py — Copia foto_url desde otras ligas a jugadores de Champions sin foto.

Flujo:
  1. Cargar jugadores de Champions (liga_id=28) sin foto_url
  2. Cargar todos los jugadores de otras ligas que SÍ tienen foto_url
  3. Cruzar por nombre normalizado (exact match primero, apellido como fallback)
  4. UPDATE jugadores SET foto_url = ... WHERE id = ...
  5. Mostrar resumen

Uso (desde backend/):
  conda activate xcout
  python scrapers/fix_fotos_champions.py
"""

import sys
import logging
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

CHAMPIONS_LIGA_ID = 28
BATCH_SIZE        = 50


def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def _apellido(nombre_norm: str) -> str:
    parts = nombre_norm.split()
    return parts[-1] if parts else nombre_norm


# ---------------------------------------------------------------------------
# 1. Jugadores de Champions sin foto
# ---------------------------------------------------------------------------

def load_champions_sin_foto() -> list[dict]:
    log.info("[1/4] Cargando jugadores de Champions sin foto_url...")
    res = (
        supabase.table("jugadores")
        .select("id, nombre, equipo_id, equipos(liga_id)")
        .is_("foto_url", "null")
        .execute()
    )
    # Filtrar solo los de liga_id=28
    rows = [
        r for r in (res.data or [])
        if (r.get("equipos") or {}).get("liga_id") == CHAMPIONS_LIGA_ID
    ]
    log.info("  %d jugadores de Champions sin foto.", len(rows))
    return rows


# ---------------------------------------------------------------------------
# 2. Jugadores de otras ligas con foto
# ---------------------------------------------------------------------------

def load_jugadores_con_foto() -> dict[str, str]:
    """
    Devuelve dos índices:
      exact   : {nombre_norm: foto_url}
      apellido: {apellido_norm: foto_url}
    """
    log.info("[2/4] Cargando jugadores con foto de otras ligas...")
    res = (
        supabase.table("jugadores")
        .select("nombre, foto_url, equipo_id, equipos(liga_id)")
        .not_.is_("foto_url", "null")
        .execute()
    )
    exact: dict[str, str]    = {}
    apellido: dict[str, str] = {}

    for r in (res.data or []):
        liga = (r.get("equipos") or {}).get("liga_id")
        if liga == CHAMPIONS_LIGA_ID:
            continue  # no copiar de Champions a Champions
        foto = r.get("foto_url")
        if not foto:
            continue
        nn = _norm(r.get("nombre", ""))
        if nn and nn not in exact:
            exact[nn] = foto
        ap = _apellido(nn)
        if ap and len(ap) > 3 and ap not in apellido:
            apellido[ap] = foto

    log.info("  %d jugadores con foto en otras ligas.", len(exact))
    return exact, apellido


# ---------------------------------------------------------------------------
# 3. Cruce y UPDATE
# ---------------------------------------------------------------------------

def actualizar_fotos(sin_foto: list[dict], exact: dict, apellido_map: dict):
    log.info("[3/4] Cruzando nombres y aplicando fotos...")

    actualizaciones = []  # lista de (jugador_id, foto_url, match_type)
    sin_match       = []

    for r in sin_foto:
        nombre = r.get("nombre", "")
        nn     = _norm(nombre)
        jid    = r["id"]

        if nn in exact:
            actualizaciones.append((jid, exact[nn], "exacto"))
        else:
            ap = _apellido(nn)
            if ap and len(ap) > 3 and ap in apellido_map:
                actualizaciones.append((jid, apellido_map[ap], "apellido"))
            else:
                sin_match.append(nombre)

    log.info("  Match exacto    : %d", sum(1 for _, _, t in actualizaciones if t == "exacto"))
    log.info("  Match apellido  : %d", sum(1 for _, _, t in actualizaciones if t == "apellido"))
    log.info("  Sin match       : %d", len(sin_match))
    if sin_match:
        log.info("  Jugadores sin match (primeros 20):")
        for n in sin_match[:20]:
            log.info("    - %s", n)

    if not actualizaciones:
        log.info("  Nada que actualizar.")
        return 0

    log.info("[4/4] Aplicando UPDATE en Supabase (%d jugadores)...", len(actualizaciones))
    ok = 0
    for i in range(0, len(actualizaciones), BATCH_SIZE):
        batch = actualizaciones[i:i + BATCH_SIZE]
        for jid, foto, _ in batch:
            supabase.table("jugadores").update({"foto_url": foto}).eq("id", jid).execute()
            ok += 1
        log.info("  %d/%d actualizados...", min(i + BATCH_SIZE, len(actualizaciones)), len(actualizaciones))

    return ok


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 60)
    log.info(" fix_fotos_champions — copia foto_url desde otras ligas")
    log.info("=" * 60)

    sin_foto          = load_champions_sin_foto()
    exact, apellido   = load_jugadores_con_foto()
    actualizados      = actualizar_fotos(sin_foto, exact, apellido)

    log.info("=" * 60)
    log.info(" RESUMEN")
    log.info("  Sin foto (antes) : %d", len(sin_foto))
    log.info("  Actualizados     : %d", actualizados)
    log.info("  Sin resolver     : %d", len(sin_foto) - actualizados)
    log.info("=" * 60)


if __name__ == "__main__":
    run()
