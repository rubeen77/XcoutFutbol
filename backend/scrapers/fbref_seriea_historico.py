"""
FBref Serie A Historical Scraper
Temporadas: 2021/22, 2022/23, 2023/24, 2024/25 (soccerdata keys: 2122 ... 2425)

Solo metricas basicas desde stat_type='standard':
  goles, asistencias, minutos, goles_por_90, asistencias_por_90, ga_por_90

Solo inserta filas para jugadores que YA existen en Supabase con liga_id=26.
No crea jugadores ni equipos nuevos.
Usa INSERT con ignore_duplicates=True para no sobreescribir datos existentes.

Uso (desde backend/):
  conda activate xcout
  python scrapers/fbref_seriea_historico.py
  python scrapers/fbref_seriea_historico.py --temporada 2425
"""

import sys
import argparse
import logging
import math
import unicodedata
from pathlib import Path

import pandas as pd
import soccerdata as sd

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

FBREF_LIGA  = "ITA-Serie A"
LIGA_ID     = 26
MIN_MINUTOS = 90

# (soccerdata_key, codigo_interno_db)
TEMPORADAS = [
    ("2122", "2122"),  # 2021/22
    ("2223", "2223"),  # 2022/23
    ("2324", "2324"),  # 2023/24
    ("2425", "2425"),  # 2024/25
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def _val(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _safe_int(v) -> "int | None":
    v = _val(v)
    if v is None:
        return None
    try:
        f = float(str(v).replace(",", ""))
        return None if (math.isnan(f) or math.isinf(f)) else int(round(f))
    except Exception:
        return None


def _safe_float(v, dec: int = 2) -> "float | None":
    v = _val(v)
    if v is None:
        return None
    try:
        f = float(str(v).replace(",", ""))
        return None if (math.isnan(f) or math.isinf(f)) else round(f, dec)
    except Exception:
        return None


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        f"{a}__{b}" if b else a
        for a, b in (c if isinstance(c, tuple) else (c, "") for c in df.columns)
    ]
    return df


# ---------------------------------------------------------------------------
# Cargar mapa de jugadores Serie A desde Supabase
# ---------------------------------------------------------------------------

def load_seriea_jugadores() -> tuple[dict, dict, dict]:
    """
    Carga todos los jugadores con equipo de liga_id=26.
    Devuelve:
      full_map: {(nombre_norm, equipo_norm): jugador_id}
      name_map: {nombre_norm: jugador_id}
      last_map: {apellido_norm: jugador_id}
    """
    log.info("[DB] Cargando jugadores Serie A (liga_id=%d)...", LIGA_ID)

    eq_res = (
        supabase.table("equipos")
        .select("id, nombre")
        .eq("liga_id", LIGA_ID)
        .eq("temporada", "2526")
        .execute()
    )
    eq_ids   = [e["id"] for e in (eq_res.data or [])]
    eq_names = {e["id"]: e["nombre"] for e in (eq_res.data or [])}
    log.info("    %d equipos Serie A.", len(eq_ids))

    all_jug = []
    for i in range(0, len(eq_ids), 50):
        res = (
            supabase.table("jugadores")
            .select("id, nombre, equipo_id")
            .in_("equipo_id", eq_ids[i:i+50])
            .execute()
        )
        all_jug.extend(res.data or [])

    full_map: dict = {}
    name_map: dict = {}
    last_map: dict = {}

    for r in all_jug:
        jid  = r["id"]
        name = _norm(r.get("nombre") or "")
        team = _norm(eq_names.get(r.get("equipo_id"), ""))
        if not name:
            continue
        full_map[(name, team)] = jid
        if name not in name_map:
            name_map[name] = jid
        last = name.split()[-1]
        if last and last not in last_map:
            last_map[last] = jid

    log.info("    %d jugadores cargados.", len(name_map))
    return full_map, name_map, last_map


def _resolve(pnorm: str, snorm: str, full_map: dict, name_map: dict, last_map: dict) -> "int | None":
    return (
        full_map.get((pnorm, snorm)) or
        name_map.get(pnorm) or
        (last_map.get(pnorm.split()[-1]) if pnorm else None)
    )


# ---------------------------------------------------------------------------
# FBref: descargar standard stats para una temporada de Serie A
# ---------------------------------------------------------------------------

def fetch_standard(fbref_key: str) -> pd.DataFrame:
    log.info("  [FBref] Descargando standard stats (key=%s)...", fbref_key)
    try:
        fbref = sd.FBref(leagues=FBREF_LIGA, seasons=fbref_key)
        df    = _flatten(fbref.read_player_season_stats(stat_type="standard").reset_index())
        log.info("    %d filas, %d columnas.", len(df), len(df.columns))
        return df
    except Exception as e:
        log.error("    Error descargando %s: %s", fbref_key, e)
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Construir filas de estadisticas
# ---------------------------------------------------------------------------

def build_rows(
    df: pd.DataFrame,
    temporada: str,
    full_map: dict,
    name_map: dict,
    last_map: dict,
) -> list[dict]:
    rows = []
    skipped_min = skipped_nomatch = 0

    for _, row in df.iterrows():
        player = _val(row.get("player"))
        if not player or str(player).strip().lower() == "player":
            continue

        pnorm = _norm(str(player))
        snorm = _norm(str(row.get("team") or ""))

        min_val = _safe_int(row.get("Playing Time__Min"))
        if min_val is not None and min_val < MIN_MINUTOS:
            skipped_min += 1
            continue

        jid = _resolve(pnorm, snorm, full_map, name_map, last_map)
        if not jid:
            skipped_nomatch += 1
            continue

        rows.append({
            "jugador_id":         jid,
            "temporada":          temporada,
            "liga_id":            LIGA_ID,
            "goles":              _safe_int(row.get("Performance__Gls")),
            "asistencias":        _safe_int(row.get("Performance__Ast")),
            "minutos":            min_val,
            "goles_por_90":       _safe_float(row.get("Per 90 Minutes__Gls"), 3),
            "asistencias_por_90": _safe_float(row.get("Per 90 Minutes__Ast"), 3),
            "ga_por_90":          _safe_float(row.get("Per 90 Minutes__G+A"), 3),
        })

    log.info(
        "    Filas construidas: %d | sin_match: %d | filtrados_min: %d",
        len(rows), skipped_nomatch, skipped_min,
    )
    return rows


# ---------------------------------------------------------------------------
# Deduplicar y insertar
# ---------------------------------------------------------------------------

def insert_estadisticas(rows: list[dict]) -> int:
    if not rows:
        log.info("    Nada que insertar.")
        return 0

    seen: dict[tuple, int] = {}
    for i, r in enumerate(rows):
        seen[(r["jugador_id"], r["temporada"])] = i
    rows_dedup = [rows[i] for i in seen.values()]

    dupes = len(rows) - len(rows_dedup)
    if dupes:
        log.info("    Duplicados eliminados: %d", dupes)

    res = (
        supabase.table("estadisticas_jugador")
        .upsert(rows_dedup, on_conflict="jugador_id,temporada,liga_id", ignore_duplicates=True)
        .execute()
    )
    ok = len(res.data)
    log.info("    Insertadas: %d (las ya existentes se ignoran).", ok)
    return ok


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run(solo_temporada: str | None = None):
    temporadas = TEMPORADAS
    if solo_temporada:
        temporadas = [(k, t) for k, t in TEMPORADAS if t == solo_temporada]
        if not temporadas:
            log.error(
                "Temporada '%s' no valida. Opciones: %s",
                solo_temporada, [t for _, t in TEMPORADAS],
            )
            return

    log.info("=" * 64)
    log.info(" FBref Serie A Historico  (liga_id=%d)", LIGA_ID)
    log.info(" Temporadas: %s", [t for _, t in temporadas])
    log.info(" Metricas  : goles, asistencias, minutos, g90, a90, ga90")
    log.info("=" * 64)

    full_map, name_map, last_map = load_seriea_jugadores()
    if not name_map:
        log.error("Sin jugadores Serie A en DB. Ejecuta fbref_seriea.py primero.")
        return

    total_ok   = 0
    procesadas = 0

    for fbref_key, temporada in temporadas:
        log.info("")
        log.info("--- Temporada %s (FBref: %s) ---", temporada, fbref_key)

        df = fetch_standard(fbref_key)
        if df.empty:
            log.warning("  DataFrame vacio, saltando %s.", temporada)
            continue

        rows = build_rows(df, temporada, full_map, name_map, last_map)
        ok   = insert_estadisticas(rows)

        total_ok   += ok
        procesadas += 1

    log.info("")
    log.info("=" * 64)
    log.info(" RESUMEN")
    log.info("  Temporadas procesadas : %d / %d", procesadas, len(temporadas))
    log.info("  Total insertadas      : %d", total_ok)
    log.info("=" * 64)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FBref historico Serie A — solo standard stats")
    parser.add_argument(
        "--temporada",
        metavar="CLAVE",
        choices=[t for _, t in TEMPORADAS],
        help="Procesar solo esta temporada (ej: --temporada 2425)",
    )
    args = parser.parse_args()
    run(solo_temporada=args.temporada)
