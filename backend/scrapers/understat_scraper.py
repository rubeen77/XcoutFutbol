"""
Understat Scraper — xG y xA para LaLiga via soccerdata

Estrategia de cruce de nombres:
  FBref  usa: "Abde Rebbach",  "Alavés",       "Kylian Mbappé"
  Understat:  "Abderrahmane R.", "Alaves",     "Kylian Mbappe"

Pasos:
  1. Normalizar ambos (sin acentos, minúsculas, sin espacios dobles)
  2. Match por (nombre_norm, equipo_norm) — match exacto
  3. Fallback: match solo por nombre_norm dentro del mismo equipo_norm
  4. Fetch de stats existentes en Supabase → merge → upsert batch completo
     (un solo request, sin N+1 por jugador)
"""

import sys
import logging
import unicodedata
from pathlib import Path
import pandas as pd
import soccerdata as sd

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

LIGA_ID      = 1       # LaLiga insertada en la fase anterior
TEMPORADA    = "2526"
UNDERSTAT_LIGA    = "ESP-La Liga"
UNDERSTAT_SEASON  = 2025   # Understat usa el año de inicio de temporada


# ---------------------------------------------------------------------------
# Normalización de nombres para el cruce FBref ↔ Understat
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Elimina acentos, pasa a minúsculas, colapsa espacios."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_str.lower().split())


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------

def load_understat() -> pd.DataFrame:
    log.info("[1/4] Cargando datos de Understat (ESP-La Liga 2025)...")
    understat = sd.Understat(leagues=UNDERSTAT_LIGA, seasons=UNDERSTAT_SEASON)
    df = understat.read_player_season_stats().reset_index()
    log.info("      %d jugadores cargados desde Understat.", len(df))

    df["player_norm"] = df["player"].apply(_norm)
    df["team_norm"]   = df["team"].apply(_norm)
    return df


def load_supabase_stats() -> pd.DataFrame:
    """
    Descarga de Supabase: estadisticas_jugador + nombre jugador + nombre equipo.
    Devuelve DataFrame con todas las columnas para poder hacer upsert completo.
    """
    log.info("[2/4] Leyendo estadisticas existentes en Supabase...")
    res = (
        supabase.table("estadisticas_jugador")
        .select(
            "id, jugador_id, temporada, liga_id, "
            "goles, asistencias, xg, xa, minutos, "
            "pases_completados, regates, presiones, recuperaciones, "
            "goles_por_90, asistencias_por_90, ga_por_90, "
            "jugadores(nombre, equipos(nombre))"
        )
        .eq("temporada", TEMPORADA)
        .eq("liga_id", LIGA_ID)
        .execute()
    )
    rows = []
    for r in res.data:
        jug = r.get("jugadores") or {}
        eq  = jug.get("equipos") or {}
        rows.append({
            "stat_id":         r["id"],
            "jugador_id":      r["jugador_id"],
            "temporada":       r["temporada"],
            "liga_id":         r["liga_id"],
            "goles":           r.get("goles"),
            "asistencias":     r.get("asistencias"),
            "xg":              r.get("xg"),
            "xa":              r.get("xa"),
            "minutos":         r.get("minutos"),
            "pases_completados": r.get("pases_completados"),
            "regates":         r.get("regates"),
            "presiones":       r.get("presiones"),
            "recuperaciones":  r.get("recuperaciones"),
            "goles_por_90":    r.get("goles_por_90"),
            "asistencias_por_90": r.get("asistencias_por_90"),
            "ga_por_90":       r.get("ga_por_90"),
            "player_nombre":   jug.get("nombre", ""),
            "team_nombre":     eq.get("nombre", ""),
        })
    df = pd.DataFrame(rows)
    df["player_norm"] = df["player_nombre"].apply(_norm)
    df["team_norm"]   = df["team_nombre"].apply(_norm)
    log.info("      %d filas leidas de Supabase.", len(df))
    return df


# ---------------------------------------------------------------------------
# Cruce de nombres FBref ↔ Understat
# ---------------------------------------------------------------------------

def build_xg_map(df_understat: pd.DataFrame) -> dict:
    """
    Devuelve {(player_norm, team_norm): (xg, xa)} desde Understat.
    También índice secundario {player_norm: (xg, xa)} para fallback.
    """
    exact  = {}
    by_name = {}
    for _, row in df_understat.iterrows():
        key = (row["player_norm"], row["team_norm"])
        val = (
            round(float(row["xg"]), 3) if pd.notna(row["xg"]) else None,
            round(float(row["xa"]), 3) if pd.notna(row["xa"]) else None,
        )
        exact[key]             = val
        by_name[row["player_norm"]] = val   # último gana si hay duplicados de nombre
    return exact, by_name


def merge_xg(df_supabase: pd.DataFrame, df_understat: pd.DataFrame) -> pd.DataFrame:
    log.info("[3/4] Cruzando nombres FBref <-> Understat...")
    exact_map, name_map = build_xg_map(df_understat)

    matched_exact   = 0
    matched_fallback = 0
    unmatched       = 0

    xg_list, xa_list = [], []

    for _, row in df_supabase.iterrows():
        key = (row["player_norm"], row["team_norm"])

        if key in exact_map:
            xg, xa = exact_map[key]
            matched_exact += 1
        elif row["player_norm"] in name_map:
            xg, xa = name_map[row["player_norm"]]
            matched_fallback += 1
        else:
            xg, xa = None, None
            unmatched += 1

        xg_list.append(xg)
        xa_list.append(xa)

    df_supabase = df_supabase.copy()
    df_supabase["xg"] = xg_list
    df_supabase["xa"] = xa_list

    log.info("      Match exacto (nombre+equipo): %d", matched_exact)
    log.info("      Match por nombre solo        : %d", matched_fallback)
    log.info("      Sin match                    : %d", unmatched)
    return df_supabase, matched_exact + matched_fallback


# ---------------------------------------------------------------------------
# Upsert batch a Supabase — un solo request
# ---------------------------------------------------------------------------

def upsert_xg(df: pd.DataFrame) -> int:
    log.info("[4/4] Actualizando xG/xA en Supabase (batch unico)...")

    # Solo filas con xg o xa real
    df_update = df[df["xg"].notna() | df["xa"].notna()].copy()
    log.info("      %d filas con xG/xA para actualizar.", len(df_update))

    rows = []
    for _, row in df_update.iterrows():
        rows.append({
            "jugador_id":         int(row["jugador_id"]),
            "temporada":          row["temporada"],
            "liga_id":            int(row["liga_id"]),
            "xg":                 row["xg"],
            "xa":                 row["xa"],
            # Preservar campos existentes para no machacarlos con NULL
            "goles":              row.get("goles"),
            "asistencias":        row.get("asistencias"),
            "minutos":            row.get("minutos"),
            "pases_completados":  row.get("pases_completados"),
            "regates":            row.get("regates"),
            "presiones":          row.get("presiones"),
            "recuperaciones":     row.get("recuperaciones"),
            "goles_por_90":       row.get("goles_por_90"),
            "asistencias_por_90": row.get("asistencias_por_90"),
            "ga_por_90":          row.get("ga_por_90"),
        })

    res = (
        supabase.table("estadisticas_jugador")
        .upsert(rows, on_conflict="jugador_id,temporada,liga_id")
        .execute()
    )
    ok = len(res.data)
    log.info("      %d filas actualizadas.", ok)
    return ok


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 52)
    log.info(" Understat Scraper -- xG/xA LaLiga %s", TEMPORADA)
    log.info("=" * 52)

    df_understat       = load_understat()
    df_supabase        = load_supabase_stats()
    df_merged, matched = merge_xg(df_supabase, df_understat)
    updated            = upsert_xg(df_merged)

    log.info("=" * 52)
    log.info(" RESUMEN")
    log.info("  Jugadores en Understat         : %d", len(df_understat))
    log.info("  Jugadores en Supabase          : %d", len(df_supabase))
    log.info("  Matches encontrados            : %d", matched)
    log.info("  Filas actualizadas con xG/xA   : %d", updated)
    log.info("=" * 52)


if __name__ == "__main__":
    run()
