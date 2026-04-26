"""
FBref Directo — Possession + Passing para temporadas historicas

Usa Playwright (Chromium headless) para renderizar el JavaScript de FBref
y extraer las tablas de possession y passing que no estan en HTML estatico:
  - regates          : Take-Ons Succ (successful dribbles)
  - pases_completados: Total Cmp%    (pass completion %)

La Liga (comp 12) — temporadas 2020/21 a 2024/25
"""

import sys
import math
import logging
import unicodedata
from io import StringIO
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

FBREF_BASE  = "https://fbref.com"
COMP_ID     = 12      # La Liga
LIGA_ID     = 1
PAGE_DELAY  = 5000    # ms a esperar tras cargar la pagina (JS)
NAV_DELAY   = 8000    # ms entre paginas

TEMPORADAS = [
    ("2020-2021", "2021"),
    ("2021-2022", "2122"),
    ("2022-2023", "2223"),
    ("2023-2024", "2324"),
    ("2024-2025", "2425"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


def _safe_int(v) -> int | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else int(f)
    except (TypeError, ValueError):
        return None


def _safe_float(v, dec: int = 1) -> float | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, dec)
    except (TypeError, ValueError):
        return None


def _find_col(df: pd.DataFrame, *keywords) -> str | None:
    for col in df.columns:
        cl = col.lower()
        if all(k in cl for k in keywords):
            return col
    return None


# ---------------------------------------------------------------------------
# Descarga con Playwright
# ---------------------------------------------------------------------------

def _fetch_table(page, url: str, table_id: str) -> pd.DataFrame:
    """Navega a url con Playwright y extrae la tabla table_id ya renderizada."""
    log.info("  -> %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(PAGE_DELAY)  # esperar JS

    # Aceptar cookies si aparece el banner
    try:
        page.click("button:has-text('Accept')", timeout=3000)
    except Exception:
        pass

    html_content = page.content()
    dfs = pd.read_html(StringIO(html_content), attrs={"id": table_id})
    if not dfs:
        log.warning("    Tabla '%s' no encontrada en %s", table_id, url)
        return pd.DataFrame()

    df = dfs[0]

    # Aplanar MultiIndex si lo hay
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for a, b in df.columns:
            a = (str(a) if a else "").strip()
            b = (str(b) if b else "").strip()
            a_ok = bool(a) and not a.startswith("Unnamed") and a != "nan"
            b_ok = bool(b) and not b.startswith("Unnamed") and b != "nan"
            if a_ok and b_ok:
                new_cols.append(f"{a}__{b}")
            elif b_ok:
                new_cols.append(b)
            elif a_ok:
                new_cols.append(a)
            else:
                new_cols.append("")
        df.columns = new_cols

    # Eliminar filas de sub-header
    if "Player" in df.columns:
        df = df[df["Player"] != "Player"]

    return df.reset_index(drop=True)


def build_season_stats(page, season_slug: str) -> pd.DataFrame:
    rows: dict[tuple, dict] = {}
    base = f"{FBREF_BASE}/en/comps/{COMP_ID}/{season_slug}"
    end  = f"{season_slug}-La-Liga-Stats"

    # ── Possession → regates ────────────────────────────────────────────────
    try:
        df_poss = _fetch_table(page, f"{base}/possession/{end}", "stats_possession")
        if not df_poss.empty:
            col = _find_col(df_poss, "take", "succ") or _find_col(df_poss, "drib", "succ")
            if col:
                log.info("    Regates <- '%s'  (%d filas)", col, len(df_poss))
                for _, row in df_poss.iterrows():
                    p = _norm(str(row.get("Player") or ""))
                    t = _norm(str(row.get("Squad")  or ""))
                    if not p or p == "player":
                        continue
                    key = (p, t)
                    rows.setdefault(key, {"player_norm": p, "team_norm": t,
                                          "regates": None, "pases_completados": None})
                    rows[key]["regates"] = _safe_int(row.get(col))
            else:
                log.warning("    Sin columna regates. Cols: %s",
                            [c for c in df_poss.columns if "succ" in c.lower()][:10])
    except Exception as e:
        log.warning("    Error possession: %s", e)

    page.wait_for_timeout(NAV_DELAY)

    # ── Passing → pases_completados ─────────────────────────────────────────
    try:
        df_pass = _fetch_table(page, f"{base}/passing/{end}", "stats_passing")
        if not df_pass.empty:
            col = _find_col(df_pass, "total", "cmp%") or _find_col(df_pass, "cmp%")
            if col:
                log.info("    Pases%% <- '%s'  (%d filas)", col, len(df_pass))
                for _, row in df_pass.iterrows():
                    p = _norm(str(row.get("Player") or ""))
                    t = _norm(str(row.get("Squad")  or ""))
                    if not p or p == "player":
                        continue
                    key = (p, t)
                    rows.setdefault(key, {"player_norm": p, "team_norm": t,
                                          "regates": None, "pases_completados": None})
                    rows[key]["pases_completados"] = _safe_float(row.get(col))
            else:
                log.warning("    Sin columna pases. Cols: %s",
                            [c for c in df_pass.columns if "cmp" in c.lower()][:10])
    except Exception as e:
        log.warning("    Error passing: %s", e)

    page.wait_for_timeout(NAV_DELAY)

    return pd.DataFrame(list(rows.values())) if rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

def load_jugadores_map() -> dict:
    mapping: dict[str, int] = {}
    page_size, offset = 1000, 0
    while True:
        res = (
            supabase.table("jugadores")
            .select("id, nombre")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        for r in res.data:
            key = _norm(r["nombre"])
            if key and key not in mapping:
                mapping[key] = r["id"]
        if len(res.data) < page_size:
            break
        offset += page_size
    log.info("Jugadores en DB: %d", len(mapping))
    return mapping


def update_estadisticas(df: pd.DataFrame, jugador_map: dict, temporada: str) -> int:
    if df.empty:
        log.info("  Sin datos para temporada %s.", temporada)
        return 0

    last_map: dict[str, int] = {}
    for name_norm, jid in jugador_map.items():
        last = name_norm.split()[-1] if name_norm else ""
        if last and last not in last_map:
            last_map[last] = jid

    updated = no_match = no_data = 0

    for _, row in df.iterrows():
        pnorm = row["player_norm"]
        jid = jugador_map.get(pnorm) or last_map.get(pnorm.split()[-1] if pnorm else "")
        if not jid:
            no_match += 1
            continue

        data: dict = {}
        reg = _safe_int(row.get("regates"))
        pas = _safe_float(row.get("pases_completados"))
        if reg is not None:
            data["regates"] = reg
        if pas is not None:
            data["pases_completados"] = pas
        if not data:
            no_data += 1
            continue

        try:
            supabase.table("estadisticas_jugador") \
                .update(data) \
                .eq("jugador_id", jid) \
                .eq("temporada", temporada) \
                .eq("liga_id", LIGA_ID) \
                .execute()
            updated += 1
        except Exception as e:
            log.warning("  Error jugador %d temp %s: %s", jid, temporada, e)

    log.info("  Temporada %s: %d actualizados | %d sin match | %d sin datos",
             temporada, updated, no_match, no_data)
    return updated


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run():
    log.info("=" * 62)
    log.info(" FBref Directo -- Possession + Passing LaLiga historico")
    log.info("=" * 62)

    jugador_map = load_jugadores_map()
    total = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="es-ES",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()

        for season_slug, temporada in TEMPORADAS:
            log.info("")
            log.info(" Temporada %s  (slug: %s)", temporada, season_slug)
            log.info("-" * 62)

            df = build_season_stats(page, season_slug)
            n  = update_estadisticas(df, jugador_map, temporada)
            total += n

        browser.close()

    log.info("")
    log.info("=" * 62)
    log.info(" TOTAL filas actualizadas: %d", total)
    log.info("=" * 62)


if __name__ == "__main__":
    run()
