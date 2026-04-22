"""
FBref Historical Scraper — LaLiga últimas 5 temporadas (2020/21 – 2024/25)

Carga estadísticas históricas desde FBref via soccerdata y las inserta en:
  - estadisticas_jugador  (jugador_id, temporada, liga_id, goles, asistencias, ...)

Estrategia de matching de jugadores:
  1. Carga el mapa global nombre_normalizado → jugador_id desde Supabase
  2. Para cada temporada histórica:
       a. Descarga standard + misc de FBref (cache local soccerdata)
       b. Upserta equipos de esa temporada (on_conflict nombre,liga_id,temporada)
       c. Crea jugadores nuevos que no estén aún en la DB
       d. Upserta estadísticas vinculando al jugador_id existente
  3. Jugadores que cambiaron de equipo mid-season aparecen como filas individuales
     + fila agregada "2 Squads". Se procesa todo; el upsert mantiene una fila
     por (jugador_id, temporada, liga_id), la última escritura gana.

Temporadas soportadas (formato soccerdata YYZZ):
  "2021" → 2020/21
  "2122" → 2021/22
  "2223" → 2022/23
  "2324" → 2023/24
  "2425" → 2024/25
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

FBREF_LIGA  = "ESP-La Liga"
LIGA_NOMBRE = "LaLiga"
LIGA_PAIS   = "Espana"
MIN_MINUTOS = 90   # ignorar jugadores con < 90 minutos en la temporada

# (soccerdata_season_key, codigo_interno_db)
TEMPORADAS = [
    ("2021", "2021"),   # 2020/21
    ("2122", "2122"),   # 2021/22
    ("2223", "2223"),   # 2022/23
    ("2324", "2324"),   # 2023/24
    ("2425", "2425"),   # 2024/25
]

JOIN_ON = ["player", "team"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Sin acentos, minúsculas, espacios colapsados."""
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


def _is_aggregate(team_name: str) -> bool:
    """Detecta filas de jugadores que cambiaron de equipo ('2 Squads', '3 Clubs', etc.)."""
    if not team_name:
        return False
    return "squad" in str(team_name).lower() or "club" in str(team_name).lower()


# ---------------------------------------------------------------------------
# FBref: carga y merge de stat_types
# ---------------------------------------------------------------------------

def _load_stat(fbref: sd.FBref, stat_type: str) -> pd.DataFrame:
    log.info("    stat_type='%s'...", stat_type)
    try:
        df = _flatten(fbref.read_player_season_stats(stat_type=stat_type).reset_index())
        log.info("      %d filas, %d columnas.", len(df), len(df.columns))
        return df
    except Exception as e:
        log.warning("    No disponible '%s': %s", stat_type, e)
        return pd.DataFrame()


def build_merged(fbref: sd.FBref) -> pd.DataFrame:
    df_std  = _load_stat(fbref, "standard")
    df_misc = _load_stat(fbref, "misc")

    if df_std.empty:
        return df_std

    if not df_misc.empty:
        misc_cols = JOIN_ON + [
            c for c in ["Performance__TklW", "Performance__Int"]
            if c in df_misc.columns
        ]
        df_misc_slim = df_misc[misc_cols]
        merged = df_std.merge(df_misc_slim, on=JOIN_ON, how="left", suffixes=("", "_misc"))
    else:
        merged = df_std.copy()

    log.info("    Merged: %d filas, %d columnas.", len(merged), len(merged.columns))
    return merged


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def get_liga_id() -> int:
    """Obtiene (o crea) el registro de LaLiga; devuelve su id."""
    res = (
        supabase.table("ligas")
        .upsert(
            {"nombre": LIGA_NOMBRE, "pais": LIGA_PAIS, "temporada_actual": "2526"},
            on_conflict="nombre,pais",
        )
        .execute()
    )
    liga_id = res.data[0]["id"]
    log.info("Liga '%s' id=%d", LIGA_NOMBRE, liga_id)
    return liga_id


def load_jugadores_map() -> dict:
    """
    Devuelve {nombre_normalizado: jugador_id} para todos los jugadores en Supabase.
    Si hay duplicados de nombre, conserva el primer id encontrado.
    """
    res = supabase.table("jugadores").select("id, nombre").execute()
    mapping: dict[str, int] = {}
    for r in res.data:
        key = _norm(r["nombre"])
        if key and key not in mapping:
            mapping[key] = r["id"]
    log.info("Jugadores existentes en DB: %d", len(mapping))
    return mapping


def upsert_equipos(equipos: list[str], liga_id: int, temporada: str) -> dict:
    """Upserta la lista de equipos y devuelve {nombre: equipo_id}."""
    rows = [{"nombre": e, "liga_id": liga_id, "temporada": temporada} for e in equipos]
    res = (
        supabase.table("equipos")
        .upsert(rows, on_conflict="nombre,liga_id,temporada")
        .execute()
    )
    mapping = {r["nombre"]: r["id"] for r in res.data}
    log.info("  Equipos upsertados: %d", len(mapping))
    return mapping


def upsert_jugadores_nuevos(
    df: pd.DataFrame,
    equipo_map: dict,
    jugador_map: dict,
) -> dict:
    """
    Inserta en Supabase los jugadores que no estén aún en jugador_map.
    Solo procesa filas con equipo real (no filas '2 Squads').
    Actualiza jugador_map in-place y lo devuelve.
    """
    nuevos = []
    for _, row in df.iterrows():
        nombre = _val(row.get("player"))
        if not nombre:
            continue
        nombre_norm = _norm(nombre)
        if nombre_norm in jugador_map:
            continue

        equipo_nombre = _val(row.get("team"))
        if _is_aggregate(equipo_nombre):
            continue  # filas '2 Squads' no tienen equipo real

        equipo_id = equipo_map.get(equipo_nombre)
        if not equipo_id:
            continue

        edad = None
        raw_age = _val(row.get("age"))
        if raw_age:
            try:
                edad = int(str(raw_age).split("-")[0])
            except (ValueError, IndexError):
                pass

        nuevos.append({
            "nombre":       nombre,
            "equipo_id":    equipo_id,
            "posicion":     _val(row.get("pos")),
            "edad":         edad,
            "nacionalidad": _val(row.get("nation")),
        })

    if not nuevos:
        log.info("  Sin jugadores nuevos que insertar.")
        return jugador_map

    log.info("  Insertando %d jugadores nuevos...", len(nuevos))
    res = (
        supabase.table("jugadores")
        .upsert(nuevos, on_conflict="nombre,equipo_id")
        .execute()
    )
    for r in res.data:
        key = _norm(r["nombre"])
        if key and key not in jugador_map:
            jugador_map[key] = r["id"]

    log.info("  Mapa de jugadores total: %d", len(jugador_map))
    return jugador_map


def upsert_estadisticas(
    df: pd.DataFrame,
    jugador_map: dict,
    liga_id: int,
    temporada: str,
) -> int:
    """
    Construye y upserta las filas de estadisticas_jugador.
    Para jugadores con fila '2 Squads' (mid-season transfer), esa fila
    sobreescribe las individuales porque viene al final del DataFrame (FBref).
    """
    rows = []
    skipped = 0

    for _, row in df.iterrows():
        nombre = _val(row.get("player"))
        if not nombre:
            skipped += 1
            continue

        jugador_id = jugador_map.get(_norm(nombre))
        if not jugador_id:
            skipped += 1
            continue

        min_val = _int(row.get("Playing Time__Min"))
        if min_val is not None and min_val < MIN_MINUTOS:
            skipped += 1
            continue

        tklw  = _int(row.get("Performance__TklW"))
        ints  = _int(row.get("Performance__Int"))
        recup = (tklw or 0) + (ints or 0) if (tklw is not None or ints is not None) else None

        rows.append({
            "jugador_id":         jugador_id,
            "temporada":          temporada,
            "liga_id":            liga_id,
            "goles":              _int(row.get("Performance__Gls")),
            "asistencias":        _int(row.get("Performance__Ast")),
            "minutos":            min_val,
            "goles_por_90":       _float(row.get("Per 90 Minutes__Gls"), 3),
            "asistencias_por_90": _float(row.get("Per 90 Minutes__Ast"), 3),
            "ga_por_90":          _float(row.get("Per 90 Minutes__G+A"), 3),
            "recuperaciones":     recup,
            "xg":                 None,
            "xa":                 None,
            "pases_completados":  None,
            "regates":            None,
            "presiones":          None,
        })

    if not rows:
        log.info("  Sin estadísticas para insertar (skipped=%d).", skipped)
        return 0

    # Deduplicar por (jugador_id, temporada, liga_id) antes del upsert.
    # FBref genera filas duplicadas para jugadores que cambiaron de equipo
    # mid-season (fila por equipo + fila agregada "2 Squads"). Conservamos
    # la última aparición de cada clave, que corresponde a la fila agregada.
    seen: dict[tuple, int] = {}
    for i, r in enumerate(rows):
        key = (r["jugador_id"], r["temporada"], r["liga_id"])
        seen[key] = i
    rows_dedup = [rows[i] for i in seen.values()]

    dupes = len(rows) - len(rows_dedup)
    if dupes:
        log.info("  Duplicados eliminados antes del upsert: %d", dupes)

    res = (
        supabase.table("estadisticas_jugador")
        .upsert(rows_dedup, on_conflict="jugador_id,temporada,liga_id")
        .execute()
    )
    ok = len(res.data)
    log.info("  Estadísticas: %d OK, %d skipped.", ok, skipped)
    return ok


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 62)
    log.info(" FBref Histórico — LaLiga (2020/21 – 2024/25)")
    log.info("=" * 62)

    liga_id     = get_liga_id()
    jugador_map = load_jugadores_map()

    total_stats = 0
    procesadas  = 0

    for fbref_key, temporada in TEMPORADAS:
        log.info("")
        log.info("─" * 62)
        log.info(" Temporada %s  (FBref key: %s)", temporada, fbref_key)
        log.info("─" * 62)

        try:
            fbref = sd.FBref(leagues=FBREF_LIGA, seasons=fbref_key)
            df    = build_merged(fbref)
        except Exception as e:
            log.error("  Error descargando temporada %s: %s", fbref_key, e)
            continue

        if df.empty:
            log.warning("  DataFrame vacío, saltando temporada %s.", temporada)
            continue

        # Equipos reales de esta temporada (excluir filas agregadas)
        equipos_reales = sorted(
            e for e in df["team"].dropna().unique()
            if not _is_aggregate(e)
        )
        equipo_map  = upsert_equipos(equipos_reales, liga_id, temporada)
        jugador_map = upsert_jugadores_nuevos(df, equipo_map, jugador_map)
        n           = upsert_estadisticas(df, jugador_map, liga_id, temporada)

        total_stats += n
        procesadas  += 1
        log.info("  ✓ Temporada %s completada: %d estadísticas.", temporada, n)

    log.info("")
    log.info("=" * 62)
    log.info(" RESUMEN FINAL")
    log.info("  Temporadas procesadas : %d / %d", procesadas, len(TEMPORADAS))
    log.info("  Total estadísticas    : %d", total_stats)
    log.info("  Jugadores en mapa     : %d", len(jugador_map))
    log.info("=" * 62)


if __name__ == "__main__":
    run()
