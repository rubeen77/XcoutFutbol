"""
Fix xG/xA nulos en Serie A 2025/26

Vuelve a correr solo las fases 3 (shooting FBref) y 5 (Understat)
usando la _norm mejorada con tabla de caracteres especiales.

Solo toca jugadores que actualmente tienen xg IS NULL en Supabase.
No modifica goles, asistencias, minutos ni ninguna otra métrica.

Uso (desde backend/):
  conda activate xcout
  python scrapers/fix_seriea_xg.py
"""

import io
import sys
import math
import logging
import unicodedata
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import soccerdata as sd

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

TEMPORADA  = "2526"
LIGA_ID    = 26
LEAGUE_STR = "ITA-Serie A"

# Tabla de caracteres que NFKD no convierte bien
_CHAR_MAP = str.maketrans({
    'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G',
    'ş': 's', 'Ş': 'S', 'ð': 'd', 'Ð': 'D',
    'þ': 'th', 'ø': 'o', 'Ø': 'O',
    'æ': 'ae', 'Æ': 'Ae', 'ł': 'l', 'Ł': 'L',
    'ß': 'ss', "'": '', '’': '', '‘': '',
    '-': ' ', '–': ' ', '—': ' ',
})


def _norm(text: str) -> str:
    if not text:
        return ""
    text = str(text).translate(_CHAR_MAP)
    nfkd = unicodedata.normalize("NFKD", text)
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


def _find_col(df: pd.DataFrame, *keywords, reject=None) -> "str | None":
    reject = [r.lower() for r in (reject or [])]
    for col in df.columns:
        cl = col.lower()
        if all(k.lower() in cl for k in keywords) and not any(r in cl for r in reject):
            return col
    return None


# --- Carga jugadores con xG nulo desde Supabase ---------------------------------

def load_null_xg_players() -> tuple[dict, dict, dict]:
    """
    Devuelve tres mapas para resolver nombre -> jugador_id:
      full_map: {(nombre_norm, equipo_norm): jugador_id}
      name_map: {nombre_norm: jugador_id}
      last_map: {apellido_norm: jugador_id}  (solo para los null-xG)
    """
    log.info("[1] Cargando jugadores con xG nulo (Serie A 2025/26)...")

    res = (
        supabase.table("estadisticas_jugador")
        .select("jugador_id, jugadores(nombre, equipos(nombre))")
        .eq("temporada", TEMPORADA)
        .eq("liga_id", LIGA_ID)
        .is_("xg", "null")
        .execute()
    )
    rows = res.data or []
    log.info("    %d jugadores con xG nulo.", len(rows))

    full_map: dict = {}
    name_map: dict = {}
    last_map: dict = {}

    for r in rows:
        jid  = r["jugador_id"]
        jug  = r.get("jugadores") or {}
        eq   = (jug.get("equipos") or {})
        name = _norm(jug.get("nombre", ""))
        team = _norm(eq.get("nombre", ""))
        if not name:
            continue
        full_map[(name, team)] = jid
        if name not in name_map:
            name_map[name] = jid
        last = name.split()[-1]
        if last and last not in last_map:
            last_map[last] = jid

    log.info("    name_map: %d entradas.", len(name_map))
    for nombre_n in sorted(name_map.keys()):
        log.info("      %s", nombre_n)
    return full_map, name_map, last_map


def _resolve(pnorm, snorm, full_map, name_map, last_map):
    return (
        full_map.get((pnorm, snorm)) or
        name_map.get(pnorm) or
        (last_map.get(pnorm.split()[-1]) if pnorm else None)
    )


# --- Fase 3: shooting FBref (xG inicial) ----------------------------------------

def fetch_shooting_xg(full_map, name_map, last_map) -> int:
    log.info("[2] Descargando shooting stats (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = _flatten(fbref.read_player_season_stats(stat_type="shooting").reset_index())
        log.info("    shape=%s", df.shape)
    except Exception as e:
        log.error("    Error: %s", e)
        return 0

    col_xg = (
        _find_col(df, "expected__xg", reject=["np", "90", "/90"]) or
        _find_col(df, "xg",           reject=["np", "90", "/90"])
    )
    log.info("    xG <- %s", col_xg)
    if not col_xg:
        log.warning("    No se encontró columna xG en shooting stats.")
        return 0

    ok = sin_match = sin_xg = 0
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player or player == "player":
            continue

        jid = _resolve(player, squad, full_map, name_map, last_map)
        if not jid:
            sin_match += 1
            continue

        xg_val = _safe_float(r.get(col_xg))
        if xg_val is None:
            sin_xg += 1
            continue

        try:
            supabase.table("estadisticas_jugador") \
                .update({"xg": xg_val}) \
                .eq("jugador_id", jid) \
                .eq("temporada", TEMPORADA) \
                .eq("liga_id", LIGA_ID) \
                .execute()
            ok += 1
            log.info("    [FBref-xG] %-30s  xG=%s", player, xg_val)
        except Exception as e:
            log.warning("    Error actualizando jid=%d: %s", jid, e)

    log.info("    OK=%d | sin_match=%d | sin_xg_val=%d", ok, sin_match, sin_xg)
    return ok


# --- Fase 5: Understat (xG + xA definitivos) ------------------------------------

def fetch_understat_xgxa(full_map, name_map, last_map) -> int:
    log.info("[3] Descargando xG/xA (Understat)...")
    try:
        us = sd.Understat(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df = us.read_player_season_stats().reset_index()
        log.info("    shape=%s", df.shape)
    except Exception as e:
        log.error("    Error: %s", e)
        return 0

    ok = sin_match = 0
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player:
            continue

        jid = _resolve(player, squad, full_map, name_map, last_map)
        if not jid:
            sin_match += 1
            continue

        xg_val = _safe_float(r.get("xg"))
        xa_val = _safe_float(r.get("xa"))
        if xg_val is None and xa_val is None:
            continue

        data = {}
        if xg_val is not None:
            data["xg"] = xg_val
        if xa_val is not None:
            data["xa"] = xa_val

        try:
            supabase.table("estadisticas_jugador") \
                .update(data) \
                .eq("jugador_id", jid) \
                .eq("temporada", TEMPORADA) \
                .eq("liga_id", LIGA_ID) \
                .execute()
            ok += 1
            log.info("    [Understat] %-30s  xG=%s  xA=%s", player, xg_val, xa_val)
        except Exception as e:
            log.warning("    Error actualizando jid=%d: %s", jid, e)

    log.info("    OK=%d | sin_match=%d", ok, sin_match)
    return ok


# --- Verificación final ----------------------------------------------------------

def verify(full_map, name_map, last_map):
    log.info("")
    log.info("[VERIFY] Revisando jugadores objetivo...")

    targets = [
        "Kenan Yildiz", "Albert Gudmundsson", "Albert Gronbaek",
        "Jan Ziolkowski", "Semih Kilicsoy",
    ]
    for name in targets:
        n = _norm(name)
        jid = name_map.get(n)
        if not jid:
            log.info("  %-30s  -> no en null-xG list (ya tenía xG o no existe)", name)
            continue
        res = (
            supabase.table("estadisticas_jugador")
            .select("xg, xa")
            .eq("jugador_id", jid)
            .eq("temporada", TEMPORADA)
            .eq("liga_id", LIGA_ID)
            .execute()
        )
        if res.data:
            d = res.data[0]
            log.info("  %-30s  xG=%-6s  xA=%s", name, d.get("xg"), d.get("xa"))
        else:
            log.info("  %-30s  -> sin fila en estadisticas", name)


# --- Entrypoint ------------------------------------------------------------------

def run():
    log.info("=" * 60)
    log.info(" Fix xG/xA nulos — Serie A %s", TEMPORADA)
    log.info("=" * 60)

    full_map, name_map, last_map = load_null_xg_players()
    if not name_map:
        log.info("No hay jugadores con xG nulo. Nada que hacer.")
        return

    ok_fbref     = fetch_shooting_xg(full_map, name_map, last_map)
    ok_understat = fetch_understat_xgxa(full_map, name_map, last_map)

    verify(full_map, name_map, last_map)

    log.info("")
    log.info("=" * 60)
    log.info(" RESUMEN")
    log.info("  Actualizados FBref shooting : %d", ok_fbref)
    log.info("  Actualizados Understat      : %d", ok_understat)
    log.info("=" * 60)


if __name__ == "__main__":
    run()
