"""
Fix xG/xA nulos en Ligue 1 2025/26

Vuelve a correr solo las fases 3 (shooting FBref) y 5 (Understat)
usando la _norm mejorada con tabla de caracteres especiales.

Solo toca jugadores que actualmente tienen xg IS NULL en Supabase.
No modifica goles, asistencias, minutos ni ninguna otra métrica.

Uso (desde backend/):
  conda activate xcout
  python scrapers/fix_ligue1_xg.py
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
LIGA_ID    = 27
LEAGUE_STR = "FRA-Ligue 1"

_CHAR_MAP = str.maketrans(
    "'''–—",
    "     ",
)
_CHAR_MAP.update({
    ord("ı"): "i",  ord("İ"): "I",
    ord("ğ"): "g",  ord("Ğ"): "G",
    ord("ş"): "s",  ord("Ş"): "S",
    ord("ð"): "d",  ord("Ð"): "D",
    ord("þ"): "th",
    ord("ø"): "o",  ord("Ø"): "O",
    ord("œ"): "oe", ord("Œ"): "Oe",
    ord("æ"): "ae", ord("Æ"): "Ae",
    ord("ł"): "l",  ord("Ł"): "L",
    ord("ß"): "ss",
    ord("-"): " ",
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


def _resolve(pnorm, snorm, full_map, name_map, last_map):
    return (
        full_map.get((pnorm, snorm)) or
        name_map.get(pnorm) or
        (last_map.get(pnorm.split()[-1]) if pnorm else None)
    )


def load_null_xg_players() -> tuple[dict, dict]:
    log.info("[1] Cargando jugadores con xG nulo (Ligue 1 2025/26)...")

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

    log.info("    name_map: %d entradas.", len(name_map))
    for nombre_n in sorted(name_map.keys()):
        log.info("      %s", nombre_n)
    return full_map, name_map


def fetch_shooting_xg(full_map, name_map) -> int:
    log.info("[2] Descargando shooting stats (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = _flatten(fbref.read_player_season_stats(stat_type="shooting").reset_index())
        log.info("    shape=%s  columnas: %s", df.shape, list(df.columns))
    except Exception as e:
        log.error("    Error: %s", e)
        return 0

    col_xg = (
        _find_col(df, "expected__xg",  reject=["np", "90", "/90"]) or
        _find_col(df, "xg",            reject=["np", "90", "/90"]) or
        _find_col(df, "npxg",          reject=["90", "/90"]) or
        _find_col(df, "expected_goals", reject=["np", "90"])
    )
    log.info("    xG <- %s", col_xg)
    if not col_xg:
        log.warning("    No se encontro columna xG.")
        return 0

    ok = sin_match = sin_xg = 0
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player or player == "player":
            continue

        # Solo full_map + name_map (sin last_map para evitar colisiones de apellidos)
        jid = full_map.get((player, squad)) or name_map.get(player)
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


# Aliases Understat -> nombre normalizado en DB
UNDERSTAT_ALIASES: dict[str, str] = {
    "fabian ruiz":      "fabian ruiz pena",
    "emerson":          "emerson palmieri",
    "tosin":            "tosin aiyegun",
    "igor":             "igor carioca",
    "daniel loader":    "danny loader",
    "musa altaamari":   "musa al taamari",
    "musa al-taamari":  "musa al taamari",
    "kelvin amian legault": "kelvin amian",
    "otavio":           "otavio ataide",
}


def _fuzzy_match(us_name: str, name_map: dict) -> "int | None":
    """Busca en name_map un DB-nombre que contenga us_name como prefijo o viceversa."""
    words_us = us_name.split()
    if len(words_us) < 2:
        return None
    # Prefijo: "fabian ruiz" aparece al inicio de "fabian ruiz pena"
    for db_name, jid in name_map.items():
        if db_name.startswith(us_name) or us_name.startswith(db_name):
            return jid
    # Compacto: quita espacios (al taamari -> altaamari)
    us_compact = us_name.replace(" ", "")
    for db_name, jid in name_map.items():
        if db_name.replace(" ", "") == us_compact:
            return jid
    return None


def fetch_understat_xgxa(full_map, name_map) -> int:
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

        # Alias manual → nombre DB normalizado
        db_name_via_alias = UNDERSTAT_ALIASES.get(player)
        jid = (
            full_map.get((player, squad)) or
            name_map.get(player) or
            (name_map.get(db_name_via_alias) if db_name_via_alias else None) or
            _fuzzy_match(player, name_map)
        )
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


def verify():
    log.info("")
    log.info("[VERIFY] Contando jugadores con xG nulo tras el fix...")
    res = (
        supabase.table("estadisticas_jugador")
        .select("jugador_id", count="exact")
        .eq("temporada", TEMPORADA)
        .eq("liga_id", LIGA_ID)
        .is_("xg", "null")
        .execute()
    )
    restantes = res.count or 0
    log.info("    Jugadores con xG todavia nulo: %d", restantes)


def run():
    log.info("=" * 60)
    log.info(" Fix xG/xA nulos -- Ligue 1 %s", TEMPORADA)
    log.info("=" * 60)

    full_map, name_map = load_null_xg_players()
    if not name_map:
        log.info("No hay jugadores con xG nulo. Nada que hacer.")
        return

    ok_fbref     = fetch_shooting_xg(full_map, name_map)
    ok_understat = fetch_understat_xgxa(full_map, name_map)

    verify()

    log.info("")
    log.info("=" * 60)
    log.info(" RESUMEN")
    log.info("  Actualizados FBref shooting : %d", ok_fbref)
    log.info("  Actualizados Understat      : %d", ok_understat)
    log.info("=" * 60)


if __name__ == "__main__":
    run()
