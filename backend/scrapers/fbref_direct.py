"""
FBref Direct Scraper — xG, xA, regates, pases_completados para LaLiga 2025/26

Usa Playwright + playwright-stealth para superar la protección Cloudflare de FBref.
URLs:
  standard  → https://fbref.com/en/comps/12/stats/La-Liga-Stats
  possession→ https://fbref.com/en/comps/12/possession/La-Liga-Stats
  passing   → https://fbref.com/en/comps/12/passing/La-Liga-Stats

Uso:
  python backend/scrapers/fbref_direct.py
"""

import sys
import math
import time
import logging
import unicodedata
from io import StringIO
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

TEMPORADA  = "2526"
LIGA_ID    = 1
PAGE_DELAY = 6000   # ms a esperar tras carga (JS + Cloudflare)
NAV_DELAY  = 9000   # ms entre páginas

URLS = {
    "standard":   "https://fbref.com/en/comps/12/stats/La-Liga-Stats",
    "possession": "https://fbref.com/en/comps/12/possession/La-Liga-Stats",
    "passing":    "https://fbref.com/en/comps/12/passing/La-Liga-Stats",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

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


def _find_col(df: pd.DataFrame, *keywords, reject: "list[str] | None" = None) -> "str | None":
    """Primera columna que contiene TODOS los keywords y NINGUNO de los reject."""
    reject = [r.lower() for r in (reject or [])]
    for col in df.columns:
        cl = col.lower()
        if all(k.lower() in cl for k in keywords) and not any(r in cl for r in reject):
            return col
    return None


# ─── Playwright fetch ─────────────────────────────────────────────────────────

def _fetch_table(page, url: str, table_id: str) -> pd.DataFrame:
    """Navega a url con Playwright+stealth y extrae la tabla por id."""
    log.info("  -> %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(PAGE_DELAY)

    # Aceptar cookies si aparece
    try:
        page.click("button:has-text('Accept')", timeout=3000)
        page.wait_for_timeout(1500)
    except Exception:
        pass

    html_content = page.content()

    # Intentar leer la tabla directamente
    try:
        dfs = pd.read_html(StringIO(html_content), attrs={"id": table_id})
        if dfs:
            return _flatten_and_clean(dfs[0])
    except Exception:
        pass

    log.warning("    Tabla '%s' no encontrada en %s", table_id, url)
    return pd.DataFrame()


def _flatten_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Aplana MultiIndex y elimina filas sub-cabecera."""
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for parts in df.columns:
            parts = [str(p).strip() for p in parts]
            valid = [p for p in parts if p and not p.startswith("Unnamed") and p.lower() != "nan"]
            new_cols.append("__".join(valid) if len(valid) > 1 else (valid[0] if valid else ""))
        df.columns = new_cols

    if "Player" in df.columns:
        df = df[df["Player"].notna() & (df["Player"] != "Player")].copy()

    return df.reset_index(drop=True)


# ─── Extracción por tabla ──────────────────────────────────────────────────────

def extract_standard(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    col_xg  = _find_col(df, "xg",  reject=["per", "np", "xag"])
    col_xa  = _find_col(df, "xag", reject=["per", "np"])
    col_gls = _find_col(df, "gls", reject=["per", "pk", "np"])
    col_ast = _find_col(df, "ast", reject=["per"])
    col_min = next(
        (c for c in df.columns if c.lower().endswith("__min") or c.lower() == "min"),
        None
    )

    log.info("    Standard  xG=%-25s xAG=%-25s Gls=%-15s Ast=%-15s Min=%s",
             col_xg, col_xa, col_gls, col_ast, col_min)

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("Player") or ""))
        squad  = _norm(str(r.get("Squad")  or ""))
        if not player or player == "player":
            continue

        minutos = _safe_int(r.get(col_min))  if col_min  else None
        goles   = _safe_int(r.get(col_gls))  if col_gls  else None
        asist   = _safe_int(r.get(col_ast))  if col_ast  else None
        xg      = _safe_float(r.get(col_xg)) if col_xg   else None
        xa      = _safe_float(r.get(col_xa)) if col_xa   else None

        min_val = minutos or 0
        g90  = round(goles / (min_val / 90), 2) if goles is not None and min_val > 0 else None
        a90  = round(asist / (min_val / 90), 2) if asist is not None and min_val > 0 else None
        ga90 = round((goles + asist) / (min_val / 90), 2) \
               if goles is not None and asist is not None and min_val > 0 else None

        rows.append({
            "player_norm": player, "squad_norm": squad,
            "xg": xg, "xa": xa,
            "goles": goles, "asistencias": asist, "minutos": minutos,
            "goles_por_90": g90, "asistencias_por_90": a90, "ga_por_90": ga90,
        })
    return rows


def extract_possession(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    col_reg = (
        _find_col(df, "succ",  reject=["per", "%", "att"]) or
        _find_col(df, "take",  reject=["per", "%"]) or
        _find_col(df, "drib",  reject=["per", "%"])
    )
    log.info("    Possession  Regates <- %s", col_reg)

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

    col_pas = _find_col(df, "total", "cmp%") or _find_col(df, "cmp%")
    log.info("    Passing     Pases%% <- %s", col_pas)

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


# ─── Supabase ─────────────────────────────────────────────────────────────────

def load_jugadores() -> "tuple[dict, dict, dict]":
    log.info("[4] Cargando jugadores de Supabase...")
    res = supabase.table("jugadores").select("id, nombre, equipos(nombre)").execute()

    full_map: dict = {}
    name_map: dict = {}
    last_map: dict = {}

    for r in (res.data or []):
        jid  = r["id"]
        name = _norm(r.get("nombre") or "")
        team = _norm((r.get("equipos") or {}).get("nombre") or "")
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


def _resolve(player_norm: str, squad_norm: str,
             full_map: dict, name_map: dict, last_map: dict) -> "int | None":
    return (
        full_map.get((player_norm, squad_norm)) or
        name_map.get(player_norm) or
        (last_map.get(player_norm.split()[-1]) if player_norm else None)
    )


def update_supabase(rows: list[dict], full_map: dict, name_map: dict,
                    last_map: dict, label: str) -> "tuple[int, int, list]":
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

        data = {
            k: v for k, v in row.items()
            if k not in ("player_norm", "squad_norm") and v is not None
        }
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

    log.info("  [%-12s] Actualizados: %3d | Sin match: %3d", label, ok, sin_match)
    return ok, sin_match, fallos


# ─── Verificación ─────────────────────────────────────────────────────────────

def verify(names=("Muriqi", "Mbapp", "Pedri", "Yamal", "Bellingham")):
    log.info("")
    log.info("[6] Verificación de jugadores clave:")
    for name in names:
        res = supabase.table("jugadores") \
            .select("id, nombre") \
            .ilike("nombre", f"%{name}%") \
            .limit(1).execute()
        if not res.data:
            log.info("  %-20s → no encontrado en DB.", name)
            continue
        jid  = res.data[0]["id"]
        nom  = res.data[0]["nombre"]
        est  = supabase.table("estadisticas_jugador") \
            .select("xg, xa, regates, pases_completados, goles, minutos") \
            .eq("jugador_id", jid).eq("temporada", TEMPORADA).execute()
        if est.data:
            d = est.data[0]
            log.info("  %-25s xG=%-6s xA=%-6s reg=%-4s pases%%=%-6s gls=%-4s min=%s",
                     nom,
                     d.get("xg"), d.get("xa"),
                     d.get("regates"), d.get("pases_completados"),
                     d.get("goles"), d.get("minutos"))
        else:
            log.info("  %-25s → sin estadísticas para %s.", nom, TEMPORADA)


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def run():
    log.info("=" * 62)
    log.info(" FBref Direct Scraper — LaLiga %s (Playwright+stealth)", TEMPORADA)
    log.info("=" * 62)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        Stealth().apply_stealth_sync(page)

        # 1. Standard stats (xG, xA, goles, asistencias, minutos)
        log.info("[1] Standard stats...")
        df_std = _fetch_table(page, URLS["standard"], "stats_standard")
        rows_std = extract_standard(df_std)
        log.info("    %d jugadores.", len(rows_std))

        page.wait_for_timeout(NAV_DELAY)

        # 2. Possession (regates)
        log.info("[2] Possession stats...")
        df_poss = _fetch_table(page, URLS["possession"], "stats_possession")
        rows_poss = extract_possession(df_poss)
        log.info("    %d jugadores.", len(rows_poss))

        page.wait_for_timeout(NAV_DELAY)

        # 3. Passing (pases_completados)
        log.info("[3] Passing stats...")
        df_pass = _fetch_table(page, URLS["passing"], "stats_passing")
        rows_pass = extract_passing(df_pass)
        log.info("    %d jugadores.", len(rows_pass))

        browser.close()

    # 4. Cargar mapa de jugadores
    full_map, name_map, last_map = load_jugadores()

    # 5. Actualizar Supabase
    log.info("[5] Actualizando Supabase...")
    ok_s, nm_s, _        = update_supabase(rows_std,  full_map, name_map, last_map, "standard")
    ok_p, nm_p, _        = update_supabase(rows_poss, full_map, name_map, last_map, "possession")
    ok_a, nm_a, fallos_a = update_supabase(rows_pass, full_map, name_map, last_map, "passing")

    if fallos_a:
        log.info("  Sin match (passing): %s", ", ".join(fallos_a[:10]))

    # 6. Verificar
    verify(("Muriqi", "Mbapp", "Pedri", "Yamal", "Bellingham"))

    log.info("")
    log.info("=" * 62)
    log.info(" RESUMEN")
    log.info("  Standard  : %d actualizados, %d sin match", ok_s, nm_s)
    log.info("  Possession: %d actualizados, %d sin match", ok_p, nm_p)
    log.info("  Passing   : %d actualizados, %d sin match", ok_a, nm_a)
    log.info("=" * 62)


if __name__ == "__main__":
    run()
