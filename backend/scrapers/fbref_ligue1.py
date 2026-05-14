"""
FBref + Transfermarkt Ligue 1 Scraper — liga_id=27, temporada 2025/26

Fases:
  0. Liga      -> asegurar id=27 en tabla ligas
  A. Historico -> standard stats (2122-2425) con ignore_duplicates=True
  1. Standard  -> equipos + jugadores (upsert) + stats basicas (INSERT)
  2. Keeper    -> portero stats (UPDATE)
  3. Shooting  -> xG FBref inicial (UPDATE)
  4. Misc      -> recuperaciones, intercepciones, entradas (UPDATE)
  5. Understat -> xG, xA definitivos (UPDATE)
  6. Schedule  -> partidos (upsert)
  7. TM        -> fotos + valor de mercado (upsert)

Uso (desde la raiz del proyecto):
  conda activate xcout
  python backend/scrapers/fbref_ligue1.py

Para omitir temporadas historicas en ejecuciones posteriores:
  INCLUIR_HISTORICO = False
"""

import io
import re
import sys
import math
import time
import difflib
import logging
import unicodedata
import datetime
from pathlib import Path
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import soccerdata as sd
import cloudscraper
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Constantes FBref ──────────────────────────────────────────────────────────
TEMPORADA        = "2526"
LIGA_ID          = 27
LEAGUE_STR       = "FRA-Ligue 1"
LIGA_NOMBRE      = "Ligue 1"
LIGA_PAIS        = "Francia"
MIN_MINUTOS      = 90
PAGE_DELAY       = 8

INCLUIR_HISTORICO = True   # Poner False despues del primer run

HISTORICAS = [
    ("2122", "2122"),
    ("2223", "2223"),
    ("2324", "2324"),
    ("2425", "2425"),
]

# ── Constantes Transfermarkt ──────────────────────────────────────────────────
TM_BASE          = "https://www.transfermarkt.es"
TM_LIGA_CODE     = "FR1"
TM_SLUG          = "ligue-1"
TM_SEASON        = 2025
CARGAR_HISTORIAL = True
REQUEST_DELAY    = 2.0

_tm_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# Aliases FBref schedule -> stats (cuando el nombre difiere entre endpoints)
FBREF_ALIASES: dict[str, str] = {
    "paris s-g":       "paris saint-germain",
    "paris sg":        "paris saint-germain",
    "psg":             "paris saint-germain",
    "st etienne":      "saint-etienne",
    "saint-etienne":   "saint-etienne",
    "le havre":        "le havre",
    "havre":           "le havre",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

_CHAR_MAP = str.maketrans(
    "’‘’–—",
    "     ",
)
_CHAR_MAP.update({
    ord("œ"): "oe", ord("æ"): "ae",
    ord("Æ"): "Ae", ord("Œ"): "Oe",
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


def _is_aggregate(team_name: str) -> bool:
    if not team_name:
        return False
    return "squad" in str(team_name).lower() or "club" in str(team_name).lower()


# ── Resolve + update shared ───────────────────────────────────────────────────

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
    log.info("  [%-20s] OK=%3d | sin_match=%3d", label, ok, sin_match)
    if fallos:
        log.info("    Fallos muestra: %s", ", ".join(fallos[:6]))
    return ok, sin_match


# ── Fase 0: asegurar liga ─────────────────────────────────────────────────────

def ensure_liga():
    log.info("[0] Asegurando liga id=%d (%s) en tabla ligas...", LIGA_ID, LIGA_NOMBRE)
    try:
        supabase.table("ligas").upsert({
            "id":     LIGA_ID,
            "nombre": LIGA_NOMBRE,
            "pais":   LIGA_PAIS,
            "activa": True,
        }, on_conflict="id").execute()
        log.info("    Liga asegurada.")
    except Exception as e:
        log.warning("    No se pudo upsert liga (puede ya existir): %s", e)


# ── Fase A: historico (2122-2425) ─────────────────────────────────────────────

def _build_player_maps() -> "tuple[dict, dict, dict]":
    """Carga jugadores de liga_id=27 desde Supabase para el historico."""
    eq_res = (
        supabase.table("equipos").select("id, nombre")
        .eq("liga_id", LIGA_ID).eq("temporada", TEMPORADA).execute()
    )
    eq_ids   = [e["id"] for e in (eq_res.data or [])]
    eq_names = {e["id"]: e["nombre"] for e in (eq_res.data or [])}

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
    return full_map, name_map, last_map


def run_historico(fbref_key: str, temporada: str):
    log.info("  [hist] Temporada %s (FBref key=%s)...", temporada, fbref_key)
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=fbref_key)
        df    = _flatten(fbref.read_player_season_stats(stat_type="standard").reset_index())
        log.info("    %d filas.", len(df))
    except Exception as e:
        log.error("    Error descargando %s: %s", fbref_key, e)
        return

    full_map, name_map, last_map = _build_player_maps()
    if not name_map:
        log.warning("    Sin jugadores en DB para Ligue 1. Ejecutar fase actual primero.")
        return

    rows = []
    for _, row in df.iterrows():
        player = _val(row.get("player"))
        if not player or str(player).strip().lower() == "player":
            continue
        pnorm   = _norm(str(player))
        snorm   = _norm(str(row.get("team") or ""))
        min_val = _safe_int(row.get("Playing Time__Min"))
        if min_val is not None and min_val < MIN_MINUTOS:
            continue
        jid = _resolve(pnorm, snorm, full_map, name_map, last_map)
        if not jid:
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

    seen: dict[tuple, int] = {}
    for i, r in enumerate(rows):
        seen[(r["jugador_id"], r["temporada"])] = i
    rows = [rows[i] for i in seen.values()]

    if not rows:
        log.info("    Nada que insertar.")
        return

    res = (
        supabase.table("estadisticas_jugador")
        .upsert(rows, on_conflict="jugador_id,temporada,liga_id", ignore_duplicates=True)
        .execute()
    )
    log.info("    Insertadas: %d (existentes ignoradas).", len(res.data))


# ── Fase 1: standard → equipos + jugadores + estadisticas ────────────────────

def load_standard() -> pd.DataFrame:
    log.info("[1] Descargando standard stats (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = _flatten(fbref.read_player_season_stats(stat_type="standard").reset_index())
        log.info("    shape=%s | cols=%s", df.shape, list(df.columns[:12]))
        return df
    except Exception as e:
        log.error("    Error: %s", e)
        return pd.DataFrame()


def upsert_equipos(df: pd.DataFrame) -> dict:
    nombres = sorted(
        n for n in df.get("team", pd.Series()).dropna().unique()
        if not _is_aggregate(n)
    )
    rows = [{"nombre": n, "liga_id": LIGA_ID, "temporada": TEMPORADA} for n in nombres]
    log.info("    Upserting %d equipos...", len(rows))
    res = (
        supabase.table("equipos")
        .upsert(rows, on_conflict="nombre,liga_id,temporada")
        .execute()
    )
    mapping = {r["nombre"]: r["id"] for r in res.data}
    log.info("    %d equipos: %s", len(mapping), sorted(mapping.keys()))
    return mapping


def upsert_jugadores(df: pd.DataFrame, equipo_map: dict) -> "tuple[dict, dict, dict]":
    nuevos = []
    seen   = set()
    for _, row in df.iterrows():
        nombre = _val(row.get("player"))
        if not nombre:
            continue
        equipo_nombre = _val(row.get("team"))
        if _is_aggregate(equipo_nombre):
            continue
        equipo_id = equipo_map.get(equipo_nombre)
        if not equipo_id:
            continue
        key = (_norm(str(nombre)), equipo_id)
        if key in seen:
            continue
        seen.add(key)

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

    if nuevos:
        log.info("    Insertando %d jugadores...", len(nuevos))
        supabase.table("jugadores").upsert(nuevos, on_conflict="nombre,equipo_id").execute()

    eq_res   = (supabase.table("equipos").select("id, nombre")
                .eq("liga_id", LIGA_ID).eq("temporada", TEMPORADA).execute())
    eq_ids   = [e["id"] for e in (eq_res.data or [])]
    eq_names = {e["id"]: e["nombre"] for e in (eq_res.data or [])}

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

    log.info("    %d jugadores en mapa.", len(name_map))
    return full_map, name_map, last_map


def build_standard_rows(df: pd.DataFrame, full_map, name_map, last_map) -> list[dict]:
    rows    = []
    skipped = 0
    for _, row in df.iterrows():
        player = _val(row.get("player"))
        if not player or str(player).strip().lower() == "player":
            continue
        pnorm   = _norm(str(player))
        snorm   = _norm(str(row.get("team") or ""))
        min_val = _safe_int(row.get("Playing Time__Min"))
        if min_val is not None and min_val < MIN_MINUTOS:
            skipped += 1
            continue
        jid = _resolve(pnorm, snorm, full_map, name_map, last_map)
        if not jid:
            skipped += 1
            continue
        rows.append({
            "jugador_id":         jid,
            "temporada":          TEMPORADA,
            "liga_id":            LIGA_ID,
            "goles":              _safe_int(row.get("Performance__Gls")),
            "asistencias":        _safe_int(row.get("Performance__Ast")),
            "minutos":            _safe_int(row.get("Playing Time__Min")),
            "goles_por_90":       _safe_float(row.get("Per 90 Minutes__Gls"), 3),
            "asistencias_por_90": _safe_float(row.get("Per 90 Minutes__Ast"), 3),
            "ga_por_90":          _safe_float(row.get("Per 90 Minutes__G+A"), 3),
        })
    log.info("    %d filas standard | %d skipped", len(rows), skipped)
    return rows


def insert_estadisticas(rows: list[dict]) -> int:
    if not rows:
        log.info("    Nada que insertar.")
        return 0
    seen: dict[tuple, int] = {}
    for i, r in enumerate(rows):
        seen[(r["jugador_id"], r["temporada"])] = i
    rows_dedup = [rows[i] for i in seen.values()]
    if len(rows) != len(rows_dedup):
        log.info("    Duplicados eliminados: %d", len(rows) - len(rows_dedup))
    res = (
        supabase.table("estadisticas_jugador")
        .upsert(rows_dedup, on_conflict="jugador_id,temporada,liga_id")
        .execute()
    )
    log.info("    %d estadisticas insertadas.", len(res.data))
    return len(res.data)


# ── Fase 2: keeper ────────────────────────────────────────────────────────────

def extract_keepers() -> list[dict]:
    log.info("[2] Descargando keeper stats (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = _flatten(fbref.read_player_season_stats(stat_type="keeper").reset_index())
        log.info("    shape=%s", df.shape)
    except Exception as e:
        log.error("    Error: %s", e)
        return []

    col_ga  = _find_col(df, "ga",    reject=["90", "%", "pct", "save"])
    col_sv  = _find_col(df, "saves", reject=["%", "pct", "90"])
    col_pct = (
        _find_col(df, "save%") or
        next((c for c in df.columns if "save%" in c.lower() or "sv%" in c.lower()), None)
    )
    if not col_ga:
        col_ga = next(
            (c for c in df.columns if c.strip().lower() in ("performance__ga", "ga")), None
        )
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
            pct   = round(sv / total * 100, 1) if total > 0 else None
        rows.append({
            "player_norm": player, "squad_norm": squad,
            "portero_goles_encajados": ga,
            "portero_paradas":         sv,
            "portero_paradas_pct":     pct,
        })
    log.info("    %d porteros.", len(rows))
    return rows


# ── Fase 3: shooting → xG inicial ────────────────────────────────────────────

def extract_shooting() -> list[dict]:
    log.info("[3] Descargando shooting stats (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = _flatten(fbref.read_player_season_stats(stat_type="shooting").reset_index())
        log.info("    shape=%s", df.shape)
    except Exception as e:
        log.error("    Error: %s", e)
        return []

    col_xg = (
        _find_col(df, "expected__xg", reject=["np", "90", "/90"]) or
        _find_col(df, "xg",           reject=["np", "90", "/90"])
    )
    log.info("    xG <- %s", col_xg)

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player or player == "player":
            continue
        rows.append({
            "player_norm": player, "squad_norm": squad,
            "xg": _safe_float(r.get(col_xg)) if col_xg else None,
        })
    log.info("    %d jugadores.", len(rows))
    return rows


# ── Fase 4: misc → recuperaciones ────────────────────────────────────────────

def extract_misc() -> list[dict]:
    log.info("[4] Descargando misc stats (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = _flatten(fbref.read_player_season_stats(stat_type="misc").reset_index())
        log.info("    shape=%s", df.shape)
    except Exception as e:
        log.error("    Error: %s", e)
        return []

    col_tklw = (
        _find_col(df, "performance__tklw") or
        next((c for c in df.columns if c.lower() in ("performance__tklw", "tklw")), None)
    )
    col_int = (
        _find_col(df, "performance__int") or
        next((c for c in df.columns if c.lower() in ("performance__int", "int")), None)
    )
    log.info("    TklW=%s  Int=%s", col_tklw, col_int)

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player or player == "player":
            continue
        tklw  = _safe_int(r.get(col_tklw)) if col_tklw else None
        ints  = _safe_int(r.get(col_int))  if col_int  else None
        recup = (tklw or 0) + (ints or 0) if (tklw is not None or ints is not None) else None
        rows.append({
            "player_norm":    player,
            "squad_norm":     squad,
            "entradas":       tklw,
            "intercepciones": ints,
            "recuperaciones": recup,
        })
    log.info("    %d jugadores.", len(rows))
    return rows


# ── Fase 5: xG/xA desde Understat ────────────────────────────────────────────

def extract_understat() -> list[dict]:
    log.info("[5] Descargando xG/xA (Understat)...")
    try:
        us  = sd.Understat(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df  = us.read_player_season_stats().reset_index()
        log.info("    shape=%s", df.shape)
    except Exception as e:
        log.error("    Error: %s", e)
        return []

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player:
            continue
        rows.append({
            "player_norm": player, "squad_norm": squad,
            "xg": _safe_float(r.get("xg")),
            "xa": _safe_float(r.get("xa")),
        })
    log.info("    %d jugadores.", len(rows))
    return rows


# ── Fase 6: partidos ──────────────────────────────────────────────────────────

_equipo_cache: dict[str, int] = {}
_equipo_keys:  list[str]      = []


def _load_equipo_cache():
    global _equipo_cache, _equipo_keys
    if _equipo_cache:
        return
    res = (
        supabase.table("equipos").select("id, nombre")
        .eq("liga_id", LIGA_ID).eq("temporada", TEMPORADA).execute()
    )
    for r in res.data:
        k = _norm(r["nombre"])
        if k:
            _equipo_cache[k] = r["id"]
    _equipo_keys = list(_equipo_cache.keys())
    log.info("    Cache equipos: %d.", len(_equipo_cache))


def _resolve_equipo(nombre: str) -> "int | None":
    if not nombre:
        return None
    _load_equipo_cache()
    n     = _norm(nombre)
    alias = FBREF_ALIASES.get(n)
    if alias and alias in _equipo_cache:
        return _equipo_cache[alias]
    if n in _equipo_cache:
        return _equipo_cache[n]
    for k, eid in _equipo_cache.items():
        if n in k or k in n:
            return eid
    close = difflib.get_close_matches(n, _equipo_keys, n=1, cutoff=0.70)
    if close:
        return _equipo_cache[close[0]]
    log.warning("    Equipo no resuelto: '%s'", nombre)
    return None


def _parse_score(score: str):
    if not score or not isinstance(score, str):
        return None, None
    for sep in ["–", "-", "−"]:
        if sep in score:
            parts = score.split(sep)
            if len(parts) == 2:
                try:
                    return int(parts[0].strip()), int(parts[1].strip())
                except ValueError:
                    pass
    return None, None


def load_partidos() -> int:
    log.info("[6] Descargando schedule Ligue 1 (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = fbref.read_schedule().reset_index()
        log.info("    %d partidos en calendario.", len(df))
    except Exception as e:
        log.error("    Error: %s", e)
        return 0

    _load_equipo_cache()
    rows       = []
    sin_equipo = []
    sin_score  = 0

    for _, row in df.iterrows():
        home_nombre = str(row.get("home_team") or "")
        away_nombre = str(row.get("away_team") or "")
        score       = row.get("score")
        jornada     = row.get("week")
        fecha_raw   = row.get("date")

        home_id = _resolve_equipo(home_nombre)
        away_id = _resolve_equipo(away_nombre)
        if not home_id or not away_id:
            sin_equipo.append(f"{home_nombre} vs {away_nombre}")
            continue

        score_str = str(score) if pd.notna(score) else None
        goles_h, goles_a = _parse_score(score_str) if score_str else (None, None)
        if goles_h is None:
            sin_score += 1

        fecha = None
        if fecha_raw and pd.notna(fecha_raw):
            try:
                fecha = pd.Timestamp(fecha_raw).date().isoformat()
            except Exception:
                pass

        estado = "jugado" if goles_h is not None else "programado"

        rows.append({
            "liga_id":          LIGA_ID,
            "temporada":        TEMPORADA,
            "jornada":          _safe_int(jornada),
            "equipo_local":     home_id,
            "equipo_visitante": away_id,
            "goles_local":      goles_h,
            "goles_visitante":  goles_a,
            "fecha":            fecha,
            "estado":           estado,
        })

    if sin_equipo:
        log.warning("    Sin equipo resuelto: %d partidos", len(sin_equipo))
    log.info("    Sin score: %d | Listos: %d", sin_score, len(rows))

    if not rows:
        return 0

    res = (
        supabase.table("partidos")
        .upsert(rows, on_conflict="liga_id,temporada,equipo_local,equipo_visitante,jornada")
        .execute()
    )
    log.info("    %d partidos upsertados.", len(res.data))
    return len(res.data)


# ── Fase 7: Transfermarkt — fotos + valor de mercado ─────────────────────────

def _parse_valor(text: str) -> Optional[float]:
    if not text or text.strip() in ("-", ""):
        return None
    text = text.strip().lower().replace(",", ".")
    m = re.search(r"([\d.]+)\s*(mill|mio|m\b)", text)
    if m:
        return round(float(m.group(1)), 2)
    m = re.search(r"([\d.]+)\s*(mil|k\b|tsd)", text)
    if m:
        return round(float(m.group(1)) / 1000, 3)
    m = re.search(r"([\d.]+)", text)
    if m:
        return round(float(m.group(1)), 2)
    return None


def _tm_get(url: str) -> Optional[BeautifulSoup]:
    try:
        r = _tm_scraper.get(url, timeout=20)
        if r.status_code != 200:
            log.warning("  TM HTTP %d para %s", r.status_code, url)
            return None
        return BeautifulSoup(r.content, "lxml")
    except Exception as e:
        log.warning("  TM Error en %s: %s", url, e)
        return None


def tm_get_team_ids() -> list[dict]:
    log.info("[7a] Obteniendo equipos de Ligue 1 desde Transfermarkt...")
    url = f"{TM_BASE}/{TM_SLUG}/startseite/wettbewerb/{TM_LIGA_CODE}/saison_id/{TM_SEASON}"
    log.info("     URL: %s", url)
    soup = _tm_get(url)
    if not soup:
        raise RuntimeError("No se pudo cargar la pagina de Ligue 1 en Transfermarkt")

    teams, seen = [], set()
    for a in soup.select("td.hauptlink a[href*='/startseite/verein/']"):
        href = a.get("href", "")
        m = re.search(r"(/[^/]+/startseite/verein/(\d+))", href)
        if not m:
            continue
        slug_path = m.group(1)
        team_id   = m.group(2)
        name      = a.text.strip()
        if not name or team_id in seen:
            continue
        seen.add(team_id)
        teams.append({
            "name":      name,
            "tm_id":     team_id,
            "kader_url": f"{TM_BASE}{slug_path.replace('/startseite/', '/kader/')}/saison_id/{TM_SEASON}",
        })

    log.info("     %d equipos TM.", len(teams))
    return teams


def tm_scrape_squad(team: dict) -> list[dict]:
    soup = _tm_get(team["kader_url"])
    if not soup:
        return []
    players = []
    for row in soup.select("table.items tbody tr.odd, table.items tbody tr.even"):
        name_el  = row.select_one("td.hauptlink a")
        img_el   = row.select_one("img.bilderrahmen-fixed")
        val_el   = row.select_one("td.rechts.hauptlink")
        if not name_el:
            continue
        name = name_el.text.strip()
        foto = None
        if img_el:
            foto = img_el.get("data-src") or img_el.get("src")
            if foto:
                foto = foto.replace("/medium/", "/big/")
        valor = _parse_valor(val_el.text if val_el else "")
        player_url = None
        for a in row.select("td.hauptlink a"):
            if "/profil/spieler/" in a.get("href", ""):
                player_url = TM_BASE + a.get("href", "")
                break
        players.append({
            "nombre":        name,
            "nombre_norm":   _norm(name),
            "foto_url":      foto,
            "valor_mercado": valor,
            "player_url":    player_url,
        })
    return players


_MONTH_ABBR = {
    "jan": 1, "ene": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4,
    "may": 5, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "aug": 8,
    "sep": 9, "okt": 10, "oct": 10, "nov": 11, "dic": 12, "dez": 12, "dec": 12,
}


def _date_to_temporada(date_str: str) -> Optional[str]:
    s = date_str.strip()
    for fmt in ("%b %d, %Y", "%b. %d, %Y", "%d. %b %Y", "%d. %b. %Y",
                "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            d = datetime.datetime.strptime(s, fmt)
            y = d.year - (1 if d.month < 7 else 0)
            return f"{str(y)[2:]}{str(y + 1)[2:]}"
        except ValueError:
            pass
    year_m = re.search(r"(\d{4})", s)
    if not year_m:
        return None
    year  = int(year_m.group(1))
    month = 9
    low   = s.lower()
    for abbr, num in _MONTH_ABBR.items():
        if abbr in low:
            month = num
            break
    y = year - (1 if month < 7 else 0)
    return f"{str(y)[2:]}{str(y + 1)[2:]}"


def tm_scrape_history(player_url: str) -> list[dict]:
    m = re.search(r"/spieler/(\d+)", player_url)
    if not m:
        return []
    pid = m.group(1)
    try:
        r = _tm_scraper.get(f"{TM_BASE}/ceapi/marketValueDevelopment/graph/{pid}", timeout=15)
        if r.status_code != 200:
            return []
        entries = r.json().get("list", [])
    except Exception:
        return []
    by_temp: dict[str, float] = {}
    for entry in entries:
        datum = entry.get("datum_mw", "")
        y     = entry.get("y")
        if not datum or y is None:
            continue
        temp = _date_to_temporada(datum)
        if temp:
            by_temp[temp] = round(float(y) / 1_000_000, 3)
    return [{"temporada": t, "valor": v} for t, v in by_temp.items()]


def run_transfermarkt():
    log.info("[7] Transfermarkt Ligue 1 — fotos + valor de mercado...")

    try:
        teams = tm_get_team_ids()
    except RuntimeError as e:
        log.error("    %s", e)
        return

    # Acumular datos de todos los equipos
    tm_players: list[dict] = []
    for i, team in enumerate(teams, 1):
        log.info("    [%d/%d] %s", i, len(teams), team["name"])
        players = tm_scrape_squad(team)
        log.info("          %d jugadores", len(players))
        tm_players.extend(players)
        if i < len(teams):
            time.sleep(REQUEST_DELAY)

    log.info("    Total jugadores TM: %d", len(tm_players))

    # Cargar jugadores de la liga desde Supabase
    eq_res = (
        supabase.table("equipos").select("id, nombre")
        .eq("liga_id", LIGA_ID).eq("temporada", TEMPORADA).execute()
    )
    eq_ids   = [e["id"] for e in (eq_res.data or [])]
    all_jug  = []
    for i in range(0, len(eq_ids), 50):
        res = (supabase.table("jugadores").select("id, nombre")
               .in_("equipo_id", eq_ids[i:i+50]).execute())
        all_jug.extend(res.data or [])

    # Indices TM
    exact_idx: dict[str, int] = {}
    name_idx:  dict[str, int] = {}
    for i, p in enumerate(tm_players):
        exact_idx.setdefault(p["nombre_norm"], i)
        name_idx.setdefault(p["nombre_norm"], i)

    # Match y upsert jugadores
    jug_rows   = []
    hist_rows_now = []
    jugadores_con_url: list[dict] = []

    for jug in all_jug:
        jid    = jug["id"]
        n_norm = _norm(jug["nombre"])
        tm_i   = exact_idx.get(n_norm) or name_idx.get(n_norm)
        if tm_i is None:
            continue
        p = tm_players[tm_i]
        row = {"id": jid, "nombre": jug["nombre"]}
        if p.get("foto_url"):
            row["foto_url"] = p["foto_url"]
        if p.get("valor_mercado") is not None:
            row["valor_mercado"] = float(p["valor_mercado"])
            hist_rows_now.append({
                "jugador_id": jid,
                "temporada":  TEMPORADA,
                "valor":      float(p["valor_mercado"]),
            })
        if p.get("player_url"):
            row["tm_url"] = p["player_url"]
            jugadores_con_url.append({"jugador_id": jid, "player_url": p["player_url"]})
        jug_rows.append(row)

    if jug_rows:
        supabase.table("jugadores").upsert(jug_rows, on_conflict="id").execute()
        log.info("    %d jugadores actualizados (foto + valor).", len(jug_rows))

    if hist_rows_now:
        supabase.table("valor_mercado_historia") \
            .upsert(hist_rows_now, on_conflict="jugador_id,temporada").execute()
        log.info("    %d entradas valor actual insertadas.", len(hist_rows_now))

    # Historial multi-temporada
    if CARGAR_HISTORIAL and jugadores_con_url:
        log.info("    Cargando historial multi-temporada (%d jugadores)...", len(jugadores_con_url))
        BATCH     = 50
        hist_rows = []
        hist_total = 0
        total_j   = len(jugadores_con_url)

        for i, item in enumerate(jugadores_con_url, 1):
            time.sleep(REQUEST_DELAY)
            entries = tm_scrape_history(item["player_url"])
            for e in entries:
                hist_rows.append({
                    "jugador_id": item["jugador_id"],
                    "temporada":  e["temporada"],
                    "valor":      e["valor"],
                })
            if i % BATCH == 0 or i == total_j:
                if hist_rows:
                    supabase.table("valor_mercado_historia") \
                        .upsert(hist_rows, on_conflict="jugador_id,temporada").execute()
                    hist_total += len(hist_rows)
                    log.info("    [%d/%d] Historial: %d entradas acumuladas", i, total_j, hist_total)
                    hist_rows = []

        log.info("    Historial completado: %d entradas.", hist_total)


# ── Verificacion ──────────────────────────────────────────────────────────────

def verify():
    log.info("")
    log.info("[VERIFY] Jugadores clave Ligue 1:")
    for name in ("Mbappe", "Dembele", "Lacazette", "Ben Yedder", "Ramos"):
        res = (supabase.table("jugadores").select("id, nombre")
               .ilike("nombre", f"%{name}%").limit(1).execute())
        if not res.data:
            log.info("  %-25s -> no en DB", name)
            continue
        jid = res.data[0]["id"]
        nom = res.data[0]["nombre"]
        est = (supabase.table("estadisticas_jugador")
               .select("goles, asistencias, xg, xa, minutos")
               .eq("jugador_id", jid).eq("temporada", TEMPORADA)
               .eq("liga_id", LIGA_ID).execute())
        if est.data:
            d = est.data[0]
            log.info("  %-25s  G=%-3s A=%-3s xG=%-5s xA=%-5s min=%s",
                     nom, d.get("goles"), d.get("asistencias"),
                     d.get("xg"), d.get("xa"), d.get("minutos"))
        else:
            log.info("  %-25s -> sin stats Ligue 1 2526", nom)


# ── Entrypoint ────────────────────────────────────────────────────────────────

def run():
    log.info("=" * 64)
    log.info(" FBref + TM Ligue 1 Scraper  (liga_id=%d)  temporada=%s", LIGA_ID, TEMPORADA)
    log.info("=" * 64)

    # Fase 0: liga
    ensure_liga()

    # Fase A: historico
    if INCLUIR_HISTORICO:
        log.info("[A] Temporadas historicas: %s", [t for _, t in HISTORICAS])
        for fbref_key, temporada in HISTORICAS:
            run_historico(fbref_key, temporada)
    else:
        log.info("[A] INCLUIR_HISTORICO=False, saltando.")

    # Fases 1-6: temporada actual
    df_std = load_standard()
    if df_std.empty:
        log.error("DataFrame standard vacio. Abortando fases 1-6.")
        return

    equipo_map                  = upsert_equipos(df_std)
    full_map, name_map, last_map = upsert_jugadores(df_std, equipo_map)
    std_rows                    = build_standard_rows(df_std, full_map, name_map, last_map)
    insert_estadisticas(std_rows)

    keeper_rows   = extract_keepers()
    shooting_rows = extract_shooting()
    misc_rows     = extract_misc()
    understat_rows = extract_understat()

    update_supabase(keeper_rows,    full_map, name_map, last_map, "keeper")
    update_supabase(shooting_rows,  full_map, name_map, last_map, "shooting/xG")
    update_supabase(misc_rows,      full_map, name_map, last_map, "misc")
    update_supabase(understat_rows, full_map, name_map, last_map, "understat/xGxA")

    load_partidos()

    # Fase 7: Transfermarkt
    run_transfermarkt()

    verify()

    log.info("")
    log.info("=" * 64)
    log.info(" COMPLETADO")
    log.info("=" * 64)


if __name__ == "__main__":
    run()
