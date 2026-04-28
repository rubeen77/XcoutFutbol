"""
FBref Scraper — LaLiga via soccerdata

Stat types disponibles en esta versión de soccerdata:
  standard     → goles, asistencias, minutos, per-90
  misc         → intercepciones (Int), entradas (TklW), recuperaciones
  keeper       → portero_paradas, portero_goles_encajados, portero_paradas_pct
  shooting     → tiros_totales, tiros_a_puerta

NO disponibles en soccerdata (requieren scraping directo de FBref):
  defense      → bloques, despejes, errores, duelos_aereos
  passing      → pases_completados, pases_progresivos, xg_asistencia
  possession   → regates, conducciones_progresivas
  shooting.xG  → xg (la tabla shooting de soccerdata no incluye Expected)
  keeper.PSxG  → portero_xg_encajado
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
JOIN_ON     = ["player", "team"]


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
    df = df.copy()
    df.columns = [
        f"{a}__{b}" if b else str(a)
        for a, b in (c if isinstance(c, tuple) else (c, "") for c in df.columns)
    ]
    return df

def _load(fbref: sd.FBref, stat_type: str) -> pd.DataFrame:
    log.info("  stat_type='%s'...", stat_type)
    df = _flatten(fbref.read_player_season_stats(stat_type=stat_type).reset_index())
    log.info("    %d filas, %d cols.", len(df), len(df.columns))
    return df


# ---------------------------------------------------------------------------
# Fase 1 — Merge standard + misc
# ---------------------------------------------------------------------------

def build_merged(fbref: sd.FBref) -> pd.DataFrame:
    log.info("Cargando stat_types base (standard + misc)...")
    df_std  = _load(fbref, "standard")
    df_misc = _load(fbref, "misc")

    # Columnas reales disponibles en misc (verificado):
    #   Performance__Int, Performance__TklW
    misc_cols = JOIN_ON + [
        "Performance__TklW",
        "Performance__Int",
    ]
    df_misc_slim = df_misc[[c for c in misc_cols if c in df_misc.columns]]

    merged = df_std.merge(df_misc_slim, on=JOIN_ON, how="left", suffixes=("", "_misc"))
    log.info("DataFrame combinado: %d filas, %d cols.", len(merged), len(merged.columns))
    return merged


# ---------------------------------------------------------------------------
# Supabase: liga, equipos, jugadores
# ---------------------------------------------------------------------------

def upsert_liga() -> int:
    log.info("[1/5] Upsertando liga '%s'...", LIGA_NOMBRE)
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
    log.info("[2/5] Upsertando %d equipos...", len(equipos))
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
    log.info("[3/5] Upsertando %d jugadores...", len(df))
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
# Fase 1 — Upsert estadísticas base (standard + misc)
# ---------------------------------------------------------------------------

def upsert_estadisticas(df: pd.DataFrame, jugador_map: dict,
                        equipo_map: dict, liga_id: int) -> int:
    log.info("[4/5] Upsertando estadisticas base...")
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
            "intercepciones":     ints,
            "entradas":           tklw,
        })

    res = (
        supabase.table("estadisticas_jugador")
        .upsert(rows, on_conflict="jugador_id,temporada,liga_id")
        .execute()
    )
    log.info("      %d estadisticas OK, %d skipped.", len(res.data), skipped)
    return len(res.data)


# ---------------------------------------------------------------------------
# Fase 2 — UPDATE con keeper y shooting (sin insertar filas nuevas)
# ---------------------------------------------------------------------------

def update_extended_stats(fbref: sd.FBref, jugador_map: dict,
                          equipo_map: dict, liga_id: int):
    log.info("[5/5] Actualizando estadisticas extendidas (keeper + shooting)...")

    # Solo actualizar jugadores que ya tienen fila en estadisticas_jugador
    res = (
        supabase.table("estadisticas_jugador")
        .select("jugador_id")
        .eq("temporada", TEMPORADA)
        .eq("liga_id", liga_id)
        .execute()
    )
    existing_ids = {r["jugador_id"] for r in res.data}
    log.info("  Filas existentes: %d", len(existing_ids))

    def resolve_id(row):
        nombre = _val(row.get("player"))
        team   = _val(row.get("team"))
        if not nombre or not team:
            return None
        eid = equipo_map.get(team)
        return jugador_map.get((nombre, eid))

    def batch_upsert(updates: list, label: str):
        valid = [u for u in updates if u.get("jugador_id") in existing_ids]
        if not valid:
            log.warning("  %s: 0 filas validas", label)
            return
        BATCH = 50
        total = 0
        for i in range(0, len(valid), BATCH):
            r = (
                supabase.table("estadisticas_jugador")
                .upsert(valid[i:i + BATCH], on_conflict="jugador_id,temporada,liga_id")
                .execute()
            )
            total += len(r.data)
        log.info("  %s: %d filas actualizadas", label, total)

    # ── KEEPER ───────────────────────────────────────────────────────────────
    # Columnas reales: Performance__GA, Performance__Saves, Performance__Save%
    # NO disponible: Expected__PSxG (portero_xg_encajado)
    try:
        df = _load(fbref, "keeper")
        updates = []
        for _, row in df.iterrows():
            jid = resolve_id(row)
            if not jid:
                continue
            # Save% viene como float (ej. 72.3) — lo dividimos entre 100
            save_pct_raw = _val(row.get("Performance__Save%"))
            save_pct = None
            if save_pct_raw is not None:
                try:
                    save_pct = round(float(save_pct_raw) / 100, 4)
                except (TypeError, ValueError):
                    pass
            updates.append({
                "jugador_id":              jid,
                "temporada":               TEMPORADA,
                "liga_id":                 liga_id,
                "portero_paradas":         _int(row.get("Performance__Saves")),
                "portero_goles_encajados": _int(row.get("Performance__GA")),
                "portero_paradas_pct":     save_pct,
            })
        batch_upsert(updates, "keeper")
    except Exception as e:
        log.warning("  keeper ERROR: %s", e)

    # ── SHOOTING ─────────────────────────────────────────────────────────────
    # Columnas reales: Standard__Sh, Standard__SoT
    # NO disponible: Expected__xG (xg)
    try:
        df = _load(fbref, "shooting")
        updates = []
        for _, row in df.iterrows():
            jid = resolve_id(row)
            if not jid:
                continue
            updates.append({
                "jugador_id":     jid,
                "temporada":      TEMPORADA,
                "liga_id":        liga_id,
                "tiros_totales":  _int(row.get("Standard__Sh")),
                "tiros_a_puerta": _int(row.get("Standard__SoT")),
            })
        batch_upsert(updates, "shooting")
    except Exception as e:
        log.warning("  shooting ERROR: %s", e)


# ---------------------------------------------------------------------------
# Verificación
# ---------------------------------------------------------------------------

def verify(liga_id: int):
    log.info("VERIFICACION")
    for buscar in ("Cubarsi", "Ter Stegen", "Raya"):
        res = (
            supabase.table("jugadores")
            .select("id, nombre")
            .ilike("nombre", f"%{buscar.split()[0]}%")
            .limit(2)
            .execute()
        )
        for j in res.data:
            est = (
                supabase.table("estadisticas_jugador")
                .select(
                    "goles, minutos, intercepciones, entradas, recuperaciones,"
                    "tiros_totales, tiros_a_puerta,"
                    "portero_paradas, portero_goles_encajados, portero_paradas_pct"
                )
                .eq("jugador_id", j["id"])
                .eq("temporada", TEMPORADA)
                .execute()
            )
            if est.data:
                log.info("  %s: %s", j["nombre"], est.data[0])
            else:
                log.info("  %s: sin fila en %s", j["nombre"], TEMPORADA)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 60)
    log.info(" FBref Scraper — LaLiga %s", TEMPORADA)
    log.info("=" * 60)

    fbref = sd.FBref(leagues=FBREF_LIGA, seasons=TEMPORADA)
    df    = build_merged(fbref)

    equipos     = sorted(df["team"].dropna().unique().tolist())
    liga_id     = upsert_liga()
    equipo_map  = upsert_equipos(equipos, liga_id)
    jugador_map = upsert_jugadores(df, equipo_map)
    stats_ok    = upsert_estadisticas(df, jugador_map, equipo_map, liga_id)

    update_extended_stats(fbref, jugador_map, equipo_map, liga_id)

    verify(liga_id)

    log.info("=" * 60)
    log.info(" RESUMEN")
    log.info("  Equipos     : %d", len(equipo_map))
    log.info("  Jugadores   : %d", len(jugador_map))
    log.info("  Stats base  : %d", stats_ok)
    log.info("")
    log.info("  Campos cargados:")
    log.info("    standard: goles, asistencias, minutos, per-90")
    log.info("    misc:     intercepciones, entradas, recuperaciones")
    log.info("    keeper:   portero_paradas, portero_goles_encajados, portero_paradas_pct")
    log.info("    shooting: tiros_totales, tiros_a_puerta")
    log.info("")
    log.info("  Campos NO disponibles en soccerdata (requieren scraping directo):")
    log.info("    xg, xa, xg_asistencia, portero_xg_encajado")
    log.info("    bloques, despejes, errores, duelos_aereos")
    log.info("    pases_completados, pases_progresivos, regates, conducciones_progresivas")
    log.info("=" * 60)


if __name__ == "__main__":
    run()
