"""
FBref/Understat Premier League Stats Updater -- xG, xA, porteros
Fuentes:
  Understat (via soccerdata) -> xG, xA por jugador
  FBref     (via soccerdata) -> portero_paradas, portero_goles_encajados, portero_paradas_pct

Uso (desde backend/):
  python scrapers/fbref_premier.py
"""

import io
import sys
import math
import time
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
LIGA_ID    = 24
LEAGUE_STR = "ENG-Premier League"
PAGE_DELAY = 8


# --- Helpers ------------------------------------------------------------------

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


def _find_col(df: pd.DataFrame, *keywords, reject=None) -> "str | None":
    reject = [r.lower() for r in (reject or [])]
    for col in df.columns:
        cl = col.lower()
        if all(k.lower() in cl for k in keywords) and not any(r in cl for r in reject):
            return col
    return None


# --- Extractores --------------------------------------------------------------

def extract_xg_understat() -> list[dict]:
    """xG y xA desde Understat."""
    log.info("[Understat] Descargando player season stats...")
    us  = sd.Understat(leagues=LEAGUE_STR, seasons=TEMPORADA)
    df  = us.read_player_season_stats().reset_index()
    log.info("    shape=%s | cols=%s", df.shape, list(df.columns))

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player:
            continue
        rows.append({
            "player_norm": player,
            "squad_norm":  squad,
            "xg": _safe_float(r.get("xg")),
            "xa": _safe_float(r.get("xa")),
        })
    log.info("    %d jugadores extraidos.", len(rows))
    return rows


def extract_keepers_fbref() -> list[dict]:
    """Paradas, GA, save% desde FBref stat_type='keeper'."""
    log.info("[FBref] Descargando keeper stats...")
    fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
    raw   = fbref.read_player_season_stats(stat_type="keeper")
    df    = _flatten(raw.reset_index())
    log.info("    shape=%s | cols=%s", df.shape, list(df.columns))

    col_ga  = _find_col(df, "ga",    reject=["90", "%", "pct", "save"])
    col_sv  = _find_col(df, "saves", reject=["%", "pct", "90"])
    col_pct = (
        _find_col(df, "save%") or
        next((c for c in df.columns if "save%" in c.lower() or "sv%" in c.lower()), None)
    )
    if not col_ga:
        col_ga = next((c for c in df.columns
                       if c.strip().lower() in ("performance__ga", "ga")), None)
    log.info("    GA=%s  Saves=%s  Save%%=%s", col_ga, col_sv, col_pct)

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player or player == "player":
            continue
        ga  = _safe_int(r.get(col_ga))       if col_ga  else None
        sv  = _safe_int(r.get(col_sv))       if col_sv  else None
        pct = _safe_float(r.get(col_pct), 1) if col_pct else None
        if pct is None and sv is not None and ga is not None:
            total = sv + ga
            pct = round(sv / total * 100, 1) if total > 0 else None
        rows.append({
            "player_norm": player, "squad_norm": squad,
            "portero_goles_encajados": ga,
            "portero_paradas":         sv,
            "portero_paradas_pct":     pct,
        })
    log.info("    %d porteros extraidos.", len(rows))
    return rows


# --- Supabase -----------------------------------------------------------------

def load_jugadores() -> "tuple[dict, dict, dict]":
    log.info("[DB] Cargando jugadores PL...")
    eq_res = (
        supabase.table("equipos")
        .select("id, nombre")
        .eq("liga_id", LIGA_ID)
        .eq("temporada", TEMPORADA)
        .execute()
    )
    eq_ids   = [e["id"] for e in (eq_res.data or [])]
    eq_names = {e["id"]: e["nombre"] for e in (eq_res.data or [])}
    log.info("    %d equipos PL.", len(eq_ids))

    all_jugadores = []
    for i in range(0, len(eq_ids), 50):
        res = (
            supabase.table("jugadores")
            .select("id, nombre, equipo_id")
            .in_("equipo_id", eq_ids[i:i+50])
            .execute()
        )
        all_jugadores.extend(res.data or [])

    full_map: dict = {}
    name_map: dict = {}
    last_map: dict = {}

    for r in all_jugadores:
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


def _resolve(player_norm, squad_norm, full_map, name_map, last_map):
    return (
        full_map.get((player_norm, squad_norm)) or
        name_map.get(player_norm) or
        (last_map.get(player_norm.split()[-1]) if player_norm else None)
    )


def update_supabase(rows, full_map, name_map, last_map, label) -> tuple:
    ok = sin_match = 0
    fallos = []
    for row in rows:
        pnorm = row["player_norm"]
        snorm = row["squad_norm"]
        jid   = _resolve(pnorm, snorm, full_map, name_map, last_map)
        if not jid:
            sin_match += 1
            fallos.append(f"{pnorm} ({snorm})")
            continue
        data = {k: v for k, v in row.items()
                if k not in ("player_norm", "squad_norm") and v is not None}
        if not data:
            continue
        try:
            supabase.table("estadisticas_jugador") \
                .update(data) \
                .eq("jugador_id", jid) \
                .eq("temporada", TEMPORADA) \
                .eq("liga_id", LIGA_ID) \
                .execute()
            ok += 1
        except Exception as e:
            log.warning("  Error %s jid=%d: %s", label, jid, e)

    log.info("  [%-16s] OK=%3d | sin_match=%3d", label, ok, sin_match)
    if fallos:
        log.info("    Fallos muestra: %s", ", ".join(fallos[:6]))
    return ok, sin_match


# --- Verificacion -------------------------------------------------------------

def verify():
    log.info("")
    log.info("[VERIFY] Jugadores clave:")
    for name in ("Haaland", "Salah", "Saka", "Pickford", "Raya"):
        res = (supabase.table("jugadores")
               .select("id, nombre")
               .ilike("nombre", f"%{name}%")
               .limit(1).execute())
        if not res.data:
            log.info("  %-20s -> no en DB", name)
            continue
        jid = res.data[0]["id"]
        nom = res.data[0]["nombre"]
        est = (supabase.table("estadisticas_jugador")
               .select("xg, xa, goles, minutos, "
                       "portero_paradas, portero_goles_encajados, portero_paradas_pct")
               .eq("jugador_id", jid).eq("temporada", TEMPORADA)
               .eq("liga_id", LIGA_ID).execute())
        if est.data:
            d = est.data[0]
            if d.get("portero_paradas") is not None:
                log.info("  %-28s  paradas=%-4s  GA=%-3s  sv%%=%-5s  min=%s",
                         nom, d["portero_paradas"],
                         d["portero_goles_encajados"], d["portero_paradas_pct"],
                         d.get("minutos"))
            else:
                log.info("  %-28s  xG=%-6s  xA=%-6s  gls=%-3s  min=%s",
                         nom, d.get("xg"), d.get("xa"),
                         d.get("goles"), d.get("minutos"))
        else:
            log.info("  %-28s  -> sin stats en PL", nom)


# --- Entrypoint ---------------------------------------------------------------

def run():
    log.info("=" * 66)
    log.info(" PL Stats Updater -- Understat+FBref  (liga_id=%d, temporada=%s)",
             LIGA_ID, TEMPORADA)
    log.info("=" * 66)

    rows_xg   = extract_xg_understat()
    log.info("Esperando %ds...", PAGE_DELAY); time.sleep(PAGE_DELAY)

    rows_keep = extract_keepers_fbref()

    full_map, name_map, last_map = load_jugadores()
    if not name_map:
        log.error("Sin jugadores en DB para liga_id=%d. Abortando.", LIGA_ID)
        return

    log.info("[Supabase] Actualizando...")
    ok_x, nm_x = update_supabase(rows_xg,   full_map, name_map, last_map, "xG/xA")
    ok_k, nm_k = update_supabase(rows_keep, full_map, name_map, last_map, "keepers")

    verify()

    log.info("")
    log.info("=" * 66)
    log.info(" RESUMEN")
    log.info("  xG/xA  : %d OK, %d sin match", ok_x, nm_x)
    log.info("  Keepers: %d OK, %d sin match", ok_k, nm_k)
    log.info("=" * 66)


if __name__ == "__main__":
    run()
