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
import math
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

# Nombres que Understat no acentúa o abrevia diferente a Supabase
MANUAL_NAME_MAP = {
    "kylian mbappe-lottin": "kylian mbappe",  # Understat usa apellido compuesto
    "cucho hernandez":      "cucho",           # apodo en Supabase
    "kike garcia":          "kike",            # apodo en Supabase (Espanyol)
}


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
    df["player_norm"] = df["player_norm"].map(lambda n: MANUAL_NAME_MAP.get(n, n))
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

def _lastname(norm_name: str) -> str:
    """Último token del nombre normalizado ('kylian mbappe' → 'mbappe')."""
    parts = norm_name.split()
    return parts[-1] if parts else norm_name


def build_xg_map(df_understat: pd.DataFrame) -> tuple[dict, dict, dict]:
    """
    Devuelve tres índices desde Understat:
      exact    : {(player_norm, team_norm): (xg, xa)}
      by_name  : {player_norm: (xg, xa)}             — fallback tier 2
      by_last  : {lastname: (xg, xa)}                — fallback tier 3
    """
    exact    = {}
    by_name  = {}
    by_last  = {}
    for _, row in df_understat.iterrows():
        key = (row["player_norm"], row["team_norm"])
        val = (
            round(float(row["xg"]), 3) if pd.notna(row["xg"]) else None,
            round(float(row["xa"]), 3) if pd.notna(row["xa"]) else None,
        )
        exact[key]                          = val
        by_name[row["player_norm"]]         = val
        by_last[_lastname(row["player_norm"])] = val
    return exact, by_name, by_last


def merge_xg(df_supabase: pd.DataFrame, df_understat: pd.DataFrame) -> pd.DataFrame:
    log.info("[3/4] Cruzando nombres FBref <-> Understat...")
    exact_map, name_map, last_map = build_xg_map(df_understat)

    matched_exact    = 0
    matched_fallback = 0
    matched_last     = 0
    unmatched_names  = []

    xg_list, xa_list = [], []

    for _, row in df_supabase.iterrows():
        key  = (row["player_norm"], row["team_norm"])
        last = _lastname(row["player_norm"])

        if key in exact_map:
            xg, xa = exact_map[key]
            matched_exact += 1
        elif row["player_norm"] in name_map:
            xg, xa = name_map[row["player_norm"]]
            matched_fallback += 1
        elif last in last_map:
            xg, xa = last_map[last]
            matched_last += 1
        else:
            xg, xa = None, None
            unmatched_names.append(f"{row['player_nombre']} [{row['player_norm']}]")

        xg_list.append(xg)
        xa_list.append(xa)

    df_supabase = df_supabase.copy()
    df_supabase["xg"] = xg_list
    df_supabase["xa"] = xa_list

    log.info("      Match exacto (nombre+equipo): %d", matched_exact)
    log.info("      Match por nombre solo        : %d", matched_fallback)
    log.info("      Match por apellido           : %d", matched_last)
    log.info("      Sin match                    : %d", len(unmatched_names))
    if unmatched_names:
        log.info("      Jugadores sin match:")
        for n in unmatched_names:
            log.info("        - %s", n)
    return df_supabase, matched_exact + matched_fallback + matched_last


# ---------------------------------------------------------------------------
# Upsert batch a Supabase — un solo request
# ---------------------------------------------------------------------------

def _safe_int(v):
    """Convierte a Python int; devuelve None si es NaN/inf/None."""
    if v is None:
        return None
    try:
        f = float(v)  # float() convierte numpy scalars a Python float
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return int(f)


def _safe_float(v, dec=3):
    """Convierte a Python float redondeado; devuelve None si es NaN/inf/None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, dec)


def upsert_xg(df: pd.DataFrame) -> int:
    log.info("[4/4] Actualizando xG/xA en Supabase (batch unico)...")

    # Solo filas con xg o xa real
    df_update = df[df["xg"].notna() | df["xa"].notna()].copy()
    log.info("      %d filas con xG/xA para actualizar.", len(df_update))

    rows = []
    for _, row in df_update.iterrows():
        # Solo enviar las claves del conflicto + xg/xa.
        # Supabase UPDATE SET deja el resto de columnas sin tocar.
        rows.append({
            "jugador_id": int(row["jugador_id"]),
            "temporada":  row["temporada"],
            "liga_id":    int(row["liga_id"]),
            "xg":         _safe_float(row["xg"]),
            "xa":         _safe_float(row["xa"]),
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
