"""
FBref Scraper — LaLiga via soccerdata

Stat types disponibles en soccerdata FBref (verificado):
  standard     → goles, asistencias, minutos, tarjetas, per-90
  shooting     → disparos, disparos a puerta  (xG NO disponible en esta version)
  misc         → recuperaciones (TklW), interceptaciones (Int)

NO disponibles via soccerdata: passing, defense, possession, gca
→ xG/xA vendrán del scraper de Understat (understat_scraper.py)
→ pases, regates, presiones vendrán de FBref directo cuando soccerdata lo soporte

Estrategia de carga:
  1. Cargar todos los stat_types en pandas
  2. Merge en memoria sobre (player, team)
  3. Un único upsert en batch para jugadores y otro para estadísticas
  → Sin bucles por jugador, sin N+1 requests
"""

import sys
import logging
from pathlib import Path
import pandas as pd
import soccerdata as sd

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

LIGA_NOMBRE = "LaLiga"
LIGA_PAIS   = "Espana"
TEMPORADA   = "2526"
FBREF_LIGA  = "ESP-La Liga"
JOIN_ON     = ["player", "team"]          # clave de merge entre stat_types


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _val(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v

def _int(v):
    v = _val(v)
    return int(v) if v is not None else None

def _float(v, decimals=2):
    v = _val(v)
    return round(float(v), decimals) if v is not None else None

def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    """Aplana MultiIndex de columnas → 'Grupo__Subcol'."""
    df = df.copy()
    df.columns = [
        f"{a}__{b}" if b else a
        for a, b in (c if isinstance(c, tuple) else (c, "") for c in df.columns)
    ]
    return df

def _load(fbref: sd.FBref, stat_type: str) -> pd.DataFrame:
    log.info("  stat_type='%s'...", stat_type)
    df = _flatten(fbref.read_player_season_stats(stat_type=stat_type).reset_index())
    log.info("    %d filas, %d columnas.", len(df), len(df.columns))
    return df


# ---------------------------------------------------------------------------
# Merge de todos los stat_types en un único DataFrame
# ---------------------------------------------------------------------------

def build_merged(fbref: sd.FBref) -> pd.DataFrame:
    """
    Carga standard + misc y los une por (player, team).
    Devuelve un DataFrame con todas las columnas necesarias para el upsert.
    shooting no aporta columnas nuevas al schema actual (sin xG).
    """
    log.info("Cargando stat_types desde FBref (cache local si existe)...")
    df_std  = _load(fbref, "standard")
    df_misc = _load(fbref, "misc")

    # Seleccionar solo las columnas útiles de misc antes del merge
    misc_cols = JOIN_ON + [
        "Performance__TklW",   # tackles ganados → recuperaciones
        "Performance__Int",    # interceptaciones → sumadas a recuperaciones
    ]
    df_misc_slim = df_misc[[c for c in misc_cols if c in df_misc.columns]]

    merged = df_std.merge(df_misc_slim, on=JOIN_ON, how="left", suffixes=("", "_misc"))
    log.info("DataFrame combinado: %d filas, %d columnas.", len(merged), len(merged.columns))
    return merged


# ---------------------------------------------------------------------------
# Supabase: liga, equipos, jugadores
# ---------------------------------------------------------------------------

def upsert_liga() -> int:
    log.info("[1/4] Upsertando liga '%s'...", LIGA_NOMBRE)
    res = (
        supabase.table("ligas")
        .upsert({"nombre": LIGA_NOMBRE, "pais": LIGA_PAIS, "temporada_actual": TEMPORADA},
                on_conflict="nombre,pais")
        .execute()
    )
    liga_id = res.data[0]["id"]
    log.info("      id=%d OK", liga_id)
    return liga_id

def upsert_equipos(equipos: list, liga_id: int) -> dict:
    log.info("[2/4] Upsertando %d equipos...", len(equipos))
    rows = [{"nombre": e, "liga_id": liga_id, "temporada": TEMPORADA} for e in equipos]
    res = (
        supabase.table("equipos")
        .upsert(rows, on_conflict="nombre,liga_id,temporada")
        .execute()
    )
    mapping = {r["nombre"]: r["id"] for r in res.data}
    log.info("      %d equipos OK.", len(mapping))
    return mapping

def upsert_jugadores(df: pd.DataFrame, equipo_map: dict) -> dict:
    log.info("[3/4] Upsertando %d jugadores...", len(df))
    rows = []
    for _, row in df.iterrows():
        nombre        = _val(row.get("player"))
        equipo_nombre = _val(row.get("team"))
        if not nombre or not equipo_nombre:
            continue
        edad = None
        raw = _val(row.get("age"))
        if raw:
            try:
                edad = int(str(raw).split("-")[0])
            except (ValueError, IndexError):
                pass
        rows.append({
            "nombre":       nombre,
            "equipo_id":    equipo_map.get(equipo_nombre),
            "posicion":     _val(row.get("pos")),
            "edad":         edad,
            "nacionalidad": _val(row.get("nation")),
        })
    res = (
        supabase.table("jugadores")
        .upsert(rows, on_conflict="nombre,equipo_id")
        .execute()
    )
    mapping = {(r["nombre"], r["equipo_id"]): r["id"] for r in res.data}
    log.info("      %d jugadores OK.", len(mapping))
    return mapping


# ---------------------------------------------------------------------------
# Upsert de estadísticas — UN SOLO batch con todos los campos
# ---------------------------------------------------------------------------

def upsert_estadisticas(df: pd.DataFrame, jugador_map: dict,
                        equipo_map: dict, liga_id: int) -> int:
    log.info("[4/4] Upsertando estadisticas (batch unico)...")
    rows = []
    skipped = 0

    for _, row in df.iterrows():
        nombre        = _val(row.get("player"))
        equipo_nombre = _val(row.get("team"))
        equipo_id     = equipo_map.get(equipo_nombre)
        jugador_id    = jugador_map.get((nombre, equipo_id))

        if not jugador_id:
            skipped += 1
            continue

        tklw = _int(row.get("Performance__TklW"))
        ints = _int(row.get("Performance__Int"))
        recuperaciones = None
        if tklw is not None or ints is not None:
            recuperaciones = (tklw or 0) + (ints or 0)

        rows.append({
            "jugador_id":         jugador_id,
            "temporada":          TEMPORADA,
            "liga_id":            liga_id,
            # standard
            "goles":              _int(row.get("Performance__Gls")),
            "asistencias":        _int(row.get("Performance__Ast")),
            "minutos":            _int(row.get("Playing Time__Min")),
            "goles_por_90":       _float(row.get("Per 90 Minutes__Gls"), 3),
            "asistencias_por_90": _float(row.get("Per 90 Minutes__Ast"), 3),
            "ga_por_90":          _float(row.get("Per 90 Minutes__G+A"), 3),
            # misc
            "recuperaciones":     recuperaciones,
            # pendiente de otras fuentes
            "xg":                 None,
            "xa":                 None,
            "pases_completados":  None,
            "regates":            None,
            "presiones":          None,
        })

    res = (
        supabase.table("estadisticas_jugador")
        .upsert(rows, on_conflict="jugador_id,temporada,liga_id")
        .execute()
    )
    log.info("      %d estadisticas OK, %d skipped.", len(res.data), skipped)
    return len(res.data)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 52)
    log.info(" FBref Scraper — LaLiga %s", TEMPORADA)
    log.info("=" * 52)

    fbref  = sd.FBref(leagues=FBREF_LIGA, seasons=TEMPORADA)
    df     = build_merged(fbref)

    equipos     = sorted(df["team"].dropna().unique().tolist())
    liga_id     = upsert_liga()
    equipo_map  = upsert_equipos(equipos, liga_id)
    jugador_map = upsert_jugadores(df, equipo_map)
    stats_ok    = upsert_estadisticas(df, jugador_map, equipo_map, liga_id)

    log.info("=" * 52)
    log.info(" RESUMEN")
    log.info("  Equipos    : %d", len(equipo_map))
    log.info("  Jugadores  : %d", len(jugador_map))
    log.info("  Estadisticas: %d", stats_ok)
    log.info("  Requests HTTP totales: 4 (liga + equipos + jugadores + stats)")
    log.info("")
    log.info("  PENDIENTE:")
    log.info("    xG / xA       -> understat_scraper.py")
    log.info("    pases/regates -> FBref passing/possession (no en soccerdata aun)")
    log.info("=" * 52)


if __name__ == "__main__":
    run()
