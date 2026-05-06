"""
FBref PL Stats -- regates, pases_completados, intercepciones, entradas
Premier League 2025/26 (liga_id=24)

Usa soccerdata.FBref.get() para bypasear Cloudflare y descarga:
  - possession -> regates (Take-Ons Succ)
  - passing    -> pases_completados (Total Cmp%)
  - defense    -> intercepciones (Int) + entradas (TklW)
  - misc       -> intercepciones + entradas (fallback)

Uso (desde backend/):
  python scrapers/fbref_pl_direct.py
"""

import io
import sys
import math
import time
import logging
import unicodedata
from pathlib import Path
from io import StringIO

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd
from lxml import html as lhtml, etree

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
FBREF_BASE = "https://fbref.com"
PAGE_DELAY = 8  # segundos entre paginas

PAGES = {
    "possession": "/en/comps/9/possession/Premier-League-Stats",
    "passing":    "/en/comps/9/passing/Premier-League-Stats",
    "defense":    "/en/comps/9/defense/Premier-League-Stats",
    "misc":       "/en/comps/9/misc/Premier-League-Stats",
}


# --- Helpers ------------------------------------------------------------------

def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def _safe_int(v) -> "int | None":
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        f = float(str(v).replace(",", ""))
        return None if (math.isnan(f) or math.isinf(f)) else int(round(f))
    except Exception:
        return None


def _safe_float(v, dec: int = 2) -> "float | None":
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        f = float(str(v).replace(",", ""))
        return None if (math.isnan(f) or math.isinf(f)) else round(f, dec)
    except Exception:
        return None


def _find_col(df: pd.DataFrame, *keywords, reject=None) -> "str | None":
    reject = [r.lower() for r in (reject or [])]
    for col in df.columns:
        cl = col.lower()
        if all(k.lower() in cl for k in keywords) and not any(r in cl for r in reject):
            return col
    return None


# --- FBref fetch via soccerdata (bypasa Cloudflare) --------------------------

def _fetch_fbref_table(fbref: sd.FBref, page_path: str, table_id: str) -> pd.DataFrame:
    """
    Descarga page_path usando fbref.get() (que bypasea Cloudflare)
    y extrae la tabla table_id (que en FBref esta dentro de un comment HTML).
    """
    url      = FBREF_BASE + page_path
    filepath = fbref.data_dir / f"pl_{table_id}.html"
    log.info("  Fetching %s ...", url)

    try:
        reader = fbref.get(url, filepath)
        tree   = lhtml.parse(reader)
    except Exception as e:
        log.error("  Error descargando %s: %s", url, e)
        return pd.DataFrame()

    # FBref envuelve la tabla en un comment HTML
    parser = etree.HTMLParser(recover=True)
    comments = tree.xpath(f"//comment()[contains(.,'div_{table_id}')]")
    if comments:
        html_tables = etree.fromstring(comments[0].text, parser).xpath(
            f"//table[contains(@id, '{table_id}')]"
        )
        if html_tables:
            df = _table_to_df(html_tables[0])
            log.info("    (desde comment) shape=%s", df.shape)
            return df

    # Fallback: tabla directa en el DOM
    direct = tree.xpath(f"//table[@id='{table_id}']")
    if direct:
        df = _table_to_df(direct[0])
        log.info("    (tabla directa) shape=%s", df.shape)
        return df

    log.warning("    Tabla '%s' no encontrada en %s", table_id, url)
    return pd.DataFrame()


def _table_to_df(html_table) -> pd.DataFrame:
    """Convierte un elemento lxml <table> en DataFrame plano."""
    raw_html = etree.tostring(html_table, encoding="unicode")
    dfs = pd.read_html(StringIO(raw_html))
    if not dfs:
        return pd.DataFrame()
    df = dfs[0]
    return _flatten_and_clean(df)


def _flatten_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for parts in df.columns:
            parts = [str(p).strip() for p in parts]
            valid = [p for p in parts
                     if p and not p.startswith("Unnamed") and p.lower() != "nan"]
            new_cols.append("__".join(valid) if len(valid) > 1 else (valid[0] if valid else ""))
        df.columns = new_cols

    for col in ("Player", "Squad"):
        if col in df.columns:
            df = df[df[col].notna() & (df[col] != col)].copy()
            break

    return df.reset_index(drop=True)


# --- Extractores por tabla ----------------------------------------------------

def extract_possession(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    log.info("    Cols possession: %s", list(df.columns))

    col_reg = (
        _find_col(df, "succ",  reject=["per", "%", "att"]) or
        _find_col(df, "take",  reject=["per", "%"]) or
        _find_col(df, "drib",  reject=["per", "%"])
    )
    log.info("    Regates <- %s", col_reg)

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("Player") or ""))
        squad  = _norm(str(r.get("Squad")  or ""))
        if not player or player == "player":
            continue
        rows.append({
            "player_norm": player, "squad_norm": squad,
            "regates": _safe_int(r.get(col_reg)) if col_reg else None,
        })
    return rows


def extract_passing(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    log.info("    Cols passing: %s", list(df.columns))

    col_pas = _find_col(df, "total", "cmp%") or _find_col(df, "cmp%")
    log.info("    Pases%% <- %s", col_pas)

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("Player") or ""))
        squad  = _norm(str(r.get("Squad")  or ""))
        if not player or player == "player":
            continue
        rows.append({
            "player_norm": player, "squad_norm": squad,
            "pases_completados": _safe_float(r.get(col_pas), dec=1) if col_pas else None,
        })
    return rows


def extract_defense(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    log.info("    Cols defense: %s", list(df.columns))

    # entradas = TklW (tackles won); Tackles__Tkl es NaN en HTML (calculado por JS)
    col_tkl = (
        next((c for c in df.columns if c.lower() in ("tackles__tklw", "tklw")), None) or
        _find_col(df, "tklw", reject=["+", "%", "challenges", "att", "3rd"])
    )
    # intercepciones = Int (columna suelta fuera de Tackles)
    col_int = (
        next((c for c in df.columns if c.lower() == "int"), None) or
        next((c for c in df.columns
              if c.lower() in ("interceptions__int", "tackles+interceptions__int")), None) or
        _find_col(df, "int", reject=["+", "tkl", "err", "tackles", "penalty"])
    )
    log.info("    Entradas <- %s | Intercepciones <- %s", col_tkl, col_int)

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("Player") or ""))
        squad  = _norm(str(r.get("Squad")  or ""))
        if not player or player == "player":
            continue
        rows.append({
            "player_norm": player, "squad_norm": squad,
            "entradas":       _safe_int(r.get(col_tkl)) if col_tkl else None,
            "intercepciones": _safe_int(r.get(col_int)) if col_int else None,
        })
    return rows


def extract_misc(df: pd.DataFrame) -> list[dict]:
    """Fallback: intercepciones y entradas desde misc."""
    if df.empty:
        return []
    log.info("    Cols misc: %s", list(df.columns))

    col_int = (
        _find_col(df, "performance__int") or
        next((c for c in df.columns if c.lower() in ("performance__int", "int")), None)
    )
    col_tkl = (
        _find_col(df, "performance__tklw") or
        next((c for c in df.columns if c.lower() in ("performance__tklw", "tklw")), None)
    )
    log.info("    Misc  Int <- %s | TklW <- %s", col_int, col_tkl)

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("Player") or ""))
        squad  = _norm(str(r.get("Squad")  or ""))
        if not player or player == "player":
            continue
        rows.append({
            "player_norm": player, "squad_norm": squad,
            "intercepciones": _safe_int(r.get(col_int)) if col_int else None,
            "entradas":       _safe_int(r.get(col_tkl)) if col_tkl else None,
        })
    return rows


# --- Supabase ----------------------------------------------------------------

def load_jugadores() -> "tuple[dict, dict, dict]":
    log.info("[DB] Cargando jugadores PL (liga_id=%d)...", LIGA_ID)
    eq_res = (supabase.table("equipos").select("id, nombre")
              .eq("liga_id", LIGA_ID).eq("temporada", TEMPORADA).execute())
    eq_ids   = [e["id"] for e in (eq_res.data or [])]
    eq_names = {e["id"]: e["nombre"] for e in (eq_res.data or [])}
    log.info("    %d equipos PL.", len(eq_ids))

    all_jug = []
    for i in range(0, len(eq_ids), 50):
        res = (supabase.table("jugadores").select("id, nombre, equipo_id")
               .in_("equipo_id", eq_ids[i:i+50]).execute())
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


def _resolve(pnorm, snorm, full_map, name_map, last_map):
    return (
        full_map.get((pnorm, snorm)) or
        name_map.get(pnorm) or
        (last_map.get(pnorm.split()[-1]) if pnorm else None)
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

    log.info("  [%-12s] OK=%3d | sin_match=%3d", label, ok, sin_match)
    if fallos:
        log.info("    Sin match: %s", ", ".join(fallos[:8]))
    return ok, sin_match


# --- Verificacion ------------------------------------------------------------

def verify():
    log.info("")
    log.info("[VERIFY] Jugadores clave PL:")
    for name in ("Haaland", "Salah", "Bruno Fernandes", "Rodri", "Alexander-Arnold"):
        res = (supabase.table("jugadores").select("id, nombre")
               .ilike("nombre", f"%{name}%").limit(1).execute())
        if not res.data:
            log.info("  %-25s -> no en DB", name)
            continue
        jid = res.data[0]["id"]
        nom = res.data[0]["nombre"]
        est = (supabase.table("estadisticas_jugador")
               .select("regates, pases_completados, intercepciones, entradas, xg, goles, minutos")
               .eq("jugador_id", jid).eq("temporada", TEMPORADA)
               .eq("liga_id", LIGA_ID).execute())
        if est.data:
            d = est.data[0]
            log.info("  %-25s  reg=%-4s  pases%%=%-6s  int=%-4s  entr=%-4s  xG=%-5s  gls=%s",
                     nom, d.get("regates"), d.get("pases_completados"),
                     d.get("intercepciones"), d.get("entradas"),
                     d.get("xg"), d.get("goles"))
        else:
            log.info("  %-25s -> sin stats PL", nom)


# --- Entrypoint --------------------------------------------------------------

def run():
    log.info("=" * 66)
    log.info(" FBref PL Direct -- regates, pases%%, intercepciones, entradas")
    log.info(" liga_id=%d  temporada=%s  (via soccerdata.FBref.get)", LIGA_ID, TEMPORADA)
    log.info("=" * 66)

    fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)

    log.info("[1] Possession (regates)...")
    df_poss  = _fetch_fbref_table(fbref, PAGES["possession"], "stats_possession")
    rows_poss = extract_possession(df_poss)
    log.info("    %d jugadores.", len(rows_poss))
    time.sleep(PAGE_DELAY)

    log.info("[2] Passing (pases_completados)...")
    df_pass  = _fetch_fbref_table(fbref, PAGES["passing"], "stats_passing")
    rows_pass = extract_passing(df_pass)
    log.info("    %d jugadores.", len(rows_pass))
    time.sleep(PAGE_DELAY)

    log.info("[3] Defense (intercepciones, entradas)...")
    df_def  = _fetch_fbref_table(fbref, PAGES["defense"], "stats_defense")
    rows_def = extract_defense(df_def)
    log.info("    %d jugadores.", len(rows_def))

    # Si defense no trajo datos, usar misc como fallback
    def_ok = any(
        r.get("intercepciones") is not None or r.get("entradas") is not None
        for r in rows_def
    )
    if not def_ok:
        log.info("[3b] Defense vacio -- usando misc como fallback...")
        time.sleep(PAGE_DELAY)
        df_misc  = _fetch_fbref_table(fbref, PAGES["misc"], "stats_misc")
        rows_def = extract_misc(df_misc)
        log.info("    %d jugadores (misc).", len(rows_def))

    full_map, name_map, last_map = load_jugadores()
    if not name_map:
        log.error("Sin jugadores PL en DB. Abortando.")
        return

    log.info("[4] Actualizando Supabase...")
    ok_p, nm_p = update_supabase(rows_poss, full_map, name_map, last_map, "possession")
    ok_a, nm_a = update_supabase(rows_pass, full_map, name_map, last_map, "passing")
    ok_d, nm_d = update_supabase(rows_def,  full_map, name_map, last_map, "defense/misc")

    verify()

    log.info("")
    log.info("=" * 66)
    log.info(" RESUMEN")
    log.info("  Possession (regates)       : %d OK, %d sin match", ok_p, nm_p)
    log.info("  Passing    (pases%%)       : %d OK, %d sin match", ok_a, nm_a)
    log.info("  Defense    (int+entradas)  : %d OK, %d sin match", ok_d, nm_d)
    log.info("=" * 66)


if __name__ == "__main__":
    run()
